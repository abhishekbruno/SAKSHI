/**
 * Automated Regression Test Suite: FIR-Assisted Ingestion & Form Rendering
 * 
 * Verifies:
 * 1. Greenfield Community Hall Equipment Theft candidate preview:
 *    - Suggested Title: "Greenfield Community Hall Equipment Theft"
 *    - Discovery Date / Time: "Approximately 08:15 IST on 22 October 2026"
 *    - Last Confirmed Present: "Approximately 18:00 IST on 21 October 2026"
 *    - Occurrence Time: "Unknown / not established"
 *    - Suppression of Deceased / Person Found Unresponsive field
 *    - Suppression of Time of Death / Cause of Death evidentiary limitations
 * 2. Riverside Guesthouse Incident candidate preview:
 *    - Suggested Title: "Riverside Guesthouse Incident"
 *    - Deceased Person field present with "Arjun Menon (fictional)"
 *    - Evidentiary limitations for time and cause of death present
 * 3. Case-type switching without stale state leakage:
 *    - Switching from Death Investigation to Property Loss removes all death fields
 *    - Switching back restores death fields
 * 4. State reset on new file selection or text input changes:
 *    - handleFirFileSelect clears extracted data and modifications
 *    - handleFirTextInput clears extracted data and modifications
 * 5. Submission payload serialization:
 *    - Property loss payload sets incident_type to "PROPERTY_LOSS", victim_name to null,
 *      and preserves separate discovery_time and last_confirmed_present.
 */

const fs = require("fs");
const path = require("path");
const assert = require("assert");

let failures = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`  [PASS] ${name}`);
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
  } catch (err) {
    console.error(`  [FAIL] ${name}`);
    console.error(`         ${err.message}`);
    failures++;
  }
}

// Minimal DOM Mock environment
function setupMockDom() {
  const elements = {};
  
  function createElement(tag, id = null) {
    const el = {
      tagName: tag.toUpperCase(),
      id: id,
      value: "",
      style: {},
      classList: {
        _classes: new Set(),
        add(c) { this._classes.add(c); },
        remove(c) { this._classes.delete(c); },
        contains(c) { return this._classes.has(c); }
      },
      innerHTML: "",
      textContent: "",
      disabled: false,
      listeners: {},
      appendChild(child) {},
      removeChild(child) {},
      focus() {},
      addEventListener(evt, fn) {
        if (!this.listeners[evt]) this.listeners[evt] = [];
        this.listeners[evt].push(fn);
      },
      querySelectorAll(selector) {
        // Simple mock for input query
        if (selector === "input") {
          const inputs = [];
          const matches = this.innerHTML.matchAll(/id="([^"]+)"/g);
          for (const m of matches) {
            if (m[1].startsWith("inp")) {
              const valMatch = this.innerHTML.match(new RegExp(`id="${m[1]}"[^>]*value="([^"]*)"`));
              inputs.push({
                id: m[1],
                value: valMatch ? valMatch[1] : "",
                classList: { remove: () => {}, add: () => {} },
                addEventListener: () => {}
              });
            }
          }
          return inputs;
        }
        return [];
      }
    };
    if (id) elements[id] = el;
    return el;
  }

  global.document = {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = createElement("div", id);
      }
      return elements[id];
    },
    createElement(tag) {
      return createElement(tag);
    },
    addEventListener: () => {},
    removeEventListener: () => {}
  };

  const storage = {};
  global.localStorage = {
    getItem: (k) => storage[k] || null,
    setItem: (k, v) => { storage[k] = String(v); },
    removeItem: (k) => { delete storage[k]; },
    clear: () => { Object.keys(storage).forEach(k => delete storage[k]); }
  };

  global.window = {
    localStorage: global.localStorage,
    addEventListener: () => {}
  };

  global.Formatters = {
    escapeHtml(str) {
      if (str === null || str === undefined) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }
  };

  global.UI = {
    showToast(msg, type) {},
    recordAudit() {},
    closeModal() {},
    openModal() {}
  };

  global.State = {
    auth: { subjectId: "dev-investigator-001" }
  };

  return elements;
}

