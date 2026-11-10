"""Test Supabase alone: REST auth with the API key, key type, and pgvector via direct Postgres."""
import os, sys, base64, json
sys.path.insert(0, os.path.dirname(__file__))
import _env  # noqa: F401
import httpx

url = os.environ["SUPABASE_PROJECT_URL"].rstrip("/")
key = os.environ["SUPABASE_API_KEY"]
kind = ("secret (server-side)" if key.startswith("sb_secret_") else
        "publishable (client-safe, RLS applies)" if key.startswith("sb_publishable_") else
        "legacy JWT" if key.count(".") == 2 else "unknown format")
print("key type:", kind)
if key.count(".") == 2:
    try:
        pad = key.split(".")[1]; pad += "=" * (-len(pad) % 4)
        print("legacy role:", json.loads(base64.urlsafe_b64decode(pad)).get("role"))
    except Exception:
        pass

r = httpx.get(f"{url}/rest/v1/", headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=15)
print("REST status:", r.status_code)

try:
    import psycopg
    ref = url.split("//")[1].split(".")[0]
    pw = os.environ["SUPABASE_DB_PASSWORD"]
    with psycopg.connect(host=f"db.{ref}.supabase.co", dbname="postgres", user="postgres",
                         password=pw, connect_timeout=10) as conn:
        row = conn.execute("select extname from pg_extension where extname='vector'").fetchone()
        print("pgvector enabled:", bool(row))
except ImportError:
    print("psycopg not installed; skipping pgvector check")
except Exception as e:
    print("direct DB check failed:", type(e).__name__, str(e)[:120])
