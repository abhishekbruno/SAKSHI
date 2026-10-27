/**
 * SAKSHI Forensic Investigation Platform
 * Fresh-Case End-to-End Workflow & Verification Suite
 * Verifies clean directory, manual registration, FIR-assisted ingestion,
 * evidence pipeline, RAG indexing, knowledge graph, timeline, and dossiers.
 */

const http = require('http');

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;

function assert(condition, message) {
  totalTests++;
  if (condition) {
    passedTests++;
    console.log(`  [PASS] ${message}`);
  } else {
    failedTests++;
    console.error(`  [FAIL] ${message}`);
  }
}

function makeRequest(options, postData = null) {
  return new Promise((resolve, reject) => {
    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          resolve({
            statusCode: res.statusCode,
            headers: res.headers,
            body: data ? JSON.parse(data) : null,
            rawBody: data
          });
        } catch (e) {
          resolve({
            statusCode: res.statusCode,
            headers: res.headers,
            body: data,
            rawBody: data
          });
        }
      });
    });
    req.on('error', (err) => reject(err));
    if (postData) {
      req.write(typeof postData === 'string' ? postData : JSON.stringify(postData));
    }
    req.end();
  });
}

async function runFreshCaseVerification() {
  console.log('=================================================================');
  console.log('SAKSHI Fresh-Case End-to-End Verification Suite');
  console.log('=================================================================\n');

  const devHeaders = {
    'X-Investigator-Id': 'dev-investigator-001',
    'X-Investigator-Role': 'INVESTIGATING_OFFICER',
    'X-Investigator-Jurisdiction': 'KERALA',
    'Content-Type': 'application/json'
  };

  // -----------------------------------------------------------------
  // 1. Verify Clean Case Directory Post-Reset
  // -----------------------------------------------------------------
  console.log('-- Step 1: Verify Clean Case Directory Post-Reset --');
  const listCasesRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: '/api/v1/cases',
    method: 'GET',
    headers: devHeaders
  });
  assert(listCasesRes.statusCode === 200, 'GET /api/v1/cases returns 200 OK');
  assert(listCasesRes.body.total === 0, `Case directory total is 0 (actual: ${listCasesRes.body.total})`);
  assert(listCasesRes.body.cases.length === 0, 'No old disposable test cases appear in case directory');

  // -----------------------------------------------------------------
  // 2. Manual Case Registration
  // -----------------------------------------------------------------
  console.log('\n-- Step 2: Manual Case Registration --');
  const uniqueFirSuffix = Math.floor(Math.random() * 90000 + 10000);
  const manualCasePayload = {
    title: "Unnatural Death at Kovalam Cliff Resort - Room 104",
    incident_type: "UNNATURAL_DEATH",
    fir_metadata: {
      fir_number: `FIR-KVL-2026-${uniqueFirSuffix}`,
      police_station: "Kovalam Police Station",
      incident_date: "2026-10-25T14:30:00Z",
      report_date: "2026-10-25T16:00:00Z",
      jurisdiction_code: "KERALA"
    },
    assigned_io_id: "dev-investigator-001",
    summary: "Investigation into suspected poisoning or unnatural death of male guest."
  };

  const manualCreateRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: '/api/v1/cases',
    method: 'POST',
    headers: devHeaders
  }, manualCasePayload);

  assert(manualCreateRes.statusCode === 201, 'POST /api/v1/cases creates manual case with status 201 Created');
  const manualCaseId = manualCreateRes.body.case_id;
  assert(typeof manualCaseId === 'string' && manualCaseId.startsWith('SAKSHI-CASE-'), `Assigned valid case ID: ${manualCaseId}`);
  assert(manualCreateRes.body.lifecycle_stage === 'INITIALIZED', 'Initial lifecycle stage is INITIALIZED');

  // -----------------------------------------------------------------
  // 3. FIR-Assisted Ingestion & Field Suggestions
  // -----------------------------------------------------------------
  console.log('\n-- Step 3: FIR-Assisted Ingestion & Field Suggestions --');
  const uniqueFirNum = `${Math.floor(Math.random() * 800 + 100)}/2026`;
  const syntheticFirText = `FIRST INFORMATION REPORT (Under Section 173 BNSS / 154 CrPC)
FIR No: ${uniqueFirNum}
Police Station: Cantonment Police Station
Place of Occurrence: Room 204, Royal Palms Residency, MG Road
Date of Report: 2026-10-25
Complainant: Rajesh K. Pillai
Deceased: Vikram Malhotra
Section: Section 194 BNSS
Brief Facts / Allegations:
Room service attendant discovered deceased guest Vikram Malhotra unresponsive on bed with superficial throat laceration and a kitchen knife of approximately 18 cm blade on the nightstand. No signs of forced entry. Guest Arjun Menon was seen departing room 204 at 02:15 hrs.`;

  const firPreviewRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: '/api/v1/cases/fir-preview',
    method: 'POST',
    headers: devHeaders
  }, { fir_text: syntheticFirText });

  assert(firPreviewRes.statusCode === 200, 'POST /cases/fir-preview returns 200 OK');
  assert(firPreviewRes.body.fir_number === uniqueFirNum, `Extracted FIR number ${uniqueFirNum} correctly`);
  assert(firPreviewRes.body.police_station === 'Cantonment Police Station', 'Extracted Police Station correctly');
  assert(firPreviewRes.body.complainant_name.includes('Rajesh'), 'Extracted Complainant name correctly');
  assert(firPreviewRes.body.victim_name.includes('Vikram Malhotra'), 'Extracted Deceased name correctly');
  assert(firPreviewRes.body.source_passages.length > 0, 'Extracted candidate passages with exact character offsets');

  // Submit FIR-assisted Case Creation
  const firAssistedPayload = {
    title: "Inquest into Unnatural Death of Vikram Malhotra",
    fir_text: syntheticFirText,
    fir_metadata: {
      fir_number: firPreviewRes.body.fir_number,
      police_station: firPreviewRes.body.police_station,
      jurisdiction_code: "KERALA",
      victim_name: firPreviewRes.body.victim_name,
      complainant_name: firPreviewRes.body.complainant_name
    },
    assigned_io_id: "dev-investigator-001"
  };

  const firCreateRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: '/api/v1/cases/fir-assisted',
    method: 'POST',
    headers: devHeaders
  }, firAssistedPayload);

  assert(firCreateRes.statusCode === 201, 'POST /cases/fir-assisted creates case with 201 Created');
  const firCaseId = firCreateRes.body.case.case_id;
  const initialExhibitId = firCreateRes.body.fir_evidence_id || firCreateRes.body.evidence_id;
  assert(typeof firCaseId === 'string' && (firCaseId.startsWith('SAKSHI-CASE-') || firCaseId.startsWith('SAKSHI-FIR-')), `Assigned valid case ID: ${firCaseId}`);
  assert(typeof initialExhibitId === 'string' && initialExhibitId.startsWith('SAKSHI-EVID-'), `Preserved initial FIR exhibit ID: ${initialExhibitId}`);
  assert(firCreateRes.body.case.lifecycle_stage === 'EVIDENCE_INGESTION', 'Case progressed to EVIDENCE_INGESTION stage for intake');

  // -----------------------------------------------------------------
  // 4. Evidence Verification & Preservation
  // -----------------------------------------------------------------
  console.log('\n-- Step 4: Evidence Verification & Preservation --');
  const getEvidenceRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/evidence/${initialExhibitId}`,
    method: 'GET',
    headers: devHeaders
  });
  assert(getEvidenceRes.statusCode === 200, 'GET exhibit metadata returns 200 OK');
  assert(getEvidenceRes.body.status === 'COMMITTED', 'Exhibit status is COMMITTED');
  assert(getEvidenceRes.body.worm_status === 'COMMITTED', 'WORM preservation status is COMMITTED');
  assert(getEvidenceRes.body.integrity_status === 'VERIFIED', 'Cryptographic SHA-256 integrity is VERIFIED');
  assert(typeof getEvidenceRes.body.checksum_sha256 === 'string' && getEvidenceRes.body.checksum_sha256.length === 64, 'Computed authentic 64-char SHA-256 fingerprint');

  // -----------------------------------------------------------------
  // 5. Entity Knowledge Graph & Citations
  // -----------------------------------------------------------------
  console.log('\n-- Step 5: Entity Knowledge Graph & Citations --');
  const graphRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/knowledge-graph`,
    method: 'GET',
    headers: devHeaders
  });
  assert(graphRes.statusCode === 200, 'GET /knowledge-graph returns 200 OK');
  assert(graphRes.body.nodes.length >= 4, `Knowledge graph generated ${graphRes.body.nodes.length} grounded nodes`);
  assert(graphRes.body.edges.length >= 4, `Knowledge graph generated ${graphRes.body.edges.length} citation-backed relationships`);
  const edge = graphRes.body.edges[0];
  assert(edge && edge.evidence_id === initialExhibitId, 'Graph relationship edge cites preserved FIR exhibit');
  assert(edge.citation && (edge.citation.cryptographic_hash || edge.citation.source_sha256), 'Graph relationship includes cryptographic citation');

  // -----------------------------------------------------------------
  // 6. Timeline & Chronological Events
  // -----------------------------------------------------------------
  console.log('\n-- Step 6: Timeline & Chronological Events --');
  const timelineRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/timeline-events`,
    method: 'GET',
    headers: devHeaders
  });
  assert(timelineRes.statusCode === 200, 'GET /timeline-events returns 200 OK');
  assert(timelineRes.body.events.length > 0, `Timeline extracted ${timelineRes.body.events.length} chronological events`);
  assert(timelineRes.body.events[0].evidence_id === initialExhibitId, 'Timeline events ground to authentic exhibit');

  // -----------------------------------------------------------------
  // 7. Dual-Brain Reasoning & Review Decisions
  // -----------------------------------------------------------------
  console.log('\n-- Step 7: Dual-Brain Reasoning & Review Decisions --');
  const dualBrainRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/dual-brain`,
    method: 'GET',
    headers: devHeaders
  });
  assert(dualBrainRes.statusCode === 200, 'GET /dual-brain returns 200 OK');
  assert(dualBrainRes.body.intuition_proposals.length > 0, 'Intuition Brain generated candidate explanations');
  assert(dualBrainRes.body.discipline_challenges.length > 0, 'Discipline Brain raised statutory legal challenges');
  assert(dualBrainRes.body.firewall_status === 'ACTIVE_ENFORCED', 'Information Firewall active (quarantines hypotheses from facts)');

  // Record an IO Review Decision on an Edge
  const edgeId = edge.id || edge.edge_id;
  const decisionRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/knowledge-graph/edges/${edgeId}/decision`,
    method: 'POST',
    headers: devHeaders
  }, {
    decision: "CONFIRMED",
    investigator_notes: "Verified against formal complainant statement under BNSS."
  });
  assert(decisionRes.statusCode === 200, 'POST edge review decision returns 200 OK');
  assert(decisionRes.body.new_status === 'CONFIRMED', 'Edge status updated to CONFIRMED');

  // -----------------------------------------------------------------
  // 8. Evidence Intelligence Unified Search & Dossiers (Phase F.1)
  // -----------------------------------------------------------------
  console.log('\n-- Step 8: Evidence Intelligence Unified Search & Dossiers --');
  const intelSearchRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/intelligence/search?q=Vikram&filter_type=ALL`,
    method: 'GET',
    headers: devHeaders
  });
  assert(intelSearchRes.statusCode === 200, 'GET /intelligence/search?q=Vikram returns 200 OK');
  assert(intelSearchRes.body.results.length > 0, 'Search returned grounded person/exhibit match');
  assert(intelSearchRes.body.case_id === firCaseId, 'Search response strictly case-scoped');

  // Exact Exhibit Search
  const exactExhibitRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/intelligence/search?q=${initialExhibitId}&filter_type=EVIDENCE`,
    method: 'GET',
    headers: devHeaders
  });
  assert(exactExhibitRes.statusCode === 200, 'Exact exhibit lookup returns 200 OK');
  assert(exactExhibitRes.body.results.length === 1, 'Exact exhibit match returned single exact record');
  assert(exactExhibitRes.body.results[0].match_type === 'EXACT_IDENTIFIER', 'Tag is EXACT_IDENTIFIER');

  // Unknown Exhibit Search (Negative Test)
  const unknownExhibitRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/intelligence/search?q=SAKSHI-EVID-UNKNOWN-999&filter_type=EVIDENCE`,
    method: 'GET',
    headers: devHeaders
  });
  assert(unknownExhibitRes.statusCode === 200, 'Unknown exhibit lookup returns 200 OK');
  assert(unknownExhibitRes.body.exact_match_found === false, 'exact_match_found is false');
  assert(unknownExhibitRes.body.results.length === 0, 'No similar exhibit returned silently');

  // Entity Registry
  const registryRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/intelligence/registry`,
    method: 'GET',
    headers: devHeaders
  });
  assert(registryRes.statusCode === 200, 'GET /intelligence/registry returns 200 OK');
  assert(registryRes.body.total_entities >= 4, `Cataloged ${registryRes.body.total_entities} entities in registry`);

  // Person Dossier
  const victimNode = graphRes.body.nodes.find(n => n.category === 'PERSON' && n.name.includes('Vikram')) || { id: 'node-person-victim' };
  const personDossierRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/intelligence/person/${victimNode.id}`,
    method: 'GET',
    headers: devHeaders
  });
  assert(personDossierRes.statusCode === 200, `GET /intelligence/person/${victimNode.id} returns 200 OK`);
  assert(personDossierRes.body.canonical_name.includes('Vikram Malhotra'), 'Person dossier canonical name is Vikram Malhotra');
  assert(personDossierRes.body.legal_safeguard.toLowerCase().includes('judicial caution'), 'Judicial caution notice present in dossier');

  // Object Dossier (Knife)
  const objectDossierRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/intelligence/object/obj-knife-1`,
    method: 'GET',
    headers: devHeaders
  });
  assert(objectDossierRes.statusCode === 200, 'GET /intelligence/object/obj-knife-1 returns 200 OK');
  assert(Array.isArray(objectDossierRes.body.characteristics_register), 'Characteristics register present');
  assert(objectDossierRes.body.forensic_limitations_notice.toLowerCase().includes('sharpness'), 'Forensic limitation alert present');

  // 6-Section Structured Answer Generation
  const askRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/intelligence/ask`,
    method: 'POST',
    headers: devHeaders
  }, { question: "What physical objects and persons were documented at the scene?" });
  assert(askRes.statusCode === 200, 'POST /intelligence/ask returns 200 OK');
  assert(askRes.body.answer_text.includes('1. DIRECTLY DOCUMENTED INFORMATION:'), 'Answer includes Section 1');
  assert(askRes.body.answer_text.includes('2. SUPPORTING SOURCE REFERENCES:'), 'Answer includes Section 2');
  assert(askRes.body.answer_text.includes('3. CONFLICTING OR INCONSISTENT INFORMATION:'), 'Answer includes Section 3');
  assert(askRes.body.answer_text.includes('4. MISSING OR UNDOCUMENTED INFORMATION:'), 'Answer includes Section 4');
  assert(askRes.body.answer_text.includes('5. POSSIBLE INTERPRETATIONS (HYPOTHESES ONLY):'), 'Answer includes Section 5');
  assert(askRes.body.answer_text.includes('6. SUGGESTED FOLLOW-UP QUESTIONS:'), 'Answer includes Section 6');

  // -----------------------------------------------------------------
  // 9. Investigation Analysis & Scenarios
  // -----------------------------------------------------------------
  console.log('\n-- Step 9: Investigation Analysis & Scenarios --');
  const analysisRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/analysis-summary`,
    method: 'GET',
    headers: devHeaders
  });
  assert(analysisRes.statusCode === 200, 'GET /analysis-summary returns 200 OK');
  assert(Array.isArray(analysisRes.body.supported_observations), 'Analysis includes supported observations array');
  assert(Array.isArray(analysisRes.body.candidate_scenarios), 'Analysis includes candidate scenarios array');
  assert(analysisRes.body.candidate_scenarios.every(s => s.hypothesis_disclaimer.includes('Hypothesis')), 'Candidate scenarios strictly flagged with hypothesis disclaimer');

  // -----------------------------------------------------------------
  // 10. Compact Investigation Overview & Stage Engine
  // -----------------------------------------------------------------
  console.log('\n-- Step 10: Compact Investigation Overview & Stage Engine --');
  const caseDetailRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}`,
    method: 'GET',
    headers: devHeaders
  });
  assert(caseDetailRes.statusCode === 200, 'GET /cases/:id returns 200 OK');
  assert(caseDetailRes.body.case_id === firCaseId, 'Case ID matches');
  assert(caseDetailRes.body.assigned_io_id === 'dev-investigator-001', 'Assigned IO matches');
  assert(caseDetailRes.body.fir_metadata && caseDetailRes.body.fir_metadata.fir_number === uniqueFirNum, 'FIR metadata persisted correctly');

  const stageRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/cases/${firCaseId}/stage`,
    method: 'GET',
    headers: devHeaders
  });
  assert(stageRes.statusCode === 200, 'GET /cases/:id/stage returns 200 OK');
  assert(stageRes.body.lifecycle_stage === 'EVIDENCE_INGESTION', 'Stage is EVIDENCE_INGESTION');
  assert(Array.isArray(stageRes.body.allowed_transitions), 'Stage engine reports valid allowed transitions');

  // -----------------------------------------------------------------
  // 11. Final Directory Verification
  // -----------------------------------------------------------------
  console.log('\n-- Step 11: Final Directory Verification --');
  const finalListRes = await makeRequest({
    hostname: '127.0.0.1',
    port: 8000,
    path: '/api/v1/cases',
    method: 'GET',
    headers: devHeaders
  });
  assert(finalListRes.statusCode === 200, 'GET /api/v1/cases returns 200 OK');
  assert(finalListRes.body.total === 2, `Directory contains exactly the 2 fresh cases (total: ${finalListRes.body.total})`);
  assert(finalListRes.body.cases.some(c => c.case_id === manualCaseId), `Case 1: ${manualCaseId} visible`);
  assert(finalListRes.body.cases.some(c => c.case_id === firCaseId), `Case 2: ${firCaseId} visible`);

  // -----------------------------------------------------------------
  // Final Summary
  // -----------------------------------------------------------------
  console.log('\n=================================================================');
  console.log(`Fresh-Case Workflow Verification: ${passedTests} passed, ${failedTests} failed.`);
  console.log('=================================================================\n');

  if (failedTests > 0) {
    process.exit(1);
  }
}

runFreshCaseVerification();
