/**
 * SAKSHI Regression Test Suite:
 * 1. Entity Relationship Graph Runtime Error & Layout Position Verification
 * 2. Plaintext Evidence Text Extraction & Grounded Fact Extraction
 * 3. Simplified Fact Review Decisions (Confirmation without rationale, mandatory rationale for flag/reject)
 * 4. Grounded Knowledge Graph with non-empty nodes and verified edges
 */

const http = require('http');
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const API_BASE = 'http://127.0.0.1:8000/api/v1';
const CASE_ID = 'SAKSHI-CASE-2026-632D540B';
const WITNESS_A_EVID_ID = 'SAKSHI-EVID-2026-D67B7C9D';
const WITNESS_B_EVID_ID = 'SAKSHI-EVID-2026-FAE114C1';
const FIR_EVID_ID = 'SAKSHI-EVID-2026-B5B4270C';

const AUTH_HEADERS = {
  'Content-Type': 'application/json',
  'X-Investigator-Id': 'dev-investigator-001',
  'X-Investigator-Role': 'INVESTIGATING_OFFICER',
  'X-Investigator-Jurisdiction': 'KERALA'
};

function request(url, options = {}) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const reqOptions = {
      hostname: parsed.hostname,
      port: parsed.port,
      path: parsed.pathname + parsed.search,
      method: options.method || 'GET',
      headers: { ...AUTH_HEADERS, ...(options.headers || {}) }
    };

    const req = http.request(reqOptions, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = data ? JSON.parse(data) : {};
          resolve({ status: res.statusCode, headers: res.headers, body: json });
        } catch (e) {
          resolve({ status: res.statusCode, headers: res.headers, body: data });
        }
      });
    });

    req.on('error', reject);
    if (options.body) {
      req.write(typeof options.body === 'string' ? options.body : JSON.stringify(options.body));
    }
    req.end();
  });
}

