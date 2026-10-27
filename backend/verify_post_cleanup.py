import os
import sys
import json
import urllib.request
from sqlalchemy import text

sys.path.insert(0, os.path.abspath("backend"))
from app.db.session import engine

headers_supervisor = {
    "X-Investigator-Id": "dev-investigator-001",
    "X-Investigator-Role": "SUPERVISORY_OFFICER",
    "X-Investigator-Jurisdiction": "KERALA"
}

headers_io = {
    "X-Investigator-Id": "dev-investigator-001",
    "X-Investigator-Role": "INVESTIGATING_OFFICER",
    "X-Investigator-Jurisdiction": "KERALA"
}

headers_unauthorized = {
    "X-Investigator-Id": "external-officer-999",
    "X-Investigator-Role": "INVESTIGATING_OFFICER",
    "X-Investigator-Jurisdiction": "TAMIL_NADU"
}

print("=== RUNNING POST-CLEANUP VERIFICATION ===")

# 1. Verify Case Directory via API
print("\n[1] Verifying Case Directory API (/api/v1/cases)...")
req = urllib.request.Request("http://127.0.0.1:8000/api/v1/cases", headers=headers_supervisor)
with urllib.request.urlopen(req) as resp:
    assert resp.status == 200
    data = json.loads(resp.read().decode())
    cases = data.get("cases", [])
    total = data.get("total")
    print(f"Total cases returned: {len(cases)}, total count: {total}")
    assert total == 1, f"Expected exactly 1 case, got {total}"
    assert len(cases) == 1
    c = cases[0]
    assert c["case_id"] == "SAKSHI-CASE-2026-C5A64E99"
    assert "Riverside Guesthouse Incident" in c["title"]
    assert c["fir_metadata"]["fir_number"] == "FIR-SYN-2026-1042"
    print(f"PASS: Case Directory contains solely the preserved case '{c['case_id']}'")

# 2. Verify Preserved FIR Evidence
print("\n[2] Verifying Evidence registration (/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/evidence)...")
req_ev = urllib.request.Request("http://127.0.0.1:8000/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/evidence", headers=headers_io)
with urllib.request.urlopen(req_ev) as resp:
    assert resp.status == 200
    ev_data = json.loads(resp.read().decode())
    ev_items = ev_data.get("items", [])
    print(f"Evidence exhibits returned: {len(ev_items)}, total: {ev_data.get('total')}")
    assert len(ev_items) == 1, f"Expected 1 evidence exhibit, got {len(ev_items)}"
    ev = ev_items[0]
    assert ev["evidence_id"] == "SAKSHI-EVID-2026-54C01EA8"
    assert ev["original_file_name"] == "E00_synthetic_FIR.pdf"
    assert ev["evidence_category"] == "DOCUMENT_PDF"
    print(f"PASS: Evidence registered under {ev['evidence_id']} ({ev['original_file_name']})")

# 3. Verify Authenticated Evidence File (/file)
print("\n[3] Verifying authenticated evidence file retrieval (/file)...")
req_file = urllib.request.Request("http://127.0.0.1:8000/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/evidence/SAKSHI-EVID-2026-54C01EA8/file", headers=headers_io)
with urllib.request.urlopen(req_file) as resp:
    assert resp.status == 200
    content_type = resp.headers.get("Content-Type")
    content_len = resp.headers.get("Content-Length")
    pdf_bytes = resp.read()
    print(f"Status: {resp.status}, Content-Type: {content_type}, Size: {len(pdf_bytes)} bytes")
    assert content_type == "application/pdf"
    assert len(pdf_bytes) == 3025
    assert pdf_bytes.startswith(b"%PDF"), "Content is not a valid PDF"
    print("PASS: Authentic FIR PDF accessible with correct MIME type and size")

# 4. Verify Extracted Facts & Provenance
print("\n[4] Verifying extracted facts and provenance (/extracted-facts)...")
req_facts = urllib.request.Request("http://127.0.0.1:8000/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/evidence/SAKSHI-EVID-2026-54C01EA8/extracted-facts", headers=headers_io)
with urllib.request.urlopen(req_facts) as resp:
    assert resp.status == 200
    facts_data = json.loads(resp.read().decode())
    facts = facts_data.get("facts", [])
    passages = facts_data.get("important_source_passages", [])
    print(f"Facts count: {len(facts)}, Source passages count: {len(passages)}")
    assert len(facts) >= 20, f"Expected >= 20 facts, got {len(facts)}"
    assert len(passages) >= 5, f"Expected >= 5 source passages, got {len(passages)}"
    print("PASS: Extracted facts, source passages, and provenance intact")

# 5. Verify Integrity and Storage-Protection Statuses
print("\n[5] Verifying evidence integrity and storage protection statuses in database...")
with engine.connect() as conn:
    row = conn.execute(text("""
        SELECT
            status, worm_status, integrity_status, lock_status, encryption_status,
            checksum_sha256, checksum_sha3_512, lock_storage_reference, encryption_storage_reference
        FROM evidence
        WHERE evidence_id = 'SAKSHI-EVID-2026-54C01EA8'
    """)).fetchone()
    assert row is not None
    print(f"  status: {row[0]}")
    print(f"  worm_status: {row[1]}")
    print(f"  integrity_status: {row[2]}")
    print(f"  lock_status: {row[3]}")
    print(f"  encryption_status: {row[4]}")
    print(f"  checksum_sha256: {row[5]}")
    assert row[0] == "COMMITTED"
    assert row[1] == "COMMITTED"
    assert row[2] == "VERIFIED"
    assert row[3] == "LOCKED"
    assert row[4] == "ENCRYPTED"
    assert row[5] is not None
    print("PASS: Integrity and storage-protection statuses are intact and unchanged")

# 6. Verify Case-Scoped Authorization
print("\n[6] Verifying case-scoped authorization...")
# Unauthorized officer should be denied
try:
    req_denied = urllib.request.Request("http://127.0.0.1:8000/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/evidence/SAKSHI-EVID-2026-54C01EA8/file", headers=headers_unauthorized)
    urllib.request.urlopen(req_denied)
    raise AssertionError("Unauthorized request should have been rejected!")
except urllib.error.HTTPError as e:
    assert e.code == 403, f"Expected 403 Forbidden, got {e.code}"
    print(f"PASS: Unauthorized access correctly rejected with HTTP 403")

# Authorized officer should be permitted
req_allowed = urllib.request.Request("http://127.0.0.1:8000/api/v1/cases/SAKSHI-CASE-2026-C5A64E99", headers=headers_io)
with urllib.request.urlopen(req_allowed) as resp:
    assert resp.status == 200
    print("PASS: Authorized investigator successfully accessed case")

print("\n=== ALL POST-CLEANUP VERIFICATIONS PASSED ===")
