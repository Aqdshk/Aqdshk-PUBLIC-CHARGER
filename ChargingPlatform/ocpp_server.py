"""
PlagSini EV — OCPP 1.6J WebSocket Server

Handles charger connections via WebSocket (ws://host:9000/{charge_point_id}).

Inbound (charger → server): BootNotification, Authorize, StatusNotification,
  StartTransaction, StopTransaction, MeterValues, Heartbeat,
  FirmwareStatusNotification, DiagnosticsStatusNotification.

Outbound (server → charger): RemoteStart/Stop, ChangeAvailability, Reset,
  UpdateFirmware, GetConfiguration, SendLocalList, etc.

Auth: OCPP_REQUIRE_AUTH, OCPP_SHARED_TOKEN, OCPP_CHARGER_TOKENS.
"""
import asyncio
import logging
import os
import re
import secrets
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs

import websockets.exceptions
from ocpp.exceptions import FormatViolationError
from sqlalchemy import desc
from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp, call, call_result
from ocpp.v16.enums import AuthorizationStatus, RegistrationStatus

from database import SessionLocal, Charger, ChargingSchedule, ChargingSession, MeterValue, Fault, User, PaymentTransaction

logger = logging.getLogger(__name__)

# ─── Edge Sync (Local Server Mode) ────────────────────────────────────────────
# When LOCAL_SERVER_MODE=true (Banana Pi), push data to VPS after each OCPP event.
_LOCAL = os.getenv("LOCAL_SERVER_MODE", "false").lower() == "true"
if _LOCAL:
    try:
        import vps_sync as _sync
        logger.info("Edge sync enabled — charger/session data will be pushed to VPS")
    except ImportError:
        _sync = None  # type: ignore
        logger.warning("LOCAL_SERVER_MODE=true but vps_sync.py not found — sync disabled")
else:
    _sync = None  # type: ignore


