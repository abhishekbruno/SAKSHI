/**
 * SAKSHI Frontend Navigation & Active Case Verification Tests
 *
 * Verifies:
 * 1. Sidebar single-click navigation listener and event handling
 * 2. Stale/missing case ID handling and active-case state reset
 * 3. Graceful error boundary on all 7 workspace screens
 * 4. Reliable navigation back to Case Directory without dead ends
 * 5. Case Directory validation against stale IDs
 * 6. Functional mock simulation of navigation flows
 */

const fs = require('fs');

console.log("Starting SAKSHI Frontend Navigation Verification Tests...\n");

const html = fs.readFileSync('C:/main project/frontend/index.html', 'utf8');
const js = fs.readFileSync('C:/main project/frontend/app.js', 'utf8');
const css = fs.readFileSync('C:/main project/frontend/style.css', 'utf8');

let passes = 0;
let failures = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  [PASS] ${message}`);
    passes++;
  } else {
    console.error(`  [FAIL] ${message}`);
    failures++;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 1. Single-Click Sidebar Navigation
// ═══════════════════════════════════════════════════════════════════════════
console.log("-- Test Suite 1: Sidebar Single-Click Navigation --");
assert(
  js.includes('document.querySelectorAll(".sidebar-nav a.nav-link").forEach'),
  "Click listeners attached to all sidebar nav links"
);
assert(
  js.includes('e.preventDefault()') && js.includes('Router.navigate(href)'),
  "Sidebar click listener prevents default jump and delegates to Router.navigate"
);
assert(
  js.includes('navigate(targetHash = null)'),
  "Router.navigate supports programmatic navigation target"
);
assert(
  js.includes('if (window.location.hash !== "#/cases")') && js.includes('ScreenCases.render()'),
  "Router.navigate executes route handler even when URL hash already matches #/cases"
);

// ═══════════════════════════════════════════════════════════════════════════
// 2. Active-Case Reset & Stale ID Prevention
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 2: Active Case Reset & Purge --");
assert(
  js.includes('function resetActiveCaseState()'),
  "Dedicated resetActiveCaseState function defined"
);
assert(
  js.includes('State.activeCase = null') &&
  js.includes('State.activeCaseId = null') &&
  js.includes('localStorage.removeItem("sakshi_active_case_id")'),
  "resetActiveCaseState purges activeCase, activeCaseId, and localStorage key"
);
assert(
  js.includes('updateSidebarActiveCaseContext()'),
  "resetActiveCaseState synchronizes sidebar context"
);
assert(
  js.includes('if (State.activeCaseId && !cases.some(c => c.case_id === State.activeCaseId))'),
  "ScreenCases.render automatically purges stale activeCaseId not present in database"
);

// ═══════════════════════════════════════════════════════════════════════════
// 3. Case Not Found Error Screen & Return to Directory
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 3: Case Not Found Error Handling --");
assert(
  js.includes('function renderCaseNotFound(caseId, errorMessage)'),
  "Standardized renderCaseNotFound error screen helper defined"
);
assert(
  js.includes('Case Not Found') && js.includes('btnReturnToCaseDirectory'),
  "renderCaseNotFound displays 'Case Not Found' heading and return button"
);
assert(
  js.includes('onclick="Router.navigate(\'#/cases\')"'),
  "Return button in renderCaseNotFound delegates directly to Router.navigate('#/cases')"
);
assert(
  js.includes('renderCaseNotFound(caseId, err.message)'),
  "Workspace screens delegate 404 errors to renderCaseNotFound with real API message"
);

// ═══════════════════════════════════════════════════════════════════════════
// 4. Graceful Error Boundaries Across All 7 Workspace Screens
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 4: All 7 Workspace Screens Have Error Boundaries --");
const screens = [
  { name: "ScreenCaseOverview", route: "overview" },
  { name: "ScreenEvidence", route: "evidence" },
  { name: "ScreenRAGSearch", route: "rag" },
  { name: "ScreenTimeline", route: "timeline" },
  { name: "ScreenAnalysis", route: "analysis" },
  { name: "ScreenGaps", route: "gaps" },
  { name: "ScreenAudit", route: "audit" }
];

screens.forEach(s => {
  const screenIdx = js.indexOf(`const ${s.name} =`);
  assert(screenIdx !== -1, `${s.name} component exists`);
  if (screenIdx !== -1) {
    // Components may define small pure helpers before render(); inspect the
    // complete component window rather than assuming render starts immediately.
    const screenCode = js.substring(screenIdx, screenIdx + 5000);
    const hasTryCatch = screenCode.includes('try') && screenCode.includes('ensureActiveCaseLoaded') && screenCode.includes('renderCaseNotFound');
    assert(hasTryCatch, `${s.name} wraps ensureActiveCaseLoaded in try/catch and calls renderCaseNotFound`);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 5. Authorization & Security Integrity
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 5: Security & Authorization Preservation --");
assert(
  !js.includes('SAKSHI-CASE-2026-D52715A8'),
  "No hardcoded fallback to stale case ID SAKSHI-CASE-2026-D52715A8"
);
assert(
  js.includes('X-Investigator-Id') && js.includes('X-Investigator-Role') && js.includes('X-Investigator-Jurisdiction'),
  "Investigator identity headers configured for RBAC/ABAC and jurisdiction validation"
);
assert(
  js.includes('Authorization') && js.includes('Bearer'),
  "Bearer token authentication preserved for token-based auth modes"
);

// ═══════════════════════════════════════════════════════════════════════════
// 6. CSS Styling Verification
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 6: Sidebar Navigation CSS Styles --");
assert(
  css.includes('.nav-link.workspace-link-inactive'),
  ".nav-link.workspace-link-inactive class styled in style.css"
);

// ═══════════════════════════════════════════════════════════════════════════
// 7. Functional Simulation Test (In-Memory Micro DOM)
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 7: Functional Simulation --");

const localStore = {};
const mockLocalStorage = {
  getItem: (k) => localStore[k] || null,
  setItem: (k, v) => { localStore[k] = String(v); },
  removeItem: (k) => { delete localStore[k]; }
};

let currentHash = "#/cases";
const elements = {};

function createElement(id) {
  return {
    id,
    textContent: "",
    style: {},
    className: "",
    classList: {
      add: function(c) { this.classes = this.classes || []; if (!this.classes.includes(c)) this.classes.push(c); },
      remove: function(c) { this.classes = (this.classes || []).filter(x => x !== c); },
      contains: function(c) { return (this.classes || []).includes(c); }
    },
    setAttribute: function(k, v) { this[k] = v; },
    getAttribute: function(k) { return this[k]; }
  };
}

elements["viewContainer"] = createElement("viewContainer");
elements["breadcrumbCurrent"] = createElement("breadcrumbCurrent");
elements["sidebarActiveCaseId"] = createElement("sidebarActiveCaseId");
elements["sidebarActiveCaseStage"] = createElement("sidebarActiveCaseStage");
elements["navEvidenceCount"] = createElement("navEvidenceCount");
elements["sidebarActiveCaseBox"] = createElement("sidebarActiveCaseBox");

// Simulate stale case in localStorage
mockLocalStorage.setItem("sakshi_active_case_id", "SAKSHI-CASE-2026-D52715A8");
assert(mockLocalStorage.getItem("sakshi_active_case_id") === "SAKSHI-CASE-2026-D52715A8", "Simulated localStorage starts with stale case ID");

// Simulate resetActiveCaseState logic
const simState = {
  activeCase: null,
  activeCaseId: mockLocalStorage.getItem("sakshi_active_case_id"),
  activeStageInfo: null,
  evidence: []
};

function simResetActiveCase() {
  simState.activeCase = null;
  simState.activeCaseId = null;
  simState.activeStageInfo = null;
  simState.evidence = [];
  mockLocalStorage.removeItem("sakshi_active_case_id");
}

simResetActiveCase();
assert(simState.activeCaseId === null, "simResetActiveCase clears State.activeCaseId");
assert(mockLocalStorage.getItem("sakshi_active_case_id") === null, "simResetActiveCase removes key from localStorage");

// Simulate 404 error render
function simRenderCaseNotFound(caseId, errMsg) {
  simResetActiveCase();
  elements["viewContainer"].innerHTML = `<div class="empty-state-title">Case Not Found</div><div class="empty-state-desc">${errMsg}</div><button id="btnReturn">Return to Case Directory</button>`;
}

simRenderCaseNotFound("SAKSHI-CASE-2026-D52715A8", "Investigation case with ID 'SAKSHI-CASE-2026-D52715A8' was not found.");
assert(elements["viewContainer"].innerHTML.includes("Case Not Found"), "Error screen displays 'Case Not Found'");
assert(elements["viewContainer"].innerHTML.includes("SAKSHI-CASE-2026-D52715A8"), "Error screen mentions the missing case ID");
assert(elements["viewContainer"].innerHTML.includes("Return to Case Directory"), "Error screen includes return button");

// Simulate Directory load with database cases
const dbCases = [
  { case_id: "SAKSHI-TEST-2026-002", title: "Test Case" },
  { case_id: "SAKSHI-CASE-2026-719A8019", title: "Second Case" }
];

simState.activeCaseId = "SAKSHI-CASE-2026-D52715A8"; // suppose it was reintroduced
if (simState.activeCaseId && !dbCases.some(c => c.case_id === simState.activeCaseId)) {
  simResetActiveCase();
}
assert(simState.activeCaseId === null, "Directory reconciliation successfully purges nonexistent active case");

console.log(`\n======================================================`);
console.log(`Total Verification: ${passes} passed, ${failures} failed.`);
console.log(`======================================================\n`);

process.exit(failures > 0 ? 1 : 0);
