"""Apply sql/*.sql to the Supabase Postgres (idempotent). Uses SUPABASE_DB_PASSWORD."""
import os, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
import _env  # noqa: F401
import psycopg

ref = os.environ["SUPABASE_PROJECT_URL"].split("//")[1].split(".")[0]
with psycopg.connect(host=f"db.{ref}.supabase.co", dbname="postgres", user="postgres",
                     password=os.environ["SUPABASE_DB_PASSWORD"], connect_timeout=10, autocommit=True) as conn:
    for f in sorted((Path(__file__).resolve().parent.parent / "sql").glob("*.sql")):
        conn.execute(f.read_text())
        print("applied", f.name)
    print("pgvector:", bool(conn.execute("select 1 from pg_extension where extname='vector'").fetchone()))
    print("rls on:", conn.execute("select relrowsecurity from pg_class where relname='documents'").fetchone()[0])
