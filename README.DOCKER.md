# Docker Setup

## Quick Start

```bash
# Build images
make build

# Start services
make up

# View logs
make logs

# Stop services
make down
```

## Access Services

- **AppEV**: http://localhost:3000
- **ChargingPlatform API**: http://localhost:8000
- **OCPP Server**: ws://localhost:9000

## Services

### charging-platform
- Backend API + OCPP Server
- Ports: 8000 (API), 9000 (OCPP)
- Database: Persistent volume

### appev
- Flutter Web Frontend
- Port: 3000
- Proxies API calls to charging-platform

## Connect Charger

Configure your charger to connect to:
```
ws://YOUR_SERVER_IP:9000/{charge_point_id}
```

Example:
```
ws://192.168.1.100:9000/0748911403000154
```

## Commands

```bash
make build    # Build images
make up       # Start services
make down     # Stop services
make logs     # View logs
make restart  # Restart services
make clean    # Remove everything
```

## Troubleshooting

**Port already in use:**
Edit `docker-compose.yml` and change ports

**Services won't start:**
```bash
make logs
docker-compose ps
```

**Reset everything:**
```bash
make clean
make build
make up
```
