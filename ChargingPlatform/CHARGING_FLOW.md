# Charging Flow Documentation

## Complete Flow: AppEV → ChargingPlatform → Charger

### 1. **AppEV User Clicks "Start Charging"**

User clicks button in app, app calls:
```dart
await sessionProvider.startCharging(
  '0748911403000154',  // charge_point_id
  1,                   // connector_id
  idTag: 'USER_123',   // optional
);
```

### 2. **AppEV Sends HTTP Request to ChargingPlatform**

**Request:**
```
POST http://localhost:8000/api/charging/start
Content-Type: application/json

{
  "charger_id": "0748911403000154",
  "connector_id": 1,
  "id_tag": "APP_USER"
}
```

### 3. **ChargingPlatform API Validates Request**

- ✅ Check charger exists in database
- ✅ Check charger is online
- ✅ Check charger is available
- ✅ Check charger is connected to OCPP server

### 4. **ChargingPlatform Sends RemoteStartTransaction via OCPP**

ChargingPlatform sends OCPP message to charger:
```
RemoteStartTransaction
├── connector_id: 1
└── id_tag: "APP_USER"
```

### 5. **Charger Receives RemoteStartTransaction**

Charger (your ESP32/steve ocpp) receives the message and:
- ✅ Validates id_tag
- ✅ Starts charging on connector 1
- ✅ Sends StartTransaction back to ChargingPlatform

### 6. **Charger Sends StartTransaction to ChargingPlatform**

```
StartTransaction
├── transaction_id: 12345
├── connector_id: 1
├── id_tag: "APP_USER"
└── meter_start: 0
```

### 7. **ChargingPlatform Updates Database**

- Creates/updates charging session
- Sets status to "active"
- Stores transaction_id

### 8. **ChargingPlatform Returns Success to AppEV**

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Charging started successfully. Charger is starting...",
  "transaction_id": 12345
}
```

### 9. **AppEV Shows Success Message**

App displays: "Charging started!" and begins polling for session updates.

---

## Stop Charging Flow

### 1. **AppEV User Clicks "Stop Charging"**

```dart
await sessionProvider.stopCharging();
```

### 2. **AppEV Sends HTTP Request**

```
POST http://localhost:8000/api/charging/stop
Content-Type: application/json

{
  "transaction_id": 12345
}
```

### 3. **ChargingPlatform Sends RemoteStopTransaction**

```
RemoteStopTransaction
└── transaction_id: 12345
```

### 4. **Charger Stops Charging**

Charger stops and sends StopTransaction back.

### 5. **ChargingPlatform Returns Success**

```json
{
  "success": true,
  "message": "Charging stop requested successfully. Charger is stopping...",
  "transaction_id": 12345
}
```

---

## Charger Connection Setup

### Connect Your Charger to ChargingPlatform

1. **Start ChargingPlatform OCPP Server:**
   ```bash
   cd ChargingPlatform
   python main.py
   ```
   
   OCPP server will start on: `ws://0.0.0.0:9000`

2. **Configure Your Charger:**
   
   Your charger (ESP32/steve ocpp) needs to connect to:
   ```
   ws://YOUR_SERVER_IP:9000/{charge_point_id}
   ```
   
   Example:
   ```
   ws://34.16.91.156:9000/0748911403000154
   ```

3. **Charger Registration:**
   
   When charger connects, it will send:
   - `BootNotification` → ChargingPlatform registers charger
   - `Heartbeat` (every 7200 seconds) → Keep connection alive
   - `StatusNotification` → Update availability status

4. **Verify Connection:**
   
   Check logs for:
   ```
   🔌 New OCPP connection from charge point: 0748911403000154
   ✅ Charge point 0748911403000154 registered. Total active connections: 1
   ```

---

## API Endpoints

### Start Charging
```
POST /api/charging/start
```

**Request Body:**
```json
{
  "charger_id": "0748911403000154",
  "connector_id": 1,
  "id_tag": "APP_USER"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Charging started successfully. Charger is starting...",
  "transaction_id": 0
}
```

### Stop Charging
```
POST /api/charging/stop
```

**Request Body:**
```json
{
  "transaction_id": 12345
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Charging stop requested successfully. Charger is stopping...",
  "transaction_id": 12345
}
```

---

## Important Notes

1. **id_tag Validation:**
   - `id_tag` must be valid in your SteVe OCPP server
   - Default: "APP_USER" (make sure this exists in SteVe)
   - Can use user-specific id_tag from app

2. **Charge Point ID:**
   - Must match the charge_point_id in your SteVe OCPP server
   - Format: Usually like "0748911403000154"
   - Used in WebSocket connection URL

3. **Connector ID:**
   - Your charger has 1 connector (from configuration)
   - Always use `connector_id: 1`

4. **Connection Status:**
   - Charger must be connected to OCPP server before starting charging
   - Check connection status via: `GET /api/chargers/{charge_point_id}/status`

5. **Transaction ID:**
   - Initially 0 when RemoteStartTransaction is sent
   - Updated when charger sends StartTransaction back
   - Use this transaction_id for stop charging

---

## Testing

1. **Start Backend:**
   ```bash
   cd ChargingPlatform
   python main.py
   ```

2. **Connect Charger:**
   - Ensure charger connects to `ws://YOUR_SERVER:9000/{charge_point_id}`
   - Check logs for connection confirmation

3. **Test from App:**
   - Open AppEV
   - Find charger
   - Click "Start Charging"
   - Verify charger starts charging
   - Click "Stop Charging"
   - Verify charger stops

4. **Check Logs:**
   - ChargingPlatform logs show all OCPP messages
   - App logs show API responses

---

## Troubleshooting

### Charger Not Found
- Ensure charger is registered in database (via BootNotification)
- Check charge_point_id matches exactly

### Charger Not Connected
- Verify charger WebSocket connection to OCPP server
- Check OCPP server is running on port 9000
- Check firewall/network settings

### RemoteStartTransaction Failed
- Verify id_tag is valid in SteVe OCPP server
- Check charger is available (not already charging)
- Check connector_id is valid (1 for your charger)

### Transaction Not Starting
- Check charger receives RemoteStartTransaction
- Verify charger sends StartTransaction back
- Check database for session updates
