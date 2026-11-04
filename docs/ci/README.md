# Continuous integration

The active workflow is `.github/workflows/ci.yml`. It includes Ruff, dataset and
model preparation, SQLite tests/migrations, actual PostgreSQL migration and
concurrency checks, browser journeys/offline isolation, and an HTTP smoke job.
The browser job also runs keyboard navigation and axe-core 4.14.0 checks in both
languages and themes. Its JSON accessibility report is uploaded with the screenshot.
Install the locked QA dependency with `npm ci --prefix tools/a11y --ignore-scripts`.
Run `python tools/keyboard_smoke.py` and `python tools/accessibility_audit.py`
against `python tools/review_server.py`; these tools accept local fixtures only.
The HTTP smoke job logs in to the seeded demo account and separately verifies
that anonymous triage is rejected. Tokens are kept in memory and never logged.
Model builds use `ml/prepare_all.py --skip-download` against the committed source
data. Acquiring new external datasets is separate from CI; a remote data host
going offline must not block testing an existing revision.

Install tools with `python -m pip install -r requirements-dev.txt`. The file in
this directory is a documentation copy; edit the active workflow first. Publishing
workflow changes still requires a GitHub credential that can write workflows.
Inspect the repository's Actions tab for the results of each pushed commit.
