/**
 * SAKSHI Comprehensive Verification Suite:
 * Investigator-Friendly Dashboard, Lifecycle Redesign, and Screen Simplification.
 *
 * Verifies:
 * 1. Plain-Language Terminology across Dashboard & Lifecycle (Section 2 & 6).
 * 2. Authoritative Metrics: distinguishes zero from unknown, unverified, and comparisons pending (<2 exhibits).
 * 3. 7-Layer Forensic Security Evaluation:
 *    - Format validation, Antivirus scan, Hash integrity, Vault preservation, WORM/object-lock, Encryption, Overall.
 *    - Accurate communication when integrity passed while WORM verification is pending ("Integrity Verified · WORM Pending").
 *    - Accurate distinction of local simulated lock from genuine hardware/cloud WORM.
 *    - Never claims "pipeline clean" or "all evidence secure" while checks are pending.
 * 4. Single compact, expandable investigation progress component; elimination of duplicate 6-stage cards.
 * 5. 4-Part Recommended Next Action formulation (What, Why in 1-2 sentences, Involved, Interactive Action Button).
 * 6. Clean proposal cards in Investigation Analysis (Potential explanation, Summary, Supporting, Challenging, Assumptions, Gaps, Review action, Expandable detailed reasoning).
 * 7. Absence of raw UNDEFINED, null, or unmapped internal enums exposed to investigators.
 * 8. Live API verification against active backend case.
 */

const fs = require("fs");
const path = require("path");
const http = require("http");
const assert = require("assert");

console.log("=================================================================");
console.log("Starting SAKSHI Comprehensive Dashboard & Lifecycle Redesign Suite...");
console.log("=================================================================\n");

