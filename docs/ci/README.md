# Continuous integration

The active workflow is `.github/workflows/ci.yml`. It includes Ruff, dataset and
model preparation, SQLite tests/migrations, actual PostgreSQL migration and
concurrency checks, browser journeys/offline isolation, and an HTTP smoke job.

Install tools with `python -m pip install -r requirements-dev.txt`. The file in
this directory is a documentation copy; edit the active workflow first. Publishing
workflow changes still requires a GitHub credential that can write workflows.
Inspect the repository's Actions tab for the results of each pushed commit.
