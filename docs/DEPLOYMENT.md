# Deployment

Two supported shapes. Both are configured in this repository.

| | All on Vercel | Container host |
|---|---|---|
| Frontend | Vercel CDN | nginx or the same container |
| API | Vercel Function | Railway, Render, Fly.io, a VPS |
| Database | Managed Postgres (Neon, Supabase, Vercel Postgres) | Postgres beside the app |
| Imaging models | Not available | Optional |
| Setup | One project, one domain, no CORS | Two services to wire together |

Start with Vercel. Move to a container host when the imaging models matter.

---

## All on Vercel

One project serves the pages and the API from the same domain. `vercel.json`
rewrites `/api/*`, `/health` and `/docs` to the function in `api/index.py`
and serves everything else as static files, so the browser only ever talks to
one origin and no CORS configuration is involved.

### 1. A Postgres database

Any managed Postgres works — [Neon](https://neon.tech),
[Supabase](https://supabase.com) and Vercel Postgres all have a free tier.

SQLite cannot be used. A serverless instance handles one request and is then
discarded along with its filesystem, so every registration, appointment and
uploaded file written to a local file would be lost immediately.

The connection string can be used exactly as the provider gives it. All
three forms are accepted:

```
postgres://user:password@host/dbname?sslmode=require
postgresql://user:password@host/dbname?sslmode=require
postgresql+psycopg2://user:password@host/dbname?sslmode=require
```

SQLAlchemy reads the scheme as the name of the driver to load, and the first
two name no driver. The application supplies `psycopg2` itself rather than
asking anyone to edit a string that an integration may overwrite on the next
deployment.

The easiest route on Vercel is the Neon integration: **Storage** → **Create
Database** → **Neon**. It creates the database and sets `DATABASE_URL` on
the project, so step 2 only needs the remaining two variables.

### 2. Create the project

Import the repository on Vercel. Leave the framework preset as **Other** —
there is nothing to detect, and no Node build.

Set one environment variable:

| Variable | Value |
|---|---|
| `DATABASE_URL` | the connection string from step 1 |
| `SECRET_KEY` | 32+ characters, `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `APP_ENV` | `production` |

`API_BASE_URL` is not needed. The build defaults it to `/api/v1`, which keeps
every preview deployment working on its own hostname.

### 3. Deploy

The build runs `scripts/vercel_build.py`, which applies the database
migrations and then writes the static pages into `frontend/dist`.

### 4. Seed the reference data

The hospitals, doctors and drug tables are not created by migrations. Run
this once from your own machine, pointed at the same database:

```powershell
$env:DATABASE_URL="postgresql+psycopg2://..."
$env:SECRET_KEY="the same key"
python scripts/seed_database.py
python scripts/check_setup.py
```

### What does not work on Vercel

**The imaging models.** Skin and chest X-ray need several GB of training
images and produce artifacts far larger than a function bundle allows. Their
`/status` endpoints report `available: false`, the two pages say so, and
nothing else is affected. Triage, surge forecasting, the drug checker and
every clinical workflow are unchanged.

**Cold starts.** The installed dependencies come to about 423 MB, most of it
scipy, pandas, scikit-learn and numpy together with their bundled native
libraries. That is inside Vercel's 500 MB limit for Python functions but not
by a wide margin, which is why `requirements.txt` at the repository root
omits the three packages only the data pipeline needs — `pyarrow` alone is
145 MB. A cold instance loads the models in about a second and answers
warm requests in milliseconds.

If a future dependency pushes the bundle past the limit, the deploy fails
with "exceeded the unzipped maximum size". Either drop something or move the
API to a container host, where the limit does not apply.

---

## Container host

Use this when you want the imaging models, predictable latency, or a disk.

The `Dockerfile` builds the datasets and trains the text models during the
image build, so a started container serves AI requests immediately.
`railway.json` selects it and points the health check at `/health`.

1. Create the service from this repository and add a PostgreSQL instance.
2. Set the variables below.
3. Deploy. Migrations are applied by the entrypoint before the server starts.

On Railway the database connection string is composed from the Postgres
service:

```
DATABASE_URL=postgresql+psycopg2://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
```

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+psycopg2://...` |
| `SECRET_KEY` | yes | 32+ characters |
| `APP_ENV` | yes | `production` |
| `CORS_ORIGINS` | if the frontend is elsewhere | The frontend's public address. Not needed when the container serves both. |
| `WEB_CONCURRENCY` | recommended | Each worker holds ~190 MB once the models load. `2` on 1 GB, `1` on 512 MB. |
| `SEED_ON_START` | optional | `true` loads the 570 hospitals, 50 doctors and drug data on first boot. |
| `PORT` | automatic | Supplied by the host; the entrypoint binds to it. |

To include the imaging models, add `--with-skin` to the `prepare_all.py` call
in the `models` stage of the Dockerfile and expect a much larger image and a
much longer build.

### Hosting the frontend separately

If the pages are on a CDN and the API is on another domain, build them with
the API's address and then allow that origin on the API:

```bash
API_BASE_URL=https://your-api.up.railway.app python scripts/build_frontend.py
```

Then set `CORS_ORIGINS` on the API to the frontend's URL and redeploy.
Skipping that leaves the browser discarding every response: the API answers
correctly but without an `Access-Control-Allow-Origin` header for that
origin.

---

## Docker Compose

For a single machine running everything, including Postgres and nginx:

```bash
cp .env.example .env     # set SECRET_KEY and POSTGRES_PASSWORD
docker compose up -d
```

Serves on port 8080.

---

## Verifying a deployment

```bash
curl https://your-deployment/health
```

Expect `{"status":"ok"}`.

```bash
curl -X POST https://your-deployment/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"patient@sasthosetu.gov.bd","password":"Patient@12345"}'
```

Expect an `access_token`.

| Symptom | Cause |
|---|---|
| 503 mentioning the schema | Migrations have not run. Check the build log. |
| 401 on the demo account | Seed data is absent. Run `scripts/seed_database.py` against the deployment database. |
| Pages load, every action fails | Open the console. A CORS message means the API does not allow the frontend's origin; a request to `localhost:8000` means the pages were built without `API_BASE_URL`. |
| Skin or X-ray says unavailable | Expected on Vercel. The models are not in the bundle. |

Change the demo passwords before exposing a deployment publicly. They are
listed in `docs/TESTING-GUIDE.md` and seeded by `scripts/seed_database.py`.

---

## Where the files went

Uploaded medical files are stored in the database, not on disk. A local
directory does not survive an instance being replaced, and on a serverless
host that is after every request. Uploads are capped at 10 MB and limited to
JPEG, PNG, WebP and PDF.
