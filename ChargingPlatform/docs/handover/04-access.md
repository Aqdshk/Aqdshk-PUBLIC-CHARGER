# 04 — Access

**No passwords, keys or tokens are written in this file, and none should
ever be added to it.** This repository is shared and versioned: a secret
committed here is a secret published, and rewriting git history does not
reliably take it back. The actual values are handed over separately — see
"Getting the secrets" at the bottom.

What this file gives you is the list of what exists, and how to get your
own access to each of it.

## The principle

Where there is a choice, **Aina gets her own credential, not Aqid's.**

A shared login cannot be revoked for one person, cannot be audited, and
turns "who changed this?" into a question nobody can answer. Every system
below supports a second account. Use that.

## 1. SSH to the VPS

The server is `203.99.148.43`, user `plagsini`. **Root login over SSH is
disabled** and should stay that way.

### Generate your key, on your own laptop

The private key must never leave the machine that made it. Do not let
anyone send you a private key, including Aqid.

```powershell
ssh-keygen -t ed25519 -C "aina@plagsini" -f $env:USERPROFILE\.ssh\id_ed25519_plagsini
```

Press Enter twice for no passphrase, or set one — better, and you will be
asked for it once per session.

Then send **only the `.pub` file** to Aqid, by any channel. A public key is
not a secret:

```powershell
Get-Content $env:USERPROFILE\.ssh\id_ed25519_plagsini.pub
```

### What Aqid does with it, once

```bash
# as plagsini on the VPS
echo "<the public key line Aina sent>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Better, if Aina is taking the system over rather than sharing it — give her
a user of her own, so the logs name her:

```bash
sudo adduser --disabled-password --gecos "" aina
sudo usermod -aG sudo,docker aina
sudo mkdir -p /home/aina/.ssh
echo "<public key>" | sudo tee /home/aina/.ssh/authorized_keys
sudo chown -R aina:aina /home/aina/.ssh
sudo chmod 700 /home/aina/.ssh && sudo chmod 600 /home/aina/.ssh/authorized_keys
```

### Then, on Aina's laptop

Add to `%USERPROFILE%\.ssh\config` so `ssh plagsini` just works:

```
Host plagsini
    HostName 203.99.148.43
    User plagsini
    IdentityFile ~/.ssh/id_ed25519_plagsini
    ServerAliveInterval 30
```

Test:

```powershell
ssh plagsini 'whoami; hostname; sudo docker ps --format "{{.Names}}" | head'
```

If that prints container names, you are in.

> The server is also reachable as `charger.czeros.tech`, which is the same
> machine. Either works.

## 2. The dashboard (staff login)

<https://charger.czeros.tech> — this is where the day-to-day work happens.

Two staff accounts exist today, both with the `admin` role:

| Account | |
|---|---|
| `admin@plagsini.com` | the original |
| `staff@plagsini.com` | second admin |

**Create one for Aina** rather than sharing either. From the dashboard:
**Administration → Staff Management → Add staff**, role `admin`.

Roles are `admin` and `manager`. `manager` can start and stop charges but
not reach the admin APIs. Most endpoints in `api.py` are guarded by
`require_admin_or_staff_admin`.

Sessions are rows in `staff_sessions` and the browser holds a token in
`localStorage` as `staffToken`, sent as the `X-Staff-Token` header. That is
why API endpoints cannot be opened by pasting a URL into a browser: there
is no cookie, by design, so a token never lands in a server log or in
browser history.

## 3. Grafana

<https://charger.czeros.tech/monitoring/>

Has its own login, separate from the dashboard. Ask Aqid to create a second
admin user: **Administration → Users → Invite**.

## 4. GitHub

Repository: `Aqdshk/Aqdshk-PUBLIC-CHARGER`.

Aina needs **write access** to push branches, and that is all — deploys run
from the Actions tab. Aqid adds her under Settings → Collaborators.

Install the CLI and authenticate as herself:

```powershell
winget install GitHub.cli
gh auth login
```

The deploy workflow uses repository **secrets** (`VPS_HOST`, `VPS_PORT`,
and the deploy SSH key). Those stay as they are; nobody needs to see them
to run a deploy.

## 5. The database

MySQL 8 in `charging-platform-mysql`, bound to `127.0.0.1:3307` so it is
**not reachable from the internet**. Keep it that way.

Day to day you do not need the password: the app's own shell is easier and
safer.

```bash
ssh plagsini 'sudo docker exec -w /app -it plagsini-api python'
>>> from database import SessionLocal, Charger
>>> db = SessionLocal()
>>> db.query(Charger).count()
```

The root password is only needed for restores. It is in the handover set.

## 6. Everything else that has a credential

These exist and are in the handover set. None of them is needed on day one,
but you will meet them:

| What | Why it exists |
|---|---|
| Domain registrar / DNS | `czeros.tech`, `plagsini.com`, `c-zero.com.my` |
| VPS provider panel | Reboots, console access, billing |
| Telegram bot token | Alerts from Grafana and the watchdog |
| rclone / Google Drive | Where the nightly database backup goes |
| SMTP | OTP emails and charging receipts |
| Payment gateway | Live keys. Treat as money |
| OCPI partner tokens | In `ocpi_partners` in the database, not in a file |
| OCPP charger tokens | Env vars on the container |

### A note on the OCPI tokens

They live in the `ocpi_partners` table, two columns: `token` is what we
present when we call a partner, `token_inbound` is what they present to us.
They are secrets and must never be logged in full. There are two partner
rows for Voltality, one UAT and one production — see
[06 — Who to talk to](06-contacts.md).

## Getting the secrets

Ask Aqid to hand over the credential set through a **password manager
share** (Bitwarden, 1Password, or an encrypted file sent over a different
channel than the password to open it). Not WhatsApp, not email, not a file
in this repository.

When you have them, change what you can:

- [ ] Your own SSH key added, and Aqid's removed if he is leaving
- [ ] Your own staff account on the dashboard
- [ ] Your own Grafana user
- [ ] Your own GitHub account with write access
- [ ] Rotate anything shared that Aqid no longer needs

## Known security decisions, taken deliberately

You will find these and wonder. They are choices, not oversights, and
changing them has a cost:

| | Why |
|---|---|
| Port **8000** is open to the internet | Some chargers can only fetch firmware over plain HTTP. Closing it breaks firmware updates on that hardware |
| Port **9000** is plain WebSocket | Chargers that cannot do TLS connect there |
| `/api/chargers` answers **unauthenticated** | The login page uses it for a count. It redacts vendor, model, firmware, heartbeat and connection state for anonymous callers, but still exposes 493 charger ids, tenants, tariffs and coordinates. **This is on the list to fix and is not fixed.** |
| `/api/chargers/{id}/configuration` is unauthenticated | Left as-is deliberately for now |
| A BootNotification creates a charger with no approval | Mitigated by new chargers being created hidden |

The first two are permanent until the hardware changes. The third is
genuine unfinished work and the most worthwhile security task on the list.
