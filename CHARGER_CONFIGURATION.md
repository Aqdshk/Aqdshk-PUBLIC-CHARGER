# Charger Configuration Guide

## Current Configuration (SteVe OCPP Server)

Berdasarkan charger configuration screen anda:

### SteVe OCPP Server Settings:
```
Server Address: 34.16.91.156
Port Number: 8080
URL Path: /steve/websocket/CentralSystemService/0748911403000085
Charger ID: 0748911403000085
Service Type: WS (WebSocket)
```

**Full WebSocket URL:**
```
ws://34.16.91.156:8080/steve/websocket/CentralSystemService/0748911403000085
```

---

## Configuration untuk ChargingPlatform (Local)

Jika anda nak connect charger ke ChargingPlatform yang kita dah setup:

### Option 1: Connect ke Local ChargingPlatform (Development)

**Jika charger dan ChargingPlatform dalam network yang sama:**

```
Server Address: YOUR_LOCAL_IP (contoh: 192.168.1.100)
Port Number: 9000
URL Path: /0748911403000085
Charger ID: 0748911403000085
Service Type: WS (WebSocket)
```

**Full WebSocket URL:**
```
ws://YOUR_LOCAL_IP:9000/0748911403000085
```

**Cara dapatkan local IP:**
- Windows: `ipconfig` → cari IPv4 Address
- Linux/Mac: `ifconfig` atau `ip addr`

### Option 2: Connect ke ChargingPlatform di Server (Production)

**Jika ChargingPlatform deploy di server:**

```
Server Address: YOUR_SERVER_IP (contoh: 34.16.91.156)
Port Number: 9000
URL Path: /0748911403000085
Charger ID: 0748911403000085
Service Type: WS (WebSocket)
```

**Full WebSocket URL:**
```
ws://YOUR_SERVER_IP:9000/0748911403000085
```

---

## Perbezaan SteVe vs ChargingPlatform

### SteVe OCPP Server:
- URL format: `/steve/websocket/CentralSystemService/{charge_point_id}`
- Port: 8080
- Full path dalam URL

### ChargingPlatform (Kita):
- URL format: `/{charge_point_id}` (lebih simple)
- Port: 9000
- Direct charge_point_id dalam path

---

## Recommended Configuration

### Untuk Development (Local Testing):

```
Server Address: [Your Local IP]
Port Number: 9000
URL Path: /0748911403000085
Charger ID: 0748911403000085
Service Type: WS
```

**Example dengan IP 192.168.1.100:**
```
ws://192.168.1.100:9000/0748911403000085
```

### Untuk Production (Deploy di Server):

```
Server Address: 34.16.91.156 (atau server IP anda)
Port Number: 9000
URL Path: /0748911403000085
Charger ID: 0748911403000085
Service Type: WS
```

**Example:**
```
ws://34.16.91.156:9000/0748911403000085
```

---

## Testing Connection

### 1. Pastikan ChargingPlatform Running

```bash
# Check jika running
docker-compose ps

# View logs
docker-compose logs -f charging-platform
```

### 2. Configure Charger

Update charger configuration dengan settings di atas.

### 3. Verify Connection

Bila charger connect, anda akan nampak dalam logs:

```
🔌 New OCPP connection from charge point: 0748911403000085
✅ Charge point 0748911403000085 registered. Total active connections: 1
```

### 4. Check Dashboard

Buka http://localhost:8000 dan verify charger muncul dalam list.

---

## Important Notes

1. **Charger ID**: Mesti match dengan `charge_point_id` dalam URL
2. **Port**: ChargingPlatform guna port 9000 (bukan 8080)
3. **URL Path**: Simple format `/{charge_point_id}` (tak perlu `/steve/websocket/CentralSystemService/`)
4. **Service Type**: WS untuk development, WSS untuk production (jika ada SSL)

---

## Troubleshooting

### Charger Tak Connect?

1. **Check ChargingPlatform running:**
   ```bash
   docker-compose ps
   docker-compose logs charging-platform
   ```

2. **Check port accessible:**
   ```bash
   netstat -ano | findstr ":9000"
   ```

3. **Check firewall:**
   - Pastikan port 9000 open
   - Check Windows Firewall settings

4. **Verify IP address:**
   - Pastikan IP betul (local atau server)
   - Test connectivity: `ping YOUR_IP`

5. **Check charger logs:**
   - View charger serial output/logs
   - Look for connection errors

### Connection Timeout?

- Verify ChargingPlatform accessible dari charger network
- Check firewall rules
- Verify port forwarding (jika perlu)

---

## Quick Reference

### SteVe (Current):
```
ws://34.16.91.156:8080/steve/websocket/CentralSystemService/0748911403000085
```

### ChargingPlatform (Local):
```
ws://YOUR_LOCAL_IP:9000/0748911403000085
```

### ChargingPlatform (Server):
```
ws://YOUR_SERVER_IP:9000/0748911403000085
```
