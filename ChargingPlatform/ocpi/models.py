"""
OCPI 2.2.1 Pydantic models for CPO interface.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============ OCPI Response Wrapper ============
class OCPIResponse(BaseModel):
    """Standard OCPI response envelope."""
    status_code: int = 1000  # 1000=Success, 2xxx=Client error, 3xxx=Server error
    status_message: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    data: Optional[Any] = None


# ============ Version Module ============
class VersionInfo(BaseModel):
    version: str = "2.2.1"
    url: str


class VersionEndpoint(BaseModel):
    identifier: str  # ModuleID: credentials, locations, sessions, cdrs, tokens, tariffs, commands
    role: str = "SENDER"  # SENDER or RECEIVER
    url: str


class VersionDetails(BaseModel):
    version: str = "2.2.1"
    endpoints: List[VersionEndpoint]


# ============ Location Module ============
class DisplayText(BaseModel):
    language: str = "en"
    text: str


class Connector(BaseModel):
    id: str
    standard: str = "IEC_62196_T2"  # Connector type
    format: str = "SOCKET"
    power_type: str = "AC_1_PHASE"
    voltage: Optional[int] = None
    amperage: Optional[int] = None
    max_electric_power: Optional[int] = None  # Watts
    tariff_ids: Optional[List[str]] = None
    terms_and_conditions: Optional[str] = None
    last_updated: str


class EVSE(BaseModel):
    uid: str
    evse_id: Optional[str] = None
    status: str = "AVAILABLE"  # AVAILABLE, BLOCKED, CHARGING, INOPERATIVE, PLANNED, REMOVED, RESERVED, UNKNOWN
    connectors: List[Connector]
    floor_level: Optional[str] = None
    physical_reference: Optional[str] = None
    directions: Optional[List[DisplayText]] = None
    parking_restrictions: Optional[List[str]] = None
    images: Optional[List[Dict]] = None
    last_updated: str


class Location(BaseModel):
    id: str
    publish: bool = True
    name: Optional[str] = None
    address: str
    city: str
    postal_code: str
    country: str
    coordinates: Dict[str, float]  # latitude, longitude
    related_locations: Optional[List[Dict]] = None
    evse_uid: Optional[str] = None
    evses: List[EVSE]
    operator: Optional[Dict] = None
    suboperator: Optional[Dict] = None
    owner: Optional[Dict] = None
    facility_id: Optional[str] = None
    time_zone: str = "Asia/Kuala_Lumpur"
    opening_times: Optional[Dict] = None
    charging_when_closed: Optional[bool] = True
    images: Optional[List[Dict]] = None
    energy_mix: Optional[Dict] = None
    last_updated: str


# ============ Session Module ============
class CdrToken(BaseModel):
    uid: str
    type: str = "RFID"  # AD_HOC_USER, APP_USER, RFID, OTHER
    contract_id: str


class Session(BaseModel):
    id: str
    start_datetime: str
    end_datetime: Optional[str] = None
    kwh: float = 0.0
    cdr_token: CdrToken
    auth_method: str = "AUTH_REQUEST"
    authorization_reference: Optional[str] = None
    location_id: str
    evse_uid: str
    connector_id: str
    meter_id: Optional[str] = None
    currency: str = "MYR"
    charging_periods: Optional[List[Dict]] = None
    total_cost: Optional[float] = None
    status: str  # ACTIVE, COMPLETED, INVALID, PENDING, RESERVATION
    last_updated: str


# ============ CDR Module ============
class CdrDimension(BaseModel):
    type: str  # ENERGY, FLAT, TIME, PARKING_TIME
    volume: float


class CDR(BaseModel):
    id: str
    start_datetime: str
    end_datetime: str
    auth_id: str
    auth_method: str = "AUTH_REQUEST"
    location_id: str
    evse_uid: str
    connector_id: str
    meter_id: Optional[str] = None
    currency: str = "MYR"
    total_cost: Optional[float] = None
    total_energy: float  # kWh
    total_time: Optional[float] = None  # hours
    total_parking_time: Optional[float] = None
    cdr_token: CdrToken
    charging_periods: Optional[List[Dict]] = None
    credit: Optional[bool] = False
    credit_reference_id: Optional[str] = None
    last_updated: str


# ============ Token Module ============
class Token(BaseModel):
    uid: str
    type: str = "RFID"
    contract_id: str
    issuer: str
    is_valid: bool = True
    whitelist: str = "ALWAYS"  # ALWAYS, ALLOWED, ALLOWED_OFFLINE, NEVER
    language: Optional[str] = None
    default_profile_type: Optional[str] = None
    energy_contract: Optional[Dict] = None
    last_updated: str
