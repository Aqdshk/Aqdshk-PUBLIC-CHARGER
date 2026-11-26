# 08 — Secrets inventory

**This file contains no secret values and must never be given any.** It is
the map: what secrets exist, where each one lives, and how to read it when
you need it.

A list of copied passwords goes stale the moment one is rotated, and a copy
in a repository is a copy that leaks. The server is the single source of
truth for most of this, and once Aina has SSH she can read any of it
herself.

## The main store: `/opt/plagsini-ev/.env`

Every secret the API uses is here, injected into the container by
docker compose. To read one:

```bash
ssh plagsini 'sudo grep "^JWT_SECRET_KEY=" /opt/plagsini-ev/.env'
```

To list the names without the values:

```bash
ssh plagsini 'sudo grep -oE "^[A-Z_]+=" /opt/plagsini-ev/.env | sed "s/=$//" | sort'
```

### What is in there

| Variable | What it opens | Notes |
|---|---|---|
| `JWT_SECRET_KEY` | Signs every auth token | Rotating it logs everybody out. No default: the app refuses to start without it |
| `MYSQL_ROOT_PASSWORD` | Database root | Needed for restores |
| `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` | The app's database login | |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Bootstrap admin, created only if no admin exists | Not a live login once staff accounts exist |
| `STAFF_EMAIL` / `STAFF_NAME` / `STAFF_PASSWORD` | Bootstrap staff account | Same |
| `GRAFANA_USER` / `GRAFANA_PASSWORD` | Grafana admin | |
| `DOCS_USER` / `DOCS_PASS` | Basic auth on the API docs page | |
| `OCPI_TOKEN` | The shared inbound OCPI token | Anonymous: identifies nobody. Per-partner tokens live in the database |
| `OCPP_SHARED_TOKEN` / `OCPP_CHARGER_TOKENS` | What a charger presents to connect | `OCPP_CHARGER_TOKENS` is a `CP1:token1,CP2:token2` map |
| `PARTNER_API_KEY` / `PARTNER_NAME` | The partner API (separate from OCPI) | |
| `PAYMENT_TNG_*`, `PAYMENT_FIUU_*`, `PAYMENT_BILLPLZ_*`, `PAYMENT_OCBC_*` | Payment gateways | **Live keys. These move money** |
| `PAYMENT_CALLBACK_SECRET` | Verifies gateway callbacks | |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_EMAIL` / `SMTP_PASSWORD` | OTP emails and receipts | |
| `GEMINI_API_KEY` | The support chatbot | |
| `OCPI_*` location and party settings | Our CPO identity and default address | Not secret, but configuration you will want |

## Secrets that are **not** in that file

| What | Where it actually lives |
|---|---|
| **OCPI partner tokens** | `ocpi_partners` table. `token` is what we present to them, `token_inbound` is what they present to us. Two rows: SG/VLT live, SG/VOL UAT |
| **Staff passwords** | Hashed in `support_staff`. Not recoverable — reset, don't retrieve |
| **SSH access** | `~/.ssh/authorized_keys` on the VPS. Public keys only; private keys never leave the laptop that made them |
| **GitHub Actions deploy key** | Repository → Settings → Secrets (`VPS_HOST`, `VPS_PORT`, the SSH key). Write-only in the UI: you can replace them, not read them |
| **rclone / Google Drive** | `~/.config/rclone/rclone.conf` on the VPS. This is what the nightly backup uploads with |
| **Telegram bot token** | In the Grafana alert configuration and the watchdog script |
| **Domain registrar, VPS panel** | Outside this system entirely. Aqid has to hand these over personally |

## Reading a secret from the database

```bash
ssh plagsini 'sudo docker exec -w /app -it plagsini-api python'
```
```python
from database import SessionLocal, OcpiPartner
db = SessionLocal()
for p in db.query(OcpiPartner).all():
    print(p.country_code, p.party_id, p.versions_url)
    # p.token and p.token_inbound are the secrets — print only if you need them
```

## What Aqid still has to hand over personally

These cannot be read off the server and have to come from him, through a
password manager share, not WhatsApp:

- [ ] Domain registrar logins (`czeros.tech`, `plagsini.com`, `c-zero.com.my`)
- [ ] VPS provider panel (reboots, console, billing)
- [ ] Google account behind the Drive backups
- [ ] Payment gateway merchant portals (as opposed to the API keys, which are on the server)
- [ ] Telegram bot ownership
- [ ] Anything billed to a personal card

## When Aqid hands over for good

In this order:

1. Aina's SSH key added and tested
2. Aina's own staff, Grafana and GitHub accounts created and tested
3. Rotate: `JWT_SECRET_KEY` (logs everyone out, do it at a quiet hour),
   Grafana admin, `DOCS_PASS`
4. Rotate the payment gateway keys through each provider's portal
5. Remove Aqid's SSH key from `authorized_keys`
6. Remove him as a GitHub collaborator

Do not rotate `OCPP_SHARED_TOKEN` or `OCPP_CHARGER_TOKENS` casually: every
charger in the field is configured with one, and changing it takes them all
offline until each is reconfigured.

Do not rotate OCPI partner tokens without telling Venu first. That is a
credentials handshake with another company, and getting it wrong stops
Touch 'n Go customers from charging.
