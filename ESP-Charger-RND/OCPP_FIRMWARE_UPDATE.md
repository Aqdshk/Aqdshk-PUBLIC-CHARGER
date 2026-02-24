# OCPP Firmware Update via SteVe

ESP32 EV Charger sekarang support **OCPP Firmware Management** - kau boleh update firmware dari **SteVe OCPP server** menggunakan standard OCPP 1.6J `UpdateFirmware` command.

## Cara Guna OCPP Firmware Update

### 1. Setup Firmware URL dalam SteVe

Dalam SteVe OCPP backend, kau boleh trigger firmware update dengan:

1. **Upload firmware file** ke web server (HTTP/HTTPS accessible)
   - Contoh: `http://your-server.com/firmware/esp32-ev-charger-v1.2.0.bin`
   - Atau: `https://github.com/your-repo/releases/download/v1.2.0/firmware.bin`

2. **Send UpdateFirmware command** dari SteVe ke charge point:
   ```json
   {
     "location": "http://your-server.com/firmware/esp32-ev-charger-v1.2.0.bin",
     "retrieveDate": "2024-01-15T10:00:00.000Z",
     "retries": 3,
     "retryInterval": 180
   }
   ```

### 2. How It Works

1. **SteVe sends UpdateFirmware** → ESP32 receives via WebSocket
2. **ESP32 downloads firmware** dari URL yang diberikan (HTTP download)
3. **Progress reported** via `FirmwareStatusNotification` ke SteVe
4. **Install firmware** → ESP32 restart dengan firmware baru

### 3. Firmware Update Flow

```
UpdateFirmware Command (from SteVe)
    ↓
ESP32 starts download from URL
    ↓
FirmwareStatusNotification: Downloading (with progress)
    ↓
FirmwareStatusNotification: Downloaded
    ↓
ESP32 installs firmware
    ↓
ESP32 restarts with new firmware
    ↓
FirmwareStatusNotification: Installed
```

### 4. Requirements

- ✅ **WiFi connected** (untuk download firmware)
- ✅ **OCPP connected** ke SteVe (untuk receive command)
- ✅ **Firmware URL accessible** (HTTP/HTTPS)
- ✅ **Sufficient flash memory** untuk firmware baru

### 5. Status Notifications

ESP32 akan automatically send `FirmwareStatusNotification` ke SteVe dengan status:

- **Downloading** - Firmware sedang download
- **Downloaded** - Download complete
- **Installing** - Firmware sedang install
- **Installed** - Install successful, restart pending
- **DownloadFailed** - Download failed
- **InstallationFailed** - Installation failed

### 6. Serial Monitor Output

Semasa firmware update, kau akan nampak output macam ni:

```
[FW-OCPP] Starting firmware download from: http://your-server.com/firmware.bin
[FW-OCPP] Firmware size: 1234567 bytes
[FW-OCPP] Downloading firmware...
[FW-OCPP] Progress: 10%
[FW-OCPP] Progress: 20%
...
[FW-OCPP] Progress: 100%
[FW-OCPP] Firmware download completed successfully
[FW-OCPP] Installing firmware...
[FW-OCPP] Firmware ready, restarting ESP32 in 2 seconds...
```

## Comparison: OCPP Update vs ArduinoOTA

| Feature | OCPP Update | ArduinoOTA |
|---------|-------------|------------|
| **Trigger** | From SteVe server | From PlatformIO/Arduino IDE |
| **Protocol** | OCPP 1.6J UpdateFirmware | ArduinoOTA (port 3232) |
| **URL Source** | SteVe provides URL | Manual IP address |
| **Status Reporting** | Automatic to SteVe | Local only |
| **Use Case** | Production, remote management | Development, local update |

## Notes

- **OCPP firmware update** akan **stop charging** semasa update (safety)
- **Download timeout**: 60 seconds
- **Auto-restart** selepas installation complete
- **Fail-safe**: Kalau update fail, ESP32 akan restart dengan firmware lama

## Troubleshooting

### UpdateFirmware Command Rejected
- Check charge point **online** dalam SteVe
- Check charge point support **FirmwareManagement** feature
- Check firmware URL **accessible** dari ESP32 network

### Download Failed
- Check firmware URL **betul** dan accessible
- Check **WiFi connection** stable
- Check **flash memory** cukup untuk firmware baru
- Check **HTTP timeout** (default 60s)

### Installation Failed
- Check firmware file **valid** untuk ESP32
- Check firmware file **size** tidak exceed flash memory
- Check firmware **compatible** dengan hardware

---

**Summary**: OCPP Firmware Update membolehkan kau manage firmware updates secara remote dari SteVe backend, perfect untuk production deployment tanpa perlu physical access ke charger.







