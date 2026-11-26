# 07 — Setting up on your laptop

Windows, PowerShell. About twenty minutes.

## Before anything: which branch

> **Clone `main`, but check what is actually deployed before you trust it.**
>
> ```powershell
> gh repo clone Aqdshk/Aqdshk-PUBLIC-CHARGER
> cd Aqdshk-PUBLIC-CHARGER
> git log --oneline -1
> ```
>
> then
>
> ```powershell
> ssh plagsini 'cd /opt/plagsini-ev && sudo git log --oneline -1'
> ```
>
> **If those two do not match, production is running something that is not
> on `main`, and `main` is not the truth.** Ask before you build on it.

## 1. The tools

```powershell
winget install Python.Python.3.11
winget install Git.Git
winget install GitHub.cli
winget install Docker.DockerDesktop
```

Python 3.11 specifically: CI runs 3.11, and a newer Python changes
behaviour that this codebase depends on (`datetime.fromisoformat` is the
one that has already caused a bug).

## 2. The repository

```powershell
gh auth login
gh repo clone Aqdshk/Aqdshk-PUBLIC-CHARGER "C:\PUBLIC CHARGER RND"
cd "C:\PUBLIC CHARGER RND\ChargingPlatform"
```

## 3. Dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest
```

## 4. Run the tests

This is the real check that your setup works, and it needs no database,
no credentials and no network. The test suite points itself at a throwaway
SQLite file (`tests/conftest.py`).

```powershell
python -m pytest tests/ -q
```

Expect **400 passed**. If you get that, your environment is correct.

## 5. Running the app locally (optional)

You rarely need to. The tests cover the logic, and the dashboard templates
can be checked against a stub. But if you want the real thing:

### The database

```powershell
docker run -d --name plagsini-mysql-local `
  -e MYSQL_ROOT_PASSWORD=localdev `
  -e MYSQL_DATABASE=charging_platform `
  -p 3306:3306 mysql:8.0
```

### The environment

Create `ChargingPlatform\.env` — **and never commit it**, it is gitignored
for a reason:

```
DATABASE_URL=mysql+pymysql://root:localdev@localhost:3306/charging_platform
JWT_SECRET_KEY=<generate your own, see below>
APP_ENV=development
OCPI_TOKEN=local-test-token
ADMIN_EMAIL=you@example.com
ADMIN_PASSWORD=<something local>
```

Generate a secret key:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

`JWT_SECRET_KEY` has no default on purpose — the app refuses to start
without it rather than silently signing tokens with a guessable value.

### Migrate and run

```powershell
alembic upgrade head
python main.py
```

That starts FastAPI on <http://localhost:8000> and the OCPP WebSocket
server on port 9000, the same as production.

`http://localhost:8000/docs` is FastAPI's own interactive API reference,
generated from the code. It is the most reliable API documentation that
exists for this project.

## 6. Checking a dashboard page without a login

The dashboard pages authenticate with a staff token, so you cannot just
open one from disk. The trick used during development is a stub: serve the
template over HTTP with a small script that fakes the API responses.

```powershell
# Extract the page's script block and syntax-check it — do this before
# every deploy that touches a template. There is no build step and no
# compiler, so a typo takes the page down.
python -c @'
import io, re
s = io.open("templates/invoice.html", encoding="utf-8").read()
io.open("page.js", "w", encoding="utf-8").write(re.findall(r"<script>(.*?)</script>", s, re.S)[-1])
'@
node --check page.js
```

## 7. Connecting to the VPS

See [04 — Access](04-access.md). Once your key is in place:

```powershell
ssh plagsini 'sudo docker ps'
```

## A normal day's workflow

```powershell
git checkout main
git pull
git checkout -b fix/the-thing

# ... edit ...

python -m pytest tests/ -q          # must pass
git add -A
git commit -m "fix(area): what and why"
git push -u origin fix/the-thing

gh workflow run deploy.yml -f ref=fix/the-thing
```

Then verify it landed, per [03 — Operations](03-operations.md). Merge to
`main` once it is proven in production.

## What not to do

- Do not run `alembic upgrade head` against production from your laptop.
  The deploy workflow does it, against the new image, before the container
  swaps.
- Do not point your local `.env` at the production database. There is no
  guard that stops you.
- Do not commit `.env`, a `.pem`, or anything with a token in it.
