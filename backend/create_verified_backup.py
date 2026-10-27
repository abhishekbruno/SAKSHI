import os
import sys
import json
import shutil
import subprocess
from datetime import datetime
from urllib.parse import urlparse

# Ensure backend path
sys.path.insert(0, os.path.abspath("backend"))

from app.core.config import settings
from app.db.session import engine
from sqlalchemy import text

BACKUP_ROOT_1 = r"C:\Users\zone\.gemini\antigravity-ide\brain\ec763fce-efbe-41c7-870e-c9a3d0b6beba\backups\pre_cleanup_backup_20261026"
BACKUP_ROOT_2 = r"c:\main project\backups\pre_cleanup_backup_20261026"

for b_path in [BACKUP_ROOT_1, BACKUP_ROOT_2]:
    os.makedirs(b_path, exist_ok=True)

print("=== 1. Active Database & Connection Identification ===")
parsed = urlparse(settings.DATABASE_URL)
safe_host = parsed.hostname or "localhost"
safe_port = parsed.port or 5432
safe_db = parsed.path.lstrip("/")
print(f"Dialect: {parsed.scheme.split('+')[0]}")
print(f"Host: {safe_host}:{safe_port}")
print(f"Database: {safe_db}")

metadata = {
    "timestamp": datetime.now().isoformat(),
    "database": safe_db,
    "host": safe_host,
    "port": safe_port,
    "table_counts": {},
    "cases": [],
    "evidence": [],
    "rag_documents": [],
    "rag_chunks": []
}

with engine.connect() as conn:
    tables = [r[0] for r in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).fetchall()]
    print(f"\nDiscovered {len(tables)} tables in schema 'public'")
    for t in sorted(tables):
        cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        metadata["table_counts"][t] = cnt
        print(f"  {t}: {cnt} rows")

    cases = conn.execute(text("SELECT case_id, title, fir_metadata, status, lifecycle_stage, created_at, updated_at FROM cases ORDER BY created_at")).fetchall()
    for c in cases:
        metadata["cases"].append({
            "case_id": c[0],
            "title": c[1],
            "fir_metadata": c[2],
            "status": c[3],
            "lifecycle_stage": c[4],
            "created_at": str(c[5]),
            "updated_at": str(c[6])
        })
    print(f"\nRecorded {len(cases)} total cases")

    evs = conn.execute(text("SELECT * FROM evidence")).fetchall()
    cols_ev = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'evidence'")).fetchall()]
    for e in evs:
        row_dict = {}
        for col_name, val in zip(cols_ev, e):
            row_dict[col_name] = str(val) if val is not None else None
        metadata["evidence"].append(row_dict)
    print(f"Recorded {len(evs)} total evidence exhibits")

    docs = conn.execute(text("SELECT * FROM rag_documents")).fetchall()
    cols_doc = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'rag_documents'")).fetchall()]
    for d in docs:
        row_dict = {col: (str(val) if val is not None else None) for col, val in zip(cols_doc, d)}
        metadata["rag_documents"].append(row_dict)
    print(f"Recorded {len(docs)} total RAG documents")

    chunks = conn.execute(text("SELECT chunk_id, document_id, case_id, evidence_id, chunk_index, page_number, char_start, char_end, content FROM rag_chunks")).fetchall()
    for ch in chunks:
        metadata["rag_chunks"].append({
            "chunk_id": ch[0],
            "document_id": ch[1],
            "case_id": ch[2],
            "evidence_id": ch[3],
            "chunk_index": ch[4],
            "page_number": ch[5],
            "char_start": ch[6],
            "char_end": ch[7],
            "content_len": len(ch[8]) if ch[8] else 0
        })
    print(f"Recorded {len(chunks)} total RAG chunks")

# 2. Dump complete database using pg_dump
pg_dump_path = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
if os.path.exists(pg_dump_path):
    user = parsed.username or "postgres"
    password = parsed.password or ""
    dump_sql_1 = os.path.join(BACKUP_ROOT_1, "database_dump.sql")
    dump_sql_2 = os.path.join(BACKUP_ROOT_2, "database_dump.sql")
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    
    cmd = [
        pg_dump_path,
        "-h", safe_host,
        "-p", str(safe_port),
        "-U", user,
        "-d", safe_db,
        "-f", dump_sql_1
    ]
    print(f"\nRunning pg_dump to {dump_sql_1}...")
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print("pg_dump ERROR:", proc.stderr)
        sys.exit(1)
    print("pg_dump succeeded. Size:", os.path.getsize(dump_sql_1), "bytes")
    shutil.copy2(dump_sql_1, dump_sql_2)

# Save JSON metadata backup
for root in [BACKUP_ROOT_1, BACKUP_ROOT_2]:
    with open(os.path.join(root, "database_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

# 3. Preserve uploaded FIR file and its stored evidence objects
fir_workspace = r"C:\sakshi\workspaces\SAKSHI-CASE-2026-C5A64E99"
if os.path.exists(fir_workspace):
    def win_long_path(p):
        ap = os.path.abspath(p)
        if sys.platform == "win32" and not ap.startswith("\\\\?\\"):
            return "\\\\?\\" + ap
        return ap

    dest_ws_1 = win_long_path(os.path.join(BACKUP_ROOT_1, "workspace_backup", "SAKSHI-CASE-2026-C5A64E99"))
    dest_ws_2 = win_long_path(os.path.join(BACKUP_ROOT_2, "workspace_backup", "SAKSHI-CASE-2026-C5A64E99"))
    src_long = win_long_path(fir_workspace)

    def handle_remove_readonly(func, path, exc_info):
        import stat
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    for dest in [dest_ws_1, dest_ws_2]:
        if os.path.exists(dest):
            shutil.rmtree(dest, onexc=handle_remove_readonly)
        shutil.copytree(src_long, dest)
    print(f"\nPreserved FIR workspace: {fir_workspace} -> {dest_ws_1}")
else:
    print(f"ERROR: Expected workspace {fir_workspace} does not exist!")
    sys.exit(1)

# 4. Verify backup can be read
with open(os.path.join(BACKUP_ROOT_1, "database_manifest.json"), "r", encoding="utf-8") as f:
    v_data = json.load(f)
assert len(v_data["cases"]) == len(cases)
assert len(v_data["evidence"]) == len(evs)
assert os.path.getsize(os.path.join(BACKUP_ROOT_1, "database_dump.sql")) > 5000

# Verify FIR file in backup
backup_fir_pdf = win_long_path(os.path.join(BACKUP_ROOT_1, "workspace_backup", "SAKSHI-CASE-2026-C5A64E99", "evidence", "raw", "SAKSHI-EVID-2026-54C01EA8", "E00_synthetic_FIR.pdf"))
assert os.path.exists(backup_fir_pdf), f"Missing {backup_fir_pdf}"
assert os.path.getsize(backup_fir_pdf) > 0, "FIR PDF is 0 bytes"
print(f"Verified backup FIR PDF: {backup_fir_pdf} ({os.path.getsize(backup_fir_pdf)} bytes)")

print("\n=== BACKUP COMPLETED & VERIFIED SUCCESSFULLY ===")
