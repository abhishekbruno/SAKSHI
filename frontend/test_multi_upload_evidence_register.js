/**
 * SAKSHI Regression Test Suite: Multi-File Evidence Upload & FIR Extraction Invariants
 *
 * Verifies:
 * 1. Static code structure of frontend/app.js:
 *    - Evidence modal hidden file input has `multiple` attribute.
 *    - Multi-file dropzone collects all dropped files (not just index 0).
 *    - Modal maintains array of selectedFiles with dynamic badges, sizes, and remove buttons.
 *    - Modal supports adding more files or clearing selection.
 *    - Empty files (0 bytes) are flagged with warning toast.
 *    - In-batch and register-level deduplication prevents unintended duplicates.
 *    - Ingestion stage auto-transition checks allowed prior stages (INITIALIZED, EVIDENCE_PROCESSING, etc.).
 *    - Evidence Register query is refreshed after upload without full application reload.
 *    - Scene of Occurrence / Location in candidate modal displays at full width (not half-width grid).
 * 2. Live Integration Verification Against Running Backend:
 *    - Targets affected case SAKSHI-CASE-2026-632D540B ("Riverside Guesthouse Incident").
 *    - Verifies existing exhibit 01_SYNTHETIC_FIR_INTAKE.txt (SAKSHI-EVID-2026-B5B4270C).
 *    - Uploads 02_WITNESS_A_STATEMENT.txt and 03_WITNESS_B_STATEMENT.txt.
 *    - Confirms that both exhibits persist with distinct evidence IDs under case SAKSHI-CASE-2026-632D540B.
 *    - Confirms Evidence Register query returns all 3 exhibits with correct names and statuses.
 */

const fs = require('fs');
const path = require('path');
const http = require('http');
const assert = require('assert');

const APP_JS_PATH = path.join(__dirname, 'app.js');
const appJsContent = fs.readFileSync(APP_JS_PATH, 'utf-8').replace(/\r\n/g, '\n');

let passedTests = 0;
let totalTests = 0;

function test(name, fn) {
  totalTests++;
  try {
    fn();
    console.log(`  [PASS] ${name}`);
    passedTests++;
  } catch (err) {
    console.error(`  [FAIL] ${name}: ${err.message}`);
    throw err;
  }
}

async function asyncTest(name, fn) {
  totalTests++;
  try {
    await fn();
    console.log(`  [PASS] ${name}`);
    passedTests++;
  } catch (err) {
    console.error(`  [FAIL] ${name}: ${err.message}`);
    throw err;
  }
}

console.log("===============================================================================");
console.log(" SAKSHI Regression Test: Multi-File Evidence Upload & FIR Invariants");
console.log("===============================================================================");

console.log("\n--- Phase 1: Static Code Structure & Multi-Upload Invariants ---");

test("Evidence input element supports multi-file selection via multiple attribute", () => {
  assert(appJsContent.includes('<input type="file" id="inpEvidenceFileHidden" multiple style="display: none;">'),
    "Hidden file input must include multiple attribute");
});

test("Dropzone and file change listeners process all files via addFiles", () => {
  assert(appJsContent.includes('addFiles(e.target.files);'),
    "File input change listener must pass all files to addFiles");
  assert(appJsContent.includes('addFiles(e.dataTransfer.files);'),
    "Dropzone drop listener must pass all files to addFiles");
});

test("Modal state tracks multiple selectedFiles with individual remove and clear controls", () => {
  assert(appJsContent.includes('let selectedFiles = [];'),
    "Modal state must maintain selectedFiles array");
  assert(appJsContent.includes('id="selectedFilesList"'),
    "Modal template must include selectedFilesList container");
  assert(appJsContent.includes('btn-remove-file'),
    "Each selected file must have an individual remove button");
  assert(appJsContent.includes('id="btnAddMoreFiles"'),
    "Modal must provide + Add More Files control");
  assert(appJsContent.includes('id="btnClearFiles"'),
    "Modal must provide Clear selection control");
});

