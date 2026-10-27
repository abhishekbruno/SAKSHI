import os
import sys
import shutil
import stat
from sqlalchemy import text

sys.path.insert(0, os.path.abspath("backend"))
from app.db.session import engine

PRESERVED_CASE_ID = "SAKSHI-CASE-2026-C5A64E99"
PRESERVED_EVIDENCE_ID = "SAKSHI-EVID-2026-54C01EA8"

TEST_CASE_IDS = [
    "SAKSHI-CASE-2026-F6D96985",
    "SAKSHI-CASE-2026-508A1E4E",
    "SAKSHI-CASE-2026-C018C702",
    "SAKSHI-CASE-2026-FCF1783C",
    "SAKSHI-CASE-2026-B6C58AC0",
    "SAKSHI-CASE-2026-EB402877",
    "SAKSHI-FIR-TEST-0712",
    "SAKSHI-CASE-2026-0C14C106",
    "SAKSHI-CASE-2026-8BC5E5A1",
    "SAKSHI-CASE-2026-EBB264C5",
    "SAKSHI-CASE-2026-DEE55B59",
    "SAKSHI-CASE-2026-B8D94D63",
]

print("=== STARTING SAFE TEST DATA CLEANUP ===")

with engine.begin() as conn:
    # 1. Verify preserved case and evidence exist
    pres_case = conn.execute(text("SELECT case_id, title FROM cases WHERE case_id = :cid"), {"cid": PRESERVED_CASE_ID}).fetchone()
    assert pres_case is not None, f"Preserved case {PRESERVED_CASE_ID} not found in database!"
    print(f"Verified preserved case: {pres_case[0]} - '{pres_case[1]}'")

    pres_ev = conn.execute(text("SELECT evidence_id, case_id FROM evidence WHERE evidence_id = :eid"), {"eid": PRESERVED_EVIDENCE_ID}).fetchone()
    assert pres_ev is not None, f"Preserved evidence {PRESERVED_EVIDENCE_ID} not found!"
    assert pres_ev[1] == PRESERVED_CASE_ID, "Preserved evidence does not belong to preserved case!"
    print(f"Verified preserved evidence: {pres_ev[0]} under {pres_ev[1]}")

    # 2. Check total cases before cleanup
    total_before = conn.execute(text("SELECT COUNT(*) FROM cases")).scalar()
    print(f"Total cases before cleanup: {total_before}")
    assert total_before == 13, f"Expected 13 cases before cleanup, found {total_before}"

    # Verify that the test cases to delete do NOT include the preserved case
    assert PRESERVED_CASE_ID not in TEST_CASE_IDS, "CRITICAL ERROR: Preserved case ID found in deletion list!"

    # 3. Perform deletions in strict FK dependency order
    # Step A: rag_chunks
    del_chunks = conn.execute(
        text("DELETE FROM rag_chunks WHERE case_id = ANY(:cids) RETURNING chunk_id"),
        {"cids": TEST_CASE_IDS}
    ).fetchall()
    print(f"Deleted {len(del_chunks)} rag_chunks from test cases.")

    # Step B: rag_index_jobs
    del_jobs = conn.execute(
        text("DELETE FROM rag_index_jobs WHERE case_id = ANY(:cids) RETURNING job_id"),
        {"cids": TEST_CASE_IDS}
    ).fetchall()
    print(f"Deleted {len(del_jobs)} rag_index_jobs from test cases.")

    # Step C: rag_documents
    del_docs = conn.execute(
        text("DELETE FROM rag_documents WHERE case_id = ANY(:cids) RETURNING document_id"),
        {"cids": TEST_CASE_IDS}
    ).fetchall()
    print(f"Deleted {len(del_docs)} rag_documents from test cases.")

    # Step D: evidence
    del_evidence = conn.execute(
        text("DELETE FROM evidence WHERE case_id = ANY(:cids) RETURNING evidence_id"),
        {"cids": TEST_CASE_IDS}
    ).fetchall()
    print(f"Deleted {len(del_evidence)} evidence exhibits from test cases: {[e[0] for e in del_evidence]}")

    # Step E: case_assignments
    del_assignments = conn.execute(
        text("DELETE FROM case_assignments WHERE case_id = ANY(:cids) RETURNING id"),
        {"cids": TEST_CASE_IDS}
    ).fetchall()
    print(f"Deleted {len(del_assignments)} case assignments from test cases.")

    # Step F: cases
    del_cases = conn.execute(
        text("DELETE FROM cases WHERE case_id = ANY(:cids) RETURNING case_id"),
        {"cids": TEST_CASE_IDS}
    ).fetchall()
    print(f"Deleted {len(del_cases)} cases: {[c[0] for c in del_cases]}")
    assert len(del_cases) == 12, f"Expected 12 deleted cases, got {len(del_cases)}"

    # 4. Verify post-cleanup database state inside transaction
    total_cases_after = conn.execute(text("SELECT COUNT(*) FROM cases")).scalar()
    remaining_cases = conn.execute(text("SELECT case_id, title FROM cases")).fetchall()
    assert total_cases_after == 1, f"Expected exactly 1 case remaining, got {total_cases_after}"
    assert remaining_cases[0][0] == PRESERVED_CASE_ID, f"Remaining case {remaining_cases[0][0]} != {PRESERVED_CASE_ID}"

    total_evidence_after = conn.execute(text("SELECT COUNT(*) FROM evidence")).scalar()
    remaining_evidence = conn.execute(text("SELECT evidence_id, case_id FROM evidence")).fetchall()
    assert total_evidence_after == 1, f"Expected exactly 1 evidence remaining, got {total_evidence_after}"
    assert remaining_evidence[0][0] == PRESERVED_EVIDENCE_ID
    assert remaining_evidence[0][1] == PRESERVED_CASE_ID

    total_docs_after = conn.execute(text("SELECT COUNT(*) FROM rag_documents")).scalar()
    assert total_docs_after == 1

    total_chunks_after = conn.execute(text("SELECT COUNT(*) FROM rag_chunks")).scalar()
    assert total_chunks_after == 5

    print("\nDatabase transaction successfully committed.")

# 5. Clean test workspaces for the deleted test cases, preserving target workspace
def handle_remove_readonly(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

base_ws = r"C:\sakshi\workspaces"
for test_cid in TEST_CASE_IDS:
    assert test_cid != PRESERVED_CASE_ID, "CANNOT DELETE PRESERVED WORKSPACE"
    ws_path = os.path.join(base_ws, test_cid)
    if os.path.exists(ws_path):
        shutil.rmtree(ws_path, onexc=handle_remove_readonly)
        print(f"Cleaned up test workspace directory: {ws_path}")

# 6. Verify preserved workspace and FIR file
fir_file = os.path.join(base_ws, PRESERVED_CASE_ID, "evidence", "raw", PRESERVED_EVIDENCE_ID, "E00_synthetic_FIR.pdf")
assert os.path.exists(fir_file), f"CRITICAL: Preserved FIR file missing at {fir_file}!"
fir_size = os.path.getsize(fir_file)
assert fir_size == 3025, f"Preserved FIR size mismatch: {fir_size} != 3025"
print(f"Verified preserved FIR on disk: {fir_file} ({fir_size} bytes)")

print("\n=== SAFE DATABASE CLEANUP COMPLETED SUCCESSFULLY ===")