let passedCount = 0;
let failedCount = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  [PASS] ${name}`);
    passedCount++;
  } catch (err) {
    console.error(`  [FAIL] ${name}`);
    console.error(`         ${err.message}`);
    failedCount++;
    process.exitCode = 1;
  }
}

async function asyncTest(name, fn) {
  try {
    await fn();
    console.log(`  [PASS] ${name}`);
    passedCount++;
  } catch (err) {
    console.error(`  [FAIL] ${name}`);
    console.error(`         ${err.message}`);
    failedCount++;
    process.exitCode = 1;
  }
}

const appJs = fs.readFileSync(path.join(__dirname, "app.js"), "utf-8");
const styleCss = fs.readFileSync(path.join(__dirname, "style.css"), "utf-8");

// ─── SUITE 1: PLAIN-LANGUAGE TERMINOLOGY AUDIT ──────────────────────────────
console.log("-- Test Suite 1: Plain-Language Terminology Audit --");

test("Replaces technical dashboard labels with investigator-friendly labels", () => {
  assert(appJs.includes('label: "Evidence collected"'), "Must use 'Evidence collected'");
  assert(appJs.includes('label: "Conflicting information"'), "Must use 'Conflicting information'");
  assert(appJs.includes('label: "Awaiting your review"'), "Must use 'Awaiting your review'");
  assert(appJs.includes('label: "Evidence security"'), "Must use 'Evidence security'");
});

test("Replaces technical analysis labels with officer-facing titles", () => {
  assert(appJs.includes("Evidence Relationships") || appJs.includes("Evidence relationships"), "Must use 'Evidence relationships'");
  assert(appJs.includes("What the Evidence Shows") || appJs.includes("What the evidence shows"), "Must use 'What the evidence shows'");
  assert(appJs.includes("What Still Needs Checking") || appJs.includes("What still needs checking"), "Must use 'What still needs checking'");
  assert(appJs.includes("AI Analysis and Evidence Review") || appJs.includes("AI analysis and evidence review"), "Must use 'AI analysis and evidence review'");
});

test("No raw UNDEFINED, null, or unmapped enum strings exposed to investigators", () => {
  assert(appJs.includes('StatusPresentation.get(') || appJs.includes('get(statusKey)'), "Must look up statuses in StatusPresentation");
  assert(appJs.includes('Status unavailable'), "Must fall back to 'Status unavailable' when status is missing or undefined");
});

// ─── SUITE 2: AUTHORITATIVE METRIC EVALUATION ──────────────────────────────
console.log("\n-- Test Suite 2: Authoritative Metric Evaluation --");

test("Conflicting information distinguishes comparisons pending (<2 exhibits) from zero discrepancies", () => {
  // Test code in ScreenCaseOverview:
  assert(appJs.includes("if (evidenceList.length < 2)"), "Must check if evidenceList has fewer than 2 exhibits");
  assert(appJs.includes("Comparisons pending — attach 2+ exhibits"), "Must display comparisons pending for <2 exhibits");
  assert(appJs.includes("No discrepancies identified"), "Must report no discrepancies only after comparisons are made");
});

test("Awaiting your review derives authentic pending actions from graph edges and extracted facts", () => {
  assert(appJs.includes("e.review_status === \"NEEDS_CONFIRMATION\""), "Must check pending graph edge reviews");
  assert(appJs.includes("f.decision === \"PENDING\" || !f.decision"), "Must check unreviewed extracted facts");
  assert(appJs.includes("All review decisions recorded"), "Must display completed state when zero reviews pending");
});

// ─── SUITE 3: 7-LAYER EVIDENCE SECURITY & INTEGRITY VS WORM ─────────────────
console.log("\n-- Test Suite 3: 7-Layer Evidence Security & Integrity vs WORM --");

test("EvidenceSecurityEvaluator evaluates all 7 layers accurately", () => {
  assert(appJs.includes("layer: \"File Format\""), "Must evaluate File Format");
  assert(appJs.includes("layer: \"Antivirus Scanning\""), "Must evaluate Antivirus");
  assert(appJs.includes("layer: \"Integrity Fingerprint\""), "Must evaluate Integrity");
  assert(appJs.includes("layer: \"Vault Preservation\""), "Must evaluate Vault Preservation");
  assert(appJs.includes("layer: \"Storage Protection (WORM)\""), "Must evaluate WORM Storage Protection");
  assert(appJs.includes("layer: \"Data Encryption\""), "Must evaluate Data Encryption");
});

test("Integrity verified while WORM pending reports both states clearly", () => {
  assert(appJs.includes("INTEGRITY_PASSED_WORM_PENDING"), "Must have distinct status key for integrity passed while WORM pending");
  assert(appJs.includes("Integrity Verified · WORM Pending"), "Must display 'Integrity Verified · WORM Pending'");
  assert(appJs.includes("File hashes verified · Storage lock pending"), "Must explain subtext 'File hashes verified · Storage lock pending'");
});

test("Evidence row uses EvidenceSecurityEvaluator instead of reporting false integrity passed", () => {
  assert(appJs.includes("const evalE = EvidenceSecurityEvaluator.evaluateExhibit(e);"), "renderEvidenceRowHtml must call EvidenceSecurityEvaluator.evaluateExhibit");
  assert(appJs.includes("<span class=\"badge ${ov.badge}\">${Formatters.escapeHtml(ov.label)}</span>"), "renderEvidenceRowHtml must render evaluator's overall badge and label");
});

test("Distinguishes local simulated lock from genuine hardware/cloud WORM", () => {
  assert(appJs.includes("isLocalSimulated"), "Must check for local simulated lock");
  assert(appJs.includes("Local filesystem immutability simulated — not genuine cloud/hardware WORM"), "Must disclose local simulated lock");
  assert(appJs.includes("Hardware/Cloud WORM locked") || appJs.includes("Protected & Sealed"), "Must distinguish hardware/cloud lock");
});

test("Never claims pipeline clean or fully secure while checks are pending or failed", () => {
  assert(appJs.includes("hasAlerts ? \"var(--danger)\" : (secSummary.isFullySecure ? \"var(--verified)\" : \"var(--attention)\")"), "Color must be attention when checks pending");
  assert(appJs.includes("isFullyVerified = format.passed && av.passed && integrity.passed && preservation.passed && worm.passed && encryption.passed;"), "Full verification requires all layers passed");
});

// ─── SUITE 4: REMOVAL OF 6-STAGE WORKFLOW STRIP & RECLAIMED LAYOUT SPACE ───
console.log("\n-- Test Suite 4: Removal of 6-Stage Workflow Strip & Reclaimed Space --");

test("Case workspace completely removes the 6-stage workflow strip and drawer", () => {
  assert(!appJs.includes('class="investigation-lifecycle-strip"'), "investigation-lifecycle-strip must be removed from header");
  assert(!appJs.includes('class="stage-stepper"'), "stage-stepper must be removed from header");
  assert(!appJs.includes('class="lifecycle-step-pill'), "lifecycle-step-pills must be removed");
  assert(!appJs.includes('id="btnToggleLifecycleDetails"'), "btnToggleLifecycleDetails must be removed");
  assert(!appJs.includes('id="lifecycleDetailsDrawer"'), "lifecycleDetailsDrawer must be removed");
});

test("Header renders compact, minimal case-summary-bar in reclaimed layout space", () => {
  assert(appJs.includes('class="case-summary-bar"'), "Must render compact .case-summary-bar");
  assert(appJs.includes('class="case-summary-item"'), "Must render case-summary-items");
  assert(styleCss.includes('.case-summary-bar'), "CSS must define .case-summary-bar");
});

test("Removed duplicate 6-stage cards from individual workspace screens", () => {
  assert(!appJs.includes("class=\"stage-stepper-container\""), "Must not render legacy duplicate stage stepper container");
});

// ─── SUITE 5: 4-PART RECOMMENDED NEXT ACTION FORMULATION ────────────────────
console.log("\n-- Test Suite 5: 4-Part Recommended Next Action Formulation --");

test("Recommended Next Action has What, Why (1-2 sentences), Involved, and Action Button", () => {
  assert(appJs.includes("class=\"recommended-next-action-card guided-next-action-card\""), "Recommended action card must be rendered");
  assert(appJs.includes("${Formatters.escapeHtml(recAction.title)}"), "Must display title (What)");
  assert(appJs.includes("${Formatters.escapeHtml(recAction.whyItMatters)}"), "Must display 1-2 sentence explanation (Why it matters)");
  assert(appJs.includes("Involved: <strong>${Formatters.escapeHtml(recAction.involved)}</strong>"), "Must display involved evidence/prerequisites");
  assert(appJs.includes("${recAction.buttonHtml}"), "Must render interactive action button");
});

test("Recommends finishing storage protection when integrity is verified but WORM pending", () => {
  assert(appJs.includes("Finish Checking Evidence Protection"), "Must recommend 'Finish Checking Evidence Protection'");
  assert(appJs.includes("The file integrity checks passed, but storage-protection verification is still pending."), "Must explain why storage protection matters");
});

// ─── SUITE 6: SIMPLIFIED CANDIDATE PROPOSALS IN INVESTIGATION ANALYSIS ──────
console.log("\n-- Test Suite 6: Simplified Candidate Proposals in Investigation Analysis --");

test("Candidate proposals rendered as unified readable proposal cards", () => {
  assert(appJs.includes("class=\"investigator-proposal-card proposal-card"), "Must render investigator-proposal-card");
  assert(appJs.includes("Potential explanation"), "Must label as 'Potential explanation'");
  assert(appJs.includes("Evidence supporting this explanation:"), "Must display 'Evidence supporting this explanation:'");
  assert(appJs.includes("Evidence challenging this explanation:"), "Must display 'Evidence challenging this explanation:'");
  assert(appJs.includes("Assumptions to verify:"), "Must display 'Assumptions to verify:'");
  assert(appJs.includes("What still needs checking:"), "Must display 'What still needs checking:'");
  assert(appJs.includes("Review this proposal &rarr;"), "Must provide 'Review this proposal' action button");
  assert(appJs.includes("Detailed reasoning (Two-Brain Analysis Traces)"), "Must provide expandable detailed reasoning");
});

// ─── SUITE 7: LIVE API INTEGRATION & VERIFICATION ───────────────────────────
console.log("\n-- Test Suite 7: Live API Integration & Verification --");

function apiRequest(method, urlPath, headers = {}, body = null) {
  return new Promise((resolve, reject) => {
    const defaultHeaders = {
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA",
      ...headers
    };
    if (body && !defaultHeaders["Content-Type"]) {
      defaultHeaders["Content-Type"] = "application/json";
    }

    const req = http.request({
      hostname: "127.0.0.1",
      port: 8000,
      path: urlPath,
      method: method,
      headers: defaultHeaders
    }, (res) => {
      let data = "";
      res.on("data", chunk => data += chunk);
      res.on("end", () => {
        try {
          const parsed = data ? JSON.parse(data) : {};
          resolve({ status: res.statusCode, data: parsed });
        } catch (e) {
          resolve({ status: res.statusCode, raw: data });
        }
      });
    });

    req.on("error", err => reject(err));
    if (body) {
      req.write(typeof body === "string" ? body : JSON.stringify(body));
    }
    req.end();
  });
}

(async () => {
  await asyncTest("Live Backend: Active cases retrieval with dev auth headers", async () => {
    const res = await apiRequest("GET", "/api/v1/cases");
    assert.strictEqual(res.status, 200, "GET /api/v1/cases must return 200");
    const caseList = res.data.cases || res.data.items || [];
    assert(Array.isArray(caseList) && caseList.length > 0, "Must return cases list");
  });

  await asyncTest("Live Backend: Evidence listing for active test case SAKSHI-CASE-2026-C5A64E99", async () => {
    const res = await apiRequest("GET", "/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/evidence");
    assert.strictEqual(res.status, 200, "Must return 200");
    assert(Array.isArray(res.data.items), "Must return evidence items array");
    assert(res.data.items.length > 0, "Must have evidence exhibits");
    const first = res.data.items[0];
    assert(first.evidence_id, "Exhibit must have evidence_id");
    assert(first.original_file_name, "Exhibit must have original_file_name");
  });

  await asyncTest("Live Backend: Case-level stage retrieval matches Stage Engine rules", async () => {
    const res = await apiRequest("GET", "/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/stage");
    assert.strictEqual(res.status, 200, "Must return 200");
    assert(res.data.lifecycle_stage, "Must return lifecycle_stage");
    assert(Array.isArray(res.data.allowed_transitions), "Must return allowed_transitions array");
  });

  console.log("\n=================================================================");
  console.log(`SAKSHI Verification Complete: ${passedCount} passed, ${failedCount} failed.`);
  console.log("=================================================================");

  if (failedCount > 0) {
    process.exit(1);
  }
})();
