# PlagSini EV — Handover

Written for Aina, 26 November 2026.

This is everything needed to run the PlagSini EV charging platform without
asking Aqid. Read it in order the first time. After that it is reference.

| | |
|---|---|
| [01 — Architecture](01-architecture.md) | What the system is made of and how a request travels through it |
| [02 — How OCPP works](02-ocpp.md) | The protocol the chargers speak, and what our server does with it |
| [03 — Operations](03-operations.md) | Deploying, backups, monitoring, and what to do when something breaks |
| [04 — Access](04-access.md) | Getting your own keys and logins. **Do this first.** |
| [05 — What will bite you](05-gotchas.md) | Things that have already gone wrong once |
| [06 — Who to talk to](06-contacts.md) | Partners, vendors, and what is still outstanding |
| [07 — Local setup](07-local-setup.md) | Getting the code running on your own laptop |
| [08 — Secrets inventory](08-secrets-inventory.md) | What exists and where to read it. No values, by design |

## What this platform is

A CSMS: a Charging Station Management System. Charge points around Malaysia
connect to it over the internet and it decides what they do. It bills the
driver, it answers roaming partners who send their customers to our
chargers, and it gives the operator a dashboard to watch all of it.

It is live and it takes real money. On any given day a driver is plugged
into DC3001 in Shah Alam and a Touch 'n Go customer may be starting a
charge through Voltality's app.

## The first hour

1. Work through **[04 — Access](04-access.md)**. You need an SSH key on the
   server and a staff login to the dashboard before anything else is useful.
2. Open <https://charger.czeros.tech> and sign in. Click through Dashboard,
   Chargers, Sessions, Invoice. That is the operator's whole world.
3. Clone the repository and run the test suite locally:

   ```
   cd ChargingPlatform
   python -m pytest tests/ -q
   ```

   It should say 400 passed. If it does not, stop and find out why before
   you change anything.
4. Read **[05 — What will bite you](05-gotchas.md)**. It is short and every
   line in it cost someone a day.

## The one rule

**Production is live and it bills people.** Three things follow from that:

- Never deploy while a partner is testing or a car is charging. A deploy
  restarts the API container, and a session in flight can be marked
  interrupted. Check `/sessions` for an active row first.
- Never change a price, a tariff or an idle fee without knowing that past
  sessions are frozen and will not move. They are. See
  [05 — What will bite you](05-gotchas.md).
- The test suite is not decoration. It encodes bugs that reached customers.
  Run it before every deploy.

## Where the truth lives

Documentation goes stale. These do not:

| Question | Ask this, not a document |
|---|---|
| What is deployed right now? | `ssh plagsini 'cd /opt/plagsini-ev && sudo git log --oneline -1'` |
| What is running? | `ssh plagsini 'sudo docker ps'` |
| What does this endpoint return? | <https://charger.czeros.tech/docs> (FastAPI's own, live) |
| What does the schema look like? | `ChargingPlatform/database.py` — the models are the schema |
| Why is this code like this? | `git log -p <file>`. The commit messages explain the reasoning, not just the change |

If this documentation and the system disagree, the system is right and the
documentation is a bug. Fix it.