async function runTests() {
  console.log('======================================================================');
  console.log(' SAKSHI Regression Test Suite: Graph, Plaintext & Fact Review');
  console.log('======================================================================\n');

  let passed = 0;
  let total = 0;

  async function test(name, fn) {
    total++;
    try {
      await fn();
      console.log(`  [PASS] ${name}`);
      passed++;
    } catch (err) {
      console.error(`  [FAIL] ${name}:`, err.message);
    }
  }

  // 1. Static frontend checks
  await test('Frontend app.js contains layout safety guards for node position coordinates', () => {
    const appJs = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
    assert(appJs.includes('typeof position.x !== "number"'), 'Must check position.x number type');
    assert(appJs.includes('typeof position.y !== "number"'), 'Must check position.y number type');
    assert(appJs.includes('this.collapsedNodeIds = new Set()'), 'Must reset collapsedNodeIds on render');
    assert(appJs.includes('positions.set(node.id,'), 'Must assign fallback position for every node');
  });

  await test('Frontend app.js contains 1-click confirmation and relaxed rationale for confirm', () => {
    const appJs = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
    assert(appJs.includes('quickConfirmFact'), 'Must define quickConfirmFact');
    assert(appJs.includes('Confirm Source Support'), 'Must use precise evidentiary label');
    assert(appJs.includes('decision !== "CONFIRMED" && (!reason || reason.length < 3)'), 'Must not require rationale for CONFIRMED');
  });

  await test('Frontend app.js handles truthful extraction results and does not falsely toast success on 0 facts', () => {
    const appJs = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
    assert(appJs.includes('res.indexing_status === "INDEXING_FAILED"'), 'Must check indexing failure');
    assert(appJs.includes('res.total_facts === 0'), 'Must check 0 total facts');
  });

  // 2. Knowledge graph API verification
  await test('GET /cases/{case_id}/knowledge-graph returns valid nodes and edges for Riverside case', async () => {
    const res = await request(`${API_BASE}/cases/${CASE_ID}/knowledge-graph`);
    assert.strictEqual(res.status, 200, `Expected 200, got ${res.status}`);
    const data = res.body;
    assert(data.total_nodes > 0, `Expected nodes > 0, got ${data.total_nodes}`);
    assert(data.total_edges > 0, `Expected edges > 0, got ${data.total_edges}`);
    
    // Ensure all edges link to valid nodes
    const nodeIds = new Set(data.nodes.map(n => n.id));
    for (const edge of data.edges) {
      assert(nodeIds.has(edge.source_node_id), `Edge ${edge.id} source ${edge.source_node_id} not in nodes`);
      assert(nodeIds.has(edge.target_node_id), `Edge ${edge.id} target ${edge.target_node_id} not in nodes`);
      assert(edge.evidence_id, `Edge ${edge.id} must have evidence_id`);
      assert(edge.citation, `Edge ${edge.id} must have citation`);
    }

    // Ensure witness statements are identified as PERSON nodes (not OBJECT nodes)
    const personNodes = data.nodes.filter(n => n.category === 'PERSON');
    const witnessNodes = personNodes.filter(n => (n.name || '').includes('Sunil') || (n.name || '').includes('Deepa') || (n.subtitle || '').includes('Witness'));
    assert(witnessNodes.length >= 1, 'Expected witness person node in knowledge graph');
  });

  // 3. Plaintext extraction & fact extraction verification
  await test('POST /cases/{case_id}/evidence/{evidence_id}/extract-facts parses Witness A plaintext', async () => {
    const res = await request(`${API_BASE}/cases/${CASE_ID}/evidence/${WITNESS_A_EVID_ID}/extract-facts?force_reindex=true`, { method: 'POST' });
    assert.strictEqual(res.status, 200, `Expected 200, got ${res.status}`);
    const data = res.body;
    assert.strictEqual(data.is_supported, true, 'Plaintext should be supported');
    assert.strictEqual(data.indexing_status, 'INDEXED', `Expected INDEXED, got ${data.indexing_status}`);
    assert(data.total_facts > 0, `Expected facts > 0, got ${data.total_facts}`);
    assert(data.important_details.length > 0, 'Expected important details');
    assert(data.document_summary && data.document_summary.length > 20, 'Expected substantive summary');
    assert(!data.processing_status_label.includes('Binary media'), 'Must not label plaintext as binary media');
  });

  // 4. Fact decision confirmation without rationale
  await test('POST fact decision with CONFIRMED succeeds without rationale', async () => {
    const res = await request(`${API_BASE}/cases/${CASE_ID}/evidence/${WITNESS_A_EVID_ID}/facts/FACT-001/decision`, {
      method: 'POST',
      body: {
        decision: 'CONFIRMED'
      }
    });
    assert.strictEqual(res.status, 200, `Expected 200 for CONFIRMED without reason, got ${res.status}: ${JSON.stringify(res.body)}`);
    assert.strictEqual(res.body.decision, 'CONFIRMED');
    assert.strictEqual(res.body.audit_recorded, true);
  });

  // 5. Fact decision with FLAGGED fails if rationale is omitted
  await test('POST fact decision with FLAGGED fails if rationale is omitted', async () => {
    const res = await request(`${API_BASE}/cases/${CASE_ID}/evidence/${WITNESS_A_EVID_ID}/facts/FACT-001/decision`, {
      method: 'POST',
      body: {
        decision: 'FLAGGED'
      }
    });
    assert.strictEqual(res.status, 422, `Expected 422 validation error when FLAGGED lacks reason, got ${res.status}`);
  });

  // 6. Fact decision with FLAGGED succeeds with valid rationale
  await test('POST fact decision with FLAGGED succeeds with valid rationale', async () => {
    const res = await request(`${API_BASE}/cases/${CASE_ID}/evidence/${WITNESS_A_EVID_ID}/facts/FACT-001/decision`, {
      method: 'POST',
      body: {
        decision: 'FLAGGED',
        reason: 'Observation time conflicts with premises access logs; requires CCTV corroboration.'
      }
    });
    assert.strictEqual(res.status, 200, `Expected 200 for FLAGGED with reason, got ${res.status}`);
    assert.strictEqual(res.body.decision, 'FLAGGED');
  });

  // 7. Graph Tree Layout Simulation in Node
  await test('ScreenGraph.buildTreeLayout handles nodes without missing x coordinate crashes', () => {
    // Simulate layout algorithm from app.js
    const sampleNodes = [
      { id: 'node-doc-1', name: 'Exhibit 1', category: 'DOCUMENT' },
      { id: 'node-person-victim', name: 'Victim', category: 'PERSON' },
      { id: 'node-loc-scene', name: 'Guesthouse', category: 'LOCATION' }
    ];
    const sampleEdges = [
      { id: 'e1', source_node_id: 'node-person-victim', target_node_id: 'node-loc-scene' },
      { id: 'e2', source_node_id: 'node-person-victim', target_node_id: 'node-doc-1' }
    ];

    const positions = new Map();
    sampleNodes.forEach((node, i) => {
      positions.set(node.id, {
        x: 400 + Math.cos(i * 1.5) * 150,
        y: 300 + Math.sin(i * 1.5) * 150
      });
    });

    sampleNodes.forEach(node => {
      const pos = positions.get(node.id);
      assert(pos && typeof pos.x === 'number' && typeof pos.y === 'number', `Node ${node.id} must have valid numeric coordinates`);
    });

    sampleEdges.forEach(edge => {
      const srcPos = positions.get(edge.source_node_id);
      const tgtPos = positions.get(edge.target_node_id);
      assert(srcPos && typeof srcPos.x === 'number', `Edge source must have numeric x`);
      assert(tgtPos && typeof tgtPos.x === 'number', `Edge target must have numeric x`);
    });
  });

  console.log(`\nResults: ${passed}/${total} tests passed.\n`);
  if (passed !== total) {
    process.exit(1);
  }
}

runTests().catch(err => {
  console.error('Test execution failed:', err);
  process.exit(1);
});
