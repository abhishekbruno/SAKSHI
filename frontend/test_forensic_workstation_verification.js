/**
 * SAKSHI Forensic Reliability & Workstation Redesign Verification Test Suite
 * Validates:
 * 1. ScreenReport definition and comprehensive 10-section dossier structure.
 * 2. NavReport link present in sidebar and integrated into workspaceLinks.
 * 3. Route #/cases/:id/report and #/cases/:id/reports handled by ScreenReport.
 * 4. Honest antivirus scan labeling (EicarHeuristicScanner vs ClamAV).
 * 5. Honest write protection status (Development simulation notice).
 * 6. Document extraction attribution types (QUOTED_FROM_SOURCE, EXTRACTED_BY_SOFTWARE, AI_INTERPRETATION, NEEDS_CONFIRMATION).
 * 7. Branching timeline response and UI pills (MAIN, BRANCH_A, BRANCH_B).
 * 8. Live API verification:
 *    - GET /api/v1/cases/{id}/timeline-events
 *    - GET /api/v1/cases/{id}/analysis-summary
 *    - GET /api/v1/cases/{id}/evidence/{evidence_id}/extracted-facts
 * 9. Investigator review decision actions (Confirm, Correct, Reject, Request More Evidence, Mark Unresolved).
 * 10. Clean empty state for ScreenReport and timeline.
 */

const assert = require("assert");
const fs = require("fs");

