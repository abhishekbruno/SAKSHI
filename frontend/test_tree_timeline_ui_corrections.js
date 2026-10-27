/**
 * Static regression checks for the targeted relationship-tree and timeline UI.
 * These checks intentionally do not create, modify, or delete case records.
 */
const assert = require("assert");
const fs = require("fs");

const app = fs.readFileSync("frontend/app.js", "utf8");
const css = fs.readFileSync("frontend/style.css", "utf8");
let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`  [PASS] ${name}`);
  } catch (error) {
    failed += 1;
    console.error(`  [FAIL] ${name}: ${error.message}`);
  }
}

const graphStart = app.indexOf("const ScreenGraph = {");
const timelineStart = app.indexOf("const ScreenTimeline = {");
const analysisStart = app.indexOf("const ScreenAnalysis = {");
const graphSource = app.slice(graphStart, timelineStart);
const timelineSource = app.slice(timelineStart, analysisStart);
const casesSource = app.slice(app.indexOf("const ScreenCases = {"), app.indexOf("const ScreenCaseOverview = {"));

console.log("Targeted relationship tree and timeline regression checks\n");

test("relationship view uses a deterministic hierarchical layout", () => {
  assert(graphSource.includes("buildTreeLayout(nodes, edges)"));
  assert(graphSource.includes("countLeaves"));
  assert(graphSource.includes("graph-tree-edge"));
  assert(!graphSource.includes("Math.cos(angle)"));
});

test("tree links use only returned relationship records", () => {
  assert(graphSource.includes("const filteredEdges = allEdges.filter"));
  assert(graphSource.includes("tree.treeEdges.map(renderTreeEdge)"));
  assert(graphSource.includes("supplementalEdges: edges.filter"));
  assert(graphSource.includes("source_passage"));
});

test("tree keeps labels readable and supports branch controls", () => {
  assert(graphSource.includes("wrapNodeLabel"));
  assert(graphSource.includes("conciseName"));
  assert(graphSource.includes("toggleBranch(caseId, nodeId)"));
  assert(graphSource.includes("preferredRootX"));
  assert(graphSource.includes(">Reset view<"));
  assert(css.includes(".graph-canvas-area") && css.includes("overflow: auto"));
});

test("timeline groups non-main events only when the backend assigns a branch", () => {
  assert(timelineSource.includes('event.branchId !== "MAIN"'));
  assert(timelineSource.includes("buildBranchingTimeline(events)"));
  assert(timelineSource.includes("chronologicalValue(event)"));
  assert(timelineSource.includes("timeline-branch"));
});

test("timeline makes chronology-versus-causation explicit", () => {
  assert(timelineSource.includes("the layout does not claim that one event caused another"));
  assert(timelineSource.includes("separate source path identified by the case data"));
  assert(!timelineSource.includes("8-minute variance"));
  assert(!timelineSource.includes("Surveillance Video / Call Record Corroboration"));
});

test("timeline default rows retain a route to their source without repeated IDs", () => {
  assert(timelineSource.includes("timeline-source-link"));
  assert(timelineSource.includes("Open source"));
  assert(timelineSource.includes("eventsById"));
  assert(timelineSource.includes("showEventDetails(eventId)"));
  assert(timelineSource.includes("plainTitle"));
  assert(timelineSource.includes('title: this.plainTitle(ev.title)'));
});

test("case directory is a compact list without progress bars or filter chips", () => {
  assert(casesSource.includes("case-directory-list"));
  assert(casesSource.includes("case-row"));
  assert(casesSource.includes("caseStageFilter"));
  assert(!casesSource.includes("progressPct"));
  assert(!casesSource.includes("filter-chip"));
});

console.log(`\n${passed} passed, ${failed} failed.`);
process.exitCode = failed ? 1 : 0;
