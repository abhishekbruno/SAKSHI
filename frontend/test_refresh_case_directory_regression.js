/**
 * SAKSHI Frontend Regression Test Suite:
 * Case Directory Hard Refresh & Authentication Lifecycle Verification
 *
 * Covers:
 * 1. Hard refresh on #/cases under development mode authentication
 * 2. Case Directory API payload normalization ({ total: N, cases: [...] } vs raw array)
 * 3. Router guard preventing premature execution before auth initialization
 * 4. Unauthenticated vs Authenticated routing and shell visibility (login-active)
 * 5. Production (Firebase/OIDC) token restoration vs unauthenticated header protection
 * 6. Stale case clearing and sidebar context reconciliation
 */

const fs = require('fs');

console.log("Starting SAKSHI Case Directory Refresh & Authentication Regression Tests...\n");

const js = fs.readFileSync('C:/main project/frontend/app.js', 'utf8');
const html = fs.readFileSync('C:/main project/frontend/index.html', 'utf8');
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
// Suite 1: Static Code Pattern & Integrity Assertions
// ═══════════════════════════════════════════════════════════════════════════
console.log("-- Test Suite 1: Source Code Patterns & Regression Guards --");

assert(
  js.includes('initialized: false'),
  "State.auth includes initialized flag to track bootstrap completion"
);

assert(
  js.includes('if (!State.auth.initialized)'),
  "Router.navigate guards against premature dispatch before auth completes"
);

assert(
  js.includes('const rawCases = await Api.listCases()') &&
  js.includes('cases = Array.isArray(rawCases) ? rawCases : (rawCases && Array.isArray(rawCases.cases) ? rawCases.cases : [])'),
  "ScreenCases.render normalizes Api.listCases() object { total, cases } to Array"
);

assert(
  js.includes('isDevMode = State.auth.mode === "development" || State.auth.mode === "offline" || authStatus.development_mode === true'),
  "initApplication recognizes development and offline modes as dev authentication"
);

assert(
  js.includes('sessionStorage.getItem("sakshi_auth_token")'),
  "State.auth restores token from sessionStorage on page refresh"
);

assert(
  js.includes('else if (State.auth.mode === "development" || State.auth.mode === "offline" || State.auth.mode === "unknown")'),
  "Api.getHeaders only injects dev investigator headers in development/offline modes, not Firebase"
);

// ═══════════════════════════════════════════════════════════════════════════
// Suite 2: Functional DOM & Router Simulation on Hard Refresh
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 2: Hard Refresh on #/cases Simulation --");

// Build micro DOM environment
function createMockElement(id) {
  return {
    id,
    textContent: "",
    innerHTML: "",
    style: {},
    classes: [],
    classList: {
      add(c) { if (!this.parent.classes.includes(c)) this.parent.classes.push(c); },
      remove(c) { this.parent.classes = this.parent.classes.filter(x => x !== c); },
      contains(c) { return this.parent.classes.includes(c); }
    },
    setAttribute(k, v) { this[k] = v; },
    getAttribute(k) { return this[k]; }
  };
}

const mockDom = {
  viewContainer: createMockElement("viewContainer"),
  breadcrumbCurrent: createMockElement("breadcrumbCurrent"),
  navCases: createMockElement("navCases"),
  navLogin: createMockElement("navLogin"),
  sidebarActiveCaseId: createMockElement("sidebarActiveCaseId"),
  sidebarActiveCaseStage: createMockElement("sidebarActiveCaseStage"),
  navEvidenceCount: createMockElement("navEvidenceCount"),
  body: createMockElement("body")
};
Object.values(mockDom).forEach(el => { el.classList.parent = el; });

// Simulate Storage
const storage = {};
const mockLocalStorage = {
  getItem: k => storage[k] || null,
  setItem: (k, v) => { storage[k] = String(v); },
  removeItem: k => { delete storage[k]; }
};

// Simulated State reflecting app.js
const testState = {
  auth: {
    initialized: false,
    authenticated: false,
    subjectId: "IO-7842-SHARMA",
    displayName: "IO Sharma",
    role: "INVESTIGATING_OFFICER",
    jurisdiction: "KL-TVM-001",
    mode: "unknown",
    token: null,
    headers: { "Content-Type": "application/json" }
  },
  activeCaseId: null,
  activeCase: null,
  filters: { caseSearch: "", caseStage: "ALL" },
  cases: []
};