def _utcnow():
    """Timezone-safe replacement for deprecated _utcnow()"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── Globals ─────────────────────────────────────────────────────────────
# Active charger WebSocket connections (charge_point_id → ChargePoint instance)
# Used by API to send RemoteStart, UpdateFirmware, etc. to connected chargers
active_charge_points: Dict[str, 'ChargePoint'] = {}

# Reference to the FastAPI (main) event loop.
# Set by api.py startup handler. Used by the scheduled charging worker
# — which runs inside the OCPP background-thread loop — to dispatch
# ChargePoint.call() requests onto the same loop that API handlers use
# (ChargePoint's internal Queue/Lock get bound to whichever loop first
# touches them; the API binds them to its loop, so cross-loop calls
# from the worker would otherwise raise "bound to a different event loop").
API_LOOP: Optional[asyncio.AbstractEventLoop] = None

# Recent firmware events (last 50) — shared with API layer
firmware_events: List[Dict] = []

def _add_firmware_event(charger_id: str, status: str, firmware_version: str = ""):
    """Store a firmware event so the dashboard can poll and show toast."""
    from datetime import datetime, timezone, timedelta
    myt = timezone(timedelta(hours=8))
    firmware_events.append({
        "charger_id": charger_id,
        "status": status,
        "firmware_version": firmware_version,
        "timestamp": datetime.now(myt).isoformat(),
    })
    # Keep only last 50 events
    if len(firmware_events) > 50:
        firmware_events.pop(0)
# Charge point ID format: alphanumeric, dots, underscores, colons, hyphens; 3–64 chars
_CP_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{3,64}$")


def _parse_token_map(raw_tokens: str) -> Dict[str, str]:
    """
    Parse OCPP charger token map from env:
    OCPP_CHARGER_TOKENS="CP001:tokenA,CP002:tokenB"
    """
    token_map: Dict[str, str] = {}
    if not raw_tokens:
        return token_map
    for pair in raw_tokens.split(","):
        item = pair.strip()
        if not item or ":" not in item:
            continue
        cp_id, token = item.split(":", 1)
        cp_id = cp_id.strip()
        token = token.strip()
        if cp_id and token:
            token_map[cp_id] = token
    return token_map


def _extract_ws_token(websocket: Any, raw_path: str) -> Optional[str]:
    """Extract charger token from query string or headers."""
    # 1) Query string: ws://host:9000/CP001?token=xxx
    # Note: MicroOcpp may append /charge_point_id to path, giving token=xxx/CP001
    token = None
    if "?" in raw_path:
        query = raw_path.split("?", 1)[1]
        parsed = parse_qs(query, keep_blank_values=False)
        values = parsed.get("token")
        if values:
            raw_val = values[0].strip()
            # If token value contains "/" (e.g. "token123/ESP32-CP-01"), use only the token part
            if "/" in raw_val:
                token = raw_val.split("/", 1)[0].strip()
            else:
                token = raw_val
    if token:
        return token

    # 2) Header: X-CP-Token: xxx (websockets 12+: request.headers; legacy: request_headers)
    headers = None
    req = getattr(websocket, "request", None)
    if req and hasattr(req, "headers"):
        headers = req.headers
    if not headers:
        headers = getattr(websocket, "request_headers", None)
    if headers:
        x_cp_token = headers.get("X-CP-Token")
        if x_cp_token:
            return x_cp_token.strip()

        # 3) Authorization: Bearer xxx
        auth_header = headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
    return None

def utc_now_iso_z() -> str:
    """RFC3339 timestamp — uses Malaysia time (UTC+8) so charger display shows correct local time."""
    myt = timezone(timedelta(hours=8))
    return datetime.now(myt).isoformat()


# ─── ChargePoint: OCPP 1.6 Message Handlers (Inbound) ─────────────────────
# Handles: BootNotification, Authorize, StatusNotification, StartTransaction,
#          StopTransaction, MeterValues, Heartbeat, FirmwareStatusNotification,
#          DiagnosticsStatusNotification
class ChargePoint(cp):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.db = SessionLocal()
    
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()
    
    @on('BootNotification')
    async def on_boot_notification(self, charge_point_model: str, charge_point_vendor: str, **kwargs):
        """Handle BootNotification from charging station"""
        logger.info(f"BootNotification received from {self.id}")
        try:
            # Get or create charger
            charger = self.db.query(Charger).filter(Charger.charge_point_id == self.id).first()
            
            if not charger:
                charger = Charger(
                    charge_point_id=self.id,
                    vendor=charge_point_vendor,
                    model=charge_point_model,
                    firmware_version=kwargs.get('firmware_version', 'Unknown'),
                    status="online",
                    last_heartbeat=_utcnow()
                )
                self.db.add(charger)
            else:
                charger.vendor = charge_point_vendor
                charger.model = charge_point_model
                charger.firmware_version = kwargs.get('firmware_version', charger.firmware_version)
                charger.status = "online"
                charger.last_heartbeat = _utcnow()
                
                # BootNotification means charger just rebooted — any active/pending sessions
                # from before the reboot are orphaned (StopTransaction was never received).
                # Close them now using the last known meter value as final energy reading.
                orphaned = self.db.query(ChargingSession).filter(
                        ChargingSession.charger_id == charger.id,
                    ChargingSession.status.in_(['active', 'pending'])
                    ).all()
                    
                if orphaned:
                    now = _utcnow()
                    for s in orphaned:
                        last_meter = (
                            self.db.query(MeterValue)
                            .filter(MeterValue.transaction_id == s.transaction_id)
                            .order_by(desc(MeterValue.timestamp))
                            .first()
                        )
                        final_energy = (last_meter.total_kwh or 0.0) if last_meter else (s.energy_consumed or 0.0)
                        s.status = "interrupted"
                        s.stop_time = now
                        s.energy_consumed = final_energy
                        logger.warning(
                            f"Orphan session {s.id} (tx={s.transaction_id}) closed on charger reboot — "
                            f"energy={final_energy:.3f} kWh"
                        )
                    charger.availability = "available"
                    logger.info(f"Charger {self.id} rebooted — closed {len(orphaned)} orphan session(s)")
            
            # Auto-populate max_power_kw from model name if not manually set (e.g. "30kW" → 30.0)
            if charger.max_power_kw is None and charge_point_model:
                match = re.search(r'(\d+\.?\d*)\s*kw', charge_point_model, re.IGNORECASE)
                if match:
                    charger.max_power_kw = float(match.group(1))

            # Auto-infer connector_type from power if not manually set (>22kW = DC CCS2, else AC Type 2)
            if charger.connector_type is None and charger.max_power_kw is not None:
                charger.connector_type = "CCS2" if charger.max_power_kw > 22 else "Type 2"

            self.db.commit()

            # Edge sync → push charger info to VPS
            if _sync:
                _sync.sync_charger(
                    self.id,
                    status="online",
                    availability=charger.availability or "available",
                    vendor=charger.vendor,
                    model=charger.model,
                    firmware_version=charger.firmware_version,
                    connector_type=charger.connector_type,
                    max_power_kw=charger.max_power_kw,
                    number_of_connectors=charger.number_of_connectors,
                    last_heartbeat=utc_now_iso_z(),
                )

            # Get charger configuration for heartbeat interval
            # Cap at 30s so ESP32 sends heartbeats frequently - DB default 7200 causes "offline" after 90s
            raw_interval = getattr(charger, 'heartbeat_interval', None) or 10
            heartbeat_interval = min(int(raw_interval), 30)
            
            return call_result.BootNotification(
                current_time=utc_now_iso_z(),
                interval=heartbeat_interval,
                status=RegistrationStatus.accepted
            )
        except Exception as e:
            logger.error(f"Error in BootNotification handler for {self.id}: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception:
                pass
            return call_result.BootNotification(
                current_time=utc_now_iso_z(),
                interval=30,
                status=RegistrationStatus.accepted
            )

    @on('Authorize')
    async def on_authorize(self, id_tag: str):
        """
        Handle Authorize from charger — when user taps RFID card locally.
        Returns Accepted/Blocked based on id_tag validation.
        Without this handler, chargers requiring CSMS auth would reject local RFID taps.
        """
        logger.info(f"Authorize received from {self.id}: id_tag={id_tag}")
        try:
            # Known app-initiated id_tags (RemoteStart flow) — always accept
            if id_tag in ("APP_USER", "DASHBOARD_USER", "LOCAL_CHARGING", ""):
                return call_result.Authorize(id_tag_info={"status": AuthorizationStatus.accepted})

            # Numeric id_tag may be user_id from app
            if id_tag and id_tag.isdigit():
                user = self.db.query(User).filter(User.id == int(id_tag), User.is_active == True).first()
                if user:
                    return call_result.Authorize(id_tag_info={"status": AuthorizationStatus.accepted})

            # Unknown id_tag — block. Add RFID cards via admin dashboard to whitelist.
            logger.warning(f"Authorize BLOCKED unknown id_tag={id_tag!r} on charger {self.id}")
            return call_result.Authorize(id_tag_info={"status": AuthorizationStatus.blocked})
        except Exception as e:
            logger.error(f"Error in Authorize handler for {self.id}: {e}", exc_info=True)
            return call_result.Authorize(id_tag_info={"status": AuthorizationStatus.blocked})

    @on('StatusNotification')
    async def on_status_notification(self, connector_id: int, error_code: str, status: str, **kwargs):
        """Handle StatusNotification from charging station"""
        try:
            logger.info(f"StatusNotification from {self.id}: connector {connector_id}, status: {status}, error: {error_code}")
            
            charger = self.db.query(Charger).filter(Charger.charge_point_id == self.id).first()
            if not charger:
                logger.warning(f"StatusNotification received for unknown charger {self.id}")
                return call_result.StatusNotification()

            # Map OCPP status to our availability status
            # If connector is "Charging", set availability to "charging" (charger might be charging locally)
            status_map = {
                'Available': 'available',
                'Preparing': 'preparing',
                'Charging': 'charging',   # Set to charging if connector status is Charging
                'SuspendedEVSE': 'preparing',
                'SuspendedEV': 'preparing',
                'Finishing': 'preparing',
                'Reserved': 'unavailable',
                'Unavailable': 'unavailable',
                'Faulted': 'faulted'
            }
            
            # Update availability based on actual connector status
            # Only set to "charging" if connector status is actually "Charging"
            if status == 'Charging':
                # Set availability to charging
                charger.availability = 'charging'
                # Check if we have an active session, if not, create one (charger might be charging locally)
                try:
                    active_session = self.db.query(ChargingSession).filter(
                        ChargingSession.charger_id == charger.id,
                        ChargingSession.status == 'active'
                    ).first()
                    
                    if not active_session:
                        # Charger is charging but no session exists - might be local charging
                        # Don't create session here - wait for StartTransaction
                        # Just update availability to charging
                        logger.info(f"Charger {self.id} is charging but no active session found. Will wait for StartTransaction.")
                        # Don't create placeholder session - it causes database conflicts
                        # Session will be created when StartTransaction is received
                except Exception as e:
                    logger.error(f"Error checking sessions for charger {self.id}: {e}", exc_info=True)
                    # Don't fail the StatusNotification - just log the error
            else:
                # For other statuses (Available, Preparing, etc.), sync availability with actual charger state
                # IMPORTANT: Trust the charger's actual status, not just database sessions
                # If charger says "Available" or "Preparing", it's not charging - sync accordingly
                try:
                    active_session = self.db.query(ChargingSession).filter(
                        ChargingSession.charger_id == charger.id,
                        ChargingSession.status == 'active',
                        ChargingSession.transaction_id > 0  # Only consider valid sessions
                    ).first()
                    
                    # Sync availability with actual charger status
                    # If charger status is "Available" or "Preparing", charger is NOT charging
                    # Update availability to match actual state, even if we have an active session
                    # (The session might be stale from before disconnect)
                    new_availability = status_map.get(status, 'unknown')
                    
                    if status in ['Available', 'Preparing']:
                        # Charger says it's NOT charging - trust the device (source of truth)
                        # Don't keep 'charging' based on stale session - user may have stopped locally
                        charger.availability = new_availability
                        if active_session:
                            logger.info(
                                f"Charger {self.id} reports '{status}' - completing stale session "
                                f"{active_session.transaction_id} (charger stopped charging)"
                            )
                            active_session.status = 'completed'
                            active_session.stop_time = _utcnow()
                    else:
                        # Other statuses (Unavailable, Faulted, etc.) - update availability
                        charger.availability = new_availability
                    
                    # Clear placeholder sessions (transaction_id = 0 or negative) if charger is not charging
                    try:
                        placeholder_sessions = self.db.query(ChargingSession).filter(
                            ChargingSession.charger_id == charger.id,
                            ChargingSession.status.in_(['active', 'pending']),
                            ChargingSession.transaction_id <= 0  # Clear both 0 and negative transaction_ids
                        ).all()
                        for session in placeholder_sessions:
                            session.status = 'completed'
                            session.stop_time = _utcnow()
                            logger.info(f"Cleared placeholder session (transaction_id={session.transaction_id}) for charger {self.id}")
                    except Exception as e:
                        logger.error(f"Error clearing placeholder sessions for charger {self.id}: {e}", exc_info=True)
                        self.db.rollback()
                except Exception as e:
                    logger.error(f"Error checking sessions for charger {self.id}: {e}", exc_info=True)
                    # Fallback: use simple status mapping when error occurs
                    charger.availability = status_map.get(status, 'unknown')
            
            charger.last_heartbeat = _utcnow()
            charger.status = 'online'  # Update status to online when we receive StatusNotification
            
            # Handle faults
            if error_code and error_code != 'NoError':
                fault_type_map = {
                    'OverCurrentFailure': 'overcurrent',
                    'GroundFailure': 'ground_fault',
                    'OtherError': 'cp_error'
                }
                fault_type = fault_type_map.get(error_code, 'cp_error')
                
                # Check if fault already exists and is not cleared
                existing_fault = self.db.query(Fault).filter(
                    Fault.charger_id == charger.id,
                    Fault.fault_type == fault_type,
                    Fault.cleared == False
                ).first()
                
                if not existing_fault:
                    fault = Fault(
                        charger_id=charger.id,
                        fault_type=fault_type,
                        message=f"Error code: {error_code}, Status: {status}",
                        timestamp=_utcnow()
                    )
                    self.db.add(fault)
            
            # Clear faults if status is not faulted
            if status != 'Faulted' and error_code == 'NoError':
                self.db.query(Fault).filter(
                    Fault.charger_id == charger.id,
                    Fault.cleared == False
                ).update({'cleared': True, 'cleared_at': _utcnow()})
            
            try:
                self.db.commit()
            except Exception as e:
                logger.error(f"Error committing StatusNotification for charger {self.id}: {e}", exc_info=True)
                self.db.rollback()
                # Don't fail the StatusNotification - just log the error
                # Return success response to prevent charger from disconnecting

            # Edge sync → push availability update to VPS
            if _sync:
                _sync.sync_charger(
                    self.id,
                    status="online",
                    availability=charger.availability,
                    last_heartbeat=utc_now_iso_z(),
                )

            return call_result.StatusNotification()
        except Exception as e:
            logger.error(f"Unexpected error in StatusNotification handler for charger {self.id}: {e}", exc_info=True)
            # Always return success response to prevent InternalError and charger disconnection
            # The error is logged but we don't want to disconnect the charger
            try:
                self.db.rollback()
            except Exception:
                pass
            return call_result.StatusNotification()
    
    @on('StartTransaction')
    async def on_start_transaction(self, connector_id: int, id_tag: str, meter_start: int, timestamp: str, **kwargs):
        """Handle StartTransaction from charging station.
        
        NOTE: In OCPP 1.6, the Central System (server) generates and assigns the
        transaction_id — the charger does NOT provide one in StartTransaction.req.
        We use the session's auto-increment DB id as the transaction_id.
        """
        try:
            charger = self.db.query(Charger).filter(Charger.charge_point_id == self.id).first()
            if charger:
                start_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                # Check if a pending/active session already exists (created by RemoteStart)
                existing_session = self.db.query(ChargingSession).filter(
                    ChargingSession.charger_id == charger.id,
                    ChargingSession.status.in_(["pending", "active"])
                ).order_by(desc(ChargingSession.start_time)).first()
                
                if existing_session:
                    existing_session.status = "active"
                    existing_session.start_time = start_dt
                    existing_session.connector_id = connector_id
                    existing_session.meter_start = meter_start if meter_start is not None else existing_session.meter_start
                    if not existing_session.user_id or existing_session.user_id in ("LOCAL_CHARGING", "DASHBOARD_USER"):
                        existing_session.user_id = id_tag
                    # Assign transaction_id from DB id if not already a valid one
                    if not existing_session.transaction_id or existing_session.transaction_id <= 0:
                        self.db.flush()
                        existing_session.transaction_id = existing_session.id
                    transaction_id = existing_session.transaction_id
                else:
                    # New session — flush to get auto-increment id, use it as transaction_id
                    session = ChargingSession(
                        charger_id=charger.id,
                        transaction_id=0,  # placeholder; will be replaced with DB id below
                        connector_id=connector_id,
                        start_time=start_dt,
                        status="active",
                        user_id=id_tag,
                        meter_start=meter_start,
                    )
                    self.db.add(session)
                    self.db.flush()  # populate session.id
                    session.transaction_id = session.id
                    transaction_id = session.transaction_id
                
                charger.availability = "charging"
                charger.status = "online"
                self.db.commit()

                # Edge sync → push new session to VPS
                if _sync:
                    _sync.sync_session_start(
                        self.id,
                        transaction_id,
                        connector_id=connector_id,
                        start_time=start_dt.isoformat(),
                        meter_start=meter_start,
                        user_id=id_tag,
                    )

                logger.info(f"Charger {self.id} started charging — assigned transaction_id={transaction_id}")
                
                return call_result.StartTransaction(
                    transaction_id=transaction_id,
                    id_tag_info={'status': AuthorizationStatus.accepted}
                )
            
            return call_result.StartTransaction(
                transaction_id=0,
                id_tag_info={'status': AuthorizationStatus.invalid}
            )
        except Exception as e:
            logger.error(f"Error in StartTransaction handler for {self.id}: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception:
                pass
            return call_result.StartTransaction(
                transaction_id=0,
                id_tag_info={'status': AuthorizationStatus.accepted}
            )
    
    @on('StopTransaction')
    async def on_stop_transaction(self, transaction_id: int, id_tag: str, meter_stop: int, timestamp: str, **kwargs):
        """Handle StopTransaction from charging station.
        Uses meter_stop (Wh) as authoritative final energy when available for billing accuracy.
        """
        logger.info(f"StopTransaction from {self.id}: transaction {transaction_id}, meter_stop={meter_stop}")
        try:
            session = self.db.query(ChargingSession).filter(
                ChargingSession.transaction_id == transaction_id
            ).first()
            
            if session:
                session.stop_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                session.status = "completed"
                session.meter_stop = meter_stop
                session.stop_reason = kwargs.get("reason")

                # Use meter_stop for billing accuracy — OCPP spec: meter_stop is authoritative Wh at session end
                if meter_stop is not None:
                    if session.meter_start is not None:
                        session.energy_consumed = (meter_stop - session.meter_start) / 1000.0  # Wh → kWh
                    else:
                        session.energy_consumed = meter_stop / 1000.0  # Fallback: treat as session delta
                    logger.info(f"Session {transaction_id}: energy={session.energy_consumed:.3f} kWh (meter_stop={meter_stop} Wh)")
                # Else keep energy_consumed from MeterValues stream

                self.db.commit()

                # Edge sync → push completed session to VPS
                if _sync:
                    _sync.sync_session_stop(
                        transaction_id,
                        stop_time=session.stop_time.isoformat(),
                        meter_stop=meter_stop,
                        energy_consumed=session.energy_consumed,
                        stop_reason=kwargs.get("reason"),
                    )

                # Update charger availability
                charger = self.db.query(Charger).filter(Charger.id == session.charger_id).first()
                if charger:
                    charger.availability = "available"
                    self.db.commit()

                # Quick-pay post-charge invoice email.
                # _trigger_remote_start_after_payment sets id_tag = f"PAY{txn.id}" so
                # we can correlate the StopTransaction back to the originating payment.
                try:
                    if id_tag and id_tag.startswith("PAY"):
                        pay_id = int(id_tag[3:])
                        txn = self.db.query(PaymentTransaction).filter(
                            PaymentTransaction.id == pay_id
                        ).first()
                        recipient = (txn.customer_email or txn.user_email) if txn else None
                        if txn and recipient and charger:
                            # Compute duration string
                            if session.start_time and session.stop_time:
                                delta = session.stop_time - session.start_time
                                total = int(delta.total_seconds())
                                hh, rem = divmod(total, 3600)
                                mm, ss = divmod(rem, 60)
                                dur_str = f"{hh:02d}:{mm:02d}:{ss:02d}"
                            else:
                                dur_str = "—"

                            # Local import so module load order doesn't matter
                            from email_service import send_charging_invoice
                            asyncio.create_task(send_charging_invoice(
                                to_email=recipient,
                                transaction_ref=txn.transaction_ref,
                                charger_id=charger.charge_point_id,
                                connector_id=int(session.connector_id or txn.connector_id or 1),
                                started_at_str=session.start_time.strftime("%Y-%m-%d %H:%M:%S") if session.start_time else "—",
                                stopped_at_str=session.stop_time.strftime("%Y-%m-%d %H:%M:%S") if session.stop_time else "—",
                                duration_str=dur_str,
                                energy_kwh=float(session.energy_consumed or 0),
                                amount_paid=float(txn.amount or 0),
                                stop_reason=kwargs.get("reason") or "Local",
                            ))
                            logger.info(
                                f"[invoice] queued post-charge email → {recipient} "
                                f"(txn {txn.transaction_ref}, {session.energy_consumed:.3f} kWh)"
                            )
                except Exception as e:
                    logger.error(f"[invoice] failed to send post-charge email: {e}", exc_info=True)

            return call_result.StopTransaction(
                id_tag_info={'status': AuthorizationStatus.accepted}
            )
        except Exception as e:
            logger.error(f"Error in StopTransaction handler for {self.id}: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception:
                pass
            return call_result.StopTransaction(
                id_tag_info={'status': AuthorizationStatus.accepted}
            )
    
    @on('MeterValues')
    async def on_meter_values(self, connector_id: int, meter_value: list, transaction_id: int = None, **kwargs):
        """Handle MeterValues from charging station"""
        charger = self.db.query(Charger).filter(Charger.charge_point_id == self.id).first()
        if not charger:
            return call_result.MeterValues()
        
        for mv in meter_value:
            timestamp = datetime.fromisoformat(mv['timestamp'].replace('Z', '+00:00'))
            # python-ocpp converts camelCase → snake_case, so sampledValue → sampled_value
            sampled_value = mv.get('sampled_value', mv.get('sampledValue', []))
            
            voltage = None
            current = None
            power = None
            total_kwh = None
            
            for sv in sampled_value:
                try:
                    value = float(sv.get('value', 0) or 0)
                except (ValueError, TypeError):
                    value = 0.0
                measurand = sv.get('measurand', '')
                
                if measurand == 'Voltage':
                    voltage = value
                elif measurand == 'Current.Import':
                    current = value
                elif measurand == 'Power.Active.Import':
                    # Store watts; UI divides by 1000 once for kW (avoid double conversion)
                    power = value
                elif measurand == 'Energy.Active.Import.Register':
                    total_kwh = value / 1000.0  # Wh → kWh
            
            meter_value_obj = MeterValue(
                charger_id=charger.id,
                transaction_id=transaction_id,
                timestamp=timestamp,
                voltage=voltage,
                current=current,
                power=power,
                total_kwh=total_kwh
            )
            self.db.add(meter_value_obj)
            
            # Update session energy consumed
            if transaction_id:
                session = self.db.query(ChargingSession).filter(
                    ChargingSession.transaction_id == transaction_id
                ).first()
                if session and total_kwh:
                    session.energy_consumed = total_kwh
                    self.db.commit()
        
        self.db.commit()

        # Edge sync → push latest meter sample to VPS (only last sample per MeterValues message)
        if _sync and meter_value:
            last_mv = meter_value[-1]
            sampled = last_mv.get('sampled_value', last_mv.get('sampledValue', []))
            _v = _c = _p = _e = None
            for sv in sampled:
                try:
                    val = float(sv.get('value', 0) or 0)
                except (ValueError, TypeError):
                    val = 0.0
                m = sv.get('measurand', '')
                if m == 'Voltage':                          _v = val
                elif m == 'Current.Import':                 _c = val
                elif m == 'Power.Active.Import':            _p = val
                elif m == 'Energy.Active.Import.Register':  _e = val / 1000.0
            _sync.sync_meter_value(
                self.id,
                transaction_id=transaction_id,
                timestamp=last_mv.get('timestamp', utc_now_iso_z()),
                voltage=_v, current=_c, power=_p, total_kwh=_e,
            )

        return call_result.MeterValues()

    @on('FirmwareStatusNotification')
    async def on_firmware_status_notification(self, status: str, **kwargs):
        """Handle FirmwareStatusNotification from charging station."""
        logger.info(f"FirmwareStatusNotification from {self.id}: status={status}")
        try:
            charger = self.db.query(Charger).filter(Charger.charge_point_id == self.id).first()
            fw_version = charger.firmware_version if charger else ""
            if status == "Installed":
                logger.info(f"Charger {self.id} firmware installed successfully")
            _add_firmware_event(self.id, status, fw_version)
        except Exception as e:
            logger.error(f"Error handling FirmwareStatusNotification for {self.id}: {e}")
        return call_result.FirmwareStatusNotification()

    @on('DiagnosticsStatusNotification')
    async def on_diagnostics_status_notification(self, status: str, **kwargs):
        """Handle DiagnosticsStatusNotification from charging station."""
        logger.info(f"DiagnosticsStatusNotification from {self.id}: status={status}")
        return call_result.DiagnosticsStatusNotification()
    
    @on('Heartbeat')
    async def on_heartbeat(self):
        """Handle Heartbeat from charging station"""
        try:
            charger = self.db.query(Charger).filter(Charger.charge_point_id == self.id).first()
            if charger:
                charger.last_heartbeat = _utcnow()
                charger.status = "online"
                try:
                    self.db.commit()
                    logger.debug(f"Heartbeat received from {self.id}, status updated to online")
                    # Edge sync → lightweight heartbeat ping to VPS
                    if _sync:
                        _sync.sync_charger(self.id, status="online", last_heartbeat=utc_now_iso_z())
                except Exception as e:
                    logger.error(f"Error committing heartbeat for charger {self.id}: {e}", exc_info=True)
                    self.db.rollback()
            else:
                logger.warning(f"Heartbeat received from unknown charger {self.id}")
            
            return call_result.Heartbeat(current_time=utc_now_iso_z())
        except Exception as e:
            logger.error(f"Unexpected error in Heartbeat handler for charger {self.id}: {e}", exc_info=True)
            # Always return success response to prevent InternalError
            try:
                self.db.rollback()
            except Exception:
                pass
            return call_result.Heartbeat(current_time=utc_now_iso_z())

    @on('DataTransfer')
    async def on_data_transfer(self, vendor_id: str, message_id: str = None, data: str = None, **kwargs):
        """Handle incoming DataTransfer from charger (e.g. ChargingScheduleReport from GAC)."""
        import base64, json as _json
        logger.info(f"DataTransfer from {self.id}: vendor={vendor_id} messageId={message_id}")

        if message_id == "ChargingScheduleReport" and vendor_id == "GAC":
            # Charger reporting its current schedule — decode and log
            schedule = None
            if data:
                try:
                    # Try base64 decode first (GAC sends base64-encoded JSON)
                    decoded = base64.b64decode(data).decode()
                    schedule = _json.loads(decoded)
                except Exception:
                    try:
                        # Fallback: plain JSON string
                        schedule = _json.loads(data)
                    except Exception:
                        schedule = data

            day_names = {1:"Mon",2:"Tue",3:"Wed",4:"Thu",5:"Fri",6:"Sat",7:"Sun"}
            if isinstance(schedule, dict):
                days = [day_names.get(d, str(d)) for d in schedule.get("dateSchedule", [])]
                logger.info(
                    f"GAC ChargingScheduleReport from {self.id}: "
                    f"reservationId={schedule.get('reservationId')} "
                    f"recurrency={schedule.get('recurrency')} "
                    f"{schedule.get('startTime')}–{schedule.get('endTime')} "
                    f"days={days}"
                )
            else:
                logger.info(f"GAC ChargingScheduleReport raw from {self.id}: {data}")

            return call_result.DataTransfer(status="Accepted")

        # Generic handler for any other vendor DataTransfer
        logger.info(f"DataTransfer from {self.id} (unhandled): vendor={vendor_id} messageId={message_id}")
        return call_result.DataTransfer(status="Accepted")

    # ─── Outbound OCPP Commands (Server → Charger) ─────────────────────────
    async def remote_start_transaction(self, connector_id: int = 1, id_tag: str = "APP_USER"):
        """
        Send RemoteStartTransaction to charger via OCPP
        
        This will tell the charger to start charging on the specified connector
        """
        try:
            logger.info(f"Sending RemoteStartTransaction to {self.id}: connector_id={connector_id}, id_tag={id_tag}")
            request = call.RemoteStartTransaction(
                id_tag=id_tag,
                connector_id=connector_id
            )
            response = await self.call(request)
            logger.info(f"RemoteStartTransaction response for {self.id}: status={response.status if response else 'None'}")
            return response
        except Exception as e:
            logger.error(f"Error sending RemoteStartTransaction to {self.id}: {e}", exc_info=True)
            return None
    
    async def remote_stop_transaction(self, transaction_id: int):
        """Send RemoteStopTransaction to charger"""
        try:
            request = call.RemoteStopTransaction(
                transaction_id=transaction_id
            )
            response = await self.call(request)
            logger.info(f"RemoteStopTransaction response for {self.id}: {response}")
            return response
        except Exception as e:
            logger.error(f"Error sending RemoteStopTransaction to {self.id}: {e}")
            return None

    async def get_configuration(self, keys: Any = None) -> Any:
        """
        Send GetConfiguration to charger.

        - If keys is None → request full configuration (what the charger supports)
        - If keys is list[str] → request specific keys
        """
        try:
            logger.info(f"Sending GetConfiguration to {self.id}: keys={keys}")
            req = call.GetConfiguration()
            # ocpp library expects either no 'key' field (all keys) or a list
            if keys:
                # Normalise to list[str]
                if isinstance(keys, str):
                    keys = [keys]
                req = call.GetConfiguration(key=keys)
            resp = await self.call(req)
            logger.info(
                f"GetConfiguration response from {self.id}: "
                f"{len(getattr(resp, 'configuration_key', []) or [])} keys, "
                f"{len(getattr(resp, 'unknown_key', []) or [])} unknown"
            )
            return resp
        except Exception as e:
            logger.error(f"Error sending GetConfiguration to {self.id}: {e}", exc_info=True)
            return None

    async def change_configuration(self, key: str, value: str) -> Any:
        """
        Send ChangeConfiguration to charger.

        Returns the raw OCPP response (with .status field) or None on error.
        """
        try:
            logger.info(f"Sending ChangeConfiguration to {self.id}: {key}={value}")
            req = call.ChangeConfiguration(key=key, value=value)
            resp = await self.call(req)
            logger.info(
                f"ChangeConfiguration response from {self.id}: "
                f"status={getattr(resp, 'status', None)}"
            )
            return resp
        except Exception as e:
            logger.error(f"Error sending ChangeConfiguration to {self.id}: {e}", exc_info=True)
            return None

    # ==================== OCPP 1.6 OPERATIONS ====================

    async def change_availability(self, connector_id: int, type: str) -> Any:
        """
        Send ChangeAvailability to charger.
        type: 'Operative' or 'Inoperative'
        """
        try:
            logger.info(f"Sending ChangeAvailability to {self.id}: connector={connector_id}, type={type}")
            req = call.ChangeAvailability(connector_id=connector_id, type=type)
            resp = await self.call(req)
            logger.info(f"ChangeAvailability response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending ChangeAvailability to {self.id}: {e}", exc_info=True)
            return None

    async def clear_cache(self) -> Any:
        """Send ClearCache to charger."""
        try:
            logger.info(f"Sending ClearCache to {self.id}")
            req = call.ClearCache()
            resp = await self.call(req)
            logger.info(f"ClearCache response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending ClearCache to {self.id}: {e}", exc_info=True)
            return None

    async def reset(self, type: str) -> Any:
        """
        Send Reset to charger.
        type: 'Hard' or 'Soft'
        """
        try:
            logger.info(f"Sending Reset to {self.id}: type={type}")
            req = call.Reset(type=type)
            resp = await self.call(req)
            logger.info(f"Reset response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending Reset to {self.id}: {e}", exc_info=True)
            return None

    async def unlock_connector(self, connector_id: int) -> Any:
        """Send UnlockConnector to charger."""
        try:
            logger.info(f"Sending UnlockConnector to {self.id}: connector={connector_id}")
            req = call.UnlockConnector(connector_id=connector_id)
            resp = await self.call(req)
            logger.info(f"UnlockConnector response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending UnlockConnector to {self.id}: {e}", exc_info=True)
            return None

    async def get_diagnostics(self, location: str, retries: Optional[int] = None,
                               retry_interval: Optional[int] = None,
                               start_time: Optional[str] = None,
                               stop_time: Optional[str] = None) -> Any:
        """Send GetDiagnostics to charger."""
        try:
            logger.info(f"Sending GetDiagnostics to {self.id}: location={location}")
            kwargs = {"location": location}
            if retries is not None:
                kwargs["retries"] = retries
            if retry_interval is not None:
                kwargs["retry_interval"] = retry_interval
            if start_time:
                kwargs["start_time"] = start_time
            if stop_time:
                kwargs["stop_time"] = stop_time
            req = call.GetDiagnostics(**kwargs)
            resp = await self.call(req)
            logger.info(f"GetDiagnostics response from {self.id}: file_name={getattr(resp, 'file_name', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending GetDiagnostics to {self.id}: {e}", exc_info=True)
            return None

    async def update_firmware(self, location: str, retrieve_date: str,
                               retries: Optional[int] = None,
                               retry_interval: Optional[int] = None) -> Any:
        """Send UpdateFirmware to charger (no response payload in OCPP 1.6)."""
        try:
            logger.info(f"Sending UpdateFirmware to {self.id}: location={location}, retrieve_date={retrieve_date}")
            kwargs = {"location": location, "retrieve_date": retrieve_date}
            if retries is not None:
                kwargs["retries"] = retries
            if retry_interval is not None:
                kwargs["retry_interval"] = retry_interval
            req = call.UpdateFirmware(**kwargs)
            resp = await self.call(req)
            logger.info(f"UpdateFirmware sent to {self.id}")
            return resp
        except Exception as e:
            logger.error(f"Error sending UpdateFirmware to {self.id}: {e}", exc_info=True)
            return None

    async def reserve_now(self, connector_id: int, expiry_date: str,
                           id_tag: str, reservation_id: int) -> Any:
        """Send ReserveNow to charger."""
        try:
            logger.info(f"Sending ReserveNow to {self.id}: connector={connector_id}, reservation={reservation_id}")
            req = call.ReserveNow(
                connector_id=connector_id,
                expiry_date=expiry_date,
                id_tag=id_tag,
                reservation_id=reservation_id
            )
            resp = await self.call(req)
            logger.info(f"ReserveNow response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending ReserveNow to {self.id}: {e}", exc_info=True)
            return None

    async def cancel_reservation(self, reservation_id: int) -> Any:
        """Send CancelReservation to charger."""
        try:
            logger.info(f"Sending CancelReservation to {self.id}: reservation={reservation_id}")
            req = call.CancelReservation(reservation_id=reservation_id)
            resp = await self.call(req)
            logger.info(f"CancelReservation response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending CancelReservation to {self.id}: {e}", exc_info=True)
            return None

    async def data_transfer(self, vendor_id: str, message_id: Optional[str] = None,
                             data: Optional[str] = None) -> Any:
        """Send DataTransfer to charger."""
        try:
            logger.info(f"Sending DataTransfer to {self.id}: vendor={vendor_id}")
            kwargs = {"vendor_id": vendor_id}
            if message_id:
                kwargs["message_id"] = message_id
            if data:
                kwargs["data"] = data
            req = call.DataTransfer(**kwargs)
            # Default OCPP client timeout is 30s; some GAC firmware is slow or only replies for certain messageIds.
            prev_timeout = self._response_timeout
            self._response_timeout = max(prev_timeout, 90)
            try:
                resp = await self.call(req)
            finally:
                self._response_timeout = prev_timeout
            logger.info(f"DataTransfer response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except asyncio.TimeoutError:
            logger.warning(
                "DataTransfer from %s: no CallResult within timeout (vendor=%s message_id=%s). "
                "Firmware may ignore this messageId or never reply.",
                self.id,
                vendor_id,
                message_id,
            )
            return SimpleNamespace(status="Timeout", data=None)
        except FormatViolationError as e:
            # GAC/AION may return DataTransfer.conf status "Invalid" (not in OCPP 1.6 enum).
            # The ocpp library then raises FormatViolationError when validating CallResult.
            err = f"{e!s} {e!r}"
            if "Invalid" in err and "DataTransfer" in err:
                logger.warning(
                    "DataTransfer from %s: firmware status 'Invalid' (non-OCPP enum). vendor=%s message_id=%s",
                    self.id,
                    vendor_id,
                    message_id,
                )
                return SimpleNamespace(status="Invalid", data=None)
            logger.error(f"Error sending DataTransfer to {self.id}: {e}", exc_info=True)
            return None
        except Exception as e:
            err = f"{e!s} {e!r}"
            if "Invalid" in err and ("DataTransfer" in err or "is not one of" in err):
                logger.warning(
                    "DataTransfer from %s: treated vendor 'Invalid' / schema mismatch. vendor=%s message_id=%s",
                    self.id,
                    vendor_id,
                    message_id,
                )
                return SimpleNamespace(status="Invalid", data=None)
            logger.error(f"Error sending DataTransfer to {self.id}: {e}", exc_info=True)
            return None

    async def get_local_list_version(self) -> Any:
        """Send GetLocalListVersion to charger."""
        try:
            logger.info(f"Sending GetLocalListVersion to {self.id}")
            req = call.GetLocalListVersion()
            resp = await self.call(req)
            logger.info(f"GetLocalListVersion response from {self.id}: version={getattr(resp, 'list_version', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending GetLocalListVersion to {self.id}: {e}", exc_info=True)
            return None

    async def send_local_list(self, list_version: int, update_type: str,
                               local_authorization_list: Optional[List[Dict]] = None) -> Any:
        """
        Send SendLocalList to charger.
        update_type: 'Full' or 'Differential'
        """
        try:
            logger.info(f"Sending SendLocalList to {self.id}: version={list_version}, type={update_type}")
            kwargs = {"list_version": list_version, "update_type": update_type}
            if local_authorization_list:
                kwargs["local_authorization_list"] = local_authorization_list
            req = call.SendLocalList(**kwargs)
            resp = await self.call(req)
            logger.info(f"SendLocalList response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending SendLocalList to {self.id}: {e}", exc_info=True)
            return None

    async def trigger_message(self, requested_message: str,
                               connector_id: Optional[int] = None) -> Any:
        """
        Send TriggerMessage to charger.
        requested_message: e.g. 'BootNotification', 'StatusNotification', 'Heartbeat',
                           'MeterValues', 'DiagnosticsStatusNotification', 'FirmwareStatusNotification'
        """
        try:
            logger.info(f"Sending TriggerMessage to {self.id}: message={requested_message}")
            kwargs = {"requested_message": requested_message}
            if connector_id is not None:
                kwargs["connector_id"] = connector_id
            req = call.TriggerMessage(**kwargs)
            resp = await self.call(req)
            logger.info(f"TriggerMessage response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending TriggerMessage to {self.id}: {e}", exc_info=True)
            return None

    async def get_composite_schedule(self, connector_id: int, duration: int,
                                      charging_rate_unit: Optional[str] = None) -> Any:
        """Send GetCompositeSchedule to charger."""
        try:
            logger.info(f"Sending GetCompositeSchedule to {self.id}: connector={connector_id}, duration={duration}")
            kwargs = {"connector_id": connector_id, "duration": duration}
            if charging_rate_unit:
                kwargs["charging_rate_unit"] = charging_rate_unit
            req = call.GetCompositeSchedule(**kwargs)
            resp = await self.call(req)
            logger.info(f"GetCompositeSchedule response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending GetCompositeSchedule to {self.id}: {e}", exc_info=True)
            return None

    async def clear_charging_profile(self, id: Optional[int] = None,
                                      connector_id: Optional[int] = None,
                                      charging_profile_purpose: Optional[str] = None,
                                      stack_level: Optional[int] = None) -> Any:
        """Send ClearChargingProfile to charger."""
        try:
            logger.info(f"Sending ClearChargingProfile to {self.id}")
            kwargs = {}
            if id is not None:
                kwargs["id"] = id
            if connector_id is not None:
                kwargs["connector_id"] = connector_id
            if charging_profile_purpose:
                kwargs["charging_profile_purpose"] = charging_profile_purpose
            if stack_level is not None:
                kwargs["stack_level"] = stack_level
            req = call.ClearChargingProfile(**kwargs)
            resp = await self.call(req)
            logger.info(f"ClearChargingProfile response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending ClearChargingProfile to {self.id}: {e}", exc_info=True)
            return None

    async def set_charging_profile(self, connector_id: int, cs_charging_profiles: Dict) -> Any:
        """Send SetChargingProfile to charger."""
        try:
            logger.info(f"Sending SetChargingProfile to {self.id}: connector={connector_id}")
            req = call.SetChargingProfile(
                connector_id=connector_id,
                cs_charging_profiles=cs_charging_profiles
            )
            resp = await self.call(req)
            logger.info(f"SetChargingProfile response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
            logger.error(f"Error sending SetChargingProfile to {self.id}: {e}", exc_info=True)
            return None


# ─── WebSocket Connection Handler ─────────────────────────────────────────
async def on_connect(websocket):
    """
    Handle new WebSocket connection from charger
    
    Charger connects to: ws://your-server:9000/{charge_point_id}
    Example: ws://localhost:9000/0748911403000154
    
    Note: websockets 12+ passes only (connection); path is in connection.request.path
    """
    try:
        # Extract charge point ID from path (websockets 12+: path in request.path)
        raw_path = getattr(getattr(websocket, "request", None), "path", None) or ""
        clean_path = raw_path.split("?", 1)[0]
        charge_point_id = clean_path.strip("/")
        if not charge_point_id:
            logger.warning("Connection attempt without charge point ID")
            await websocket.close(code=1008, reason="Missing charge_point_id")
            return
        if not _CP_ID_PATTERN.match(charge_point_id):
            logger.warning("Rejected OCPP connection with invalid charge_point_id format: %s", charge_point_id)
            await websocket.close(code=1008, reason="Invalid charge_point_id format")
            return

        # Optional OCPP auth hardening (recommended for production).
        # - OCPP_REQUIRE_AUTH=1 (default): token required.
        # - OCPP_SHARED_TOKEN=...      : one shared token for all chargers.
        # - OCPP_CHARGER_TOKENS=CP1:t1,CP2:t2 : per-charger token map.
        require_auth = os.getenv("OCPP_REQUIRE_AUTH", "1").strip().lower() not in ("0", "false", "no")
        shared_token = os.getenv("OCPP_SHARED_TOKEN", "").strip()
        charger_tokens = _parse_token_map(os.getenv("OCPP_CHARGER_TOKENS", ""))
        provided_token = _extract_ws_token(websocket, raw_path)

        # Fallback: try full request target if path lacks query (some clients send it separately)
        if not provided_token and hasattr(websocket, "request"):
            req = websocket.request
            if hasattr(req, "request_target"):
                provided_token = _extract_ws_token(websocket, getattr(req, "request_target", "") or "")
            elif hasattr(req, "uri"):
                provided_token = _extract_ws_token(websocket, getattr(req, "uri", "") or "")

        if require_auth:
            expected_token = charger_tokens.get(charge_point_id) or shared_token
            if not expected_token:
                logger.warning(
                    "Rejected charger %s: OCPP auth enabled but no token configured (set OCPP_SHARED_TOKEN or OCPP_CHARGER_TOKENS)",
                    charge_point_id,
                )
                await websocket.close(code=1008, reason="Charger token not configured")
                return
            if not provided_token or not secrets.compare_digest(provided_token, expected_token):
                # Debug: log request attributes to diagnose token extraction
                req = getattr(websocket, "request", None)
                req_info = ""
                if req:
                    req_info = " req.path=%r" % (getattr(req, "path", None),)
                logger.warning(
                    "Rejected charger %s: invalid or missing OCPP token (path=%r, token_received=%s)%s",
                    charge_point_id, raw_path[:100], "yes" if provided_token else "no", req_info,
                )
                await websocket.close(code=1008, reason="Invalid charger token")
                return
        
        logger.info(f"🔌 New OCPP connection from charge point: {charge_point_id}")
        
        # Update last_heartbeat immediately for existing chargers (before BootNotification)
        try:
            db = SessionLocal()
            charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
            if charger:
                charger.last_heartbeat = _utcnow()
                charger.status = "online"
                db.commit()
                logger.info(f"Updated last_heartbeat for {charge_point_id} on connect")
            db.close()
        except Exception as e:
            logger.warning(f"Could not update heartbeat on connect for {charge_point_id}: {e}")
        
        # Create charge point instance and start handling messages
        charge_point = ChargePoint(charge_point_id, websocket)
        
        # Register charge point in global dictionary (for RemoteStartTransaction/RemoteStopTransaction)
        active_charge_points[charge_point_id] = charge_point
        logger.info(f"✅ Charge point {charge_point_id} registered. Total active connections: {len(active_charge_points)}")
        
        try:
            # Start handling OCPP messages from charger
            # Wrap in try-except to handle errors gracefully without closing connection
            await charge_point.start()
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error from {charge_point_id}: {e}. Charger may be sending invalid data.")
            # Log but don't close connection - charger might recover
            # The connection will be closed by the websocket library, but we'll handle reconnection
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Connection closed for {charge_point_id}: {e.code} - {e.reason}")
            # Normal connection close, don't log as error
        except Exception as e:
            logger.error(f"Error in charge point {charge_point_id} message handling: {e}", exc_info=True)
            # Log error but let connection close naturally
        finally:
            # Remove from active connections when disconnected
            active_charge_points.pop(charge_point_id, None)
            logger.info(f"❌ Charge point {charge_point_id} disconnected. Remaining connections: {len(active_charge_points)}")
            
            # IMPORTANT:
            # Many chargers (especially embedded/low-cost firmwares) drop WS connections frequently and reconnect.
            # Marking the charger "offline" immediately causes the dashboard to flap OFFLINE/UNAVAILABLE even when
            # the charger is actively communicating (StatusNotification) moments before disconnecting.
            #
            # We therefore do NOT force status=offline here. Instead, we rely on:
            # - `last_heartbeat` (updated by Heartbeat/StatusNotification handlers)
            # - API-side "effective status" computation (based on heartbeat age)
            #
            # This makes the dashboard reflect reality better under flaky WS behavior.
            try:
                db = SessionLocal()
                charger = db.query(Charger).filter(Charger.charge_point_id == charge_point_id).first()
                if charger:
                    logger.info(
                        f"Charger {charge_point_id} disconnected; leaving status/availability unchanged "
                        f"(status={charger.status}, availability={charger.availability}, last_heartbeat={charger.last_heartbeat})"
                    )
                db.close()
            except Exception as e:
                logger.error(f"Error updating charger status on disconnect: {e}", exc_info=True)
    except UnicodeDecodeError as e:
        logger.error(f"Unicode decode error in connection handler: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error handling connection: {e}", exc_info=True)
        try:
            await websocket.close()
        except Exception:
            pass


def get_active_charge_point(charge_point_id: str) -> ChargePoint:
    """Get active charge point connection"""
    return active_charge_points.get(charge_point_id)


async def orphan_session_watchdog(interval_seconds: int = 600):
    """
    Background task — runs every `interval_seconds` (default 10 min).
    Closes any charging session that:
      - Is still 'active' or 'pending'
      - Has had no MeterValue update for > 30 minutes
      - The charger is currently offline (not in active_charge_points)
    This catches sessions that were never properly stopped due to abrupt disconnects.
    """
    logger.info("Orphan session watchdog started (interval=%ds)", interval_seconds)
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            db = SessionLocal()
            cutoff = _utcnow() - timedelta(minutes=30)

            stuck_sessions = db.query(ChargingSession).filter(
                ChargingSession.status.in_(["active", "pending"]),
                ChargingSession.start_time <= cutoff
            ).all()

            closed = 0
            for s in stuck_sessions:
                charger = db.query(Charger).filter(Charger.id == s.charger_id).first()
                cp_id = charger.charge_point_id if charger else None

                # Only close if the charger is not currently connected
                if cp_id and cp_id in active_charge_points:
                    continue

                # Check last meter value timestamp
                last_meter = (
                    db.query(MeterValue)
                    .filter(MeterValue.transaction_id == s.transaction_id)
                    .order_by(desc(MeterValue.timestamp))
                    .first()
                )
                if last_meter and last_meter.timestamp > cutoff:
                    continue  # Still receiving meter updates, skip

                final_energy = (last_meter.total_kwh or 0.0) if last_meter else (s.energy_consumed or 0.0)
                s.status = "interrupted"
                s.stop_time = _utcnow()
                s.energy_consumed = final_energy

                if charger:
                    charger.availability = "available"

                closed += 1
                logger.warning(
                    f"Watchdog closed orphan session {s.id} (charger={cp_id}, "
                    f"tx={s.transaction_id}, energy={final_energy:.3f} kWh)"
                )

            if closed:
                db.commit()
                logger.info(f"Orphan watchdog: closed {closed} stuck session(s)")
            db.close()
        except Exception as e:
            logger.error(f"Orphan session watchdog error: {e}", exc_info=True)
            try:
                db.close()
            except Exception:
                pass


async def scheduled_charging_worker(interval_seconds: int = 60):
    """
    Background task — runs every minute.
    Checks all enabled ChargingSchedule rows. If the current time (Asia/Kuala_Lumpur)
    matches a schedule's start_time or stop_time AND today is in days_of_week,
    send RemoteStartTransaction / RemoteStopTransaction via OCPP.
    """
    # Malaysia timezone: UTC+8 (no DST)
    MYT = timezone(timedelta(hours=8))
    logger.info("Scheduled charging worker started (interval=%ds)", interval_seconds)

    while True:
        await asyncio.sleep(interval_seconds)
        try:
            now = datetime.now(MYT)
            current_hhmm = now.strftime("%H:%M")
            # Python weekday(): Monday=0..Sunday=6 — we use Sunday=0..Saturday=6 to match JS Date.getDay()
            current_dow = (now.weekday() + 1) % 7  # Mon=0->1, Sun=6->0

            db = SessionLocal()
            schedules = db.query(ChargingSchedule).filter(
                ChargingSchedule.enabled == True
            ).all()

            for sch in schedules:
                # Check if today is an active day
                days = (sch.days_of_week or "daily").strip().lower()
                if days != "daily":
                    active_days = [int(x) for x in days.split(",") if x.strip().isdigit()]
                    if current_dow not in active_days:
                        continue

                is_start = current_hhmm == sch.start_time
                is_stop  = current_hhmm == sch.stop_time

                if not (is_start or is_stop):
                    continue

                # Fetch live OCPP connection
                cp_conn = active_charge_points.get(sch.charge_point_id)
                if cp_conn is None:
                    logger.warning(
                        f"[Scheduler] Charger {sch.charge_point_id} offline — "
                        f"skip {'start' if is_start else 'stop'} trigger"
                    )
                    continue

                # Helper: dispatch an OCPP call onto the API event loop.
                # Prevents "Queue bound to a different event loop" — see API_LOOP docstring.
                async def _dispatch(coro):
                    if API_LOOP is not None and API_LOOP.is_running():
                        fut = asyncio.run_coroutine_threadsafe(coro, API_LOOP)
                        return await asyncio.wrap_future(fut)
                    # Fallback: run in current loop (works if API never touched this CP yet)
                    return await coro

                try:
                    if is_start:
                        # Debounce: don't re-trigger within same 2-min window
                        if sch.last_triggered_start and \
                                (_utcnow() - sch.last_triggered_start).total_seconds() < 120:
                            continue
                        logger.info(
                            f"[Scheduler] Triggering RemoteStart for {sch.charge_point_id} "
                            f"(schedule #{sch.id}, user={sch.user_id}, connector={sch.connector_id})"
                        )
                        await _dispatch(cp_conn.remote_start_transaction(
                            connector_id=sch.connector_id,
                            id_tag=sch.id_tag or "APP_USER",
                        ))
                        sch.last_triggered_start = _utcnow()
                        db.commit()

                    elif is_stop:
                        if sch.last_triggered_stop and \
                                (_utcnow() - sch.last_triggered_stop).total_seconds() < 120:
                            continue
                        # Find active session on this charger to get transaction_id
                        charger = db.query(Charger).filter(
                            Charger.charge_point_id == sch.charge_point_id
                        ).first()
                        if not charger:
                            continue
                        # Match any unfinished session (status may be "active",
                        # "interrupted" after a reconnect, etc). stop_time is the
                        # authoritative signal — NULL means session not yet closed.
                        active = db.query(ChargingSession).filter(
                            ChargingSession.charger_id == charger.id,
                            ChargingSession.stop_time.is_(None),
                        ).order_by(desc(ChargingSession.start_time)).first()
                        if not active:
                            logger.info(
                                f"[Scheduler] No active session on {sch.charge_point_id} — "
                                f"skip stop trigger"
                            )
                            continue
                        logger.info(
                            f"[Scheduler] Triggering RemoteStop for {sch.charge_point_id} "
                            f"(tx={active.transaction_id}, schedule #{sch.id})"
                        )
                        await _dispatch(cp_conn.remote_stop_transaction(
                            transaction_id=active.transaction_id
                        ))
                        sch.last_triggered_stop = _utcnow()
                        db.commit()
                except Exception as e:
                    logger.error(
                        f"[Scheduler] Error executing schedule #{sch.id}: {e}",
                        exc_info=True,
                    )

            db.close()
        except Exception as e:
            logger.error(f"Scheduled charging worker error: {e}", exc_info=True)
            try:
                db.close()
            except Exception:
                pass