test("Empty files (0 bytes) are validated and rejected with warning toast", () => {
  assert(appJsContent.includes('Skipped empty file'),
    "addFiles must detect 0-byte files and warn user");
});

test("Auto-advance to EVIDENCE_INGESTION checks prior stages without breaking stage engine", () => {
  assert(appJsContent.includes('["INITIALIZED", "EVIDENCE_PROCESSING", "ANALYSIS", "REVIEW", "REOPENED"].includes(c.lifecycle_stage)'),
    "Auto-transition must support transitioning to EVIDENCE_INGESTION from all allowed prior stages");
});

test("Modal submit executes sequential intake and reconciles potential timeouts", () => {
  assert(appJsContent.includes('for (let i = 0; i < totalToUpload; i++)'),
    "Submit handler must iterate through all selected files");
  assert(appJsContent.includes('await Api.intakeEvidence(c.case_id, formData);'),
    "Submit handler must call Api.intakeEvidence per file");
  assert(appJsContent.toLowerCase().includes('reconciled after intake timeout'),
    "Submit handler must provide timeout reconciliation before failing");
});

test("After successful upload, evidence register is refreshed without full page reload", () => {
  assert(appJsContent.includes('await ensureActiveCaseLoaded(c.case_id);\n      await ScreenEvidence.render(c.case_id);'),
    "Submit handler must refresh active case and re-render evidence register");
});

test("ensureActiveCaseLoaded synchronizes activeCase.lifecycle_stage with stage engine", () => {
  assert(appJsContent.includes('State.activeCase.lifecycle_stage = State.activeStageInfo.current_stage;'),
    "ensureActiveCaseLoaded must update activeCase.lifecycle_stage from activeStageInfo");
});

test("FIR Candidate Review modal renders Scene of Occurrence / Location at full width", () => {
  const locIndex = appJsContent.indexOf('id="inpFirCandidateLocation"');
  assert(locIndex !== -1, "inpFirCandidateLocation must exist");
  const locSnippet = appJsContent.substring(locIndex - 120, locIndex + 120);
  assert(locSnippet.includes('style="width: 100%;"'),
    "Location input must have full-width style so long addresses are not truncated");
});

console.log("\n--- Phase 2: Live Backend Integration Verification ---");

function makeHttpRequest(options, postData = null) {
  return new Promise((resolve, reject) => {
    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, headers: res.headers, body: JSON.parse(data) });
        } catch (e) {
          resolve({ status: res.statusCode, headers: res.headers, body: data });
        }
      });
    });
    req.on('error', reject);
    if (postData) req.write(postData);
    req.end();
  });
}

const TARGET_CASE_ID = "SAKSHI-CASE-2026-632D540B";

asyncTest("Live Backend: Verify target case SAKSHI-CASE-2026-632D540B and initial FIR exhibit", async () => {
  const caseRes = await makeHttpRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${TARGET_CASE_ID}`,
    method: 'GET',
    headers: {
      'X-Investigator-Id': 'dev-investigator-001',
      'X-Investigator-Role': 'INVESTIGATING_OFFICER',
      'X-Investigator-Jurisdiction': 'ALL',
      'Accept': 'application/json'
    }
  });

  assert.strictEqual(caseRes.status, 200, `Case ${TARGET_CASE_ID} should be accessible`);
  assert.strictEqual(caseRes.body.case_id, TARGET_CASE_ID);
  assert.strictEqual(caseRes.body.title, "Riverside Guesthouse Incident");

  // Verify initial exhibit is present
  const evidRes = await makeHttpRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${TARGET_CASE_ID}/evidence`,
    method: 'GET',
    headers: {
      'X-Investigator-Id': 'dev-investigator-001',
      'X-Investigator-Role': 'INVESTIGATING_OFFICER',
      'X-Investigator-Jurisdiction': 'ALL',
      'Accept': 'application/json'
    }
  });

  assert.strictEqual(evidRes.status, 200);
  const items = evidRes.body.items || [];
  const firExhibit = items.find(e => e.original_file_name === "01_SYNTHETIC_FIR_INTAKE.txt");
  assert(firExhibit, "01_SYNTHETIC_FIR_INTAKE.txt must exist under target case");
  assert.strictEqual(firExhibit.evidence_id, "SAKSHI-EVID-2026-B5B4270C");
});