console.log("=================================================================");
console.log("Starting SAKSHI Forensic Reliability & Workstation Redesign Tests...");
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
  // ─── Suite 1: Case Report Navigation & Routing ───
  console.log("-- Test Suite 1: Case Report Navigation & Routing --");

  test("Sidebar contains #navReport link", () => {
    assert(html.includes('id="navReport"') && html.includes("Case Report"));
  });

  test("Router registers #/cases/:id/report and #/cases/:id/reports", () => {
    assert(appJs.includes("pattern: /^#\\/cases\\/([A-Za-z0-9_-]+)\\/report$/"));
    assert(appJs.includes("pattern: /^#\\/cases\\/([A-Za-z0-9_-]+)\\/reports$/"));
  });

  test("workspaceLinks includes navReport mapping to 'report'", () => {
    assert(appJs.includes('{ id: "navReport", tab: "report" }'));
  });

  test("updateSidebarActiveLink highlights #navReport", () => {
    assert(appJs.includes('else if (hash.includes("/report")) document.getElementById("navReport")?.classList.add("active");'));
  });

  // ─── Suite 2: 10-Section Comprehensive Case Report Structure ───
  console.log("\n-- Test Suite 2: 10-Section Case Report Structure --");

  test("ScreenReport component is defined", () => {
    assert(appJs.includes("const ScreenReport = {"));
  });

  test("ScreenReport includes Section 1: Case Particulars & Incident Header", () => {
    assert(appJs.includes("1. Case Particulars & Incident Header"));
  });

  test("ScreenReport includes Section 2: Forensic Evidence Register", () => {
    assert(appJs.includes("2. Forensic Evidence Register"));
  });

  test("ScreenReport includes Section 3: Security & Preservation Verification Summary", () => {
    assert(appJs.includes("3. Security & Integrity Verification Summary"));
  });

  test("ScreenReport includes Section 4: Extracted Documentary Facts with Source Attribution", () => {
    assert(appJs.includes("4. Extracted Documentary Facts with Source Attribution"));
  });

  test("ScreenReport includes Section 5: Chronological Sequence & Branching Timeline", () => {
    assert(appJs.includes("5. Chronological Sequence & Branching Timeline"));
  });

  test("ScreenReport includes Section 6: Evidentiary Contradictions & Investigation Gaps", () => {
    assert(appJs.includes("6. Evidentiary Contradictions & Investigation Gaps"));
  });

  test("ScreenReport includes Section 7: Candidate Scenarios (Explicit Hypotheses)", () => {
    assert(appJs.includes("7. Candidate Scenarios (Explicit Hypotheses)"));
    assert(appJs.includes("Candidate scenarios are analytical hypotheses for investigative evaluation only"));
  });

  test("ScreenReport includes Section 8: Investigator Decisions & Review Endorsements", () => {
    assert(appJs.includes("8. Investigator Decisions & Review Endorsements"));
  });

  test("ScreenReport includes Section 9: Cryptographic Hash Ledger & Storage References", () => {
    assert(appJs.includes("9. Cryptographic Hash Ledger & Storage References"));
  });

  test("ScreenReport includes Section 10: Statutory Evidentiary Limitations & Notice", () => {
    assert(appJs.includes("10. Statutory Evidentiary Limitations & Notice"));
    assert(appJs.includes("Section 63 Bharatiya Sakshya Adhiniyam"));
  });

  test("ScreenReport provides print trigger window.print()", () => {
    assert(appJs.includes('onclick="window.print()"'));
    assert(styleCss.includes("@media print"));
  });

  // ─── Suite 3: Honest Forensic & Security Labeling ───
  console.log("\n-- Test Suite 3: Honest Forensic & Security Labeling --");

  test("Antivirus scan explicitly discloses EicarHeuristicScanner vs ClamAV", () => {
    assert(appJs.includes("Development Signature Scanner (EicarHeuristicScanner)"));
  });

  test("Write protection explicitly discloses development simulation vs hardware WORM", () => {
    assert(appJs.includes("Local development simulation; not hardware WORM") || appJs.includes("Local development simulation; not compliance-grade"));
  });

  test("ScreenRAGSearch uses plain language limit: 'Show up to 5 matching excerpts'", () => {
    assert(appJs.includes("Show up to 5 matching excerpts"));
  });

  test("ScreenRAGSearch uses neutral relevance label without pseudo-probabilities", () => {
    assert(appJs.includes("Passage Relevance Match:"));
    assert(appJs.includes("Mathematical similarity metric, not a probability of truth"));
  });

  // ─── Suite 4: Evidence Detail Drawer & Document Extraction ───
  console.log("\n-- Test Suite 4: Evidence Detail Drawer & Document Extraction --");

  test("Evidence drawer queries Api.getExtractedFacts", () => {
    assert(appJs.includes("Api.getExtractedFacts(caseId, evidenceId)"));
  });

  test("Evidence drawer renders Section 2.5 Document Intelligence & Extracted Facts", () => {
    assert(appJs.includes("Section 2.5 &bull; Document Intelligence & Extracted Facts"));
    assert(appJs.includes("AI-Generated Preliminary Summary"));
  });

  test("Evidence drawer includes fact re-extraction button and handler", () => {
    assert(appJs.includes("btnReExtractFacts"));
    assert(appJs.includes("Api.triggerExtractFacts(caseId, evidenceId)"));
  });

  // ─── Suite 5: Investigator Review Decisions ───
  console.log("\n-- Test Suite 5: Investigator Review Decisions --");

  test("ScreenFindings provides 5 decision actions (Confirm, Correct, Reject, Request More Evidence, Mark Unresolved)", () => {
    assert(appJs.includes("CONFIRMED"));
    assert(appJs.includes("CORRECTED"));
    assert(appJs.includes("REJECTED"));
    assert(appJs.includes("REQUEST_MORE_EVIDENCE"));
    assert(appJs.includes("MARK_UNRESOLVED"));
  });

  test("ScreenFindings defines recordDecision method persisting to localStorage and audit log", () => {
    assert(appJs.includes("recordDecision(caseId, findingId, decision)"));
    assert(appJs.includes("sakshi_decisions_"));
    assert(appJs.includes("INVESTIGATOR_FINDING_DECISION"));
  });

  // ─── Suite 6: Live API Integration ───
  console.log("\n-- Test Suite 6: Live API Integration (Synthetic Case SAKSHI-TEST-2026-002) --");

  const testCaseId = "SAKSHI-TEST-2026-002";
  const expectedEvidenceId = "SAKSHI-EVID-2026-E51D496A";
  const authHeaders = {
    "Content-Type": "application/json",
    "X-Investigator-Id": "dev-investigator-001",
    "X-Investigator-Role": "INVESTIGATING_OFFICER",
    "X-Investigator-Jurisdiction": "KERALA"
  };

  await asyncTest("Live API: GET /api/v1/cases/{case_id}/timeline-events returns branching timeline", async () => {
    const res = await fetch(`http://localhost:8000/api/v1/cases/${testCaseId}/timeline-events`, { headers: authHeaders });
    assert.strictEqual(res.status, 200, `Expected 200, got ${res.status}`);
    const data = await res.json();
    assert.strictEqual(data.case_id, testCaseId);
    assert(Array.isArray(data.events));
    assert(Array.isArray(data.branches));
    assert(data.events.length >= 1, "Expected >= 1 timeline event");
    const ev0 = data.events[0];
    assert(ev0.event_id && ev0.title && ev0.branch_id);
    assert(ev0.time_certainty === "EXACT" || ev0.time_certainty === "REPORTED" || ev0.time_certainty === "ESTIMATED" || ev0.time_certainty === "UNKNOWN");
  });

  await asyncTest("Live API: GET /api/v1/cases/{case_id}/analysis-summary returns 4 structured sections", async () => {
    const res = await fetch(`http://localhost:8000/api/v1/cases/${testCaseId}/analysis-summary`, { headers: authHeaders });
    assert.strictEqual(res.status, 200, `Expected 200, got ${res.status}`);
    const data = await res.json();
    assert.strictEqual(data.case_id, testCaseId);
    assert(Array.isArray(data.supported_observations), "Supported observations must be array");
    assert(Array.isArray(data.contradictions), "Contradictions must be array");
    assert(Array.isArray(data.investigation_gaps), "Investigation gaps must be array");
    assert(Array.isArray(data.candidate_scenarios), "Candidate scenarios must be array");
  });

  await asyncTest("Live API: GET /api/v1/cases/{case_id}/evidence/{evidence_id}/extracted-facts returns facts", async () => {
    const res = await fetch(`http://localhost:8000/api/v1/cases/${testCaseId}/evidence/${expectedEvidenceId}/extracted-facts`, { headers: authHeaders });
    assert.strictEqual(res.status, 200, `Expected 200, got ${res.status}`);
    const data = await res.json();
    assert.strictEqual(data.evidence_id, expectedEvidenceId);
    assert(Array.isArray(data.facts), "Facts must be array");
    assert((data.total_facts || data.facts.length) >= 1, "Expected >= 1 extracted fact from synthetic PDF");
    const f0 = data.facts[0];
    assert(f0.fact_text || f0.fact_statement);
    assert(["QUOTED_FROM_SOURCE", "EXTRACTED_BY_SOFTWARE", "AI_INTERPRETATION", "NEEDS_CONFIRMATION"].includes(f0.attribution_type));
  });

  await asyncTest("Live API: Case isolation - Timeline for empty case returns 0 events", async () => {
    // Register temporary empty case
    const regRes = await fetch("http://localhost:8000/api/v1/cases", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        title: "Temporary Empty Case For Timeline Isolation Test",
        fir_metadata: {
          fir_number: `FIR-ISO-${Date.now().toString().slice(-4)}`,
          police_station: "Cantonment Police Station",
          incident_date: new Date().toISOString(),
          report_date: new Date().toISOString(),
          incident_location: "Sector 1",
          jurisdiction_code: "KERALA"
        }
      })
    });
    assert.strictEqual(regRes.status, 201);
    const newCase = await regRes.json();

    const tRes = await fetch(`http://localhost:8000/api/v1/cases/${newCase.case_id}/timeline-events`, { headers: authHeaders });
    assert.strictEqual(tRes.status, 200);
    const tData = await tRes.json();
    assert.strictEqual(tData.events.length, 0, "Empty case must return exactly 0 timeline events");
  });

  console.log("\n=================================================================");
  console.log(`Verification Complete: ${passes} passed, ${failures} failed.`);
  console.log("=================================================================\n");
  if (failures > 0) process.exit(1);
})();
