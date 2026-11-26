# 03 — Operations

## Deploying

**Every project here deploys through GitHub Actions. Never by hand.**
Pulling the repository on the VPS changes nothing, because production runs
a *built image*, not the working tree. A `git pull` with no rebuild is the
classic way to convince yourself you have deployed something you have not.

```powershell
gh workflow run deploy.yml -f ref=<branch>
```

| Input | When to tick it |
|---|---|
| `ref` | The branch to deploy. **Always `-f ref=...`, never `--ref`** |
| `run_migrations` | The commit adds a file in `migrations/versions/` |
| `rebuild_appev` | You changed the Flutter app under `AppEV/` |
| `skip_tests` | Emergency only. You are saying out loud that you are shipping untested code |

> **`--ref` does not do what it looks like.** `gh workflow run --ref <branch>`
> selects which branch's *workflow file* to run, and the workflow then
> deploys whatever its own `ref` input says, which defaults to `main`. Pass
> the branch as an **input**: `-f ref=my-branch`. Use a branch name, not a
> commit SHA.

### What the deploy actually does

1. Waits for the CI gate (`test.yml`: syntax, import canary, pytest)
2. SSHes to the VPS, checks out the ref in `/opt/plagsini-ev`
3. `docker compose build` for changed services
4. If `run_migrations`: `alembic upgrade head` against the **new** image,
   before swapping the running container, so the app never starts against a
   schema it does not expect
5. `docker compose up -d --force-recreate`
6. Compares the running image against the built one and fails if they differ

### After every deploy, verify it landed

A green workflow is not proof. This has lied before.

```bash
ssh plagsini 'cd /opt/plagsini-ev && sudo git log --oneline -1'
ssh plagsini 'sudo docker ps --format "{{.Names}}\t{{.Status}}" | grep plagsini-api'
ssh plagsini 'curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health'
```

The container's `Status` should read "Up <seconds>", not hours. If it says
hours, nothing restarted and your change is not live.

For a code change, confirm the code is *inside* the container:

```bash
ssh plagsini 'sudo docker exec plagsini-api grep -c "<something you added>" api.py'
```

### Before you deploy at all

- `python -m pytest tests/ -q` locally. 400 passing
- Check `/sessions` for an **active** row. A deploy restarts the API and an
  in-flight charge can be marked interrupted
- If a partner is testing, ask first

## Backups

`/opt/plagsini-ev/scripts/mysql-backup.sh`, by root cron at **18:30 UTC
daily** (02:30 MYT).

- Dumps `charging_platform`, gzips it to `/opt/backups/mysql/`
- Uploads to Google Drive via rclone: `gdrive:PlagSiniBackups/daily/YYYY/MM/`
- Keeps 7 days locally; the cloud copy is the long tail
- Logs to `/var/log/plagsini-backup.log`

Check it is alive:

```bash
ssh plagsini 'sudo tail -5 /var/log/plagsini-backup.log; sudo ls -la /opt/backups/mysql | tail -3'
```

A dump is roughly 700 KB and grows slowly. If it stops growing, something
is wrong with the dump, not with the business.

> **There is a stale copy at `/opt/backups/mysql-backup.sh`.** It has a
> hardcoded root password and references a container name that no longer
> exists (`plagsini-mysql`; the real one is `charging-platform-mysql`).
> Cron does not run it. Do not be misled by it, and it would be a good
> small task to delete it.

### Restoring

```bash
# On the VPS, as a test first — never straight over production
gunzip -c /opt/backups/mysql/charging_platform_YYYYMMDD_HHMMSS.sql.gz \
  | sudo docker exec -i charging-platform-mysql mysql -u root -p'<root pw>' charging_platform
```

Take a fresh dump before restoring over anything.

## The other scheduled jobs

```
0  3 * * *   certbot renew && nginx -s reload      TLS certificates
30 18 * * *  mysql-backup.sh                        the database
0  0 * * *   plagsini-daily.sh                      daily summary to Telegram
*/10 * * * * plagsini-watch.sh                      health watchdog
0  4 * * 0   docker builder prune                   weekly disk reclaim
```

`plagsini-watch.sh` runs every ten minutes and is what notices the API is
down before a customer does.

## Monitoring

| What | Where |
|---|---|
| Dashboards and alerts | <https://charger.czeros.tech/monitoring/> (Grafana) |
| Logs, 30 days | Loki, through Grafana's Explore |
| Alerts | Telegram, from Grafana and from `plagsini-watch.sh` |
| Health endpoint | `https://charger.czeros.tech/health` |

Loki caps queries at 30 days. Anything older has to come from the database.

Reading container logs directly:

```bash
ssh plagsini 'sudo docker logs plagsini-api --since 30m'
ssh plagsini 'sudo docker logs plagsini-api --since 1h | grep -i error'
```

## Runbooks

### The API is down

```bash
ssh plagsini 'sudo docker ps -a --format "{{.Names}}\t{{.Status}}" | grep plagsini-api'
ssh plagsini 'sudo docker logs plagsini-api --tail 80'
```

Common causes, in the order they have actually happened:

1. **A migration that did not run.** The app starts against a schema it
   does not expect and dies on the first query. Fix: run the migration.
2. **Disk full.** Five products and their backups share this machine.
   `df -h`, then `docker builder prune -af`.
3. **MySQL not ready.** The API restarts until it is. Give it a minute.

Restart: `ssh plagsini 'cd /opt/plagsini-ev && sudo docker compose -f docker-compose.prod.yml restart charging-platform'`

### A charger shows offline but the operator says it is powered

1. Chargers → ... → **Connectivity log**. Look at the close codes.
2. Close **1006** repeatedly is a weak link, usually a SIM. Not our bug.
3. No events at all means it never reached us: check the charger's
   configured CSMS URL and its token.
4. "Online" is `last_heartbeat` being recent. A charger can hold a socket
   open and stop sending heartbeats; the state healer catches that.

### A session is stuck "active" and the car has gone

The orphan-session watchdog closes stale sessions automatically. If one
survives, it is usually because meter values kept arriving. Check
`/metering` for that charger before touching anything, then close it from
the dashboard rather than with SQL.

### A partner says a command did nothing

Read the OCPP exchange after our RemoteStart, not the OCPI reply. ACCEPTED
means the charger took the instruction, not that a car charged. See
[02 — How OCPP works](02-ocpp.md).

### Writing to the production database

Don't, unless there is no endpoint that does it. If you must:

1. Take a backup first
2. Write a script, read it twice, and print the rows **before and after**
3. Beware MySQL's default REPEATABLE READ isolation: a session that has
   already read a row keeps seeing the old value for the rest of its
   transaction. Verify from a **fresh connection** or you will believe a
   write failed when it worked

## Certificates

Certbot renews at 03:00 daily and reloads nginx. Certificates cover
`charger.czeros.tech` and the four other domains. If a renewal fails you
will hear about it from a browser warning first, so check the certbot timer
occasionally: `ssh plagsini 'systemctl list-timers certbot.timer'`.

## Editing nginx

Config is at `/etc/nginx/sites-enabled/`. Two warnings learned the hard way:

- **A backup file must not stay in `sites-enabled/`.** nginx loads every
  file in that directory, so `default.bak` is a second live config. Copy
  backups somewhere else entirely.
- **The files are not plain UTF-8.** Rewriting one with a naive script can
  corrupt it. Edit in place, and always `sudo nginx -t` before reloading.

```bash
sudo nginx -t && sudo nginx -s reload
```
