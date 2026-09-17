# Deployment

The application is two pieces that deploy separately:

| Piece | What it is | Where it goes |
|---|---|---|
| `frontend/` | Static HTML, CSS and ES modules | Any CDN or static host (Vercel, Netlify, Cloudflare Pages) |
| `backend/` | FastAPI, SQLAlchemy, trained models | A host that runs a container and keeps a disk (Railway, Render, Fly.io, a VPS) |

## Why the backend is not serverless

Vercel, Netlify Functions and Lambda give each request a fresh, read-only
container. Four things in this project depend on that not being the case:

- **SQLite writes to a file.** On a serverless host the file is discarded
  after the request, so every registration and appointment disappears.
- **Uploaded files are written to `uploads/`** by
  `backend/app/modules/files/service.py`, with the same outcome.
- **The models are 4.2 MB of joblib artifacts** that are not in the
  repository — `.gitignore` excludes them, because they are rebuilt from the
  datasets. There is nothing to deploy unless they are built first.
- **scikit-learn, pandas, numpy and scipy are about 283 MB installed**, and
  loading them costs roughly 190 MB of resident memory per worker. Cold
  starts are slow enough to be noticeable on every idle request.

The Dockerfile solves all four. Use it.

---

## Backend

### Railway

1. New Project → Deploy from GitHub → pick this repository.
2. Add a **PostgreSQL** database to the project.
3. Set the variables below on the application service.
4. Deploy. `railway.json` selects the Dockerfile and points the health check
   at `/health`.

`DATABASE_URL` needs the psycopg2 driver spelled out. Railway exposes its
Postgres connection string as `DATABASE_URL` on the database service, so
reference it and prefix the scheme:

```
DATABASE_URL=postgresql+psycopg2://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
```

### Render

Create a Web Service, choose **Docker**, add a PostgreSQL instance and set
the same variables. Health check path `/health`.

### Environment variables

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+psycopg2://...`. SQLite works but does not survive a redeploy. |
| `SECRET_KEY` | yes | 32+ characters. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `APP_ENV` | yes | `production`. Anything else leaves the permissive localhost CORS rule enabled. |
| `CORS_ORIGINS` | yes | The frontend's public address, e.g. `https://sasthosetu.vercel.app`. Comma-separated for several. |
| `WEB_CONCURRENCY` | recommended | Workers. Each holds ~190 MB once the models load, so allow 512 MB per worker. `2` on a 1 GB instance, `1` on 512 MB. |
| `SEED_ON_START` | optional | `true` loads the 570 hospitals, 50 doctors and drug data on first boot. |
| `PORT` | automatic | Supplied by the host; the entrypoint binds to it. |
| `RATE_LIMIT_PER_MINUTE` | optional | Default 120. |
| `LLM_API_KEY`, `LLM_API_URL`, `LLM_MODEL` | optional | Enables the LLM symptom extractor. See `docs/LLM_SETUP.md`. |

The container applies migrations before it starts serving, so no manual
migration step is needed.

### What the image build does

`Dockerfile` has a `models` stage that runs `ml/prepare_all.py` during the
build: it fetches the public datasets, assembles the corpora and trains the
triage and surge models. The artifacts are copied into the runtime image, so
a started container is immediately able to answer AI requests.

Expect the first build to take 10–20 minutes. Later builds reuse the cached
layer unless `ml/` or `backend/` changes.

The imaging models (skin, chest X-ray) are **not** built. They need several
GB of downloads and would make the image impractical. Without them
`/api/v1/ai/skin-check` and `/api/v1/ai/xray-check` report themselves
unavailable through their `/status` endpoints and the rest of the
application is unaffected. To include them, add `--with-skin` to the
`prepare_all.py` call in the `models` stage and expect a much larger image.

---

## Frontend

The pages work out of the box during development because they assume the API
is on port 8000 of the same host. That assumption is wrong once the two are
on different domains, so the build writes the real address into each page:

```
API_BASE_URL=https://your-api.up.railway.app python scripts/build_frontend.py
```

This copies `frontend/` to `frontend/dist/` and inserts

```html
<meta name="api-base" content="https://your-api.up.railway.app/api/v1">
```

into all 20 pages. `assets/js/api.js` reads that tag before falling back to
its own guesswork. The `/api/v1` suffix is added if you leave it off.

### Vercel

1. New Project → import this repository.
2. Add an environment variable **`API_BASE_URL`** with the backend's public
   address.
3. Deploy. `vercel.json` already sets the build command, the output
   directory and the response headers.

Leave the framework preset as "Other". There is nothing to detect: no
bundler, no package.json, no Node build.

If `API_BASE_URL` is missing the build fails with an explanation rather than
publishing pages that quietly cannot reach the API.

### Netlify, Cloudflare Pages, S3

Same idea. Build command `python3 scripts/build_frontend.py`, publish
directory `frontend/dist`, with `API_BASE_URL` set.

---

## Order of operations

The two sides reference each other, so deploy in this order:

1. **Backend first.** It has no dependency on the frontend. Note the public
   URL it is given.
2. **Frontend**, with `API_BASE_URL` set to that URL.
3. **Back to the backend** and set `CORS_ORIGINS` to the frontend's URL, then
   redeploy.

Skipping step 3 leaves the browser blocking every request: the API replies
correctly but without an `Access-Control-Allow-Origin` header for that
origin, and the browser discards the response.

---

## Verifying a deployment

```bash
curl https://your-api.up.railway.app/health
```

Expect `{"status":"ok"}`.

```bash
curl -X POST https://your-api.up.railway.app/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"patient@sasthosetu.gov.bd","password":"Patient@12345"}'
```

Expect an `access_token`. A 503 mentioning the schema means migrations have
not run; check the deploy logs. A 401 means the seed data is absent — set
`SEED_ON_START=true` and redeploy.

Then open the frontend and sign in. If the pages load but every action fails,
open the browser console: a CORS message means step 3 above was skipped, and
a request going to `localhost:8000` means `API_BASE_URL` was not set at build
time.

Change the demo passwords before exposing a deployment publicly. They are
listed in `docs/TESTING-GUIDE.md` and are seeded by
`scripts/seed_database.py`.

---

## Docker Compose

For a single machine that runs everything, including Postgres and nginx:

```bash
cp .env.example .env     # set SECRET_KEY and POSTGRES_PASSWORD
docker compose up -d
```

`docker-compose.yml` wires the application to Postgres, waits for it to be
healthy, applies migrations and serves the frontend through nginx on port
8080.
