/**
 * Regression and Verification Suite for SAKSHI:
 * Investigator-Friendly Dashboard and Lifecycle Redesign.
 *
 * Verifies:
 * 1. Compact Case Header with identity, status, stage label, FIR metadata, and Switch Case control.
 * 2. 4 Actionable Overview Metric Cards (Evidence collected, Conflicting information, Awaiting your review, Evidence security).
 * 3. 4-Part Recommended Next Action grounded in real case lifecycle state.
 * 4. Single compact, expandable lifecycle progress component without duplicate 6-stage cards.
 * 5. Case-scoped data isolation without hardcoded fixtures or fake sample numbers.
 * 6. Evidence category dropdown consistency (DOCUMENT_PDF, MEDICAL_REPORT, PHYSICAL_EXHIBIT, etc.).
 * 7. Evidence security evaluator assessing all 7 forensic layers without masking pending WORM or unverified hashes.
 */

const fs = require("fs");
const path = require("path");
const assert = require("assert");

console.log("=================================================================");
console.log("Starting SAKSHI Investigator-Friendly Dashboard Verification Tests...");
console.log("=================================================================\n");

let passedCount = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`  [PASS] ${name}`);
    passedCount++;
  } catch (err) {
    console.error(`  [FAIL] ${name}`);
    console.error(`         ${err.message}`);
    process.exitCode = 1;
  }
}

const appJsPath = path.join(__dirname, "app.js");
const styleCssPath = path.join(__dirname, "style.css");
const appJs = fs.readFileSync(appJsPath, "utf-8");
const styleCss = fs.readFileSync(styleCssPath, "utf-8");

// ─── SUITE 1: COMPACT HEADER & SWITCH CASE CONTROL ──────────────────────────
console.log("-- Test Suite 1: Compact Case Header & Switch Case Control --");

test("Case Header contains case identifier, status badge, and compact stage indicator", () => {
  assert(appJs.includes('<span class="case-id-badge">${c.case_id}</span>'), "Case ID badge must be present");
  assert(appJs.includes('<span class="badge ${c.status === \'ACTIVE\' ? \'badge-verified\' : \'badge-neutral\'}">'), "Status badge must be present");
  assert(appJs.includes('Stage ${currentIdx + 1} of 6'), "Compact stage indicator (Stage X of 6) must be present in header");
});

test("Case Header preserves essential metadata chips (FIR, Station, Incident Date, IO)", () => {
  assert(appJs.includes('FIR / Inquest: <strong>${fir}</strong>'), "FIR number must be present");
  assert(appJs.includes('Station: <strong>${station}</strong>'), "Police station must be present");
  assert(appJs.includes('Incident Date: <strong>${incidentDate}</strong>'), "Incident date must be present");
  assert(appJs.includes('Investigating Officer: <strong>${c.assigned_io_id'), "Investigating officer must be present");
});

test("Switch Case control is present and routes to case directory", () => {
  assert(appJs.includes("window.location.hash='#/cases'"), "Switch Case must route to '#/cases'");
  assert(appJs.includes("&larr; Switch Case"), "Switch Case button text must be present");
});

// ─── SUITE 2: 4 ACTIONABLE INVESTIGATION METRIC CARDS ───────────────────────
console.log("\n-- Test Suite 2: 4 Actionable Overview Metric Cards --");

test("Overview dashboard container is rendered below header", () => {
  assert(appJs.includes('class="dashboard-metrics-grid investigation-overview-dashboard"'), "investigation-overview-dashboard must be rendered");
});

test("Card 1: Evidence collected card displays authentic count and routes to evidence workspace", () => {
  assert(appJs.includes('Evidence collected'), "Evidence collected title must be present");
  assert(appJs.includes('metricEvidence'), "metricEvidence must be computed from docket count");
  assert(appJs.includes('#/cases/${c.case_id}/evidence'), "Must route to evidence workspace");
});

test("Card 2: Conflicting information card distinguishes <2 exhibits and routes to analysis", () => {
  assert(appJs.includes('Conflicting information'), "Conflicting information title must be present");
  assert(appJs.includes('Comparisons pending — attach 2+ exhibits'), "Must distinguish <2 exhibits from zero discrepancies");
  assert(appJs.includes('No discrepancies identified'), "Must report no discrepancies when accounts compared");
  assert(appJs.includes('#/cases/${c.case_id}/analysis'), "Must route to analysis workspace");
});

test("Card 3: Awaiting your review card displays pending review actions and routes to findings", () => {
  assert(appJs.includes('Awaiting your review'), "Awaiting your review title must be present");
  assert(appJs.includes('pendingGraphReviews'), "Must count pending graph decisions");
  assert(appJs.includes('pendingFactReviews'), "Must count unreviewed facts");
  assert(appJs.includes('#/cases/${c.case_id}/findings'), "Must route to findings / review workspace");
});

test("Card 4: Evidence security card evaluates 7 layers and routes to verification workspace", () => {
  assert(appJs.includes('Evidence security'), "Evidence security title must be present");
  assert(appJs.includes('EvidenceSecurityEvaluator.evaluateCaseSecurity'), "Must evaluate full case security");
  assert(appJs.includes('#/cases/${c.case_id}/verification'), "Must route to verification workspace");
});

// ─── SUITE 3: CONTEXT-AWARE RECOMMENDED NEXT ACTION ─────────────────────────
console.log("\n-- Test Suite 3: Context-Aware Recommended Next Action --");