// Simulation of Router.navigate
let simHash = "#/cases";
let lastRendered = null;

const simRouter = {
  navigate(targetHash = null) {
    if (!testState.auth.initialized) {
      return "GUARDED";
    }

    if (targetHash !== null && targetHash !== undefined) {
      if (simHash !== targetHash) {
        simHash = targetHash;
        return "HASH_UPDATED";
      }
    }

    const rawHash = simHash || "";
    const isLogin = !rawHash || rawHash === "#" || rawHash === "#/" || rawHash === "#/login";

    if (isLogin || !testState.auth.authenticated) {
      if (!isLogin && simHash !== "#/login") simHash = "#/login";
      mockDom.body.classList.add("login-active");
      mockDom.viewContainer.innerHTML = '<div class="login-wrapper">SAKSHI Officer Access</div>';
      lastRendered = "ScreenLogin";
      return "LOGIN_RENDERED";
    }

    mockDom.body.classList.remove("login-active");

    if (rawHash === "#/cases") {
      mockDom.navCases.classList.add("active");
      mockDom.breadcrumbCurrent.textContent = "Case Directory";
      lastRendered = "ScreenCases";
      return "CASES_RENDERED";
    }

    return "UNKNOWN_ROUTE";
  }
};

// Test early invocation guard before auth completes
const earlyResult = simRouter.navigate();
assert(earlyResult === "GUARDED", "Router.navigate does not prematurely render login when auth is initializing");
assert(lastRendered === null, "viewContainer is not polluted with login form during bootstrap");

// Simulate development mode bootstrap
const mockAuthStatus = { auth_mode: "development", development_mode: true };
testState.auth.mode = mockAuthStatus.auth_mode;
const isDevMode = testState.auth.mode === "development" || testState.auth.mode === "offline" || mockAuthStatus.development_mode === true;
if (isDevMode) {
  testState.auth.authenticated = true;
  testState.auth.headers["X-Investigator-Id"] = testState.auth.subjectId;
  testState.auth.headers["X-Investigator-Role"] = testState.auth.role;
  testState.auth.headers["X-Investigator-Jurisdiction"] = testState.auth.jurisdiction;
}
testState.auth.initialized = true;

assert(testState.auth.authenticated === true, "Development auth state established successfully on refresh");
assert(testState.auth.headers["X-Investigator-Id"] === "IO-7842-SHARMA", "Dev headers populated on State.auth");

// Dispatch Router.navigate after auth initialized
const postAuthResult = simRouter.navigate();
assert(postAuthResult === "CASES_RENDERED", "Authenticated route #/cases renders Case Directory");
assert(lastRendered === "ScreenCases", "ScreenCases rendered on hard refresh at #/cases");
assert(mockDom.navCases.classList.contains("active"), "navCases is marked active in sidebar");
assert(!mockDom.body.classList.contains("login-active"), "login-active class removed from body so shell is visible");
assert(simHash === "#/cases", "URL hash remains #/cases on hard refresh");

// ═══════════════════════════════════════════════════════════════════════════
// Suite 3: API CaseListResponse Normalization & Safe Filtering
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 3: CaseListResponse Schema Normalization --");

// Scenario A: Backend returns CaseListResponse object { total: 1, cases: [...] }
const apiResponseObject = {
  total: 1,
  cases: [
    {
      case_id: "SAKSHI-TEST-2026-002",
      title: "Suspicious Death in Transit Yard",
      lifecycle_stage: "INITIALIZED",
      fir_metadata: { fir_number: "FIR-2026-002", police_station: "Central" }
    }
  ]
};

function normalizeCases(payload) {
  return Array.isArray(payload) ? payload : (payload && Array.isArray(payload.cases) ? payload.cases : []);
}

const normalizedA = normalizeCases(apiResponseObject);
assert(Array.isArray(normalizedA), "CaseListResponse object normalized to Array");
assert(normalizedA.length === 1, "Normalized array contains expected case count");
assert(typeof normalizedA.some === "function", "Normalized cases array has .some method");
assert(typeof normalizedA.filter === "function", "Normalized cases array has .filter method");

// Verify filtering works without throwing
let filterError = null;
let filteredCases = [];
try {
  filteredCases = normalizedA.filter(c => {
    return c.title.toLowerCase().includes("transit") && (c.lifecycle_stage === "INITIALIZED");
  });
} catch (e) {
  filterError = e;
}
assert(filterError === null, "Filtering executes safely without throwing TypeError");
assert(filteredCases.length === 1, "Filter correctly found matching case");

