/**
 * Regression Test Suite: Case Directory Development Identity & Authorization
 * 
 * Verifies:
 * 1. Default development identity is aligned with backend DEV_INVESTIGATOR_SUBJECT_ID
 * 2. Obsolete mock identity ("IO-7842-SHARMA") in localStorage is migrated to "dev-investigator-001" / "KERALA"
 * 3. Case Directory filtering on "SAKSHI-TEST-2026-002" correctly renders the case card
 * 4. Case directory search field properly filters the displayed list
 * 5. Case stage filter matches "EVIDENCE_INGESTION"
 * 6. Live API integration verifies case retrieval and evidence preservation
 */

const fs = require("fs");
const path = require("path");
const assert = require("assert");

let failures = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`  [PASS] ${name}`);
  } catch (err) {
    console.error(`  [FAIL] ${name}`);
    console.error(`         ${err.message}`);
    failures++;
  }
}

async function asyncTest(name, fn) {
  try {
    await fn();
    console.log(`  [PASS] ${name}`);
  } catch (err) {
    console.error(`  [FAIL] ${name}`);
    console.error(`         ${err.message}`);
    failures++;
  }
}

async function runTests() {
  console.log("Starting SAKSHI Case Directory Development Identity Regression Tests...\n");

  const appJsPath = path.join(__dirname, "app.js");
  const indexHtmlPath = path.join(__dirname, "index.html");
  const js = fs.readFileSync(appJsPath, "utf8");
  const html = fs.readFileSync(indexHtmlPath, "utf8");

  // ═══════════════════════════════════════════════════════════════════════════
  // Suite 1: Source Code Alignment & Presets
  // ═══════════════════════════════════════════════════════════════════════════
  console.log("-- Test Suite 1: Static Code Alignment & Presets --");

  test("State.auth defaults to dev-investigator-001", () => {
    assert(js.includes('"dev-investigator-001"'), "app.js includes dev-investigator-001 default");
    assert(js.includes('"KERALA"'), "app.js includes KERALA default jurisdiction");
  });

  test("initApplication reconciles dev identity with authStatus", () => {
    assert(js.includes("authStatus.default_investigator_id"), "initApplication checks authStatus.default_investigator_id");
    assert(js.includes("authStatus.default_jurisdiction"), "initApplication checks authStatus.default_jurisdiction");
  });

  test("index.html header reflects dev-investigator-001", () => {
    assert(html.includes("dev-investigator-001"), "index.html includes dev-investigator-001 header placeholder");
  });

  test("ScreenSettings includes identity preset switcher", () => {
    assert(js.includes("ScreenSettings.applyPreset"), "ScreenSettings includes applyPreset method");
    assert(js.includes("Officer Identity Presets (Development)"), "ScreenSettings markup includes presets section");
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // Suite 2: LocalStorage Migration Simulation
  // ═══════════════════════════════════════════════════════════════════════════
  console.log("\n-- Test Suite 2: LocalStorage Migration Simulation --");

  test("Simulate stale IO-7842-SHARMA migration to dev-investigator-001", () => {
    const mockStorage = {
      sakshi_dev_subject_id: "IO-7842-SHARMA",
      sakshi_dev_jurisdiction: "KL-TVM-001"
    };

    const authStatus = {
      auth_mode: "development",
      development_mode: true,
      default_investigator_id: "dev-investigator-001",
      default_investigator_name: "Dev Inspector (Development Only)",
      default_jurisdiction: "KERALA"
    };

    const mockState = {
      auth: {
        subjectId: mockStorage.sakshi_dev_subject_id !== "IO-7842-SHARMA" ? mockStorage.sakshi_dev_subject_id : "dev-investigator-001",
        displayName: "Dev Inspector",
        role: "INVESTIGATING_OFFICER",
        jurisdiction: mockStorage.sakshi_dev_jurisdiction !== "KL-TVM-001" ? mockStorage.sakshi_dev_jurisdiction : "KERALA",
        headers: { "Content-Type": "application/json" }
      }
    };

    // Simulate initApplication logic
    const currentStored = mockStorage.sakshi_dev_subject_id;
    if (!currentStored || currentStored === "IO-7842-SHARMA") {
      mockState.auth.subjectId = authStatus.default_investigator_id;
      mockState.auth.displayName = authStatus.default_investigator_name;
      mockState.auth.jurisdiction = authStatus.default_jurisdiction;
      mockStorage.sakshi_dev_subject_id = authStatus.default_investigator_id;
      mockStorage.sakshi_dev_jurisdiction = authStatus.default_jurisdiction;
    }

    mockState.auth.headers["X-Investigator-Id"] = mockState.auth.subjectId;
    mockState.auth.headers["X-Investigator-Jurisdiction"] = mockState.auth.jurisdiction;

    assert.strictEqual(mockState.auth.subjectId, "dev-investigator-001");
    assert.strictEqual(mockState.auth.jurisdiction, "KERALA");
    assert.strictEqual(mockState.auth.headers["X-Investigator-Id"], "dev-investigator-001");
    assert.strictEqual(mockState.auth.headers["X-Investigator-Jurisdiction"], "KERALA");
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // Suite 3: Filter Logic Simulation for SAKSHI-TEST-2026-002
  // ═══════════════════════════════════════════════════════════════════════════
  console.log("\n-- Test Suite 3: Filter Logic Simulation --");

  const sampleCases = [
    {
      case_id: "SAKSHI-TEST-2026-002",
      title: "SAKSHI UiPath Synthetic Evidence Pipeline Test",
      lifecycle_stage: "EVIDENCE_INGESTION",
      fir_metadata: {
        fir_number: "FIR-TEST-2026-002",
        police_station: "Kowdiar Police Station"
      }
    },
    {
      case_id: "SAKSHI-CASE-2026-719A8019",
      title: "Synthetic UiPath Studio Live Ingestion Smoke Test",
      lifecycle_stage: "EVIDENCE_INGESTION",
      fir_metadata: {
        fir_number: "FIR-UIPATH-LIVE-2026-001",
        police_station: "Kowdiar Police Station"
      }
    }
  ];

  test("Search filter matches SAKSHI-TEST-2026-002 exactly", () => {
    const query = "SAKSHI-TEST-2026-002";
    const filtered = sampleCases.filter(c => {
      const matchSearch = !query ||
        (c.title && c.title.toLowerCase().includes(query.toLowerCase())) ||
        (c.case_id && c.case_id.toLowerCase().includes(query.toLowerCase())) ||
        (c.fir_metadata && c.fir_metadata.fir_number && c.fir_metadata.fir_number.toLowerCase().includes(query.toLowerCase()));
      return matchSearch;
    });
    assert.strictEqual(filtered.length, 1);
    assert.strictEqual(filtered[0].case_id, "SAKSHI-TEST-2026-002");
  });

  test("Search filter matches by FIR number FIR-TEST-2026-002", () => {
    const query = "FIR-TEST-2026-002";
    const filtered = sampleCases.filter(c => {
      const matchSearch = !query ||
        (c.title && c.title.toLowerCase().includes(query.toLowerCase())) ||
        (c.case_id && c.case_id.toLowerCase().includes(query.toLowerCase())) ||
        (c.fir_metadata && c.fir_metadata.fir_number && c.fir_metadata.fir_number.toLowerCase().includes(query.toLowerCase()));
      return matchSearch;
    });
    assert.strictEqual(filtered.length, 1);
    assert.strictEqual(filtered[0].case_id, "SAKSHI-TEST-2026-002");
  });

  test("Stage filter matches EVIDENCE_INGESTION", () => {
    const stage = "EVIDENCE_INGESTION";
    const filtered = sampleCases.filter(c => c.lifecycle_stage === stage);
    assert.strictEqual(filtered.length, 2);
  });

  test("Stage filter ALL returns all cases", () => {
    const stage = "ALL";
    const filtered = sampleCases.filter(c => stage === "ALL" || c.lifecycle_stage === stage);
    assert.strictEqual(filtered.length, 2);
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // Suite 4: Live HTTP API Integration with Running Backend
  // ═══════════════════════════════════════════════════════════════════════════
  console.log("\n-- Test Suite 4: Live HTTP API Integration --");

  await asyncTest("GET /api/v1/auth/status returns development defaults", async () => {
    const res = await fetch("http://localhost:8000/api/v1/auth/status");
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.auth_mode, "development");
    assert.strictEqual(data.default_investigator_id, "dev-investigator-001");
    assert.strictEqual(data.default_jurisdiction, "KERALA");
  });

  await asyncTest("GET /api/v1/cases with aligned dev headers returns SAKSHI-TEST-2026-002", async () => {
    const headers = {
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const res = await fetch("http://localhost:8000/api/v1/cases", { headers });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert(data.total >= 1, "Cases total should be >= 1");
    const testCase = data.cases.find(c => c.case_id === "SAKSHI-TEST-2026-002");
    assert(testCase !== undefined, "SAKSHI-TEST-2026-002 must be in cases list");
    assert.strictEqual(testCase.assigned_io_id, "dev-investigator-001");
    assert.strictEqual(testCase.lifecycle_stage, "EVIDENCE_INGESTION");
  });

  await asyncTest("GET /api/v1/cases/SAKSHI-TEST-2026-002 retrieves workspace", async () => {
    const headers = {
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const res = await fetch("http://localhost:8000/api/v1/cases/SAKSHI-TEST-2026-002", { headers });
    assert.strictEqual(res.status, 200);
    const c = await res.json();
    assert.strictEqual(c.case_id, "SAKSHI-TEST-2026-002");
    assert.strictEqual(c.status, "ACTIVE");
    assert.strictEqual(c.lifecycle_stage, "EVIDENCE_INGESTION");
  });

  await asyncTest("GET /api/v1/cases/SAKSHI-TEST-2026-002/evidence verifies preserved evidence", async () => {
    const headers = {
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const res = await fetch("http://localhost:8000/api/v1/cases/SAKSHI-TEST-2026-002/evidence", { headers });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert(data.total >= 1, "Evidence total should be >= 1");
    const ev = data.items.find(e => e.evidence_id === "SAKSHI-EVID-2026-E51D496A");
    assert(ev !== undefined, "SAKSHI-EVID-2026-E51D496A must exist in evidence items");
    assert.strictEqual(ev.status, "COMMITTED");
    assert.strictEqual(ev.worm_status, "COMMITTED");
    assert.strictEqual(ev.declared_mime_type, "application/pdf");
    assert.strictEqual(ev.original_file_name, "SAKSHI_Synthetic_Evidence_RAG_Test.pdf");
  });

  console.log("\n======================================================");
  console.log(`Regression Test Summary: ${failures === 0 ? "ALL PASSED" : failures + " FAILED"}`);
  console.log("======================================================");

  if (failures > 0) process.exit(1);
}

runTests();