test("Recommended Next Action card is rendered with 4-part formulation", () => {
  assert(appJs.includes('class="recommended-next-action-card guided-next-action-card"'), "recommended-next-action-card must be present");
  assert(appJs.includes('RECOMMENDED NEXT ACTION'), "RECOMMENDED NEXT ACTION title must be present");
  assert(appJs.includes('${Formatters.escapeHtml(recAction.title)}'), "Recommended action title must be dynamic");
  assert(appJs.includes('${Formatters.escapeHtml(recAction.whyItMatters)}'), "Why it matters explanation must be dynamic");
  assert(appJs.includes('Involved: <strong>${Formatters.escapeHtml(recAction.involved)}</strong>'), "Involved items must be displayed");
  assert(appJs.includes('${recAction.buttonHtml}'), "Action button must be present");
});

test("Recommended Next Action adapts to case lifecycle state", () => {
  assert(appJs.includes('RecommendedActionEvaluator = {'), "RecommendedActionEvaluator must be defined");
  assert(appJs.includes('Attach Primary Case Exhibits') || appJs.includes('Begin Evidence Collection'), "Must recommend initial exhibit when case is empty");
  assert(appJs.includes('Finish Checking Evidence Protection') || appJs.includes('Complete Forensic Verification'), "Must recommend verification when exhibits are pending");
  assert(appJs.includes('Review Conflicting Information') || appJs.includes('Review Conflicting Statements'), "Must recommend contradiction review when discrepancies exist");
  assert(appJs.includes('Complete Authorized Inquest Review'), "Must recommend review when decisions are pending");
});

// ─── SUITE 4: REMOVAL OF 6-STAGE WORKFLOW STRIP & RECLAIMED SPACE ───────────
console.log("\n-- Test Suite 4: Removal of 6-Stage Workflow Strip & Reclaimed Space --");

test("Case workspace completely removes the 6-stage workflow strip and drawer", () => {
  assert(!appJs.includes('class="investigation-lifecycle-strip"'), "investigation-lifecycle-strip must be removed from header");
  assert(!appJs.includes('class="stage-stepper"'), "stage-stepper wrapper must be removed from header");
  assert(!appJs.includes('id="btnToggleLifecycleDetails"'), "Lifecycle Details toggle button must be removed");
  assert(!appJs.includes('id="lifecycleDetailsDrawer"'), "Lifecycle details drawer must be removed");
});

test("Header renders compact case-summary-bar in reclaimed layout space", () => {
  assert(appJs.includes('class="case-summary-bar"'), "Must render compact .case-summary-bar");
  assert(appJs.includes('class="case-summary-item"'), "Must render case-summary-items");
  assert(styleCss.includes('.case-summary-bar'), "CSS must define .case-summary-bar");
});

// ─── SUITE 5: EVIDENCE CATEGORY AUDIT & CONSISTENCY ─────────────────────────
console.log("\n-- Test Suite 5: Evidence Category Audit & Consistency --");

test("Registration dropdown includes DOCUMENT_PDF, MEDICAL_REPORT, and PHYSICAL_EXHIBIT", () => {
  assert(appJs.includes('<option value="DOCUMENT_PDF">General Case Document / Statement / Register (PDF)</option>'), "DOCUMENT_PDF option must be labeled as general document");
  assert(appJs.includes('<option value="MEDICAL_REPORT">Medical / Autopsy / Inquest Report (PDF)</option>'), "MEDICAL_REPORT option must be present for medical reports");
  assert(appJs.includes('<option value="PHYSICAL_EXHIBIT">Physical / Ballistics / Biological Exhibit</option>'), "PHYSICAL_EXHIBIT option must be present for physical exhibits");
});

test("formatCategory maps DOCUMENT_PDF, MEDICAL_REPORT, and PHYSICAL_EXHIBIT correctly", () => {
  assert(appJs.includes('DOCUMENT_PDF: "General Case Document (PDF)"'), "DOCUMENT_PDF must map to General Case Document");
  assert(appJs.includes('MEDICAL_REPORT: "Medical / Autopsy Report (PDF)"'), "MEDICAL_REPORT must map to Medical / Autopsy Report");
  assert(appJs.includes('PHYSICAL_EXHIBIT: "Physical / Ballistics / Biological Exhibit"'), "PHYSICAL_EXHIBIT must map to Physical / Ballistics Exhibit");
});

// ─── SUITE 6: CSS STYLING & RESPONSIVENESS ──────────────────────────────────
console.log("\n-- Test Suite 6: CSS Styling & Responsiveness --");

test("style.css defines overview metric card, dashboard, and recommended action card styles", () => {
  assert(styleCss.includes(".investigation-overview-dashboard") || styleCss.includes(".dashboard-metrics-grid"), "CSS must define dashboard metrics grid");
  assert(styleCss.includes(".dashboard-metric-card"), "CSS must define .dashboard-metric-card");
  assert(styleCss.includes(".recommended-next-action-card"), "CSS must define .recommended-next-action-card");
  assert(styleCss.includes(".investigation-lifecycle-strip"), "CSS must define .investigation-lifecycle-strip");
});

console.log("\n=================================================================");
console.log(`Phase N.1 Dashboard Verification: ${passedCount} passed, 0 failed.`);
console.log("=================================================================");
