/**
 * SAKSHI Redesign & Workflow Verification Test Suite
 * Validates:
 * 1. Scenario A: Empty case registration, truthful empty states across all screens,
 *    6-step progress indicator, guided next action card, lifecycle transition error handling.
 * 2. Scenario B: Preserved synthetic PDF evidence in SAKSHI-TEST-2026-002 (SAKSHI-EVID-2026-E51D496A),
 *    WORM commit, dual-hash integrity, and RAG semantic retrieval with 'BLUE ORCHID 7319'.
 * 3. Case Directory search, filters, single-click navigation, and RBAC/ABAC isolation.
 * 4. Evidence upload modal categories, format guidance, and safe timeout reconciliation.
 * 5. Primary navigation structure (Cases, Evidence, Timeline, Review Findings, Activity & Audit, Admin).
 */

const assert = require("assert");
const fs = require("fs");

console.log("=================================================================");
console.log("Starting SAKSHI UI/UX Redesign & Workflow Verification Tests...");
console.log("=================================================================\n");

let passes = 0;
let failures = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  [PASS] ${name}`);
    passes++;
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
    passes++;
  } catch (err) {
    console.error(`  [FAIL] ${name}`);
    console.error(`         ${err.message}`);
    failures++;
  }
}

const html = fs.readFileSync("frontend/index.html", "utf8");
const appJs = fs.readFileSync("frontend/app.js", "utf8");
const styleCss = fs.readFileSync("frontend/style.css", "utf8");

(async () => {
  // ─────────────────────────────────────────────────────────────────────────
  // Suite 1: Primary Application Navigation Redesign
  // ─────────────────────────────────────────────────────────────────────────
  console.log("-- Test Suite 1: Primary Navigation Redesign --");

  test("Primary navigation contains 'Cases'", () => {
    assert(html.includes('id="navCases"') && html.includes("Cases"));
  });

  test("Primary navigation contains 'Evidence'", () => {
    assert(html.includes('id="navEvidence"') && html.includes("Evidence"));
  });

  test("Primary navigation contains 'Timeline'", () => {
    assert(html.includes('id="navTimeline"') && html.includes("Timeline"));
  });

  test("Primary navigation contains 'Review Findings'", () => {
    assert(html.includes('id="navFindings"') && html.includes("Review Findings"));
  });

  test("Primary navigation contains 'Activity & Audit'", () => {
    assert(html.includes('id="navAudit"') && html.includes("Activity & Audit"));
  });

  test("Primary navigation contains conditional 'Administration'", () => {
    assert(html.includes('id="navAdmin"') && html.includes("Administration"));
    assert(appJs.includes("updateSidebarActiveCaseContext"));
  });

  test("Active case context indicator present in sidebar", () => {
    assert(html.includes('id="sidebarActiveCaseBox"'));
    assert(html.includes('id="sidebarActiveCaseId"'));
    assert(html.includes('id="sidebarActiveCaseStage"'));
  });

  test("Route #/cases/:id/findings registered and ScreenFindings defined", () => {
    assert(appJs.includes("pattern: /^#\\/cases\\/([A-Za-z0-9_-]+)\\/findings$/"));
    assert(appJs.includes("const ScreenFindings = {"));
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Suite 2: Guided Case Overview & 6-Step Workflow
  // ─────────────────────────────────────────────────────────────────────────
  console.log("\n-- Test Suite 2: Guided Case Overview & 6-Step Workflow --");

  test("6-step progress indicator mapped to authoritative backend stages", () => {
    assert(appJs.includes("1. Register case") || appJs.includes("Register Case"));
    assert(appJs.includes("2. Collect evidence") || appJs.includes("Collect Evidence"));
    assert(appJs.includes("3. Verify evidence") || appJs.includes("Verify Evidence"));
    assert(appJs.includes("4. Review timeline") || appJs.includes("Review Timeline"));
    assert(appJs.includes("5. Review findings") || appJs.includes("Review Findings"));
    assert(appJs.includes("6. Complete authorized review") || appJs.includes("Complete Authorized Review"));
  });

  test("Guided Next Action Card dynamically calculated from lifecycle stage", () => {
    assert(appJs.includes("guided-next-action-card"));
    assert(appJs.includes("nextActionTitle"));
    assert(appJs.includes("nextActionDesc"));
    assert(appJs.includes("nextActionButtonHtml"));
  });

  test("Structured API error formatter prevents '[object Object]' messages", () => {
    assert(appJs.includes("formatErrorMessage(errData, status"));
    assert(appJs.includes("Field '") || appJs.includes("Array.isArray(errData.detail)"));
  });

  test("Stage transition payload matches backend schema: { lifecycle_stage: targetStage }", () => {
    assert(appJs.includes("JSON.stringify({ lifecycle_stage: targetStage })"));
    assert(!appJs.includes("JSON.stringify({ target_stage: targetStage })"));
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Suite 3: Truthful Empty States & Evidence Provenance
  // ─────────────────────────────────────────────────────────────────────────
  console.log("\n-- Test Suite 3: Truthful Empty States & Evidence Provenance --");

  test("Timeline checks evidenceList length and shows truthful empty state for 0 exhibits", () => {
    assert(appJs.includes("No Timeline Events Available Yet"));
    assert(appJs.includes("A case with zero exhibits contains no verified events"));
  });

  test("Investigation Gaps checks evidenceList length and shows truthful empty state for 0 exhibits", () => {
    assert(appJs.includes("No Investigation Gaps Generated Yet"));
    assert(appJs.includes("No evidence exhibits have been uploaded to this case docket yet"));
  });

  test("Analytical Observations checks evidenceList length and shows truthful empty state for 0 exhibits", () => {
    assert(appJs.includes("No Analytical Observations Generated Yet"));
    assert(appJs.includes("Analytical reasoning traces and contradiction checks are derived strictly from verified case exhibits"));
  });

  test("RAG Search checks evidenceList length and shows truthful empty state for 0 exhibits", () => {
    assert(appJs.includes("No Evidence Uploaded Yet"));
    assert(appJs.includes("Forensic document search (RAG) requires committed textual exhibits"));
  });

  test("Temporal contradiction card is NOT shown on single-exhibit cases without conflicting data", () => {
    assert(appJs.includes("cctvExhibit && witnessExhibit"));
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Suite 4: Evidence Collection & Upload Workflow
  // ─────────────────────────────────────────────────────────────────────────
  console.log("\n-- Test Suite 4: Evidence Collection & Upload Workflow --");

  test("Evidence modal uses official backend EvidenceCategory enum options", () => {
    assert(appJs.includes('value="DOCUMENT_PDF"'));
    assert(appJs.includes('value="SCENE_PHOTO"'));
    assert(appJs.includes('value="AUTOPSY_PHOTO"'));
    assert(appJs.includes('value="AUDIO_RECORDING"'));
    assert(appJs.includes('value="CDR_SPREADSHEET"'));
    assert(appJs.includes('value="DIGITAL_DEVICE_EXTRACTION"'));
    assert(appJs.includes('value="OTHER"'));
  });

  test("Evidence modal explains why category is required", () => {
    assert(appJs.includes("Why category is required:"));
  });

  test("Evidence modal provides supported file format guidance", () => {
    assert(appJs.includes("Supported file types:"));
  });

  test("Safe intake timeout reconciliation implemented to prevent duplicate intake", () => {
    assert(appJs.includes("Api.listEvidence(c.case_id)"));
    assert(appJs.includes("matched.evidence_id"));
    assert(appJs.includes("EXHIBIT_RECONCILED"));
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Suite 5: Live API Integration - Scenario A (Empty Case Lifecycle)
  // ─────────────────────────────────────────────────────────────────────────
  console.log("\n-- Test Suite 5: Live API Integration - Scenario A (Empty Case) --");

  let createdCaseId = null;

  await asyncTest("Register new case through supported API workflow", async () => {
    const headers = {
      "Content-Type": "application/json",
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const payload = {
      title: "Scenario A - Empty Inquest Verification Case",
      fir_metadata: {
        fir_number: `FIR-SCENARIO-A-${Date.now().toString().slice(-4)}`,
        police_station: "Cantonment Police Station",
        incident_date: new Date().toISOString(),
        report_date: new Date().toISOString(),
        incident_location: "Sector 9 Railway Crossing",
        jurisdiction_code: "KERALA"
      }
    };
    const res = await fetch("http://localhost:8000/api/v1/cases", {
      method: "POST",
      headers,
      body: JSON.stringify(payload)
    });
    assert.strictEqual(res.status, 201, `Expected HTTP 201, got ${res.status}`);
    const data = await res.json();
    assert(data.case_id, "Case ID must be returned");
    assert.strictEqual(data.lifecycle_stage, "INITIALIZED");
    assert.strictEqual(data.assigned_io_id, "dev-investigator-001");
    createdCaseId = data.case_id;
  });

  await asyncTest("Newly registered case appears in Case Directory", async () => {
    const headers = {
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const res = await fetch("http://localhost:8000/api/v1/cases", { headers });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    const found = data.cases.find(c => c.case_id === createdCaseId);
    assert(found !== undefined, `Created case ${createdCaseId} must appear in directory`);
    assert.strictEqual(found.lifecycle_stage, "INITIALIZED");
  });

  await asyncTest("Empty case has zero exhibits", async () => {
    const headers = {
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const res = await fetch(`http://localhost:8000/api/v1/cases/${createdCaseId}/evidence`, { headers });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.total, 0, "Exhibit count must be exactly 0");
    assert.strictEqual(data.items.length, 0);
  });

  await asyncTest("Permitted stage transition: INITIALIZED -> EVIDENCE_INGESTION succeeds", async () => {
    const headers = {
      "Content-Type": "application/json",
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const res = await fetch(`http://localhost:8000/api/v1/cases/${createdCaseId}/stage`, {
      method: "POST",
      headers,
      body: JSON.stringify({ lifecycle_stage: "EVIDENCE_INGESTION" })
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.lifecycle_stage, "EVIDENCE_INGESTION");
  });

  await asyncTest("Invalid stage skip: EVIDENCE_INGESTION -> REVIEW is rejected by backend engine", async () => {
    const headers = {
      "Content-Type": "application/json",
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const res = await fetch(`http://localhost:8000/api/v1/cases/${createdCaseId}/stage`, {
      method: "POST",
      headers,
      body: JSON.stringify({ lifecycle_stage: "REVIEW" })
    });
    // Expected 400 or 409 or 422 for invalid transition
    assert(res.status >= 400 && res.status < 500, `Expected 4xx error for illegal transition, got ${res.status}`);
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Suite 6: Live API Integration - Scenario B (Synthetic PDF Evidence)
  // ─────────────────────────────────────────────────────────────────────────
  console.log("\n-- Test Suite 6: Live API Integration - Scenario B (Synthetic Evidence) --");

  const testCaseId = "SAKSHI-CASE-2026-C5A64E99";
  const expectedEvidenceId = "SAKSHI-EVID-2026-43F94E97";

  await asyncTest(`Verify test case ${testCaseId} workspace retrieval`, async () => {
    const headers = {
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const res = await fetch(`http://localhost:8000/api/v1/cases/${testCaseId}`, { headers });
    assert.strictEqual(res.status, 200);
    const c = await res.json();
    assert.strictEqual(c.case_id, testCaseId);
    assert.strictEqual(c.assigned_io_id, "dev-investigator-001");
  });

  await asyncTest(`Verify preserved synthetic evidence ${expectedEvidenceId} without re-upload`, async () => {
    const headers = {
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const res = await fetch(`http://localhost:8000/api/v1/cases/${testCaseId}/evidence/${expectedEvidenceId}`, { headers });
    assert.strictEqual(res.status, 200);
    const ev = await res.json();
    assert.strictEqual(ev.evidence_id, expectedEvidenceId);
    assert.strictEqual(ev.original_file_name, "E01_guest_register.pdf");
    assert.strictEqual(ev.declared_mime_type, "application/pdf");
    assert.strictEqual(ev.detected_mime_type, "application/pdf");
    assert.strictEqual(ev.status, "COMMITTED");
    assert.strictEqual(ev.worm_status, "COMMITTED");
    assert(ev.checksum_sha256, "SHA-256 fingerprint must be present");
  });

  await asyncTest("Execute RAG retrieval using unique synthetic phrase 'BLUE ORCHID 7319'", async () => {
    const headers = {
      "Content-Type": "application/json",
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    const payload = {
      query: "BLUE ORCHID 7319",
      limit: 5
    };
    const res = await fetch(`http://localhost:8000/api/v1/cases/${testCaseId}/rag/search`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload)
    });
    assert.strictEqual(res.status, 200, `Expected 200 from RAG search, got ${res.status}`);
    const data = await res.json();
    assert(data.result_count >= 1, `Expected >= 1 passages retrieved, got ${data.result_count}`);
    assert(Array.isArray(data.results) && data.results.length >= 1);

    const first = data.results[0];
    assert.strictEqual(first.evidence_id, expectedEvidenceId);
    assert.strictEqual(first.source_name, "E01_guest_register.pdf");
    assert(first.passage.includes("BLUE ORCHID 7319"), "Retrieved passage must contain unique phrase 'BLUE ORCHID 7319'");
    assert(first.similarity_score > 0, "Similarity score must be positive");
    assert(first.source_sha256, "Source SHA-256 fingerprint must be cited");
  });

  await asyncTest("RAG retrieval enforces case isolation (cannot search other cases)", async () => {
    const headers = {
      "Content-Type": "application/json",
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    };
    // Search on newly registered empty case with same phrase
    const payload = { query: "BLUE ORCHID 7319", limit: 5 };
    const res = await fetch(`http://localhost:8000/api/v1/cases/${createdCaseId}/rag/search`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload)
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    // The empty case has 0 exhibits and 0 chunks, so it MUST return 0 results!
    assert.strictEqual(data.result_count, 0, "Empty case must return 0 results for RAG search");
    assert.strictEqual(data.results.length, 0);
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Suite 7: RBAC/ABAC Authorization Boundaries
  // ─────────────────────────────────────────────────────────────────────────
  console.log("\n-- Test Suite 7: RBAC/ABAC Authorization Boundaries --");

  await asyncTest("Unassigned investigator from different jurisdiction cannot access test case", async () => {
    const deniedHeaders = {
      "X-Investigator-Id": "IO-EXTERNAL-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "DELHI"
    };
    const res = await fetch(`http://localhost:8000/api/v1/cases/${testCaseId}`, { headers: deniedHeaders });
    assert.strictEqual(res.status, 403, `Expected HTTP 403 Forbidden, got ${res.status}`);
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Suite 8: Officer-Friendly Workflow, Plain-Language Statuses & Technical Details Panel
  // ─────────────────────────────────────────────────────────────────────────
  console.log("\n-- Test Suite 8: Officer-Friendly Workflow & Technical Details --");

  test("Registration success modal provides case metadata, 6-step progress, and primary evidence action", () => {
    assert(appJs.includes("showRegistrationSuccessModal(newCase)"), "ScreenCases must define showRegistrationSuccessModal");
    assert(appJs.includes("btnRegModalAddEvidence"), "Registration modal must have primary Add Evidence button");
    assert(appJs.includes("Investigation Workflow Progress"), "Registration modal must show 6-step workflow progress");
  });

  test("In-flight transition lock and button disabling prevent concurrent requests and duplicate toasts", () => {
    assert(appJs.includes("isStageTransitionInProgress"), "handleStageTransition must have in-flight lock guard");
    assert(appJs.includes("Advancing..."), "handleStageTransition must provide visual in-flight spinner");
    assert(appJs.includes("Stage reconciliation check notice"), "handleStageTransition must reconcile ambiguous transitions before throwing");
  });

  test("StatusPresentation dictionary provides plain-language explanations for all technical states", () => {
    assert(appJs.includes("Collecting Evidence"), "EVIDENCE_INGESTION must map to 'Collecting Evidence'");
    assert(appJs.includes("Awaiting Verification"), "PENDING_VERIFICATION must map to 'Awaiting Verification'");
    assert(appJs.includes("Preparing Document for Search"), "INDEXING must map to 'Preparing Document for Search'");
    assert(appJs.includes("Document Received, But Search Preparation Failed"), "INDEXING_FAILED must map to plain language");
    assert(appJs.includes("File Integrity Checks Passed"), "INTEGRITY_VERIFIED must map to 'File Integrity Checks Passed'");
    assert(appJs.includes("Evidence Stored with Protection Enabled") || appJs.includes("Stored with Protection Enabled"), "OBJECT_LOCKED must map to plain language");
    assert(appJs.includes("You do not have permission to perform this action"), "UNAUTHORIZED must map to plain language");
    assert(appJs.includes("This case or record could not be found"), "NOT_FOUND must map to plain language");
  });

  test("Evidence Workspace provides prominent 'Proceed to Forensic Verification' button during Stage 2", () => {
    assert(appJs.includes("btnProceedToForensicVerification"), "Evidence toolbar must include btnProceedToForensicVerification");
    assert(appJs.includes("btnBannerProceedToVerification"), "Evidence Stage 2 banner must include btnBannerProceedToVerification");
    assert(appJs.includes("STAGE 2 &bull; EVIDENCE COLLECTION IN PROGRESS") || appJs.includes("STAGE 2 • EVIDENCE COLLECTION IN PROGRESS"), "Evidence workspace must display Stage 2 progress banner");
  });

  test("Technical Details disclosure panel replaces hardcoded objlock:// with authentic backend fields", () => {
    assert(!appJs.includes("objlock://${ev.case_id}/"), "Evidence detail drawer must NOT contain fabricated objlock:// string");
    assert(appJs.includes("renderTechnicalDetailsPanel"), "StatusPresentation must render technical details panel");
    assert(styleCss.includes(".technical-details-panel"), "CSS must define .technical-details-panel");
    assert(styleCss.includes(".btn-copy-tech"), "CSS must define .btn-copy-tech copy controls");
  });

  test("ScreenTimeline guards temporal discrepancy and requires actual CCTV and witness statement exhibits", () => {
    assert(appJs.includes("const cctvExhibit = evidenceList.find"), "ScreenTimeline must verify actual CCTV exhibit presence");
    assert(appJs.includes("const witnessExhibit = evidenceList.find"), "ScreenTimeline must verify actual witness statement presence");
  });

  test("RAG search results incorporate technical details panel with copy controls for cryptographic provenance", () => {
    assert(appJs.includes("RAG Provenance & Technical Offsets"), "RAG search results must render technical details panel");
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Suite 9: Functional 6-Stage Workspaces & Stepper Navigation
  // ─────────────────────────────────────────────────────────────────────────
  console.log("\n-- Test Suite 9: Functional 6-Stage Workspaces & Stepper Navigation --");

  test("Six-stage horizontal workflow strip is completely removed from case workspace header", () => {
    assert(!appJs.includes('<div class="stage-stepper">'), "stage-stepper must be removed from app.js workspace header");
    assert(!appJs.includes('<div class="lifecycle-steps-row">'), "lifecycle-steps-row must be removed");
    assert(!appJs.includes('<div class="investigation-lifecycle-strip">'), "investigation-lifecycle-strip must be removed");
    assert(styleCss.includes(".stage-stepper") && styleCss.includes("display: none !important;"), "CSS must zero out layout space for stage-stepper");
  });

  test("Case workspace header reclaims space with compact case-summary-bar", () => {
    assert(appJs.includes('class="case-summary-bar"'), "Workspace header must render .case-summary-bar");
    assert(appJs.includes('class="case-summary-item"'), "Summary bar must contain .case-summary-item elements");
    assert(appJs.includes('class="case-summary-action"'), "Summary bar must contain next action");
    assert(styleCss.includes(".case-summary-bar"), "CSS must define .case-summary-bar styles");
  });

  test("Routes for Stage 3 Forensic Verification and Stage 6 Case Closure are registered", () => {
    assert(appJs.includes("pattern: /^#\\/cases\\/([A-Za-z0-9_-]+)\\/verification$/"), "verification route pattern must be registered");
    assert(appJs.includes("ScreenVerification.render(match[1])"), "verification route must call ScreenVerification.render");
    assert(appJs.includes("pattern: /^#\\/cases\\/([A-Za-z0-9_-]+)\\/closure$/"), "closure route pattern must be registered");
    assert(appJs.includes("ScreenClosure.render(match[1])"), "closure route must call ScreenClosure.render");
  });

  test("ScreenVerification defines workspace with metrics, verification matrix, tech panel, and error handling", () => {
    assert(appJs.includes("const ScreenVerification = {"), "ScreenVerification must be defined");
    assert(appJs.includes("renderCaseNotFound(caseId, err.message)"), "ScreenVerification must handle case not found");
    assert(appJs.includes("verification-matrix-table"), "ScreenVerification must render verification matrix table");
    assert(appJs.includes("toggleTechPanel"), "ScreenVerification must provide tech details toggle");
    assert(appJs.includes("runAllChecks"), "ScreenVerification must provide runAllChecks batch action");
  });

  test("ScreenClosure defines workspace with 6-point checklist, certificate, role gate, and error handling", () => {
    assert(appJs.includes("const ScreenClosure = {"), "ScreenClosure must be defined");
    assert(appJs.includes("renderCaseNotFound(caseId, err.message)"), "ScreenClosure must handle case not found");
    assert(appJs.includes("closure-checklist"), "ScreenClosure must render closure requirements checklist");
    assert(appJs.includes("SUPERVISORY_ROLES"), "ScreenClosure must enforce supervisory role gate");
    assert(appJs.includes("submitClosure"), "ScreenClosure must provide submitClosure handler");
  });

  test("ScreenTimeline (Stage 4) and ScreenEvidence (Stage 2) provide context banners for prerequisite vs active vs completed", () => {
    assert(appJs.includes("STAGE 4 PREREQUISITE"), "ScreenTimeline must render Stage 4 prerequisite banner");
    assert(appJs.includes("ACTIVE WORKSPACE &bull; STAGE 4") || appJs.includes("ACTIVE WORKSPACE • STAGE 4"), "ScreenTimeline must render Stage 4 active banner");
    assert(appJs.includes("STAGE 4 COMPLETED"), "ScreenTimeline must render Stage 4 completed banner");
    assert(appJs.includes("STAGE 2 PREREQUISITE"), "ScreenEvidence must render Stage 2 prerequisite banner");
    assert(appJs.includes("STAGE 2 COMPLETED"), "ScreenEvidence must render Stage 2 completed banner");
  });

  test("CSS styles for 2-column layout, verification matrix, closure checklist, and stepper are defined", () => {
    assert(styleCss.includes(".dashboard-grid-2"), "CSS must define .dashboard-grid-2");
    assert(styleCss.includes(".verification-matrix-table"), "CSS must define .verification-matrix-table");
    assert(styleCss.includes(".verification-check-pill"), "CSS must define .verification-check-pill");
    assert(styleCss.includes(".closure-checklist"), "CSS must define .closure-checklist");
    assert(styleCss.includes(".stage-step.active-workspace"), "CSS must define .stage-step.active-workspace");
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Summary
  // ─────────────────────────────────────────────────────────────────────────
  console.log("\n=================================================================");
  console.log(`Verification Complete: ${passes} passed, ${failures} failed.`);
  console.log("=================================================================");

  process.exit(failures > 0 ? 1 : 0);
})();