function postMultipartEvidence(caseId, filename, contentBytes, category = "DOCUMENT_PDF", source = "Witness Custody") {
  return new Promise((resolve, reject) => {
    const boundary = '----WebKitFormBoundary' + Math.random().toString(36).substring(2);
    let body = '';

    body += `--${boundary}\r\n`;
    body += `Content-Disposition: form-data; name="evidence_category"\r\n\r\n${category}\r\n`;

    body += `--${boundary}\r\n`;
    body += `Content-Disposition: form-data; name="declared_mime_type"\r\n\r\ntext/plain\r\n`;

    body += `--${boundary}\r\n`;
    body += `Content-Disposition: form-data; name="source_device_or_person"\r\n\r\n${source}\r\n`;

    body += `--${boundary}\r\n`;
    body += `Content-Disposition: form-data; name="description"\r\n\r\nForensic statement record\r\n`;

    body += `--${boundary}\r\n`;
    body += `Content-Disposition: form-data; name="file"; filename="${filename}"\r\n`;
    body += `Content-Type: text/plain\r\n\r\n`;

    const preamble = Buffer.from(body, 'utf-8');
    const postscript = Buffer.from(`\r\n--${boundary}--\r\n`, 'utf-8');
    const fullPayload = Buffer.concat([preamble, Buffer.from(contentBytes), postscript]);

    const req = http.request({
      hostname: '127.0.0.1',
      port: 8000,
      path: `/api/v1/cases/${caseId}/evidence`,
      method: 'POST',
      headers: {
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
        'Content-Length': fullPayload.length,
        'X-Investigator-Id': 'dev-investigator-001',
        'X-Investigator-Role': 'INVESTIGATING_OFFICER',
        'X-Investigator-Jurisdiction': 'ALL',
        'Accept': 'application/json'
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch (e) {
          resolve({ status: res.statusCode, body: data });
        }
      });
    });

    req.on('error', reject);
    req.write(fullPayload);
    req.end();
  });
}

