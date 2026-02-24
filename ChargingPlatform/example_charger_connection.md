# Example: Connecting a Charging Station

## OCPP Connection Details

- **WebSocket URL**: `ws://localhost:9000/{charge_point_id}`
- **Protocol**: OCPP 1.6
- **Subprotocol**: `ocpp1.6`

## Example Charge Point ID

When connecting, replace `{charge_point_id}` with your actual charge point identifier, for example:
- `ws://localhost:9000/CP001`
- `ws://localhost:9000/CHARGER_01`

## Testing with OCPP Client

You can test the connection using Python:

```python
import asyncio
from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call
import websockets

async def test_charger():
    async with websockets.connect(
        'ws://localhost:9000/CP001',
        subprotocols=['ocpp1.6']
    ) as ws:
        cp = ChargePoint('CP001', ws)
        await cp.start()
        
        # Send BootNotification
        boot_notification = await cp.call(call.BootNotification(
            charge_point_model="Test Model",
            charge_point_vendor="Test Vendor"
        ))
        print(f"BootNotification response: {boot_notification}")
        
        # Send Heartbeat
        heartbeat = await cp.call(call.Heartbeat())
        print(f"Heartbeat response: {heartbeat}")

asyncio.run(test_charger())
```

## Dashboard Access

Once a charger is connected, you can view it in the dashboard at:
- **Dashboard URL**: http://localhost:8000

The dashboard will automatically display:
- Charger status (online/offline)
- Availability (available/charging/faulted)
- Last heartbeat timestamp
- Charging sessions
- Metering data
- Faults and errors
- Device information


