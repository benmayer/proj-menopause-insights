"""Apply sql/*.sql to the Supabase Postgres (idempotent). Uses SUPABASE_DB_PASSWORD.

The direct host (db.<ref>.supabase.co) is IPv6-only; on IPv4-only networks it fails to resolve,
so we fall back to the session pooler. Set SUPABASE_DB_POOLER_HOST to override (default: eu-central-1).
"""
import os, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
import _env  # noqa: F401
import psycopg

ref = os.environ["SUPABASE_PROJECT_URL"].split("//")[1].split(".")[0]
pw = os.environ["SUPABASE_DB_PASSWORD"]


def connect():
    try:
        return psycopg.connect(host=f"db.{ref}.supabase.co", dbname="postgres", user="postgres",
                               password=pw, connect_timeout=10, autocommit=True)
    except psycopg.OperationalError:
        host = os.getenv("SUPABASE_DB_POOLER_HOST", "aws-1-eu-central-1.pooler.supabase.com")
        print("direct host unreachable, using pooler", host)
        return psycopg.connect(host=host, port=5432, dbname="postgres", user=f"postgres.{ref}",
                               password=pw, connect_timeout=10, autocommit=True)


with connect() as conn:
    for f in sorted((Path(__file__).resolve().parent.parent / "sql").glob("*.sql")):
        conn.execute(f.read_text())
        print("applied", f.name)
    print("pgvector:", bool(conn.execute("select 1 from pg_extension where extname='vector'").fetchone()))
    print("rls on:", conn.execute("select relrowsecurity from pg_class where relname='documents'").fetchone()[0])
