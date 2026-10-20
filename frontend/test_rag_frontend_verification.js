const fs = require('fs');

console.log("Starting SAKSHI Frontend Evidence RAG Verification Tests...\n");

const html = fs.readFileSync('C:/main project/frontend/index.html', 'utf8');
const js = fs.readFileSync('C:/main project/frontend/app.js', 'utf8');

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

// 1. Sidebar and Tab Navigation
assert(html.includes('id="navRAG"'), "navRAG navigation anchor defined in index.html");
assert(html.includes('href="#/cases/active/rag"'), "navRAG points to #/cases/active/rag in index.html");
assert(js.includes("window.location.hash='#/cases/${c.case_id}/rag'"), "RAG tab button included in case workspace header in app.js");
assert(js.includes('navRAG'), "Sidebar active state handler updates navRAG in app.js");

// 2. Component and Route Registration
assert(js.includes('ScreenRAGSearch'), "ScreenRAGSearch component defined in app.js");
assert(js.includes('pattern: /^#\\/cases\\/([A-Za-z0-9_-]+)\\/rag$/'), "Route #/cases/:id/rag registered in Router.routes");

// 3. API Client Integration
assert(js.includes('searchRAG(caseId, query, limit = 5)'), "Api.searchRAG method defined with parameters");
assert(js.includes('rag/search'), "Api.searchRAG targets rag/search endpoint");
assert(js.includes('JSON.stringify({ query, limit })'), "Api.searchRAG sends JSON payload with query and limit");

// 4. Input Validation and State Handling
assert(js.includes('ragQueryInput'), "ragQueryInput query field present");
assert(js.includes('Please enter non-whitespace search terms'), "Empty/whitespace query validation enforced");
assert(js.includes('ScreenRAGSearch.isLoading'), "Loading state tracked");
assert(js.includes('ScreenRAGSearch.error'), "Error state handled");
assert(js.includes('Computing Neural Embeddings & Vector Proximity'), "Loading message displayed");
assert(js.includes('Retrieval Error'), "Error banner displayed on failure");
assert(js.includes('empty_result_notice'), "Empty result notice from backend displayed");

// 5. Provenance, Citation and Security Compliance
assert(js.includes('item.passage'), "Authentic passage content rendered");
assert(js.includes('item.similarity_score'), "Cosine similarity score rendered");
assert(js.includes('item.source_name'), "Source exhibit file name rendered");
assert(js.includes('item.evidence_id'), "Evidence ID rendered");
assert(js.includes('item.document_id'), "Document ID rendered");
assert(js.includes('item.chunk_id'), "Chunk ID rendered");
assert(js.includes('item.source_sha256'), "Source SHA-256 fingerprint rendered");
assert(js.includes('item.page_number'), "Page number citation rendered when present");
assert(js.includes('item.char_start') && js.includes('item.char_end'), "Character start and end offsets rendered when present");
assert(js.includes('retrieval_mode'), "Backend retrieval mode displayed without masking");

// 6. Security & Negative Constraints
assert(!js.includes('generateLLMAnswer'), "No LLM generation invented in frontend RAG search");
assert(!js.includes('runRPAScript'), "No RPA execution triggered in frontend RAG search");

console.log(`\nVerification complete: ${passes} passed, ${failures} failed.`);
process.exit(failures > 0 ? 1 : 0);