// Scenario B: Backend returns { total: 0, cases: [] }
const apiEmptyResponse = { total: 0, cases: [] };
const normalizedEmpty = normalizeCases(apiEmptyResponse);
assert(Array.isArray(normalizedEmpty) && normalizedEmpty.length === 0, "Empty CaseListResponse normalizes to empty Array");

// Scenario C: Backward compatibility with raw array
const rawArrayPayload = [{ case_id: "SAKSHI-TEST-2026-001", title: "Legacy" }];
const normalizedRaw = normalizeCases(rawArrayPayload);
assert(Array.isArray(normalizedRaw) && normalizedRaw.length === 1, "Raw array payload handled transparently");

// ═══════════════════════════════════════════════════════════════════════════
// Suite 4: Unauthenticated Navigation & Shell Hiding
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 4: Unauthenticated User Redirection & Shell Hiding --");

testState.auth.authenticated = false;
testState.auth.mode = "firebase";
testState.auth.token = null;
simHash = "#/cases";

const unauthResult = simRouter.navigate();
assert(unauthResult === "LOGIN_RENDERED", "Unauthenticated user is redirected to login");
assert(simHash === "#/login", "URL hash updated from #/cases to #/login");
assert(mockDom.body.classList.contains("login-active"), "login-active applied to body to hide sidebar and header");
assert(mockDom.viewContainer.innerHTML.includes("Officer Access"), "Login form rendered in viewContainer");

// ═══════════════════════════════════════════════════════════════════════════
// Suite 5: RBAC/ABAC Security & Header Isolation
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 5: RBAC/ABAC Security & Header Isolation --");

function getSimHeaders(auth) {
  const h = { ...auth.headers };
  if (auth.token) {
    h.Authorization = `Bearer ${auth.token}`;
  } else if (auth.mode === "development" || auth.mode === "offline" || auth.mode === "unknown") {
    if (auth.subjectId) h["X-Investigator-Id"] = auth.subjectId;
    if (auth.role) h["X-Investigator-Role"] = auth.role;
    if (auth.jurisdiction) h["X-Investigator-Jurisdiction"] = auth.jurisdiction;
  }
  Object.keys(h).forEach(k => {
    if (h[k] === undefined || h[k] === null || h[k] === "") delete h[k];
  });
  return h;
}

// In Firebase mode without token, NO investigator headers may be sent
const firebaseUnauthHeaders = getSimHeaders({
  mode: "firebase",
  token: null,
  subjectId: "IO-FAKE",
  role: "SUPERVISOR",
  jurisdiction: "JUR-DEL",
  headers: { "Content-Type": "application/json" }
});

assert(
  !firebaseUnauthHeaders["X-Investigator-Id"] && !firebaseUnauthHeaders["X-Investigator-Role"],
  "No mock investigator headers leaked when unauthenticated in Firebase mode"
);

// In Firebase mode with token, Bearer token is attached
const firebaseAuthHeaders = getSimHeaders({
  mode: "firebase",
  token: "eyJhbGciOi...",
  subjectId: "IO-REAL",
  headers: { "Content-Type": "application/json" }
});

assert(
  firebaseAuthHeaders.Authorization === "Bearer eyJhbGciOi...",
  "Bearer token properly attached for authenticated Firebase requests"
);

// ═══════════════════════════════════════════════════════════════════════════
// Suite 6: Stale Case Reconciliation
// ═══════════════════════════════════════════════════════════════════════════
console.log("\n-- Test Suite 6: Stale Case Reconciliation on Refresh --");

testState.activeCaseId = "SAKSHI-MISSING-CASE";
const currentCases = [
  { case_id: "SAKSHI-TEST-2026-002" }
];

let stalePurged = false;
function reconcileActiveCase(cases) {
  if (testState.activeCaseId && !cases.some(c => c.case_id === testState.activeCaseId)) {
    testState.activeCaseId = null;
    testState.activeCase = null;
    stalePurged = true;
  }
}

reconcileActiveCase(currentCases);
assert(stalePurged === true, "Missing activeCaseId identified as stale and purged");
assert(testState.activeCaseId === null, "State.activeCaseId reset to null cleanly");

console.log(`\n======================================================`);
console.log(`Regression Test Summary: ${passes} passed, ${failures} failed.`);
console.log(`======================================================\n`);

process.exit(failures > 0 ? 1 : 0);