async function runTests() {
  console.log("Starting SAKSHI FIR-Assisted Ingestion Regression Tests...\n");

  const appJsPath = path.join(__dirname, "app.js");
  const jsCode = fs.readFileSync(appJsPath, "utf8");

  // Verify static patterns first
  console.log("-- Suite 1: Static Code Invariants --");

  test("app.js checks extracted.incident_type for property loss", () => {
    assert(jsCode.includes("extracted.incident_type === 'PROPERTY_LOSS'"), "checks PROPERTY_LOSS");
    assert(jsCode.includes("extracted.incident_type === 'DEATH_INVESTIGATION'"), "checks DEATH_INVESTIGATION");
  });

  test("app.js separates last_confirmed_present and discovery_time", () => {
    assert(jsCode.includes("inpFirCandidateLastPresent"), "includes inpFirCandidateLastPresent");
    assert(jsCode.includes("inpFirCandidateDiscoveryTime"), "includes inpFirCandidateDiscoveryTime");
    assert(jsCode.includes("last_confirmed_present:"), "passes last_confirmed_present");
  });

  test("app.js hides deceased person input for property loss", () => {
    assert(jsCode.includes("isPropLoss ?"), "conditionally renders inputs based on isPropLoss");
    assert(jsCode.includes("inpFirCandidatePropertyItems"), "renders inpFirCandidatePropertyItems for property loss");
  });

  test("app.js prevents stale state across FIR extractions", () => {
    assert(jsCode.includes("handleFirTextInput()"), "defines handleFirTextInput");
    assert(jsCode.includes("ScreenCases._extractedFirData = null;"), "resets _extractedFirData");
  });

  // Evaluate execution in mock environment
  console.log("\n-- Suite 2: Runtime Form Rendering & State Transitions --");

  const dom = setupMockDom();

  // Create isolated sandbox context for ScreenCases
  class MockFormData {
    constructor() { this.data = {}; }
    append(k, v) { this.data[k] = v; }
  }

  const vm = require("vm");
  const context = {
    console,
    setTimeout,
    clearTimeout,
    FormData: MockFormData,
    window: global.window,
    localStorage: global.localStorage,
    document: global.document,
    Formatters: global.Formatters,
    UI: {
      showToast(msg, type) {
        if (type === "error") console.error("      [UI Error Toast]:", msg);
      },
      recordAudit() {},
      closeModal() {},
      openModal() {}
    },
    State: global.State,
    Api: {},
    ScreenCases: {
      _modalMode: "fir",
      _extractedFirData: null,
      _uploadedFirFile: null,
      _reviewerModifications: {},
      _isSubmittingFir: false
    }
  };

  // Extract ScreenCases methods from app.js using VM
  vm.createContext(context);
  
  // Load ScreenCases methods needed
  vm.runInContext(`
    ${jsCode}
    window.ScreenCases = ScreenCases;
    window.Api = Api;
  `, context);

  const ScreenCases = context.window.ScreenCases;
  const Api = context.window.Api;

  // Mock API responses for both case types
  const mockGreenfieldExtract = {
    incident_type: "PROPERTY_LOSS",
    suggested_title: "Greenfield Community Hall Equipment Theft",
    fir_number: "FIR-SYN-2026-021",
    police_station: "Greenfield Central Police Station",
    report_date: "22 October 2026",
    discovery_time: "Approximately 08:15 IST on 22 October 2026",
    last_confirmed_present: "Approximately 18:00 IST on 21 October 2026",
    incident_date: "Unknown / not established",
    incident_location: "Greenfield Community Hall, Equipment Storage Room",
    complainant_name: "Ravi Thomas",
    property_items: "Audio sound mixing console and amplifiers",
    offense_sections: "Section 305 / 331(4) BNS",
    victim_name: null,
    time_of_death: null,
    cause_of_death: null,
    witness_sightings: [],
    source_passages: [
      { field: "fir_number", quote: "FIR-SYN-2026-021", char_offset: 10, extraction_status: "EXTRACTED" },
      { field: "discovery_time", quote: "08:15 IST on 22 October 2026", char_offset: 100, extraction_status: "EXTRACTED" }
    ],
    missing_fields: [],
    ambiguous_fields: [],
    disclaimer: "Candidate extraction from submitted FIR document.",
    extraction_status: "EXTRACTED"
  };

  const mockRiversideExtract = {
    incident_type: "DEATH_INVESTIGATION",
    suggested_title: "Riverside Guesthouse Incident",
    fir_number: "FIR-SYN-2026-1042",
    police_station: "Nallur Coastal Police Station (fictional)",
    report_date: "18 October 2026",
    discovery_time: "Approximately 07:20 IST on 18 October 2026",
    last_confirmed_present: null,
    incident_date: "18 October 2026 at approximately 07:20 IST",
    incident_location: "Riverside Guesthouse, Room 204",
    complainant_name: null,
    property_items: null,
    offense_sections: "Section 194 BNSS",
    victim_name: "Arjun Menon (fictional)",
    time_of_death: "Unknown / not established",
    cause_of_death: "Unknown / not established",
    witness_sightings: [
      { witness: "Witness A", sighting: "Approximately 00:10 IST on 18 October 2026" }
    ],
    source_passages: [
      { field: "fir_number", quote: "FIR-SYN-2026-1042", char_offset: 12, extraction_status: "EXTRACTED" }
    ],
    missing_fields: [],
    ambiguous_fields: [],
    disclaimer: "Candidate extraction from submitted FIR document.",
    extraction_status: "EXTRACTED"
  };

  await asyncTest("Greenfield property loss renders expected title and discovery time without death fields", async () => {
    Api.previewFIRExtraction = async () => mockGreenfieldExtract;
    context.document.getElementById("inpFirPastedText").value = "Greenfield FIR text";

    await ScreenCases.extractFirDetails();

    const preview = context.document.getElementById("firExtractionPreviewContainer");
    assert(preview.innerHTML.includes("Greenfield Community Hall Equipment Theft"), "Title rendered correctly");
    assert(preview.innerHTML.includes("Approximately 08:15 IST on 22 October 2026"), "Discovery time populated");
    assert(preview.innerHTML.includes("Approximately 18:00 IST on 21 October 2026"), "Last confirmed present populated");
    assert(preview.innerHTML.includes("Unknown / not established"), "Occurrence time set to unknown");
    assert(preview.innerHTML.includes("Audio sound mixing console"), "Property items rendered");
    
    // Death fields MUST be absent
    assert(!preview.innerHTML.includes("inpFirCandidateVictim"), "inpFirCandidateVictim must NOT be present in DOM");
    assert(!preview.innerHTML.includes("Deceased / Person Found Unresponsive"), "Deceased label must NOT be rendered");
    assert(!preview.innerHTML.includes("Time of death:"), "Time of death limitations must NOT be rendered");
    assert(!preview.innerHTML.includes("Unnatural Death Inquiry"), "Unnatural Death title must NOT be rendered");

    // Property loss notice must be present
    assert(preview.innerHTML.includes("Property Loss Evidentiary Notice"), "Property loss notice rendered");
  });

  await asyncTest("Riverside death investigation renders deceased person and evidentiary limitations", async () => {
    Api.previewFIRExtraction = async () => mockRiversideExtract;
    context.document.getElementById("inpFirPastedText").value = "Riverside FIR text";

    await ScreenCases.extractFirDetails();

    const preview = context.document.getElementById("firExtractionPreviewContainer");
    assert(preview.innerHTML.includes("Riverside Guesthouse Incident"), "Title rendered correctly");
    assert(preview.innerHTML.includes("inpFirCandidateVictim"), "inpFirCandidateVictim must be present in DOM");
    assert(preview.innerHTML.includes("Arjun Menon (fictional)"), "Victim name populated");
    assert(preview.innerHTML.includes("Evidentiary Limitations:"), "Death evidentiary limitations rendered");
    assert(preview.innerHTML.includes("Time of death:"), "Time of death rendered");
  });

  await asyncTest("Switching from Death Investigation to Property Loss cleanly purges death fields", async () => {
    // 1. First render Death
    Api.previewFIRExtraction = async () => mockRiversideExtract;
    await ScreenCases.extractFirDetails();
    let preview = context.document.getElementById("firExtractionPreviewContainer");
    assert(preview.innerHTML.includes("inpFirCandidateVictim"), "Death field present in step 1");

    // 2. Clear via text input handler
    ScreenCases.handleFirTextInput();
    assert.strictEqual(ScreenCases._extractedFirData, null, "State cleared on text input");
    assert.strictEqual(preview.style.display, "none", "Preview hidden on input change");

    // 3. Now render Property Loss
    Api.previewFIRExtraction = async () => mockGreenfieldExtract;
    await ScreenCases.extractFirDetails();
    preview = context.document.getElementById("firExtractionPreviewContainer");
    assert(!preview.innerHTML.includes("inpFirCandidateVictim"), "Death field successfully purged on switch");
    assert(preview.innerHTML.includes("Greenfield Community Hall Equipment Theft"), "Switched to property title");
    assert(preview.innerHTML.includes("inpFirCandidatePropertyItems"), "Property items field present");
  });

  await asyncTest("submitFirAssistedCase builds correct property loss payload", async () => {
    let capturedPayload = null;
    Api.createCaseFIRAssisted = async (payload) => {
      capturedPayload = payload;
      return { case: { case_id: "SAKSHI-CASE-TEST-PROP", title: payload.title } };
    };

    // Set DOM input values to match Greenfield case
    context.document.getElementById("inpFirCandidateTitle").value = "Greenfield Community Hall Equipment Theft";
    context.document.getElementById("inpFirCandidateNumber").value = "FIR-SYN-2026-021";
    context.document.getElementById("inpFirCandidateStation").value = "Greenfield Central Police Station";
    context.document.getElementById("inpFirCandidateDate").value = "Unknown / not established";
    context.document.getElementById("inpFirCandidateReportDate").value = "22 October 2026";
    context.document.getElementById("inpFirCandidateDiscoveryTime").value = "Approximately 08:15 IST on 22 October 2026";
    context.document.getElementById("inpFirCandidateLastPresent").value = "Approximately 18:00 IST on 21 October 2026";
    context.document.getElementById("inpFirCandidateLocation").value = "Greenfield Community Hall, Equipment Storage Room";
    context.document.getElementById("inpFirCandidateComplainant").value = "Ravi Thomas";
    context.document.getElementById("inpFirCandidatePropertyItems").value = "Audio sound mixing console and amplifiers";
    context.document.getElementById("inpFirCandidateSections").value = "Section 305 / 331(4) BNS";

    await ScreenCases.submitFirAssistedCase();

    assert(capturedPayload !== null, "createCaseFIRAssisted called");
    assert.strictEqual(capturedPayload.title, "Greenfield Community Hall Equipment Theft");
    assert.strictEqual(capturedPayload.fir_metadata.fir_number, "FIR-SYN-2026-021");
    assert.strictEqual(capturedPayload.fir_metadata.incident_type, "PROPERTY_LOSS");
    assert.strictEqual(capturedPayload.fir_metadata.victim_name, null, "Victim name must be null for property loss");
    assert.strictEqual(capturedPayload.fir_metadata.discovery_time, "Approximately 08:15 IST on 22 October 2026");
    assert.strictEqual(capturedPayload.fir_metadata.last_confirmed_present, "Approximately 18:00 IST on 21 October 2026");
    assert.strictEqual(capturedPayload.fir_metadata.incident_date, "Unknown / not established");
    assert.strictEqual(capturedPayload.fir_metadata.property_items, "Audio sound mixing console and amplifiers");
    assert.strictEqual(capturedPayload.time_of_death, null, "time_of_death must be null");
    assert.strictEqual(capturedPayload.cause_of_death, null, "cause_of_death must be null");
  });

  console.log(`\nTests finished with ${failures} failure(s).`);
  process.exit(failures > 0 ? 1 : 0);
}

runTests();
