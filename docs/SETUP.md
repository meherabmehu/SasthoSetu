# Running SasthoSetu on your computer

Two ways to do this. **Option A (Docker)** is one command but needs Docker
installed. **Option B (manual)** needs only Python and gives you live reload
for development.

Both have been verified end to end from a fresh clone.

---

## Before you start

| Need | Version | Check with | Get it |
|---|---|---|---|
| Python | 3.11 or newer | `python3 --version` | [python.org/downloads](https://www.python.org/downloads/) |
| Git | any recent | `git --version` | [git-scm.com](https://git-scm.com/downloads) |
| Docker | only for Option A | `docker --version` | [docker.com](https://www.docker.com/products/docker-desktop/) |

On Windows, use **PowerShell** and type `python` wherever this guide says
`python3`.

No database server is needed. The project defaults to SQLite, which is just a
file.

---

## Option A — Docker (simplest)

```bash
git clone https://github.com/meherabmehu/SasthoSetu.git
cd SasthoSetu
cp .env.example .env
```

Open `.env` and set two values:

```
SECRET_KEY=any-long-random-string-at-least-32-characters-long
POSTGRES_PASSWORD=any-password-you-choose
```

Then:

```bash
docker compose up --build
```

The first run takes a few minutes because it trains the AI models. When you see
`Application startup complete`, open **http://localhost:8080**.

Stop it with `Ctrl+C`. Start again later with `docker compose up`.

---

## Option B — Manual

### 1. Get the code

```bash
git clone https://github.com/meherabmehu/SasthoSetu.git
cd SasthoSetu
```

### 2. Create a virtual environment

This keeps the project's packages separate from the rest of your system.

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Your prompt should now start with `(.venv)`. Everything below assumes it is
still active — if you open a new terminal, run the activate command again.

### 3. Install the dependencies

```bash
pip install --upgrade pip
pip install -r backend/requirements.txt uvicorn
```

Takes about a minute.

### 4. Build the AI models

```bash
python ml/prepare_all.py
```

Takes roughly 90 seconds. It generates the training data and trains the triage
and surge models. You only ever need to do this once.

You should see `All datasets and artifacts ready`.

### 5. Set up the configuration

**macOS / Linux**
```bash
cp backend/.env.example backend/.env
```

**Windows**
```powershell
Copy-Item backend\.env.example backend\.env
```

The defaults work as-is for local use. No editing needed.

### 6. Create the database

```bash
cd backend
alembic upgrade head
cd ..
```

### 7. Add the sample data

```bash
python scripts/seed_database.py
```

This creates 5 hospitals, 50 doctors and three login accounts. It prints the
credentials at the end.

### 8. Start the two servers

You need **two terminal windows**, both with the virtual environment active.

**Terminal 1 — the API**
```bash
cd backend
uvicorn app.main:app --reload
```
Leave it running. It serves on port 8000.

**Terminal 2 — the website**

macOS / Linux:
```bash
source .venv/bin/activate
cd frontend
python3 -m http.server 5500
```

Windows:
```powershell
.venv\Scripts\Activate.ps1
cd frontend
python -m http.server 5500
```

### 9. Open it

**http://localhost:5500**

---

## Log in

| Role | Email | Password |
|---|---|---|
| Patient | `patient@sasthosetu.gov.bd` | `Patient@12345` |
| Doctor | `doctor@sasthosetu.gov.bd` | `Doctor@12345` |
| Admin | `admin@sasthosetu.gov.bd` | `Admin@12345` |

---

## Try these first

**Symptom check** — go to উপসর্গ পরীক্ষা and paste:

```
বুকে ব্যথা, শ্বাস নিতে কষ্ট, দুই দিন ধরে জ্বর
```

It should return a red **জরুরি অবস্থা** (emergency) banner. Try it in English
(`chest pain, difficulty breathing`) and Banglish (`buke betha, shash nite
koshto`) — all three reach the same conclusion.

**Hospital beds** — হাসপাতাল shows live occupancy per ward, and hospital detail
pages show the 72-hour forecast.

**Doctor flow** — log in as the doctor, open a consultation, and add both
`Warfin` and `Ecosprin` to a prescription. A major interaction warning appears
while you type.

**API documentation** — http://localhost:8000/docs lists all 99 endpoints and
lets you call them directly.

---

## If something goes wrong

**`python3: command not found`**
Try `python` instead. If neither works, Python is not installed or not on your
PATH — reinstall and tick "Add Python to PATH".

**`.venv\Scripts\Activate.ps1 cannot be loaded` (Windows)**
PowerShell blocks scripts by default. Run once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Page loads but the symptom check says "ইন্টারনেট সংযোগ নেই"**
The API is not running or not reachable. Check Terminal 1 is still going, then
open http://localhost:8000/health — it should show `{"status":"healthy"}`.

**`Address already in use`**
Something else has the port. Use a different one:
```bash
uvicorn app.main:app --reload --port 8001
```
Then in your browser console on the site, run:
```js
localStorage.setItem('sasthosetu.apiBase', 'http://localhost:8001/api/v1')
```
and reload.

**`no such table: hospitals`**
Step 6 was skipped or run from the wrong folder. Run `alembic upgrade head`
from inside `backend/`, then re-run step 7.

**AI endpoints return 503**
Step 4 was skipped. Run `python ml/prepare_all.py` from the project root.
The rule-based triage and drug checking work without it; the ML triage, surge
forecast and surveillance need it.

**Opening `index.html` by double-clicking does nothing useful**
The pages must be served over HTTP, not opened as files. Use step 8.

---

## Everyday use after the first setup

You only repeat steps 8 and 9:

```bash
# Terminal 1
source .venv/bin/activate && cd backend && uvicorn app.main:app --reload

# Terminal 2
source .venv/bin/activate && cd frontend && python3 -m http.server 5500
```

To start over with a clean database, delete `backend/dev.db` and repeat steps
6 and 7.

---

---

## Updating to a newer version

**Always run the migration after pulling.** New features usually add database
tables, and code that expects a table the database does not have will fail at
the moment you use that feature.

```powershell
git pull origin main
pip install -r backend/requirements.txt

cd backend
alembic upgrade head
cd ..
```

If you skip the migration the API logs
`DATABASE SCHEMA IS OUT OF DATE` at startup and affected pages return
"The database schema is out of date". Running the command above fixes it; no
data is lost.


## Running the tests

```bash
cd backend
APP_ENV=test DATABASE_URL=sqlite:///./test.db \
  SECRET_KEY=test-secret-key-at-least-32-characters-long \
  python -m unittest discover -s tests -v
```

149 tests, about 80 seconds.
