# OTA (Over-The-Air) Update Guide

ESP32 EV Charger sekarang support **OTA (Over-The-Air) firmware update**, jadi kau boleh update firmware tanpa perlu sambung USB cable.

## Cara Guna OTA Update

### 1. First Upload (via USB)
Untuk kali pertama, kau masih perlu upload firmware via USB untuk enable OTA:
```bash
pio run -t upload -e esp32dev
```

### 2. Get IP Address
Selepas ESP32 connect ke WiFi, check Serial Monitor untuk IP address:
```
[OCPP] WiFi connected, IP: 192.168.1.100
[OTA] Ready for OTA updates | IP address: ESP32-EV-Charger
```

### 3. Upload via OTA (PlatformIO)

#### Option A: Command Line dengan IP Address
```bash
pio run -t upload -e esp32dev --upload-port 192.168.1.100
```
Gantikan `192.168.1.100` dengan IP address ESP32 kamu.

#### Option B: Arduino IDE
1. Buka Arduino IDE
2. Tools > Port > Network Ports
3. Pilih "ESP32 at 192.168.1.100" (atau IP address kamu)
4. Upload seperti biasa

### 4. OTA Password (Optional)
Untuk security, kau boleh set password dalam `src/main.cpp`:
```cpp
OtaManager::begin("ESP32-EV-Charger", "your_ota_password");
```

Kalau ada password, Arduino IDE akan prompt untuk password sebelum upload.

## Notes

- **OTA hanya berfungsi bila ESP32 connect ke WiFi**
- **Serial Monitor akan show progress** semasa OTA update (0%, 10%, 20%, ...)
- **ESP32 akan auto-restart** selepas update complete
- **Kalau update fail**, ESP32 akan restart dan guna firmware lama (fail-safe)

## Troubleshooting

### OTA Upload Failed / Connection Timeout
1. Check ESP32 IP address betul ke tidak (check Serial Monitor)
2. Pastikan komputer dan ESP32 dalam **network yang sama** (WiFi yang sama)
3. Check firewall tidak block port 3232 (default ArduinoOTA port)
4. Try disable password kalau ada masalah connection

### OTA Not Available
- Pastikan WiFi dah connected (check Serial Monitor)
- Pastikan OTA dah initialize (look for `[OTA] Ready for OTA updates` in Serial Monitor)

### Update Fail / Corrupted
- Pastikan firmware file betul
- Try upload via USB sekali untuk reset
- Check ESP32 flash size cukup untuk firmware baru







