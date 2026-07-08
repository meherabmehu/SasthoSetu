# SasthoSetu Backend

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and configure the database and secret.
4. Apply migrations:

   ```powershell
   alembic upgrade head
   ```

5. Run the API:

   ```powershell
   uvicorn app.main:app --reload
   ```

API documentation is available at `http://127.0.0.1:8000/docs`.

If the database was created by an older SasthoSetu version that used
`Base.metadata.create_all`, back it up, confirm its schema matches the initial
migration, and mark that baseline once with:

```powershell
alembic stamp 20260709_0001
```

Do not run `stamp` on an empty database; use `alembic upgrade head`.

## Database changes

Do not create tables from application startup. After changing SQLAlchemy models,
generate and review a migration:

```powershell
alembic revision --autogenerate -m "describe the schema change"
alembic upgrade head
```

Test migration downgrade paths before committing.

## Tests

```powershell
python -m unittest discover -s tests -v
```