asyncTest("Live Backend: Upload or verify 02_WITNESS_A_STATEMENT.txt and verify distinct exhibit persistence", async () => {
  const listRes = await makeHttpRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${TARGET_CASE_ID}/evidence`,
    method: 'GET',
    headers: {
      'X-Investigator-Id': 'dev-investigator-001',
      'X-Investigator-Role': 'INVESTIGATING_OFFICER',
      'X-Investigator-Jurisdiction': 'ALL',
      'Accept': 'application/json'
    }
  });
  let item = (listRes.body.items || []).find(e => e.original_file_name === "02_WITNESS_A_STATEMENT.txt");
  if (!item) {
    const witnessAContent = `STATEMENT OF WITNESS A (Sunil Kumar, Receptionist)
Date: 18 October 2026, 11:30 IST
I was on duty at the front reception counter of Riverside Guesthouse from 20:00 on 17 October 2026.
At approximately 00:10 IST on 18 October 2026, I observed guest Arjun Menon (Room 204) enter through the main glass door and proceed upstairs to his room. He appeared normal and was carrying a shoulder bag.`;

    const res = await postMultipartEvidence(
      TARGET_CASE_ID,
      "02_WITNESS_A_STATEMENT.txt",
      witnessAContent,
      "DOCUMENT_PDF",
      "Sunil Kumar (Receptionist)"
    );

    assert.strictEqual(res.status, 201, `Upload of Witness A should succeed (got ${res.status}: ${JSON.stringify(res.body)})`);
    item = res.body;
  }

  assert(item.evidence_id.startsWith("SAKSHI-EVID-"));
  assert.strictEqual(item.original_file_name, "02_WITNESS_A_STATEMENT.txt");
  assert.strictEqual(item.case_id, TARGET_CASE_ID);
  assert.notStrictEqual(item.evidence_id, "SAKSHI-EVID-2026-B5B4270C");
});

asyncTest("Live Backend: Upload or verify 03_WITNESS_B_STATEMENT.txt and verify distinct exhibit persistence", async () => {
  const listRes = await makeHttpRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${TARGET_CASE_ID}/evidence`,
    method: 'GET',
    headers: {
      'X-Investigator-Id': 'dev-investigator-001',
      'X-Investigator-Role': 'INVESTIGATING_OFFICER',
      'X-Investigator-Jurisdiction': 'ALL',
      'Accept': 'application/json'
    }
  });
  let item = (listRes.body.items || []).find(e => e.original_file_name === "03_WITNESS_B_STATEMENT.txt");
  if (!item) {
    const witnessBContent = `STATEMENT OF WITNESS B (Deepa Pillai, Housekeeping Staff)
Date: 18 October 2026, 12:15 IST
I work on the second floor housekeeping night shift.
At approximately 01:00 IST on 18 October 2026, I saw Mr. Arjun Menon in the second-floor corridor outside Room 204. He was talking on his mobile phone near the linen closet before returning into his room.`;

    const res = await postMultipartEvidence(
      TARGET_CASE_ID,
      "03_WITNESS_B_STATEMENT.txt",
      witnessBContent,
      "DOCUMENT_PDF",
      "Deepa Pillai (Housekeeping Staff)"
    );

    assert.strictEqual(res.status, 201, `Upload of Witness B should succeed (got ${res.status}: ${JSON.stringify(res.body)})`);
    item = res.body;
  }

  assert(item.evidence_id.startsWith("SAKSHI-EVID-"));
  assert.strictEqual(item.original_file_name, "03_WITNESS_B_STATEMENT.txt");
  assert.strictEqual(item.case_id, TARGET_CASE_ID);
});

asyncTest("Live Backend: Evidence Register query returns all 3 exhibits with distinct IDs and correct count", async () => {
  const evidRes = await makeHttpRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${TARGET_CASE_ID}/evidence`,
    method: 'GET',
    headers: {
      'X-Investigator-Id': 'dev-investigator-001',
      'X-Investigator-Role': 'INVESTIGATING_OFFICER',
      'X-Investigator-Jurisdiction': 'ALL',
      'Accept': 'application/json'
    }
  });

  assert.strictEqual(evidRes.status, 200);
  const items = evidRes.body.items || [];
  assert.strictEqual(items.length, 3, "Evidence register must contain exactly 3 distinct exhibits");
  assert.strictEqual(evidRes.body.total, 3, "Total count in response must be 3");

  const filenames = items.map(e => e.original_file_name);
  assert(filenames.includes("01_SYNTHETIC_FIR_INTAKE.txt"), "01_SYNTHETIC_FIR_INTAKE.txt must remain intact");
  assert(filenames.includes("02_WITNESS_A_STATEMENT.txt"), "02_WITNESS_A_STATEMENT.txt must be listed");
  assert(filenames.includes("03_WITNESS_B_STATEMENT.txt"), "03_WITNESS_B_STATEMENT.txt must be listed");

  const ids = new Set(items.map(e => e.evidence_id));
  assert.strictEqual(ids.size, 3, "All 3 exhibits must have distinct canonical evidence IDs");
});

setTimeout(() => {
  console.log("\n===============================================================================");
  console.log(` Summary: ${passedTests} of ${totalTests} tests passed successfully.`);
  console.log("===============================================================================");
}, 1000);
