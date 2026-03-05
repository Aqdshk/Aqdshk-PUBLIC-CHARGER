# OCPI 2.2.1 - TNG Roaming Integration

ChargingPlatform implements **OCPI 2.2.1 CPO (Charge Point Operator)** interface for EV charging roaming. This enables integration with eMSPs like **TNG** so their app users can charge at your chargers.

## Implemented Modules

| Module | Endpoint | Description |
|--------|----------|-------------|
| **Versions** | `GET /ocpi/versions` | List supported OCPI versions |
| **Version Details** | `GET /ocpi/2.2.1` | List modules and endpoint URLs |
| **Locations** | `GET /ocpi/2.2.1/locations` | Charger locations (from DB) |
| **Locations** | `GET /ocpi/2.2.1/locations/{id}` | Single location |
| **Sessions** | `GET /ocpi/2.2.1/sessions` | Charging sessions |
| **CDRs** | `GET /ocpi/2.2.1/cdrs` | Charge Detail Records (billing) |
| **Tokens** | `GET /ocpi/2.2.1/tokens` | Token whitelist (placeholder) |
| **Tariffs** | `GET /ocpi/2.2.1/tariffs` | Pricing info |
| **Credentials** | `POST /ocpi/2.2.1/credentials` | Registration (TODO: TNG docs) |

## Environment Variables

Add to `.env`:

```env
# OCPI Base URL (your public API URL)
OCPI_BASE_URL=https://api.your-domain.com

# Optional: Token for Authorization header (eMSP uses when calling)
OCPI_TOKEN=your-ocpi-token

# Party ID (3 chars) and Country (2 chars)
OCPI_PARTY_ID=PLG
OCPI_COUNTRY_CODE=MY

# Location defaults (optional)
OCPI_LOCATION_ADDRESS=Charging Station
OCPI_LOCATION_CITY=Kuala Lumpur
OCPI_LOCATION_POSTAL=50000
OCPI_LOCATION_LAT=3.1390
OCPI_LOCATION_LON=101.6869
```

## Test Endpoints

```bash
# Versions
curl http://localhost:8000/ocpi/versions

# Version details
curl http://localhost:8000/ocpi/2.2.1

# Locations
curl http://localhost:8000/ocpi/2.2.1/locations

# Sessions (with date filter)
curl "http://localhost:8000/ocpi/2.2.1/sessions?date_from=2026-01-01T00:00:00Z"

# CDRs
curl "http://localhost:8000/ocpi/2.2.1/cdrs?date_from=2026-01-01T00:00:00Z"
```

## TNG Integration

When TNG provides their API documentation:

1. **Credentials** – Implement `POST /ocpi/2.2.1/credentials` to receive and store TNG's credentials
2. **Commands** – If TNG sends START_SESSION/STOP_SESSION, implement Commands module
3. **Auth** – Align token/authorization flow with TNG's requirements
4. **Push vs Pull** – Confirm whether TNG uses Push (we send) or Pull (they fetch) model

Adjust the implementation based on TNG's specific requirements.
