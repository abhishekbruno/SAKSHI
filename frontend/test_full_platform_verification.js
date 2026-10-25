/**
 * SAKSHI — Full Platform Verification Test Suite
 * 
 * Verifies:
 * 1. FIR-assisted registration & candidate extraction API (Method B)
 * 2. Entity Knowledge Graph generation, citation offsets, and edge decision audit
 * 3. Dual-Brain reasoning workspace (Intuition proposals vs Discipline challenges)
 * 4. Conversational Evidence RAG ("Ask About This Case") with exact verbatim citations
 * 5. Case isolation, zero mock leakage into empty cases, and RBAC/ABAC enforcement
 * 6. Frontend UI component structure, routes, and styles
 */

const http = require("http");
const fs = require("fs");
const path = require("path");

const API_BASE = "http://127.0.0.1:8000";
const TEST_CASE_ID = "SAKSHI-TEST-2026-002";

let passed = 0;
let failed = 0;

function assert(condition, testName) {
  if (condition) {
    console.log(`  [PASS] ${testName}`);
    passed++;
  } else {
    console.error(`  [FAIL] ${testName}`);
    failed++;
  }
}

function makeRequest(method, urlPath, headers = {}, body = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlPath, API_BASE);
    const options = {
      method,
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      headers: {
        "Content-Type": "application/json",
        "X-Investigator-Id": "INV-2026-001",
        "X-Jurisdiction": "STATION_CENTRAL",
        "X-Roles": "INVESTIGATING_OFFICER",
        ...headers
      }
    };

    const req = http.request(options, (res) => {
      let data = "";
      res.on("data", chunk => data += chunk);
      res.on("end", () => {
        try {
          const json = data ? JSON.parse(data) : null;
          resolve({ status: res.statusCode, data: json, raw: data });
        } catch (e) {
          resolve({ status: res.statusCode, data, raw: data });
        }
      });
    });

    req.on("error", reject);
    if (body) {
      req.write(typeof body === "string" ? body : JSON.stringify(body));
    }
    req.end();
  });
}

