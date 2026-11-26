# 05 — What will bite you

Every item here has already cost someone a day, or reached a customer.
None of it is guessable from reading the code.

## Money and history

### Past invoices must reproduce exactly, and the code enforces it

A `charging_sessions` row freezes what it was sold at:

- `tariff_per_kwh_at_start` and the idle-fee columns — the prices, frozen
  when the session started (since 12 November 2026)
- `tenant_at_start` — the fleet it belonged to, frozen the same way
  (since 26 November 2026, backfilled over all 594 rows while nothing had
  yet moved, so the backfill is exact)

So you can change a charger's tariff, change the idle fee, or move a
charger to a different fleet, and **every past session keeps its own
figures**. Re-running last month's invoice returns last month's numbers.

Before the tenant freeze, moving a charger between fleets carried all of
its past sessions with it: October's report for one fleet went to zero and
another fleet gained money it never earned. Do not undo this.

Sessions older than 12 November 2026 have no frozen rate and fall back to
the charger's current tariff. They will move if you change it. There are
not many and nothing can be done about it now.

### Never reintroduce a flat platform rate

Both `/analytics` and `/invoice` used to compute revenue as
`energy × price_per_kwh`, where the rate came from the `pricing` table and
fell back to **RM0.50** when it was empty. That table has never had a row.
DC3001 sells at RM1.40, the Proton and Perodua fleets at RM0.10, and idle
fees were not counted at all. November 2026 displayed RM106.97 and was
actually RM435.07.

Revenue is now per session: `api._session_money()` and
`api._session_revenue_sql()`. If you find yourself writing a single
RM/kWh figure, stop.

### A fleet report is not an invoice

| | |
|---|---|
| **Fleet report** (`tenant=`) | Every charge on that fleet's chargers, walk-ins and app users included. Internal P&L |
| **Roaming settlement** (`party_id=`) | Only the charges one partner sent us, and only those whose CDR we released. This is what a partner can reconcile |

November 2026: the `czero-tng` fleet report is 43 sessions, RM435.07. The
SG/VLT settlement is 5 sessions, RM13.94. Sending the first to Voltality
would match nothing they hold.

**Invoice Voltality from SG/VLT.** SG/VOL is their UAT side, same business
name, 105 simulator sessions. The invoice page tags them LIVE and TEST and
turns the banner red if you pick the test one.

## Clocks

**Sessions and meter values are stored in Malaysian wall time (UTC+8).
Heartbeats, faults and `created_at` are UTC.** This is inconsistent and it
is too late to change: a column holding one zone for rows a migration
filled and another for rows written since is a worse bug than the
inconsistency.

When you add a timestamp, follow the convention of the table it joins.

Chargers disagree about what "Z" means. Some send local time with a Z
suffix. Do not trust a charger's timezone.

And in JavaScript: **`toISOString()` converts to UTC.** Local midnight on
the 1st becomes 16:00 on the last day of the previous month. The invoice
page's "This Month" button asked for 31 Oct to 29 Nov because of exactly
this. Format calendar dates by hand.

In Python: **`datetime.fromisoformat("2026-07-15")` succeeds** on 3.11+.
An "end of day" widening that lives in an `except ValueError` branch will
never run, and the closing date silently drops everything charged on it.

## FastAPI

### `response_model` silently drops fields

A key added to a handler's return dict **never reaches the client** unless
the Pydantic model declares it. This has happened twice:

- `roaming_published` was computed correctly and every charger showed as
  hidden in the browser
- `stop_initiator` likewise

Both were invisible in unit tests because the helper was right. If you add
a field to a response, add it to the model, and write the test against the
**endpoint**, not the helper.

## The database

### MySQL's REPEATABLE READ will lie to you

InnoDB defaults to REPEATABLE READ. A session that has already read a row
keeps seeing that snapshot for the rest of its transaction, even after
another connection has committed a change.

This cost a confusing ten minutes during the charger delete work: the
endpoint reported success, the verification query in the same script showed
the rows still present, and both were telling the truth. **Verify a write
from a fresh connection.**

### Mapper events enforce invariants, not call sites

Sessions are created from six places across two OCPP stacks, the API and
the edge sync. Rather than ask six call sites to remember, `database.py`
uses SQLAlchemy `before_insert` events:

- `_stamp_session_prices` — freezes prices and the tenant onto a session
- `_new_charger_starts_hidden` — a new charger is never published

Add a seventh call site and these still hold. That is the point.

## Deploying

### `gh workflow run --ref` does not deploy that branch

`--ref` picks which branch's *workflow file* runs. The workflow then
deploys its own `ref` **input**, which defaults to `main`. Use
`-f ref=<branch>`, and a branch name rather than a commit SHA.

### A green deploy is not a deploy

The workflow has reported success while the container was never recreated.
Always check `docker ps` shows "Up <seconds>", and for a code change, grep
inside the container.

### `>=` in requirements means local and production can differ

`xlsxwriter>=3.2.0` installed 3.2 here and 3.3 in the container. 3.2
coerced a bad argument that 3.3 rejects, so a test passed locally and the
endpoint returned 500 on its first real request in production. When a
library's behaviour matters, check the version **in the container**.

### Never build the Next.js PWAs while their dev server is running

HICOM, Mini and Proton are Next.js. Running a production build while the
dev server is up makes routes start returning 404. Stop the dev server
first.

### A tar deploy never deletes

The HICOM PWA was hand-deployed by unpacking a tarball. Tar adds and
overwrites; it never removes. A stale static file survived and shadowed a
new route. Everything should go through CI.

## OCPP

- **2.0.1: the "gun number" is the `evse_id`, not the `connector_id`.**
- **A simulator that answers instantly hides every timing assumption.**
  `_attach_auth_reference` waited 10 seconds for a session row. Voltality's
  simulator answered immediately; DC3001 took twenty seconds, so real
  charges ran as anonymous sessions the partner could not be billed for.
  It is 90 seconds now. Any wait tuned against `VOLTALITYTEST1` should be
  re-checked against DC3001.
- **AION frames die over TLS.** The vendor only ever tested plain ws:9000.
  Large OCPP frames over wss fail.
- **DC3001 does restart without unplugging**, whatever the vendor says.
  The rejections are intermittent and the logs contradict their answer.

## OCPI

- The outbound Authorization token must be **base64 encoded** (§4.1.3), or
  you get 401. This went unexplained for a month.
- Each partner has its own token. Replying to a UAT command with the
  production token is a silent cross-wire; `_outbound_token` takes the id
  of the partner that sent the command.
- Publishing to roaming is restricted to the `czero-tng` tenant and to
  chargers explicitly marked public. A new charger starts hidden.
- `VOLTALITYTEST1` is **Voltality's own simulator** running on a MacBook,
  not our hardware. We cannot bring it online.

## The dashboard

The templates are plain HTML and vanilla JS with no build step. Two
consequences:

- A change is live as soon as the container restarts. Convenient, and it
  means a syntax error takes a page down with no compiler to catch it.
  Run `node --check` on the extracted script block before deploying.
- `static/tenant.js` ships with a **hardcoded fallback list** of two
  tenants and replaces it once `/api/tenants` answers. Code that reads the
  switcher at boot gets the placeholder. Ask the API.
