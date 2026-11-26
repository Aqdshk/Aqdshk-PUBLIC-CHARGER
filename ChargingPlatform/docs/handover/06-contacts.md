# 06 — Who to talk to, and what is outstanding

## Voltality / Touch 'n Go — the roaming partner

Live since **25 November 2026**. This is the relationship that bills real
money to another company, so it is the one that needs attention.

| Who | What they want from us |
|---|---|
| **Venusaran "Venu" Navaneetham** (Beep Technologies) | Technical. OCPI integration, charger availability, commands |
| **Jia Hui** | Finance. The monthly session record we invoice them against |

### What is live

- OCPI 2.2.1, both directions. They are an eMSP, we are the CPO
- Two partner registrations: **SG/VLT** on `api.voltnet.io` is production,
  **SG/VOL** on `api-uat.voltnet.io` is their UAT. Same business name on
  both, which is why the invoice page tags them LIVE and TEST
- Only the `czero-tng` tenant is published, and only chargers explicitly
  marked public. In practice that is **DC3001** and **VOLTALITYTEST1**
- They confirmed on their side that they receive only those two locations

### What Jia Hui asked for

A charging session record, in Excel, for the sessions we invoice them for:
start time, end time, charger used, location, total kWh, a cost breakdown
separating energy from idling, and a session unique identifier.

All of it is in the export. Invoice → pick **Voltality — LIVE (SG/VLT)** →
Export. The PDF is what you send; the Excel is what finance opens. The
identifier is `transaction_id`, which is what the OCPI Session and CDR
publish as their `id`, so every line matches a record they already hold.

**Do not send the fleet report.** See [05](05-gotchas.md).

### Still open with them

- **`min_price` / `max_price` are unanswered.** Venu said that if we do not
  set them we fall back to their defaults, minimum RM0.50 and maximum
  RM100, and that they block a user whose charge plus idling exceeds a
  threshold. Our CDR history has 81 below RM0.50 and 18 above RM100, so
  adopting their defaults would move real figures. **Nothing is set.** This
  needs a decision, not a guess.
- Venu said the Touch 'n Go app would enable us "in two or three days" from
  25 November. When that happens, real volume starts.
- `VOLTALITYTEST1` is **their simulator on a MacBook**, not our hardware.
  We cannot bring it online, and it is still published. Hiding it is a
  one-click change nobody has made.

### Longer-term OCPI items, none urgent

- The Tokens module advertises SENDER where a CPO should be RECEIVER
- One Location is published per charge point, where the spec would prefer
  one Location with several EVSEs

## Charger vendors

| Vendor | Notes |
|---|---|
| **Gresgying** | DC3001, the 30kW demo unit. Test reports go to them as a DOCX; there is a toolchain for it in `docs/` |
| **AION** | Several E7-A units. Large OCPP frames fail over TLS — they only ever tested plain `ws:9000`. Their AuthorizationKey leaked once and was deliberately **not** rotated |

Charger manufacturers can be given a scoped login to `/vendor`, created
under Administration → Vendor Access. They see only their own chargers,
not the fleet.

## Other products on the same VPS

Not the CSMS, but they share the machine and may become your problem:

| Product | What it is |
|---|---|
| **HICOM PWA** | Public charging PWA, port 3200. Deployed by hand with tar once — should move to CI |
| **PlagSini Mini** | Guest charging PWA forked from HICOM, port 3300. Payment switched off |
| **Proton Home Charge** | Free-charging PWA for Proton, port 3400. Live, with its own partner key |
| **C-Zero Car Reservation** | Vehicle booking, port 5000, `reservation.c-zero.com.my` |

## The outstanding list, honestly

Ordered by what would hurt most if left:

1. **`/api/chargers` is unauthenticated on the public domain.** It redacts
   vendor, model, firmware and connection state for anonymous callers, but
   still exposes 493 charger ids, tenants, tariffs and coordinates. The fix
   is to lock it and give the login page a count-only endpoint. Proposed,
   never decided.
2. **`min_price` / `max_price` with Voltality**, above.
3. **VOLTALITYTEST1 is still published** to the roaming partner.
4. **`billing_locked` is not switched on for `czero-tng`.** The mechanism
   exists: it refuses to move a charger into or out of a billed fleet
   without an explicit confirmation. Turn it on once Touch 'n Go is live.
5. **Test chargers share the `czero-tng` tenant.** `VOLTALITYTEST1` at
   RM3.90/kWh and `INJTEST10` at RM0.10 sit beside DC3001 at RM1.40, so the
   TNG *fleet report* includes simulator traffic. Does not affect what
   Voltality is invoiced. Moving them to a tenant of their own would clean
   it up.
6. **The per-charger analytics block runs about 1,500 queries per page
   load** — three for each of 493 chargers. The fleet breakdown beside it
   was rewritten into four grouped queries; this block was not.
7. **`/opt/backups/mysql-backup.sh` is a stale copy** with a hardcoded root
   password and a container name that no longer exists. Cron does not run
   it. Delete it.
8. **The branch is not merged.** See the warning in
   [07 — Local setup](07-local-setup.md).
