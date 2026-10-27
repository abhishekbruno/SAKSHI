import json
import httpx

client = httpx.Client(timeout=10.0)
headers = {
    'X-Investigator-Id': 'dev-investigator-001',
    'X-Investigator-Role': 'INVESTIGATING_OFFICER',
    'X-Investigator-Jurisdiction': 'KERALA'
}
res = client.get('http://127.0.0.1:8000/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/evidence', headers=headers)
data = res.json()
print('Total exhibits in case:', data.get('total'))
for item in data.get('items', []):
    eid = item.get('evidence_id')
    fn = item.get('original_file_name')
    cat = item.get('evidence_category')
    st = item.get('status')
    integ = item.get('integrity_status')
    lock = item.get('lock_status')
    enc = item.get('encryption_status')
    print(f"{eid} :: {fn} :: {cat} :: {st} :: {integ} :: {lock} :: {enc}")
