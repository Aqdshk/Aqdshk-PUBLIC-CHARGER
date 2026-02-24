# Quick Start Guide

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the server:**
   ```bash
   python main.py
   ```

   This will start:
   - OCPP WebSocket server on port 9000
   - FastAPI dashboard server on port 8000

## Access the Dashboard

Open your browser and navigate to:
```
http://localhost:8000
```

## Connect a Charging Station

Your charging station should connect to:
```
ws://localhost:9000/{charge_point_id}
```

Replace `{charge_point_id}` with your actual charge point identifier.

**Example:**
- `ws://localhost:9000/CP001`
- `ws://localhost:9000/CHARGER_01`

## Dashboard Features

### 1. Charger Status
- View online/offline status of all chargers
- See availability status (Available/Charging/Faulted)
- Monitor last heartbeat timestamp
- Auto-refreshes every 5 seconds

### 2. Charging Sessions
- View all charging sessions
- Filter by charger
- See transaction ID, start/stop times, and energy consumed

### 3. Metering
- Real-time voltage, current, power, and total kWh
- Select a charger to view its latest metering data

### 4. Errors & Faults
- Monitor all faults (overcurrent, ground fault, emergency stop, CP error)
- Toggle to show/hide cleared faults

### 5. Device Information
- View firmware version, charger model, and vendor
- Select a charger to see its device details

## Troubleshooting

### Charger not appearing in dashboard
- Ensure the charger has sent a BootNotification
- Check that the charge_point_id in the WebSocket URL matches
- Verify the OCPP server is running on port 9000

### No metering data
- Ensure the charger is sending MeterValues messages
- Check that a charging session is active (for transaction-specific data)

### Database
The system uses SQLite database (`charging_platform.db`) which is created automatically on first run.


