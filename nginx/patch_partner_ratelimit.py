#!/usr/bin/env python3
"""Add a dedicated rate-limit bucket for /api/partner/* to the live nginx config.

Why: limit_req_zone keys on $binary_remote_addr, i.e. per IP. A partner backend
(HICOM PWA) fronts many end users from ONE IP, so the shared api_limit of
120 r/m throttles that entire tenant. This adds partner_limit (600 r/m,
burst 100) and routes /api/partner/* to it. Additive only: no existing zone or
location is modified.
"""
import sys

PATH = "/etc/nginx/sites-enabled/default"

src = open(PATH).read()

if "partner_limit" in src:
    print("ALREADY PATCHED - no change made")
    sys.exit(0)

zone_anchor = "limit_req_zone $binary_remote_addr zone=monitoring_limit:10m rate=600r/m;"
if zone_anchor not in src:
    print("FAIL: monitoring zone anchor not found")
    sys.exit(1)

new_zone = zone_anchor + """
# Partner server-to-server API. One partner backend fronts many end users from
# a SINGLE IP, so api_limit (120r/m) would throttle a whole tenant at once.
# Roomier bucket; real auth is X-Partner-API-Key + tenant guard in api.py.
limit_req_zone $binary_remote_addr zone=partner_limit:10m rate=600r/m;"""
src = src.replace(zone_anchor, new_zone, 1)

loc_anchor = "    location ^~ /api/bot/ {"
if loc_anchor not in src:
    print("FAIL: bot location anchor not found")
    sys.exit(1)

new_loc = """    # Partner server-to-server API -> ChargingPlatform (8000).
    # ^~ so it wins over the /api/(auth|...) regex and the general / prefix.
    location ^~ /api/partner/ {
        limit_req zone=partner_limit burst=100 nodelay;
        limit_req_status 429;
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_intercept_errors on;
    }

"""
src = src.replace(loc_anchor, new_loc + loc_anchor, 1)

open(PATH, "w").write(src)
print("PATCHED OK")