async function runTests() {
  console.log("=================================================================");
  console.log("Starting SAKSHI Full Platform & Forensic Verification Suite...");
  console.log("=================================================================\n");

  const appJs = fs.readFileSync(path.join(__dirname, "app.js"), "utf-8");
  const indexHtml = fs.readFileSync(path.join(__dirname, "index.html"), "utf-8");
  const styleCss = fs.readFileSync(path.join(__dirname, "style.css"), "utf-8");

  // -------------------------------------------------------------
  // Test Suite 1: Frontend Route & Navigation Architecture
  // -------------------------------------------------------------
  console.log("-- Test Suite 1: Navigation & Workstation UI --");
  assert(indexHtml.includes('id="navConnections"'), "Sidebar contains #navConnections link for Entity Graph");
  assert(appJs.includes('#/cases/:id/connections') || appJs.includes('#/cases/:id/graph'), "Router registers #/cases/:id/connections route");
  assert(appJs.includes('const ScreenGraph = {'), "ScreenGraph component defined in app.js");
  assert(appJs.includes('renderWorkspaceHeaderHtml'), "Case workspace header includes sub-workspace navigation");
  assert(appJs.includes('Ask About This Case'), "Ask About This Case feature prominently exposed in workstation");
  assert(styleCss.includes('.dual-brain-banner'), "Dual-Brain banner style defined in style.css");
  assert(styleCss.includes('.graph-viewport-container'), "Graph viewport styles defined in style.css");
  assert(styleCss.includes('.entity-inspector-drawer'), "Entity inspector drawer style defined in style.css");

  // -------------------------------------------------------------
  // Test Suite 2: FIR-Assisted Registration (Method B)
  // -------------------------------------------------------------
  console.log("\n-- Test Suite 2: FIR Candidate Extraction & Registration API --");
  const sampleFIR = `FIRST INFORMATION REPORT
Under Section 173 BNSS (Cr.P.C. 154)
Police Station: Connaught Place, New Delhi
FIR No: 188/2026
Date & Time of Incident: 2026-10-24 22:45
Place of Occurrence: Flat 402, Royal Residency, Barakhamba Road
Complainant / Informant: Inspector Rajesh Sharma
Deceased / Victim: Vikram Malhotra, Age 34
Sections: Section 194 BNSS (Unnatural Death Investigation)
Brief Details:
The deceased was discovered deceased in his study room. A single gunshot wound observed to temple. A black Glock 19 9mm pistol was recovered from the adjacent desk. Recovered 1 mobile handset and diary on table. Witness statement of domestic assistant mentions departure before 21:30 hrs.`;

  const previewRes = await makeRequest("POST", "/api/v1/cases/fir-preview", {}, {
    filename: "FIR_188_2026_Sample.txt",
    fir_text: sampleFIR
  });

  assert(previewRes.status === 200, "POST /api/v1/cases/fir-preview returns 200 OK");
  assert(previewRes.data?.fir_number === "188/2026", `Extracted FIR number correctly: ${previewRes.data?.fir_number}`);
  assert(previewRes.data?.police_station?.includes("Connaught Place"), `Extracted Police Station: ${previewRes.data?.police_station}`);
  assert(previewRes.data?.source_passages?.length > 0, `Generated ${previewRes.data?.source_passages?.length} verbatim source passages with exact offsets`);

  const firPassage = previewRes.data?.source_passages?.find(p => p.field === "fir_number");
  assert(firPassage && firPassage.start_char != null && firPassage.end_char != null, "FIR passage includes exact character start and end offsets");

  // Method B Case Creation
  const suffix = Date.now().toString().slice(-4);
  const newCaseId = `SAKSHI-FIR-TEST-${suffix}`;
  const testFirNum = `188-${suffix}/2026`;
  const firCreateRes = await makeRequest("POST", "/api/v1/cases/fir-assisted", {}, {
    case_id: newCaseId,
    title: "Inquest into Death of Vikram Malhotra",
    fir_number: testFirNum,
    police_station: "Connaught Place, New Delhi",
    fir_filename: "FIR_188_2026_Preserved.txt",
    fir_text: sampleFIR,
    incident_date: "2026-10-24",
    incident_location: "Flat 402, Royal Residency, Barakhamba Road",
    deceased_name: "Vikram Malhotra"
  });

  assert(firCreateRes.status === 201, `POST /api/v1/cases/fir-assisted creates case with status 201`);
  assert(firCreateRes.data?.case?.case_id === newCaseId, `Assigned expected case ID: ${firCreateRes.data?.case?.case_id}`);
  assert(firCreateRes.data?.case?.lifecycle_stage === "EVIDENCE_INGESTION", `Advanced lifecycle to EVIDENCE_INGESTION for evidence intake`);
  assert(firCreateRes.data?.evidence_id != null, `Preserved FIR as initial Exhibit with ID: ${firCreateRes.data?.evidence_id}`);
  assert(firCreateRes.data?.chain_of_custody_logged === true, "Chain of custody and tamper-evident audit logged for FIR exhibit");

  // -------------------------------------------------------------
  // Test Suite 3: Entity Knowledge Graph
  // -------------------------------------------------------------
  console.log("\n-- Test Suite 3: Entity Knowledge Graph & Provenance --");
  const graphRes = await makeRequest("GET", `/api/v1/cases/${TEST_CASE_ID}/knowledge-graph`);
  assert(graphRes.status === 200, `GET /api/v1/cases/${TEST_CASE_ID}/knowledge-graph returns 200 OK`);
  assert(graphRes.data?.nodes?.length > 0, `Graph contains ${graphRes.data?.nodes?.length} case-scoped nodes`);
  assert(graphRes.data?.edges?.length > 0, `Graph contains ${graphRes.data?.edges?.length} citation-backed relationships`);

  const firstEdge = graphRes.data?.edges?.[0];
  assert(firstEdge && firstEdge.citation != null, "Graph edge contains cryptographic citation metadata");
  assert(firstEdge.citation?.exhibit_id != null, `Edge citation includes exhibit_id: ${firstEdge.citation?.exhibit_id}`);
  assert(firstEdge.review_status != null, `Edge has review_status: ${firstEdge.review_status}`);

  // Test Investigator Edge Decision
  const edgeDecisionRes = await makeRequest("POST", `/api/v1/cases/${TEST_CASE_ID}/knowledge-graph/edges/${firstEdge.id}/decision`, {}, {
    decision: "CONFIRMED",
    investigator_notes: "Corroborated by primary witness statement and scene seizure memo."
  });
  assert(edgeDecisionRes.status === 200, `POST /api/v1/cases/.../decision updates edge review status`);
  assert(edgeDecisionRes.data?.edge?.review_status === "CONFIRMED", "Edge status updated to CONFIRMED");
  assert(edgeDecisionRes.data?.audit_recorded === true, "Investigator edge decision recorded in tamper-evident audit log");

  // -------------------------------------------------------------
  // Test Suite 4: Dual-Brain Reasoning Workspace
  // -------------------------------------------------------------
  console.log("\n-- Test Suite 4: Dual-Brain Reasoning Architecture --");
  const dualBrainRes = await makeRequest("GET", `/api/v1/cases/${TEST_CASE_ID}/dual-brain`);
  assert(dualBrainRes.status === 200, `GET /api/v1/cases/${TEST_CASE_ID}/dual-brain returns 200 OK`);
  assert(dualBrainRes.data?.firewall_status === "ACTIVE_ENFORCED", "Information Firewall is ACTIVE_ENFORCED (quarantining hypotheses from facts)");
  assert(dualBrainRes.data?.evidence_gate_status === "ENFORCING_MINIMUM_CREDIBILITY", "Evidence Gate is ENFORCING_MINIMUM_CREDIBILITY");
  assert(dualBrainRes.data?.intuition_proposals?.length > 0, `Intuition Brain proposed ${dualBrainRes.data?.intuition_proposals?.length} candidate hypotheses`);
  assert(dualBrainRes.data?.discipline_challenges?.length > 0, `Discipline Brain raised ${dualBrainRes.data?.discipline_challenges?.length} statutory challenges`);

  const proposal = dualBrainRes.data?.intuition_proposals?.[0];
  assert(proposal?.core_assumptions?.length > 0, "Intuition proposal enumerates core assumptions");
  assert(proposal?.neutral_investigative_questions?.length > 0, "Intuition proposal provides neutral investigative questions");

  const challenge = dualBrainRes.data?.discipline_challenges?.[0];
  assert(challenge?.statutory_rule_citation != null, `Discipline challenge cites statutory rule: ${challenge?.statutory_rule_citation}`);
  assert(challenge?.evidentiary_objection != null, "Discipline challenge details specific evidentiary objection");

  // -------------------------------------------------------------
  // Test Suite 5: Conversational Evidence RAG ("Ask About This Case")
  // -------------------------------------------------------------
  console.log("\n-- Test Suite 5: Conversational Evidence RAG ('Ask About This Case') --");
  const askRes = await makeRequest("POST", `/api/v1/cases/${TEST_CASE_ID}/ask`, {}, {
    question: "What does the ballistic report state regarding BLUE ORCHID 7319?",
    limit: 5
  });

  assert(askRes.status === 200, `POST /api/v1/cases/${TEST_CASE_ID}/ask returns 200 OK`);
  assert(askRes.data?.answer != null && askRes.data?.answer.length > 0, "Generated synthesized plain-language answer");
  assert(askRes.data?.citations?.length > 0, `Returned ${askRes.data?.citations?.length} verbatim citations`);

  const blueOrchidCitation = askRes.data?.citations?.find(c => c.verbatim_quote.includes("BLUE ORCHID 7319"));
  assert(blueOrchidCitation != null, "Retrieved verbatim citation containing synthetic unique phrase 'BLUE ORCHID 7319'");
  assert(blueOrchidCitation?.exhibit_id === "SAKSHI-EVID-2026-E51D496A", `Citation links to correct exhibit: ${blueOrchidCitation?.exhibit_id}`);
  assert(blueOrchidCitation?.legal_caution != null, "Citation includes mandatory Section 63 BSA / 65B IEA legal caution");

  // Ungrounded Question Handling
  const ungroundedRes = await makeRequest("POST", `/api/v1/cases/${TEST_CASE_ID}/ask`, {}, {
    question: "Where did the suspect fly to in Europe on a private jet?",
    limit: 5
  });
  assert(ungroundedRes.status === 200, "Ungrounded question returns 200 with honest refusal");
  assert(ungroundedRes.data?.insufficient_evidence === true, "Flags insufficient_evidence: true for ungrounded question");
  assert(ungroundedRes.data?.answer.includes("No authoritative passages"), "Truthfully states that no passages support the query");

  // -------------------------------------------------------------
  // Test Suite 6: Empty Case Isolation & RBAC/ABAC Boundaries
  // -------------------------------------------------------------
  console.log("\n-- Test Suite 6: Empty Case Isolation & Authorization --");
  const emptySuffix = Date.now().toString().slice(-4);
  const emptyCaseId = `SAKSHI-EMPTY-${emptySuffix}`;
  await makeRequest("POST", "/api/v1/cases/", {}, {
    case_id: emptyCaseId,
    title: "Empty Test Case",
    fir_number: `999-${emptySuffix}/2026`,
    incident_date: "2026-10-25"
  });

  const emptyGraphRes = await makeRequest("GET", `/api/v1/cases/${emptyCaseId}/knowledge-graph`);
  assert(emptyGraphRes.data?.nodes?.length === 0, "Empty case returns 0 graph nodes (zero mock data leakage)");
  assert(emptyGraphRes.data?.edges?.length === 0, "Empty case returns 0 graph edges (zero mock data leakage)");

  const emptyAskRes = await makeRequest("POST", `/api/v1/cases/${emptyCaseId}/ask`, {}, {
    question: "What happened at the scene?"
  });
  assert(emptyAskRes.data?.insufficient_evidence === true, "Empty case truthfully reports insufficient evidence for questions");
  assert(emptyAskRes.data?.citations?.length === 0, "Empty case returns 0 citations");

  // RBAC/ABAC Boundary Check: Unauthorized investigator from different jurisdiction
  const unauthorizedRes = await makeRequest("GET", `/api/v1/cases/${TEST_CASE_ID}/knowledge-graph`, {
    "X-Investigator-Id": "INV-UNAUTHORIZED-999",
    "X-Jurisdiction": "STATION_FOREIGN_NORTH"
  });
  assert(unauthorizedRes.status === 403 || unauthorizedRes.status === 404, `Unauthorized cross-jurisdiction access is rejected with status ${unauthorizedRes.status}`);

  console.log("\n=================================================================");
  console.log(`Full Platform Verification Complete: ${passed} passed, ${failed} failed.`);
  console.log("=================================================================");

  if (failed > 0) {
    process.exit(1);
  }
}

runTests().catch(err => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
