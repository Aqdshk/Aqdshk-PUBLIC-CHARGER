import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import websockets.exceptions
from sqlalchemy import desc
from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp, call, call_result
from ocpp.v16.enums import AuthorizationStatus, RegistrationStatus

from database import SessionLocal, Charger, ChargingSession, MeterValue, Fault

logger = logging.getLogger(__name__)

# Global dictionary to track active charge point connections
active_charge_points: Dict[str, 'ChargePoint'] = {}

def utc_now_iso_z() -> str:
    """RFC3339 UTC timestamp with 'Z' suffix (better charger compatibility)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
        
        # Get or create charger
        charger = self.db.query(Charger).filter(Charger.charge_point_id == self.id).first()
        
        if not charger:
            charger = Charger(
                charge_point_id=self.id,
                vendor=charge_point_vendor,
                model=charge_point_model,
                firmware_version=kwargs.get('firmware_version', 'Unknown'),
                status="online",
                last_heartbeat=datetime.utcnow()
            )
            self.db.add(charger)
        else:
            # Check if charger was offline (reconnected) and has active charging sessions
            was_offline = charger.status == 'offline'
            
            charger.vendor = charge_point_vendor
            charger.model = charge_point_model
            charger.firmware_version = kwargs.get('firmware_version', charger.firmware_version)
            charger.status = "online"
            charger.last_heartbeat = datetime.utcnow()
            
            # If charger reconnected, check for active charging sessions
            # If there are active sessions, trust the database and set availability to 'charging'
            # StatusNotification will correct it later if charger sends different status
            if was_offline:
                # Check for active sessions with valid transaction_id (> 0)
                active_sessions = self.db.query(ChargingSession).filter(
                    ChargingSession.charger_id == charger.id,
                    ChargingSession.status.in_(['active', 'pending']),
                    ChargingSession.transaction_id > 0  # Only consider valid sessions (transaction_id > 0)
                ).all()
                
                # Also check for recent pending sessions (transaction_id = -1) that were created recently
                # This handles case where charger disconnected right after RemoteStartTransaction
                # but before StartTransaction was received
                recent_pending_sessions = self.db.query(ChargingSession).filter(
                    ChargingSession.charger_id == charger.id,
                    ChargingSession.status == 'pending',
                    ChargingSession.transaction_id <= 0,  # Pending sessions with -1 or 0
                    ChargingSession.start_time >= datetime.utcnow() - timedelta(minutes=10)  # Created within last 10 minutes
                ).all()
                
                if active_sessions:
                    logger.info(f"Charger {self.id} reconnected with {len(active_sessions)} active charging session(s)")
                    # Trust the database - if we have active sessions, charger is likely still charging
                    # Set availability to 'charging' immediately so dashboard shows correct state
                    # StatusNotification will correct it later if charger sends different status
                    charger.availability = 'charging'
                    logger.info(f"Charger {self.id} reconnected with active sessions - setting availability to 'charging' (will be corrected by StatusNotification if needed)")
                elif recent_pending_sessions:
                    logger.info(f"Charger {self.id} reconnected with {len(recent_pending_sessions)} recent pending session(s) - charger likely still charging")
                    # If we have recent pending sessions, charger might still be charging
                    # Set availability to 'charging' to be safe - StatusNotification will correct if wrong
                    charger.availability = 'charging'
                    logger.info(f"Charger {self.id} reconnected with recent pending sessions - setting availability to 'charging' (will be corrected by StatusNotification if needed)")
                else:
                    # No valid active sessions or recent pending sessions - charger is not charging
                    # Set availability to 'available' or 'preparing' (will be updated by StatusNotification)
                    if charger.availability == 'charging':
                        charger.availability = 'preparing'  # Temporary, will be updated by StatusNotification
                        logger.info(f"Charger {self.id} reconnected with no active/recent sessions - resetting availability")
        
        self.db.commit()
        
        # Get charger configuration for heartbeat interval
        # Use charger's configured interval or default to 7200 seconds (2 hours)
        heartbeat_interval = charger.heartbeat_interval if hasattr(charger, 'heartbeat_interval') and charger.heartbeat_interval else 7200
        
        return call_result.BootNotification(
            current_time=utc_now_iso_z(),
            interval=heartbeat_interval,
            status=RegistrationStatus.accepted
        )
    
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
                        # Charger is not charging - sync availability
                        # BUT: If we have a very recent active session (started within last 2 minutes),
                        # the charger might not have synced yet after reconnection - be cautious
                        if active_session:
                            session_age_seconds = (datetime.utcnow() - active_session.start_time).total_seconds()
                            
                            # If session is very recent (< 2 minutes), charger might still be syncing after reconnect
                            # Keep availability as 'charging' temporarily, but log a warning
                            if session_age_seconds < 120:  # 2 minutes
                                logger.warning(
                                    f"Charger {self.id} reports status '{status}' but has recent active session "
                                    f"{active_session.transaction_id} (started {session_age_seconds:.0f}s ago). "
                                    f"Keeping availability as 'charging' - charger might still be syncing after reconnect."
                                )
                                # Keep availability as 'charging' - don't override yet
                                charger.availability = 'charging'
                            else:
                                # Session is old enough - charger has had time to sync, trust its status
                                logger.warning(
                                    f"Charger {self.id} reports status '{status}' but has active session "
                                    f"{active_session.transaction_id} (started {session_age_seconds:.0f}s ago). "
                                    f"Marking session as completed (charger stopped charging)."
                                )
                                charger.availability = new_availability
                                active_session.status = 'completed'
                                active_session.stop_time = datetime.utcnow()
                                logger.info(f"Completed stale session {active_session.transaction_id} for charger {self.id}")
                        else:
                            # No active session - safe to update availability
                            charger.availability = new_availability
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
                            session.stop_time = datetime.utcnow()
                            logger.info(f"Cleared placeholder session (transaction_id={session.transaction_id}) for charger {self.id}")
                    except Exception as e:
                        logger.error(f"Error clearing placeholder sessions for charger {self.id}: {e}", exc_info=True)
                        self.db.rollback()
                except Exception as e:
                    logger.error(f"Error checking sessions for charger {self.id}: {e}", exc_info=True)
                    # Fallback: use simple status mapping when error occurs
                    charger.availability = status_map.get(status, 'unknown')
            
            charger.last_heartbeat = datetime.utcnow()
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
                        timestamp=datetime.utcnow()
                    )
                    self.db.add(fault)
            
            # Clear faults if status is not faulted
            if status != 'Faulted' and error_code == 'NoError':
                self.db.query(Fault).filter(
                    Fault.charger_id == charger.id,
                    Fault.cleared == False
                ).update({'cleared': True, 'cleared_at': datetime.utcnow()})
            
            try:
                self.db.commit()
            except Exception as e:
                logger.error(f"Error committing StatusNotification for charger {self.id}: {e}", exc_info=True)
                self.db.rollback()
                # Don't fail the StatusNotification - just log the error
                # Return success response to prevent charger from disconnecting
            
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
        """Handle StartTransaction from charging station"""
        logger.info(f"StartTransaction from {self.id}: transaction {kwargs.get('transaction_id')}")
        
        charger = self.db.query(Charger).filter(Charger.charge_point_id == self.id).first()
        if charger:
            transaction_id = kwargs.get('transaction_id')
            
            # Check if session already exists (from remote start)
            existing_session = self.db.query(ChargingSession).filter(
                ChargingSession.charger_id == charger.id,
                ChargingSession.status.in_(["pending", "active"])
            ).order_by(desc(ChargingSession.start_time)).first()
            
            if existing_session:
                # Update existing session with transaction_id
                # Handle negative transaction_id (temporary placeholder)
                if existing_session.transaction_id < 0:
                    # Delete old session and create new one with real transaction_id
                    self.db.delete(existing_session)
                    self.db.commit()
                    session = ChargingSession(
                        charger_id=charger.id,
                        transaction_id=transaction_id,
                        start_time=datetime.fromisoformat(timestamp.replace('Z', '+00:00')),
                        status="active",
                        user_id=id_tag
                    )
                    self.db.add(session)
                else:
                    # Update existing session
                    existing_session.transaction_id = transaction_id
                    existing_session.status = "active"
                    existing_session.start_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    if existing_session.user_id == "LOCAL_CHARGING":
                        existing_session.user_id = id_tag  # Update from placeholder
            else:
                # Create new session
                session = ChargingSession(
                    charger_id=charger.id,
                    transaction_id=transaction_id,
                    start_time=datetime.fromisoformat(timestamp.replace('Z', '+00:00')),
                    status="active",
                    user_id=id_tag
                )
                self.db.add(session)
            
            charger.availability = "charging"
            charger.status = "online"  # Ensure status is online when charging starts
            self.db.commit()
            
            logger.info(f"Charger {self.id} started charging with transaction {transaction_id}")
            
            return call_result.StartTransaction(
                transaction_id=transaction_id,
                id_tag_info={'status': AuthorizationStatus.accepted}
            )
        
        return call_result.StartTransaction(
            transaction_id=0,
            id_tag_info={'status': AuthorizationStatus.invalid}
        )
    
    @on('StopTransaction')
    async def on_stop_transaction(self, transaction_id: int, id_tag: str, meter_stop: int, timestamp: str, **kwargs):
        """Handle StopTransaction from charging station"""
        logger.info(f"StopTransaction from {self.id}: transaction {transaction_id}")
        
        session = self.db.query(ChargingSession).filter(
            ChargingSession.transaction_id == transaction_id
        ).first()
        
        if session:
            session.stop_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            session.status = "completed"
            # Energy consumed will be updated from meter values
            self.db.commit()
            
            # Update charger availability
            charger = self.db.query(Charger).filter(Charger.id == session.charger_id).first()
            if charger:
                charger.availability = "available"
                self.db.commit()
        
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
            sampled_value = mv.get('sampledValue', [])
            
            voltage = None
            current = None
            power = None
            total_kwh = None
            
            for sv in sampled_value:
                value = float(sv.get('value', 0))
                measurand = sv.get('measurand', '')
                unit = sv.get('unit', '')
                
                if measurand == 'Voltage':
                    voltage = value
                elif measurand == 'Current.Import':
                    current = value
                elif measurand == 'Power.Active.Import':
                    power = value
                elif measurand == 'Energy.Active.Import.Register':
                    total_kwh = value / 1000.0  # Convert Wh to kWh
            
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
        return call_result.MeterValues()
    
    @on('Heartbeat')
    async def on_heartbeat(self):
        """Handle Heartbeat from charging station"""
        try:
            charger = self.db.query(Charger).filter(Charger.charge_point_id == self.id).first()
            if charger:
                charger.last_heartbeat = datetime.utcnow()
                charger.status = "online"
                try:
                    self.db.commit()
                    logger.debug(f"Heartbeat received from {self.id}, status updated to online")
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
            resp = await self.call(req)
            logger.info(f"DataTransfer response from {self.id}: status={getattr(resp, 'status', None)}")
            return resp
        except Exception as e:
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


async def on_connect(websocket, path):
    """
    Handle new WebSocket connection from charger
    
    Charger connects to: ws://your-server:9000/{charge_point_id}
    Example: ws://localhost:9000/0748911403000154
    """
    try:
        # Extract charge point ID from path
        charge_point_id = path.strip('/')
        if not charge_point_id:
            logger.warning("Connection attempt without charge point ID")
            await websocket.close()
            return
        
        logger.info(f"🔌 New OCPP connection from charge point: {charge_point_id}")
        
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
        logger.error(f"Unicode decode error in connection handler for {charge_point_id}: {e}")
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

