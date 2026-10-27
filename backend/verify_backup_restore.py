import os
import sys
import subprocess
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath("backend"))
from app.core.config import settings

parsed = urlparse(settings.DATABASE_URL)
user = parsed.username or "postgres"
password = parsed.password or ""
host = parsed.hostname or "localhost"
port = parsed.port or 5432
psql_path = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"
dump_file = r"c:\main project\backups\pre_cleanup_backup_20261026\database_dump.sql"

env = os.environ.copy()
if password:
    env["PGPASSWORD"] = password

print("Testing database restore verification...")
temp_db = "sakshi_restore_verify_temp"

# Drop temp db if exists and create fresh
subprocess.run([psql_path, "-h", host, "-p", str(port), "-U", user, "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {temp_db};"], env=env, check=True, capture_output=True)
subprocess.run([psql_path, "-h", host, "-p", str(port), "-U", user, "-d", "postgres", "-c", f"CREATE DATABASE {temp_db};"], env=env, check=True, capture_output=True)

try:
    print(f"Restoring {dump_file} into {temp_db}...")
    res = subprocess.run([psql_path, "-h", host, "-p", str(port), "-U", user, "-d", temp_db, "-f", dump_file], env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print("Restore stderr:", res.stderr)
        raise RuntimeError("Restore failed")

    # Verify counts in temp_db
    chk = subprocess.run([psql_path, "-h", host, "-p", str(port), "-U", user, "-d", temp_db, "-t", "-c", "SELECT count(*) FROM cases;"], env=env, capture_output=True, text=True)
    cases_cnt = int(chk.stdout.strip())
    print(f"Verified restored cases count in {temp_db}: {cases_cnt} (matches 13)")
    assert cases_cnt == 13

    chk_ev = subprocess.run([psql_path, "-h", host, "-p", str(port), "-U", user, "-d", temp_db, "-t", "-c", "SELECT count(*) FROM evidence;"], env=env, capture_output=True, text=True)
    ev_cnt = int(chk_ev.stdout.strip())
    print(f"Verified restored evidence count in {temp_db}: {ev_cnt} (matches 4)")
    assert ev_cnt == 4

    print("Backup can be successfully read and restored!")
finally:
    # Cleanup temp db
    subprocess.run([psql_path, "-h", host, "-p", str(port), "-U", user, "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {temp_db};"], env=env, check=True, capture_output=True)
    print(f"Cleaned up temporary restore verification database {temp_db}.")
