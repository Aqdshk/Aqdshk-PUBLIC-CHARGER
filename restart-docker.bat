@echo off
REM Restart Docker - guna code dan .env terbaru
echo Restarting Docker...
cd /d "%~dp0"

docker compose down
docker compose up -d

echo.
echo Done. ChargingPlatform running on http://localhost:8000
echo OCPP WebSocket on ws://localhost:9000
pause
