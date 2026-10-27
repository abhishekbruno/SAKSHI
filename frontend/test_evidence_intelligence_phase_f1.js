/**
 * SAKSHI Forensic Investigation Platform
 * Phase F.1 — Evidence Intelligence, Entity Registry and Investigative Dossiers
 * Comprehensive Verification & Automated Test Suite
 */

const fs = require('fs');
const path = require('path');
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

async function runTests() {
  console.log('=================================================================');
  console.log('Starting SAKSHI Phase F.1 Evidence Intelligence Verification Tests...');
  console.log('=================================================================\n');

  const appJsPath = path.join(__dirname, 'app.js');
  const styleCssPath = path.join(__dirname, 'style.css');
  const appJs = fs.readFileSync(appJsPath, 'utf8');
  const styleCss = fs.readFileSync(styleCssPath, 'utf8');

  // -----------------------------------------------------------------
  // Suite 1: Frontend API Client Extensions for Intelligence
  // -----------------------------------------------------------------
  console.log('-- Test Suite 1: Frontend Api Client for Phase F.1 --');
  assert(appJs.includes('async searchEvidenceIntelligence('), 'Api.searchEvidenceIntelligence method defined');
  assert(appJs.includes('async getPersonDossier('), 'Api.getPersonDossier method defined');
  assert(appJs.includes('async getObjectDossier('), 'Api.getObjectDossier method defined');
  assert(appJs.includes('async getEntityRegistry('), 'Api.getEntityRegistry method defined');
  assert(appJs.includes('async getSourceComparisons('), 'Api.getSourceComparisons method defined');
  assert(appJs.includes('async getInvestigationFollowups('), 'Api.getInvestigationFollowups method defined');
  assert(appJs.includes('async askEvidenceIntelligence('), 'Api.askEvidenceIntelligence method defined');

  // -----------------------------------------------------------------
  // Suite 2: Unified Search Controls & Match Presentation
  // -----------------------------------------------------------------
  console.log('\n-- Test Suite 2: Unified Search Controls & Match Presentation --');
  assert(appJs.includes('id="unifiedIntelInput"'), 'Unified search input element present in ScreenRAGSearch');
  assert(appJs.includes('id="unifiedIntelFilterSelect"'), 'Search type filter select dropdown present');
  assert(appJs.includes('value="ALL"'), 'Search filter includes ALL Records option');
  assert(appJs.includes('value="EVIDENCE"'), 'Search filter includes EVIDENCE / Exhibit option');
  assert(appJs.includes('value="PERSON"'), 'Search filter includes PERSON option');
  assert(appJs.includes('value="OBJECT"'), 'Search filter includes OBJECT option');
  assert(appJs.includes('value="LOCATION"'), 'Search filter includes LOCATION option');
  assert(appJs.includes('value="EVENT"'), 'Search filter includes EVENT option');
  assert(appJs.includes('value="SOURCE_PASSAGE"'), 'Search filter includes SOURCE_PASSAGE option');
  assert(appJs.includes('interactions involving Arjun Menon') && appJs.includes('knife length'), 'Quick investigative inquiry buttons rendered');
  assert(appJs.includes('exact_match_found === false') && appJs.includes('No Matching Exhibit Record Found'), 'Explicit handling for missing exact exhibit identifiers');
  assert(appJs.includes('disambiguation_required') && appJs.includes('disambiguation-banner'), 'Explicit disambiguation presentation for ambiguous entities');

  // -----------------------------------------------------------------
  // Suite 3: Person Dossier Structure & Safeguards
  // -----------------------------------------------------------------
  console.log('\n-- Test Suite 3: Person Dossier Structure & Judicial Safeguards --');
  assert(appJs.includes('async openPersonDossierModal('), 'openPersonDossierModal launcher defined');
  assert(appJs.includes('Identity Details'), 'Section A: Identity details tab rendered');
  assert(appJs.includes('Relationship Map'), 'Section B: Documented relationship map tab rendered');
  assert(appJs.includes('Reported Interactions'), 'Section C: Reported interactions tab rendered');
  assert(appJs.includes('Associated Evidence'), 'Section D: Associated case exhibits tab rendered');
  assert(appJs.includes('Timeline Mentions'), 'Section E: Chronological timeline tab rendered');
  assert(appJs.includes('Conflicts &amp; Gaps'), 'Section F: Conflicts and discrepancies tab rendered');
  assert(appJs.includes('Judicial Caution:') && appJs.includes('dossier.legal_safeguard'), 'Judicial caution notice explicitly rendered in person dossier');

  // -----------------------------------------------------------------
  // Suite 4: Object Dossier & Forensic Reliability Limitations
  // -----------------------------------------------------------------
  console.log('\n-- Test Suite 4: Object Dossier & Forensic Reliability Limitations --');
  assert(appJs.includes('async openObjectDossierModal('), 'openObjectDossierModal launcher defined');
  assert(appJs.includes('characteristics-table'), 'Characteristics register structured table rendered');
  assert(appJs.includes('Not documented in available evidence'), 'Explicit "Not documented in available evidence" markers used for missing attributes');
  assert(appJs.includes('forensic-limitations-alert'), 'Forensic limitation alert styled with caution theme');
  assert(appJs.includes('Forensic Limitation Notice:') && appJs.includes('dossier.forensic_limitations_notice'), 'Rule: No inference of sharpness/cutting capability without documented lab examination');

  // -----------------------------------------------------------------
  // Suite 5: Registry, Source Comparison & Gaps Modals
  // -----------------------------------------------------------------
  console.log('\n-- Test Suite 5: Registry, Source Comparison & Gap Modals --');
  assert(appJs.includes('async openRegistryModal('), 'openRegistryModal defined');
  assert(appJs.includes('async openSourceComparisonModal('), 'openSourceComparisonModal defined');
  assert(appJs.includes('async openFollowupModal('), 'openFollowupModal defined');
  assert(appJs.includes('Case Entity &amp; Exhibit Registry'), 'Case Entity Registry rendered');
  assert(appJs.includes('Source Comparisons'), 'Side-by-side claim comparison rendered');
  assert(appJs.includes('Gaps &amp; Actions') || appJs.includes('Investigation Gaps'), 'Investigation follow-up recommendations rendered');

  // -----------------------------------------------------------------
  // Suite 6: 6-Section Evidence-Backed Answer Generation
  // -----------------------------------------------------------------
  console.log('\n-- Test Suite 6: 6-Section Structured Answer Generation --');
  assert(appJs.includes('async handleAskCase('), 'handleAskCase defined');
  assert(appJs.includes('6-SECTION STRUCTURED SYNTHESIS'), 'Structured 6-section synthesis badge rendered');
  assert(appJs.includes('structuredRes.answer_text'), 'Structured 6-section plain language answer bound');
  assert(appJs.includes('Admissibility Note:'), 'Statutory admissibility disclaimer attached to synthesized answers');

  // -----------------------------------------------------------------
  // Suite 7: CSS Styles for Intelligence Workspace
  // -----------------------------------------------------------------
  console.log('\n-- Test Suite 7: CSS Styles for Intelligence Workspace --');
  assert(styleCss.includes('.intel-search-container'), 'CSS defined for .intel-search-container');
  assert(styleCss.includes('.intel-results-grid'), 'CSS defined for .intel-results-grid');
  assert(styleCss.includes('.intel-result-card'), 'CSS defined for .intel-result-card');
  assert(styleCss.includes('.characteristics-table'), 'CSS defined for .characteristics-table');
  assert(styleCss.includes('.forensic-limitations-alert'), 'CSS defined for .forensic-limitations-alert');
  assert(styleCss.includes('.disambiguation-banner'), 'CSS defined for .disambiguation-banner');

  // -----------------------------------------------------------------
  // Suite 8: Live Backend HTTP API Integration (Synthetic Case SAKSHI-TEST-2026-002)
  // -----------------------------------------------------------------
  console.log('\n-- Test Suite 8: Live Backend HTTP API Integration --');
  const devHeaders = {
    'X-Investigator-Id': 'dev-investigator-001',
    'X-Investigator-Role': 'INVESTIGATING_OFFICER',
    'X-Investigator-Jurisdiction': 'KERALA',
    'Content-Type': 'application/json'
  };

  try {
    // 8.1 Unified Search on Preserved Synthetic Case
    const searchRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/intelligence/search?q=knife&filter_type=ALL',
      method: 'GET',
      headers: devHeaders
    });
    assert(searchRes.statusCode === 200, 'GET /intelligence/search?q=knife returns 200 OK');
    assert(searchRes.body && Array.isArray(searchRes.body.results), 'Search response contains results array');
    assert(searchRes.body.case_id === 'SAKSHI-CASE-2026-C5A64E99', 'Search response is strictly case-scoped');

    // 8.2 Exact Exhibit Number Lookup
    const exactSearchRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/intelligence/search?q=SAKSHI-EVID-2026-4378479F&filter_type=EVIDENCE',
      method: 'GET',
      headers: devHeaders
    });
    assert(exactSearchRes.statusCode === 200, 'GET /intelligence/search for exact exhibit returns 200');
    assert(exactSearchRes.body.results.length > 0, 'Exact exhibit match found');
    assert(exactSearchRes.body.results[0].match_type === 'EXACT_IDENTIFIER', 'Exact exhibit match tagged as EXACT_IDENTIFIER');
    assert(exactSearchRes.body.exact_match_found === true, 'exact_match_found flag is true for existing exhibit');

    // 8.3 Non-existent Exhibit Lookup (Explicit Not Found)
    const nonExistentSearchRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/intelligence/search?q=SAKSHI-EVID-NONEXISTENT-999&filter_type=EVIDENCE',
      method: 'GET',
      headers: devHeaders
    });
    assert(nonExistentSearchRes.statusCode === 200, 'GET /intelligence/search for nonexistent exhibit returns 200');
    assert(nonExistentSearchRes.body.exact_match_found === false, 'exact_match_found is false for missing identifier');
    assert(nonExistentSearchRes.body.results.length === 0, 'Does NOT silently return random exhibits');

    // 8.4 Entity & Exhibit Registry
    const registryRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/intelligence/registry',
      method: 'GET',
      headers: devHeaders
    });
    assert(registryRes.statusCode === 200, 'GET /intelligence/registry returns 200 OK');
    assert(registryRes.body.case_id === 'SAKSHI-CASE-2026-C5A64E99', 'Registry matches case ID');
    assert(Array.isArray(registryRes.body.entities), 'Registry includes entities array');
    assert(registryRes.body.entities.some(e => e.category === 'EXHIBIT'), 'Registry contains exhibit entities');
    assert(registryRes.body.entities.some(e => e.category === 'PERSON'), 'Registry contains person entities');
    assert(registryRes.body.entities.some(e => e.category === 'LOCATION' || e.category === 'OBJECT'), 'Registry contains location/object entities');

    // 8.5 Person Dossier
    const personDossierRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/intelligence/person/arjun-menon',
      method: 'GET',
      headers: devHeaders
    });
    assert(personDossierRes.statusCode === 200, 'GET /intelligence/person/arjun-menon returns 200 OK');
    assert(personDossierRes.body.canonical_name.toLowerCase().includes('arjun'), 'Person dossier returns matching canonical name');
    assert(typeof personDossierRes.body.identifying_info === 'object', 'Person dossier includes identifying info');
    assert(Array.isArray(personDossierRes.body.relationships), 'Person dossier includes relationships list');
    assert(Array.isArray(personDossierRes.body.interactions), 'Person dossier includes interactions list');
    assert(Array.isArray(personDossierRes.body.associated_evidence), 'Person dossier includes associated evidence list');
    assert(Array.isArray(personDossierRes.body.timeline), 'Person dossier includes chronological timeline');

    // 8.6 Object Dossier with Characteristics Register
    const objectDossierRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/intelligence/object/obj-knife-1',
      method: 'GET',
      headers: devHeaders
    });
    assert(objectDossierRes.statusCode === 200, 'GET /intelligence/object/obj-knife-1 returns 200 OK');
    assert(objectDossierRes.body.object_type.toUpperCase().includes('KNIFE') || objectDossierRes.body.object_type.toUpperCase().includes('PHYSICAL'), 'Object dossier provides classification');
    assert(Array.isArray(objectDossierRes.body.characteristics_register), 'Object dossier provides characteristics register');
    assert(objectDossierRes.body.missing_characteristics.length > 0, 'Object dossier explicitly marks missing characteristics');
    assert(objectDossierRes.body.forensic_limitations_notice.toLowerCase().includes('sharpness'), 'Forensic limitation notice included in payload');

    // 8.7 Side-by-Side Source Comparisons
    const contradictionsRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/intelligence/contradictions',
      method: 'GET',
      headers: devHeaders
    });
    assert(contradictionsRes.statusCode === 200, 'GET /intelligence/contradictions returns 200 OK');
    assert(Array.isArray(contradictionsRes.body.comparisons), 'Source comparisons array returned');

    // 8.8 Investigation Follow-Up Suggestions
    const followupsRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/intelligence/followups',
      method: 'GET',
      headers: devHeaders
    });
    assert(followupsRes.statusCode === 200, 'GET /intelligence/followups returns 200 OK');
    assert(Array.isArray(followupsRes.body.followups), 'Follow-up items array returned');

    // 8.9 6-Section Structured Answer Generation
    const askRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/intelligence/ask',
      method: 'POST',
      headers: devHeaders
    }, { question: 'What is known about Arjun Menon and the physical evidence?' });
    assert(askRes.statusCode === 200, 'POST /intelligence/ask returns 200 OK');
    assert(Array.isArray(askRes.body.documented_information), 'Section 1: Documented facts returned');
    assert(Array.isArray(askRes.body.supporting_source_references), 'Section 2: Citations returned');
    assert(Array.isArray(askRes.body.conflicting_information), 'Section 3: Conflicting info returned');
    assert(Array.isArray(askRes.body.missing_or_undocumented_information), 'Section 4: Missing info returned');
    assert(Array.isArray(askRes.body.possible_interpretations), 'Section 5: Candidate interpretations returned');
    assert(Array.isArray(askRes.body.suggested_followups), 'Section 6: Follow-up inquiries returned');
    assert(askRes.body.answer_text.includes('1. DIRECTLY DOCUMENTED INFORMATION:'), 'Answer text contains Section 1 header');
    assert(askRes.body.answer_text.includes('2. SUPPORTING SOURCE REFERENCES:'), 'Answer text contains Section 2 header');
    assert(askRes.body.answer_text.includes('3. CONFLICTING OR INCONSISTENT INFORMATION:'), 'Answer text contains Section 3 header');
    assert(askRes.body.answer_text.includes('4. MISSING OR UNDOCUMENTED INFORMATION:'), 'Answer text contains Section 4 header');
    assert(askRes.body.answer_text.includes('5. POSSIBLE INTERPRETATIONS (HYPOTHESES ONLY):'), 'Answer text contains Section 5 header');
    assert(askRes.body.answer_text.includes('6. SUGGESTED FOLLOW-UP QUESTIONS:'), 'Answer text contains Section 6 header');

    // 8.10 Case & Jurisdiction Isolation: Empty Case Isolation
    const newCaseRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases',
      method: 'POST',
      headers: devHeaders
    }, {
      title: 'Temporary Isolation Verification Case',
      fir_metadata: {
        fir_number: `FIR-ISO-${Date.now().toString().slice(-4)}`,
        police_station: 'Kochi Central',
        incident_date: new Date().toISOString(),
        report_date: new Date().toISOString(),
        incident_location: 'Isolated Test Scene',
        jurisdiction_code: 'KERALA'
      }
    });
    const emptyCaseId = newCaseRes.body?.case_id;
    const emptyCaseSearchRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: `/api/v1/cases/${emptyCaseId}/intelligence/search?q=knife&filter_type=ALL`,
      method: 'GET',
      headers: devHeaders
    });
    assert(emptyCaseSearchRes.statusCode === 200, 'Empty case returns 200 OK');
    assert(emptyCaseSearchRes.body.results.length === 0, 'Empty case returns 0 results (no cross-case leakage)');

    // 8.11 Authorization: Cross-Jurisdiction Access Rejection
    const unauthHeaders = {
      'X-Investigator-Id': 'IO-EXTERNAL-001',
      'X-Investigator-Role': 'INVESTIGATING_OFFICER',
      'X-Investigator-Jurisdiction': 'Foreign District PS',
      'Content-Type': 'application/json'
    };
    const unauthRes = await makeRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/intelligence/search?q=knife',
      method: 'GET',
      headers: unauthHeaders
    });
    assert(unauthRes.statusCode === 403, 'Cross-jurisdiction direct API call is rejected with 403 Forbidden');

  } catch (err) {
    console.error('HTTP Request failed during test:', err);
    assert(false, `Live backend HTTP requests succeeded without connection error: ${err.message}`);
  }

  // -----------------------------------------------------------------
  // Final Summary
  // -----------------------------------------------------------------
  console.log('\n=================================================================');
  console.log(`Phase F.1 Verification: ${passedTests} passed, ${failedTests} failed.`);
  console.log('=================================================================\n');

  if (failedTests > 0) {
    process.exit(1);
  }
}

runTests();
