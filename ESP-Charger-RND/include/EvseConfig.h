/**
 * EV Charger runtime config
 * Edit values below for your WiFi and ChargingPlatform server.
 * Copy from EvseConfig.h.example if this file is missing.
 */
#ifndef EVSE_CONFIG_H
#define EVSE_CONFIG_H

#define EV_WIFI_SSID       "MESRA DECO"
#define EV_WIFI_PASSWORD   "mesb1234"
#define EV_OCPP_HOST       "192.168.4.112"
#define EV_OCPP_PORT       9000
#define EV_OCPP_USE_TLS    0
#define EV_OCPP_PATH_PREFIX ""
#define EV_OCPP_TOKEN      "9aq6hNtYBW6_XErEoubpZFsgwv45LaUU"
#define EV_CHARGE_POINT_ID "ESP32-CP-01"
#define EV_BUTTON_IDTAG    "BUTTON001"

#endif
