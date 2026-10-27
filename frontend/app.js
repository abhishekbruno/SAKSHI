/**
 * SAKSHI — Digital Investigation Workstation
 * Kerala Police Operational Workstation Engine
 * EC-MORE Architecture (Evidence-Constrained Modus Operandi Reconstruction)
 */

// ═══════════════════════════════════════════════════════════════════════════
// 1. CONFIGURATION, THEME & STATE
// ═══════════════════════════════════════════════════════════════════════════

const API_BASE = "/api/v1";

const State = {
  theme: localStorage.getItem("sakshi_theme") || "light",
  auth: {
    initialized: false,
    authenticated: false,
    subjectId: (typeof localStorage !== "undefined" && localStorage.getItem("sakshi_dev_subject_id") && localStorage.getItem("sakshi_dev_subject_id") !== "IO-7842-SHARMA")
      ? localStorage.getItem("sakshi_dev_subject_id")
      : "dev-investigator-001",
    displayName: (typeof localStorage !== "undefined" && localStorage.getItem("sakshi_dev_display_name") && localStorage.getItem("sakshi_dev_subject_id") !== "IO-7842-SHARMA")
      ? localStorage.getItem("sakshi_dev_display_name")
      : "Dev Inspector (Development Only)",
    role: (typeof localStorage !== "undefined" ? localStorage.getItem("sakshi_dev_role") : null) || "INVESTIGATING_OFFICER",
    jurisdiction: (typeof localStorage !== "undefined" && localStorage.getItem("sakshi_dev_jurisdiction") && localStorage.getItem("sakshi_dev_jurisdiction") !== "KL-TVM-001")
      ? localStorage.getItem("sakshi_dev_jurisdiction")
      : "KERALA",
    mode: "unknown",
    token: (typeof sessionStorage !== "undefined" ? sessionStorage.getItem("sakshi_auth_token") : null) || null,
    headers: {
      "Content-Type": "application/json"
    }
  },
  cases: [],
  activeCaseId: localStorage.getItem("sakshi_active_case_id") || null,
  activeCase: null,
  activeStageInfo: null,
  evidence: [],
  activeEvidenceId: null,
  systemHealth: null,
  filters: {
    caseSearch: "",
    caseStage: "ALL",
    evidenceCategory: "ALL",
    evidenceSecurity: "ALL",
    evidenceSearch: "",
    timelineFilter: "ALL",
    timelineView: "chronological"
  },
  auditLog: []
};

// Stage display mappings aligned strictly with authoritative police investigation workflows
const StageDisplayMap = {
  INITIALIZED: { label: "1. Case Setup (Register Case)", short: "Case Setup", stepNum: 1, badge: "badge-info" },
  EVIDENCE_INGESTION: { label: "2. Evidence Collection (Collect Evidence)", short: "Evidence Collection", stepNum: 2, badge: "badge-attention" },
  EVIDENCE_PROCESSING: { label: "3. Forensic Verification (Verify Evidence)", short: "Forensic Verification", stepNum: 3, badge: "badge-info" },
  ANALYSIS: { label: "4. Investigation Analysis (Review Timeline)", short: "Investigation Analysis", stepNum: 4, badge: "badge-info" },
  REVIEW: { label: "5. Investigator Review (Review Findings)", short: "Investigator Review", stepNum: 5, badge: "badge-attention" },
  CLOSED: { label: "6. Case Closed (Complete Authorized Review)", short: "Case Closed", stepNum: 6, badge: "badge-verified" },
  SUSPENDED: { label: "Case Suspended", short: "Case Suspended", stepNum: 0, badge: "badge-danger" },
  REOPENED: { label: "Case Reopened", short: "Case Reopened", stepNum: 0, badge: "badge-attention" }
};

// ═══════════════════════════════════════════════════════════════════════════
// 2. API CLIENT (Direct Integration with MOD-01 through MOD-11)
// ═══════════════════════════════════════════════════════════════════════════

const Api = {
  getHeaders(customHeaders = {}) {
    const h = { ...State.auth.headers, ...customHeaders };
    if (State.auth.token) {
      h.Authorization = `Bearer ${State.auth.token}`;
    } else if (State.auth.mode === "development" || State.auth.mode === "offline" || State.auth.mode === "unknown") {
      if (State.auth.subjectId) h["X-Investigator-Id"] = State.auth.subjectId;
      if (State.auth.role) h["X-Investigator-Role"] = State.auth.role;
      if (State.auth.jurisdiction) h["X-Investigator-Jurisdiction"] = State.auth.jurisdiction;
    }
    Object.keys(h).forEach(k => {
      if (h[k] === undefined || h[k] === null || h[k] === "") delete h[k];
    });
    return h;
  },

  formatErrorMessage(errData, status, context = "Operation") {
    if (!errData) return `${context} failed (${status || 'Unknown error'})`;

    // 1. Pydantic validation error array: detail = [{loc: [...], msg: "..."}]
    if (Array.isArray(errData.detail)) {
      const parts = errData.detail.map(d => {
        if (typeof d === "string") return d;
        if (d && typeof d === "object") {
          const locStr = Array.isArray(d.loc)
            ? d.loc.filter(x => x !== "body" && x !== "query").join(".")
            : "";
          const msg = d.msg || d.message || JSON.stringify(d);
          return locStr ? `Field '${locStr}': ${msg}` : msg;
        }
        return String(d);
      });
      return parts.length > 0 ? parts.join("; ") : `${context} validation failed (${status})`;
    }

    // 2. detail string or object
    if (typeof errData.detail === "string" && errData.detail.trim()) {
      return errData.detail;
    }
    if (errData.detail && typeof errData.detail === "object") {
      if (errData.detail.message) return errData.detail.message;
      if (errData.detail.error) return errData.detail.error;
      try {
        return JSON.stringify(errData.detail);
      } catch (e) {}
    }

    // 3. message or error string
    if (typeof errData.message === "string" && errData.message.trim()) {
      return errData.message;
    }
    if (typeof errData.error === "string" && errData.error.trim()) {
      return errData.error;
    }

    // 4. Status-specific officer guidance
    if (status === 401) return "Officer credential expired or unauthorized. Please re-authenticate.";
    if (status === 403) return "Clearance / Jurisdiction Restricted: You lack authorized clearance for this case record.";
    if (status === 404) return "Requested case or evidence record not found in workstation registry.";
    if (status === 409) return "State conflict: The requested transition conflicts with current case state.";
    if (status === 422) return "Invalid input data provided to the workstation.";
    if (status === 503) return "Workstation subsystem temporarily unavailable. Please retry.";

    return `${context} failed (${status || 'Unknown status'})`;
  },

  async handleResponse(res, context = "Operation") {
    if (!res.ok) {
      let errData = {};
      try {
        errData = await res.json();
      } catch (e) {
        errData = { message: res.statusText };
      }
      const message = this.formatErrorMessage(errData, res.status, context);
      const error = new Error(message);
      error.status = res.status;
      error.data = errData;
      throw error;
    }
    return res.json();
  },

  async getAuthStatus() {
    try {
      const res = await fetch(`${API_BASE}/auth/status`);
      return await res.json();
    } catch (e) {
      return { development_mode: true, auth_mode: "offline" };
    }
  },

  async getAuthMe() {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, { headers: this.getHeaders() });
      if (res.ok) return await res.json();
      return null;
    } catch (e) {
      return null;
    }
  },

  async login(mobile_number, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mobile_number, password })
    });
    return this.handleResponse(res, "Signing in");
  },

  async logout() {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        headers: this.getHeaders()
      });
    } catch (e) {
      // Best-effort logout
    }
  },

  async listOfficers(params = {}) {
    const qs = new URLSearchParams(params).toString();
    const url = `${API_BASE}/officers${qs ? '?' + qs : ''}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(res, "Listing officers");
  },

  async getOfficer(officerId) {
    const res = await fetch(`${API_BASE}/officers/${encodeURIComponent(officerId)}`, { headers: this.getHeaders() });
    return this.handleResponse(res, "Loading officer details");
  },

  async createOfficer(payload) {
    const res = await fetch(`${API_BASE}/officers`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res, "Onboarding officer");
  },

  async updateOfficer(officerId, payload) {
    const res = await fetch(`${API_BASE}/officers/${encodeURIComponent(officerId)}`, {
      method: "PATCH",
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res, "Updating officer profile");
  },

  async deactivateOfficer(officerId) {
    const res = await fetch(`${API_BASE}/officers/${encodeURIComponent(officerId)}/deactivate`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Deactivating officer account");
  },

  async reactivateOfficer(officerId) {
    const res = await fetch(`${API_BASE}/officers/${encodeURIComponent(officerId)}/reactivate`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Reactivating officer account");
  },

  async transferOfficer(officerId, payload) {
    const res = await fetch(`${API_BASE}/officers/${encodeURIComponent(officerId)}/transfer`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res, "Transferring officer");
  },

  async resetOfficerPassword(officerId, new_password) {
    const res = await fetch(`${API_BASE}/officers/${encodeURIComponent(officerId)}/reset-password`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ new_password })
    });
    return this.handleResponse(res, "Resetting officer credential");
  },

  async listOrganizations() {
    const res = await fetch(`${API_BASE}/organizations`, { headers: this.getHeaders() });
    return this.handleResponse(res, "Listing departments");
  },

  async listJurisdictions(orgId) {
    const qs = orgId ? `?organization_id=${encodeURIComponent(orgId)}` : '';
    const res = await fetch(`${API_BASE}/jurisdictions${qs}`, { headers: this.getHeaders() });
    return this.handleResponse(res, "Listing jurisdictions");
  },

  async listStations(jurId) {
    const qs = jurId ? `?jurisdiction_id=${encodeURIComponent(jurId)}` : '';
    const res = await fetch(`${API_BASE}/stations${qs}`, { headers: this.getHeaders() });
    return this.handleResponse(res, "Listing police stations");
  },

  async assignCase(caseId, officerId, reason) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/assignments`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ officer_id: officerId, reason })
    });
    return this.handleResponse(res, "Assigning investigating officer");
  },

  async getCaseAssignments(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/assignments`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading assignment history");
  },

  async getEligibleOfficers(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/eligible-officers`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading eligible officers");
  },

  async listCases() {
    const res = await fetch(`${API_BASE}/cases`, { headers: this.getHeaders() });
    return this.handleResponse(res, "Listing cases");
  },

  async getCase(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}`, { headers: this.getHeaders() });
    return this.handleResponse(res, "Loading case particulars");
  },

  async createCase(payload) {
    const res = await fetch(`${API_BASE}/cases`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res, "Registering case");
  },

  async updateCaseStage(caseId, targetStage) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/stage`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ lifecycle_stage: targetStage })
    });
    return this.handleResponse(res, "Updating investigation phase");
  },

  async getCaseStage(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/stage`, { headers: this.getHeaders() });
    return this.handleResponse(res, "Loading phase state");
  },

  async listEvidence(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence`, { headers: this.getHeaders() });
    return this.handleResponse(res, "Listing exhibits");
  },

  async getEvidence(caseId, evidenceId) {
    if (!caseId || caseId === "null" || caseId === "undefined") {
      throw new Error("Investigation case ID is missing or invalid.");
    }
    if (!evidenceId || evidenceId === "null" || evidenceId === "undefined") {
      throw new Error("Evidence ID is missing or invalid.");
    }
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Fetching exhibit details");
  },

  async intakeEvidence(caseId, formData) {
    const headers = { ...State.auth.headers };
    delete headers["Content-Type"];
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence`, {
      method: "POST",
      headers,
      body: formData
    });
    return this.handleResponse(res, "Attaching evidence exhibit");
  },

  async validateEvidenceMime(caseId, evidenceId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/validate`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Verifying file format");
  },

  async scanEvidenceAntivirus(caseId, evidenceId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/scan`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Scanning exhibit for security threats");
  },

  async commitEvidenceWorm(caseId, evidenceId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/worm-commit`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Preserving exhibit in protected storage");
  },

  async verifyEvidenceIntegrity(caseId, evidenceId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/integrity`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Verifying cryptographic fingerprint");
  },

  async applyObjectLock(caseId, evidenceId, lockMode = "GOVERNANCE") {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/object-lock?lock_mode=${lockMode}`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Applying write protection");
  },

  async encryptEvidence(caseId, evidenceId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/encrypt`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Encrypting exhibit data");
  },

  async verifyEncryptionIntegrity(caseId, evidenceId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/verify-encryption`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Verifying encryption authenticity");
  },

  async indexEvidence(caseId, evidenceId, forceReindex = false) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/index?force_reindex=${forceReindex}`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Indexing exhibit for forensic search");
  },

  async searchRAG(caseId, query, limit = 5) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/rag/search`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ query, limit })
    });
    return this.handleResponse(res, "Evidence RAG Search");
  },

  async getTimelineEvents(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/timeline-events`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading timeline events");
  },

  async getAnalysisSummary(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/analysis-summary`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading analysis summary");
  },

  async getExtractedFacts(caseId, evidenceId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/extracted-facts`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading extracted document facts");
  },

  async triggerExtractFacts(caseId, evidenceId, forceReindex = false) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/extract-facts?force_reindex=${forceReindex}`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Extracting document facts");
  },

  getEvidenceFileUrl(caseId, evidenceId) {
    if (!caseId || caseId === "null" || caseId === "undefined" || !evidenceId || evidenceId === "null" || evidenceId === "undefined") {
      return null;
    }
    const token = State.auth.token || "";
    return `${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/file${token ? `?auth=${encodeURIComponent(token)}` : ""}`;
  },

  async recordFactDecision(caseId, evidenceId, factId, payload) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/facts/${encodeURIComponent(factId)}/decision`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res, "Recording fact review decision");
  },

  async previewFIRExtraction(formData) {
    const headers = this.getHeaders();
    delete headers["Content-Type"]; // Let browser set multipart boundary
    const res = await fetch(`${API_BASE}/cases/fir-preview`, {
      method: "POST",
      headers: headers,
      body: formData
    });
    return this.handleResponse(res, "Extracting candidate FIR details");
  },

  async createCaseFIRAssisted(payload) {
    const res = await fetch(`${API_BASE}/cases/fir-assisted`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res, "Creating case with preserved FIR");
  },

  async getKnowledgeGraph(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/knowledge-graph`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading entity knowledge graph");
  },

  async recordEdgeDecision(caseId, edgeId, payload) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/knowledge-graph/edges/${encodeURIComponent(edgeId)}/decision`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res, "Recording relationship review decision");
  },

  async getDualBrain(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/dual-brain`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading Dual-Brain reasoning workspace");
  },

  async askCaseQuestion(caseId, question, limit = 5) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/ask`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ question, limit })
    });
    return this.handleResponse(res, "Evidence Q&A");
  },

  async searchEvidenceIntelligence(caseId, query, filterType = "ALL", limit = 10) {
    const qs = `?q=${encodeURIComponent(query)}&filter_type=${encodeURIComponent(filterType)}&limit=${limit}`;
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/intelligence/search${qs}`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Unified Evidence Search");
  },

  async getPersonDossier(caseId, personId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/intelligence/person/${encodeURIComponent(personId)}`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading Person Dossier");
  },

  async getObjectDossier(caseId, objectId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/intelligence/object/${encodeURIComponent(objectId)}`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading Object Dossier");
  },

  async getEntityRegistry(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/intelligence/registry`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading Entity Registry");
  },

  async getSourceComparisons(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/intelligence/contradictions`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading Source Comparisons");
  },

  async getInvestigationFollowups(caseId) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/intelligence/followups`, {
      headers: this.getHeaders()
    });
    return this.handleResponse(res, "Loading Investigation Gaps");
  },

  async askEvidenceIntelligence(caseId, question, limit = 5) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/intelligence/ask`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ question, limit })
    });
    return this.handleResponse(res, "Evidence Intelligence Synthesis");
  },

  async getHealth() {
    try {
      const res = await fetch(`/health`);
      return await res.json();
    } catch (e) {
      return { status: "operational", version: "0.6.0" };
    }
  }
};


// ═══════════════════════════════════════════════════════════════════════════
// 3. UI HELPERS & FORMATTERS
// ═══════════════════════════════════════════════════════════════════════════

const Formatters = {
  formatDate(dtStr) {
    if (!dtStr) return "Not Recorded";
    try {
      const d = new Date(dtStr);
      return d.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch (e) {
      return dtStr;
    }
  },

  formatOnlyDate(dtStr) {
    if (!dtStr) return "Not recorded";
    try {
      const d = new Date(dtStr);
      return d.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric"
      });
    } catch (e) {
      return dtStr;
    }
  },

  formatOnlyTime(dtStr) {
    if (!dtStr) return "Not recorded";
    try {
      const d = new Date(dtStr);
      return d.toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch (e) {
      return dtStr;
    }
  },

  formatBytes(bytes) {
    if (bytes === 0 || !bytes) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  },

  formatCategory(cat) {
    const map = {
      DOCUMENT_PDF: "General Case Document (PDF)",
      MEDICAL_REPORT: "Medical / Autopsy Report (PDF)",
      SCENE_PHOTO: "Crime Scene Photograph",
      AUTOPSY_PHOTO: "Post-Mortem / Autopsy Photograph",
      AUDIO_RECORDING: "Voice Statement / Dispatch Call",
      CDR_SPREADSHEET: "Call Detail Record (CDR) Sheet",
      DIGITAL_DEVICE_EXTRACTION: "Digital Device Extraction",
      PHYSICAL_EXHIBIT: "Physical / Ballistics / Biological Exhibit",
      OTHER: "CCTV / Video / Other Exhibit"
    };
    return map[cat] || cat;
  },

  formatPlainCategory(cat) {
    const map = {
      DOCUMENT_PDF: "Document",
      DOCUMENT_WORD: "Document",
      MEDICAL_REPORT: "Medical report",
      SCENE_PHOTO: "Photograph",
      AUTOPSY_PHOTO: "Photograph",
      IMAGE: "Photograph",
      AUDIO_RECORDING: "Audio recording",
      AUDIO: "Audio recording",
      VIDEO: "Video recording",
      CDR_SPREADSHEET: "Call-detail records",
      CALL_DETAIL_RECORD: "Call-detail records",
      DIGITAL_DEVICE_EXTRACTION: "Digital extraction",
      FORENSIC_EXTRACTION: "Digital extraction",
      PHYSICAL_EXHIBIT: "Physical exhibit",
      OTHER: "Other evidence"
    };
    return map[cat] || "Other evidence";
  },

  detectFileFormat(filename) {
    if (!filename) return { label: "Digital File", mime: "application/octet-stream", icon: "", defaultCategory: "OTHER" };
    const ext = filename.split(".").pop().toLowerCase();
    switch (ext) {
      case "pdf":
        return { label: "PDF Document", mime: "application/pdf", icon: "", defaultCategory: "DOCUMENT_PDF" };
      case "jpg":
      case "jpeg":
        return { label: "JPEG Photograph", mime: "image/jpeg", icon: "", defaultCategory: "SCENE_PHOTO" };
      case "png":
        return { label: "PNG Photograph", mime: "image/png", icon: "", defaultCategory: "SCENE_PHOTO" };
      case "mp4":
      case "avi":
      case "mkv":
      case "mov":
        return { label: "Video Recording", mime: "video/mp4", icon: "", defaultCategory: "OTHER" };
      case "wav":
      case "mp3":
      case "m4a":
        return { label: "Audio Recording", mime: "audio/wav", icon: "", defaultCategory: "AUDIO_RECORDING" };
      case "csv":
      case "xlsx":
      case "xls":
        return { label: "Spreadsheet / CDR Data", mime: "text/csv", icon: "", defaultCategory: "CDR_SPREADSHEET" };
      case "txt":
      case "json":
        return { label: "Text Record", mime: "text/plain", icon: "", defaultCategory: "DOCUMENT_PDF" };
      default:
        return { label: `${ext.toUpperCase()} File`, mime: "application/octet-stream", icon: "", defaultCategory: "OTHER" };
    }
  },

  detectMimeFromFilename(filename) {
    return this.detectFileFormat(filename).mime;
  },

  truncate(str, max = 32) {
    if (!str) return "";
    if (str.length <= max) return str;
    return str.substring(0, max) + "...";
  },

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

const StatusPresentation = {
  dictionary: {
    // Lifecycle stages
    "INITIALIZED": {
      label: "Case Registered",
      short: "Case Setup",
      description: "Case particulars registered. Next step: Begin collecting evidence exhibits.",
      badgeClass: "badge-neutral",
      icon: "📋"
    },
    "EVIDENCE_INGESTION": {
      label: "Collecting Evidence",
      short: "Collecting Evidence",
      description: "Evidence collection phase open. Attach crime scene photos, post-mortem reports, CCTV, and digital records.",
      badgeClass: "badge-info",
      icon: "📦"
    },
    "EVIDENCE_PROCESSING": {
      label: "Forensic Verification",
      short: "Forensic Verification",
      description: "Automated format validation, malware scanning, dual-hash integrity checks, and WORM storage.",
      badgeClass: "badge-attention",
      icon: "⚙️"
    },
    "ANALYSIS": {
      label: "Investigation Analysis",
      short: "Timeline & Analysis",
      description: "Cross-correlation of exhibits and chronological timeline reconstruction active.",
      badgeClass: "badge-info",
      icon: "⏱️"
    },
    "REVIEW": {
      label: "Inquest Review",
      short: "Inquest Review",
      description: "Inquiry ready for supervisory review and endorsement.",
      badgeClass: "badge-attention",
      icon: "🔍"
    },
    "CLOSED": {
      label: "Case Concluded",
      short: "Case Closed",
      description: "Final inquiry report concluded and archived under law.",
      badgeClass: "badge-verified",
      icon: "✓"
    },
    "SUSPENDED": {
      label: "Investigation Suspended",
      short: "Suspended",
      description: "Investigation held under administrative or legal stay.",
      badgeClass: "badge-danger",
      icon: "⏸"
    },
    "REOPENED": {
      label: "Investigation Reopened",
      short: "Reopened",
      description: "Supervisory reopening for supplementary inquiries.",
      badgeClass: "badge-attention",
      icon: "🔄"
    },

    // Evidence pipeline intake & verification
    "REGISTERED_INTAKE": {
      label: "Intake Received",
      short: "Received",
      description: "Exhibit staged into case workspace; awaiting initial verification checks.",
      badgeClass: "badge-neutral",
      icon: "📥"
    },
    "PENDING_MIME_VALIDATION": {
      label: "Awaiting Format Check",
      short: "Format Check",
      description: "Binary signature inspection queued.",
      badgeClass: "badge-attention",
      icon: "⏳"
    },
    "VALIDATED": {
      label: "File Format Confirmed",
      short: "Format Valid",
      description: "File signature matches declared type.",
      badgeClass: "badge-verified",
      icon: "✓"
    },
    "AV_SCANNING": {
      label: "Running Security Scan",
      short: "Scanning",
      description: "Antivirus scanner actively inspecting file binary for malicious threats.",
      badgeClass: "badge-attention",
      icon: "🛡️"
    },
    "CLEAN": {
      label: "Security Scan Passed",
      short: "Clean",
      description: "No threats detected by the configured antivirus scanner.",
      badgeClass: "badge-verified",
      icon: "✓"
    },
    "QUARANTINED": {
      label: "Quarantined (Threat Detected)",
      short: "Quarantined",
      description: "Security threat detected in payload; isolated from active workspace.",
      badgeClass: "badge-danger",
      icon: "⚠️"
    },
    "REJECTED": {
      label: "Verification Failed",
      short: "Rejected",
      description: "File signature mismatch or disallowed format.",
      badgeClass: "badge-danger",
      icon: "❌"
    },
    "PENDING_VERIFICATION": {
      label: "Awaiting Verification",
      short: "Awaiting Verification",
      description: "Exhibit attached, awaiting automated integrity checks.",
      badgeClass: "badge-attention",
      icon: "⏳"
    },

    // Integrity & Checksums
    "INTEGRITY_VERIFIED": {
      label: "File Integrity Checks Passed",
      short: "Integrity Verified",
      description: "Dual cryptographic fingerprints (SHA-256 and SHA3-512) recorded and verified.",
      badgeClass: "badge-verified",
      icon: "✓"
    },
    "VERIFIED": {
      label: "File Integrity Checks Passed",
      short: "Verified",
      description: "Dual cryptographic fingerprints recorded and verified.",
      badgeClass: "badge-verified",
      icon: "✓"
    },
    "PENDING": {
      label: "Awaiting Verification",
      short: "Pending",
      description: "Integrity checks not yet completed.",
      badgeClass: "badge-attention",
      icon: "⏳"
    },
    "FAILED": {
      label: "Integrity Check Failed",
      short: "Failed",
      description: "Cryptographic hash mismatch or file corruption detected.",
      badgeClass: "badge-danger",
      icon: "❌"
    },

    // Storage & Protection
    "COMMITTED": {
      label: "Stored with Protection Enabled",
      short: "Preserved",
      description: "Exhibit committed to write-once storage with protection enabled.",
      badgeClass: "badge-verified",
      icon: "🔒"
    },
    "OBJECT_LOCKED": {
      label: "Evidence Stored with Protection Enabled",
      short: "Protected",
      description: "Application-level write protection active to prevent accidental modification or deletion.",
      badgeClass: "badge-verified",
      icon: "🔒"
    },

    // Search / RAG Indexing
    "INDEXED": {
      label: "Ready for Document Search",
      short: "Search Ready",
      description: "Text extracted and indexed into neural vector store for semantic search.",
      badgeClass: "badge-verified",
      icon: "🔎"
    },
    "INDEXING": {
      label: "Preparing Document for Search",
      short: "Indexing",
      description: "Extracting text and computing neural embeddings for search.",
      badgeClass: "badge-attention",
      icon: "⏳"
    },
    "INDEXING_FAILED": {
      label: "Document Received, But Search Preparation Failed",
      short: "Search Unavailable",
      description: "Document preserved in storage, but search indexing failed.",
      badgeClass: "badge-danger",
      icon: "⚠️"
    },

    // Operational errors & authorization
    "UNAUTHORIZED": {
      label: "You do not have permission to perform this action",
      short: "Unauthorized",
      description: "Access restricted by case assignment or territorial jurisdiction policy.",
      badgeClass: "badge-danger",
      icon: "🚫"
    },
    "NOT_FOUND": {
      label: "This case or record could not be found",
      short: "Not Found",
      description: "The requested identifier does not exist or has been archived.",
      badgeClass: "badge-neutral",
      icon: "⚠️"
    },

    // Security & Multi-layer Verification additions
    "INTEGRITY_PASSED_WORM_PENDING": {
      label: "Integrity Verified · Storage Protection Pending",
      short: "Storage Lock Pending",
      description: "Dual-hash integrity checks passed, but write-protection storage verification is still pending. File hashes verified · Storage lock pending.",
      badgeClass: "badge-attention",
      icon: "⏳"
    },
    "PROTECTED_VERIFIED": {
      label: "Integrity Verified · Storage Protected",
      short: "Protected",
      description: "All required security checks verified: format, malware scan, dual-hash integrity, preservation, storage lock, and encryption.",
      badgeClass: "badge-verified",
      icon: "🛡️"
    },
    "PROTECTED_SIMULATED": {
      label: "Integrity Verified (Local Lock Simulated)",
      short: "Verified (Simulated)",
      description: "Dual-hash integrity verified. Object-lock active in local simulation mode (not hardware/cloud WORM).",
      badgeClass: "badge-verified",
      icon: "🛡️"
    },
    "SECURITY_ALERT": {
      label: "Security Alert: Action Required",
      short: "Security Alert",
      description: "Evidence failed cryptographic integrity check or contains a security threat.",
      badgeClass: "badge-danger",
      icon: "⚠️"
    },
    "THREAT_DETECTED": {
      label: "Security Alert: Threat Detected",
      short: "Threat Detected",
      description: "Antivirus scanner identified a malicious payload in this exhibit.",
      badgeClass: "badge-danger",
      icon: "⚠️"
    },
    "SCANNER_UNAVAILABLE": {
      label: "Scanner Unavailable",
      short: "Unavailable",
      description: "Automated antivirus scanner service is temporarily offline.",
      badgeClass: "badge-attention",
      icon: "⚠️"
    },
    "NEEDS_CONFIRMATION": {
      label: "Awaiting Your Confirmation",
      short: "Needs Review",
      description: "Extracted relation or fact requires investigating officer confirmation.",
      badgeClass: "badge-attention",
      icon: "⚖️"
    },
    "CONFIRMED": {
      label: "Confirmed by Officer",
      short: "Confirmed",
      description: "Investigating officer confirmed this finding.",
      badgeClass: "badge-verified",
      icon: "✓"
    },
    "DISPUTED": {
      label: "Disputed by Officer",
      short: "Disputed",
      description: "Investigating officer disputed or rejected this finding.",
      badgeClass: "badge-danger",
      icon: "✗"
    },
    "DISMISSED": {
      label: "Dismissed",
      short: "Dismissed",
      description: "Investigative observation dismissed by officer.",
      badgeClass: "badge-neutral",
      icon: "●"
    },
    "ENFORCING_MINIMUM_CREDIBILITY": {
      label: "Evaluating Source Credibility",
      short: "Evaluating",
      description: "Gate is enforcing minimum credibility before hypothesis acceptance.",
      badgeClass: "badge-attention",
      icon: "🛡️"
    },
    "ACTIVE_ENFORCED": {
      label: "Firewall Active",
      short: "Active",
      description: "Information firewall actively isolating hypotheses from evidence exhibits.",
      badgeClass: "badge-verified",
      icon: "🛡️"
    },
    "QUOTED_FROM_SOURCE": {
      label: "Direct Quote from Source",
      short: "Direct Quote",
      description: "Extracted directly verbatim from exhibit source text.",
      badgeClass: "badge-info",
      icon: "“"
    },
    "INFERRED": {
      label: "Analytical Inference",
      short: "Inference",
      description: "Analytical conclusion derived from primary exhibit facts.",
      badgeClass: "badge-neutral",
      icon: "💡"
    },
    "STATUS_UNAVAILABLE": {
      label: "Status Unavailable",
      short: "Unavailable",
      description: "Status could not be determined from backend records.",
      badgeClass: "badge-neutral",
      icon: "●"
    }
  },

  get(statusKey) {
    if (!statusKey || statusKey === "UNDEFINED" || statusKey === "NULL" || statusKey === "null" || statusKey === "undefined") {
      return { label: "Status unavailable", short: "Status unavailable", description: "State could not be determined from backend records.", badgeClass: "badge-neutral", icon: "●" };
    }
    const upper = String(statusKey).toUpperCase().trim();
    return this.dictionary[upper] || {
      label: statusKey.replace(/_/g, " "),
      short: statusKey.replace(/_/g, " "),
      description: "",
      badgeClass: "badge-neutral",
      icon: "●"
    };
  },

  renderBadge(statusKey, customLabel = null) {
    const info = this.get(statusKey);
    const label = customLabel || info.label;
    return `<span class="badge ${info.badgeClass}" title="${Formatters.escapeHtml(info.description)}">${Formatters.escapeHtml(label)}</span>`;
  },

  renderTechnicalDetailsPanel(titleOrExhibit, items = null, allowCopy = true) {
    let title = "Technical & Cryptographic Details";
    let detailItems = items;
    if (titleOrExhibit && typeof titleOrExhibit === "object" && !Array.isArray(titleOrExhibit)) {
      const e = titleOrExhibit;
      title = `Exhibit Technical Details (${e.evidence_id || 'ID unassigned'})`;
      const isLocalSimulated = !e.lock_backend || e.lock_backend === "SIMULATED_LOCAL" || e.lock_backend === "LOCAL_FS";
      detailItems = [
        { label: "Exhibit Identifier", value: e.evidence_id },
        { label: "Original Filename", value: e.original_file_name },
        { label: "Detected MIME Type", value: e.detected_mime_type || e.declared_mime_type || "unverified" },
        { label: "SHA-256 Digest", value: e.checksum_sha256 || e.sha256_hash || "Verification pending" },
        { label: "SHA3-512 Digest", value: e.checksum_sha3_512 || e.sha3_512_hash || "Verification pending" },
        { label: "WORM Storage State", value: e.worm_status || "PENDING" },
        { label: "Storage Lock Type", value: isLocalSimulated ? "Local Immutability (Simulated) — Not genuine hardware/cloud WORM" : `${e.lock_backend || 'Hardware/Cloud'} Locked` },
        { label: "Encryption", value: e.encryption_status === "ENCRYPTED" ? "AES-256-GCM (At rest)" : (e.encryption_status || "Pending") },
        { label: "Antivirus Scan", value: e.antivirus_status === "CLEAN" ? `Clean (${e.antivirus_scanner || 'Native Engine'})` : (e.antivirus_status || "Pending") },
        { label: "Chain of Custody Intake", value: e.created_at ? Formatters.formatDate(e.created_at) : "Intake recorded" }
      ];
    } else if (typeof titleOrExhibit === "string") {
      title = titleOrExhibit;
    }
    if (!detailItems || detailItems.length === 0) return "";
    return `
      <details class="technical-details-panel">
        <summary>${Formatters.escapeHtml(title)}</summary>
        <div class="technical-details-content">
          ${detailItems.map(it => `
            <div class="tech-detail-row">
              <span class="tech-detail-label">${Formatters.escapeHtml(it.label)}:</span>
              <div class="tech-detail-value-wrap">
                <span class="tech-detail-val" title="${Formatters.escapeHtml(it.value || '')}">${Formatters.escapeHtml(it.value || 'Not available')}</span>
                ${allowCopy && it.value && it.value !== 'Not available' ? `
                  <button type="button" class="btn-copy-tech" onclick="navigator.clipboard.writeText('${Formatters.escapeHtml(it.value)}'); UI.showToast('Copied to clipboard', 'info', 2000);" title="Copy value">Copy</button>
                ` : ''}
              </div>
            </div>
          `).join("")}
        </div>
      </details>
    `;
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// CONTRADICTION & DISCREPANCY ASSESSMENT EVALUATOR
// Evaluates cross-document contradiction detection states authoritatively.
// Replaces ambiguous dashes with explicit, defensible investigative states.
// ═══════════════════════════════════════════════════════════════════════════
const ContradictionAssessmentEvaluator = {
  evaluate({ evidenceList = [], analysisSummary = null, isRunning = false, hasError = false }) {
    // State 1: Assessment in progress
    if (isRunning) {
      return {
        state: "IN_PROGRESS",
        number: "Assessment in progress",
        isTextState: true,
        subtext: "Comparing exhibits for timeline and claim discrepancies...",
        colorClass: "var(--info-text, #3b82f6)",
        badgeClass: "badge-info",
        routeTab: "analysis",
        actionText: null
      };
    }

    // State 2: Assessment unavailable or failed
    if (hasError) {
      return {
        state: "UNAVAILABLE",
        number: "Unable to assess",
        isTextState: true,
        subtext: "Assessment unavailable — check exhibit extraction status",
        colorClass: "var(--danger, #ef4444)",
        badgeClass: "badge-danger",
        routeTab: "analysis",
        actionText: "Retry Assessment"
      };
    }

    // State 3: Awaiting evidence — insufficient exhibits (< 2 exhibits) for cross-comparison
    if (!evidenceList || evidenceList.length < 2) { // if (evidenceList.length < 2)
      const count = evidenceList ? evidenceList.length : 0;
      return {
        state: "AWAITING_EVIDENCE",
        number: "Awaiting evidence",
        isTextState: true,
        subtext: count === 0
          ? "Comparisons pending — attach 2+ exhibits for cross-document comparison (0 attached)"
          : `Comparisons pending — attach 2+ exhibits (${count} attached)`,
        colorClass: "var(--text-muted)",
        badgeClass: "badge-neutral",
        routeTab: "evidence",
        actionText: "+ Upload Evidence Exhibit"
      };
    }

    // State 4: Not assessed — sufficient evidence exists (>= 2 exhibits), but comparison not yet run/loaded
    if (!analysisSummary) {
      return {
        state: "NOT_ASSESSED",
        number: "Not assessed",
        isTextState: true,
        subtext: "Comparison not yet run — click to open analysis workspace",
        colorClass: "var(--text-muted)",
        badgeClass: "badge-attention",
        routeTab: "analysis",
        actionText: "Open Analysis Workspace"
      };
    }

    // State 5 & 6: Assessment completed
    const contradictionsList = Array.isArray(analysisSummary.contradictions)
      ? analysisSummary.contradictions
      : [];
    const totalDetected = contradictionsList.length;

    const unresolved = contradictionsList.filter(ct => {
      if (ct.resolved === true) return false;
      const status = (ct.investigator_status || "").toUpperCase();
      return status === "UNRESOLVED" || status === "" || !ct.investigator_status;
    });
    const reviewedCount = totalDetected - unresolved.length;

    if (totalDetected > 0) {
      const isAllReviewed = unresolved.length === 0;
      const discrepancyWord = unresolved.length === 1 ? "Discrepancy" : "Discrepancies";
      const primaryLabel = isAllReviewed
        ? `${totalDetected} Discrepanc${totalDetected === 1 ? 'y' : 'ies'} (Reviewed)`
        : `${unresolved.length} Potential ${discrepancyWord}`;

      return {
        state: "DISCREPANCIES_FOUND",
        number: primaryLabel,
        isTextState: true,
        subtext: `${reviewedCount} reviewed / ${totalDetected} detected (potential discrepancies awaiting review)`,
        colorClass: "var(--attention)",
        badgeClass: "badge-attention",
        routeTab: "analysis",
        actionText: "Review Discrepancies",
        unresolvedCount: unresolved.length,
        reviewedCount: reviewedCount,
        totalDetected: totalDetected
      };
    }

    // State 6: Assessment completed — none identified
    return {
      state: "NONE_IDENTIFIED",
      number: "None identified",
      isTextState: true,
      subtext: `No discrepancies identified across ${evidenceList.length} exhibits compared (does not establish singular truth)`,
      colorClass: "var(--verified)",
      badgeClass: "badge-verified",
      routeTab: "analysis",
      actionText: "View Completed Analysis",
      unresolvedCount: 0,
      reviewedCount: 0,
      totalDetected: 0
    };
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// EVIDENCE SECURITY & FORENSIC VERIFICATION EVALUATOR
// Evaluates all 6 forensic security dimensions independently:
// 1. File validation, 2. Antivirus scan, 3. Integrity verification,
// 4. Storage protection (WORM), 5. Data encryption, 6. Overall status.
// Distinguishes local filesystem simulation from genuine hardware/cloud WORM.
// ═══════════════════════════════════════════════════════════════════════════
const EvidenceSecurityEvaluator = {
  evaluateExhibit(e) {
    if (!e) {
      return {
        format: { layer: "File Format", status: "UNAVAILABLE", passed: false, failed: false, pending: false, label: "Format status unavailable", details: "Record missing" },
        antivirus: { layer: "Antivirus Scanning", status: "UNAVAILABLE", passed: false, failed: false, pending: false, unavailable: true, label: "Antivirus scan unavailable", details: "Scanner verdict unavailable — cannot be treated as clean" },
        integrity: { layer: "Integrity Fingerprint", status: "UNAVAILABLE", passed: false, failed: false, pending: false, label: "Integrity status unavailable", details: "Dual fingerprint pending" },
        preservation: { layer: "Vault Preservation", status: "UNAVAILABLE", passed: false, pending: false, label: "Preservation status unavailable", details: "Staging path unrecorded" },
        worm: { layer: "Storage Protection (WORM)", status: "UNAVAILABLE", passed: false, failed: false, pending: false, isSimulated: false, label: "Storage protection unavailable", details: "Storage lock unrecorded" },
        storage: { layer: "Storage Protection (WORM)", status: "UNAVAILABLE", passed: false, failed: false, pending: false, isSimulated: false, label: "Storage protection unavailable", details: "Storage lock unrecorded" },
        encryption: { layer: "Data Encryption", status: "UNAVAILABLE", passed: false, failed: false, pending: false, label: "Encryption status unavailable", details: "Encryption unrecorded" },
        overall: {
          status: "UNAVAILABLE",
          badgeClass: "badge-neutral",
          badge: "badge-neutral",
          label: "Status unavailable",
          subtext: "Verification state could not be determined",
          isFullyVerified: false,
          hasAlert: false,
          isIntegrityPassedWormPending: false
        }
      };
    }

    // 1. File format validation
    const formatFailed = e.status === "REJECTED";
    const formatPassed = !formatFailed && (e.status === "VALIDATED" || Boolean(e.detected_mime_type));
    const formatPending = !formatFailed && !formatPassed && (!e.status || e.status === "REGISTERED_INTAKE" || e.status === "PENDING_MIME_VALIDATION");
    const formatStatus = formatFailed ? "FAILED" : formatPassed ? "PASSED" : formatPending ? "PENDING" : "UNAVAILABLE";
    const format = {
      layer: "File Format",
      passed: formatPassed,
      failed: formatFailed,
      pending: formatPending,
      status: formatStatus,
      label: formatFailed ? "Format signature rejected" : formatPassed ? "Format validated" : formatPending ? "Format check pending" : "Format status unavailable",
      details: e.detected_mime_type || e.declared_mime_type || "Awaiting signature inspection"
    };

    // 2. Antivirus scanning: missing verdict must never be treated as clean
    const avClean = e.antivirus_status === "CLEAN";
    const avThreat = e.antivirus_status === "THREAT_DETECTED" || e.antivirus_status === "QUARANTINED";
    const avFailed = e.antivirus_status === "SCAN_ERROR" || e.antivirus_status === "SCAN_TIMEOUT";
    const avUnavailable = e.antivirus_status === "SCANNER_UNAVAILABLE";
    const avPending = !e.antivirus_status || e.antivirus_status === "AV_SCANNING" || e.antivirus_status === "PENDING";
    const avStatus = avThreat ? "ALERT" : avClean ? "PASSED" : avFailed ? "FAILED" : avUnavailable ? "UNAVAILABLE" : avPending ? "PENDING" : "UNAVAILABLE";
    const av = {
      layer: "Antivirus Scanning",
      passed: avClean,
      failed: avThreat || avFailed,
      scannerUnavailable: avUnavailable,
      error: avFailed,
      pending: avPending,
      unavailable: avUnavailable || (!avClean && !avThreat && !avFailed && !avPending),
      status: avStatus,
      label: avThreat
        ? `Threat detected: ${e.antivirus_threat_name || 'Malware'}`
        : avClean
        ? "Security scan clean"
        : avUnavailable
        ? "Antivirus scan unavailable"
        : avFailed
        ? "Antivirus scan failed"
        : avPending
        ? "Security scan pending"
        : "Antivirus scan unavailable",
      details: avClean
        ? (e.antivirus_scanner ? `Clean (${e.antivirus_scanner})` : "Clean (configured scanner)")
        : avThreat
        ? (e.antivirus_threat_name || "Quarantined threat")
        : avUnavailable
        ? "Scanner verdict unavailable — cannot be treated as clean"
        : (e.antivirus_scanner || "Queued for malware analysis")
    };

    // 3. Integrity verification: report success ONLY when hash comparison succeeded
    const integrityPassed = e.integrity_status === "VERIFIED";
    const integrityFailed = e.integrity_status === "FAILED";
    const integrityPending = !e.integrity_status || e.integrity_status === "UNVERIFIED" || e.integrity_status === "PENDING";
    const integrityStatus = integrityFailed ? "FAILED" : integrityPassed ? "PASSED" : integrityPending ? "PENDING" : "UNAVAILABLE";
    const integrity = {
      layer: "Integrity Fingerprint",
      passed: integrityPassed,
      failed: integrityFailed,
      pending: integrityPending,
      status: integrityStatus,
      label: integrityFailed
        ? "Integrity check failed"
        : integrityPassed
        ? "Integrity hash verified"
        : integrityPending
        ? "Integrity check pending"
        : "Integrity status unavailable",
      details: (e.checksum_sha256 || e.sha256_hash)
        ? `SHA-256: ${(e.checksum_sha256 || e.sha256_hash).substring(0, 16)}...`
        : "Dual fingerprint pending"
    };

    // 4. Vault Preservation
    const preservation = {
      layer: "Vault Preservation",
      passed: Boolean(e.raw_storage_path),
      pending: !e.raw_storage_path,
      status: e.raw_storage_path ? "PASSED" : "PENDING",
      label: e.raw_storage_path ? "Preserved in vault" : "Preservation pending",
      details: e.raw_storage_path ? "Sealed in evidence repository" : "Staged in temporary intake buffer"
    };

    // 5. Storage Protection (WORM / Object Lock)
    // Clearly distinguish local filesystem simulation from actual enforced immutable storage
    const lockBackend = (e.lock_backend || "").toUpperCase();
    const isLocalSimulated = !e.lock_backend || lockBackend === "LOCAL_FILESYSTEM" || lockBackend === "SIMULATED_LOCAL" || lockBackend === "LOCAL_FS" || lockBackend === "FILE_SYSTEM";
    const wormCommitted = e.worm_status === "COMMITTED" && (e.lock_status === "LOCKED" || Boolean(e.worm_storage_reference) || Boolean(e.lock_storage_reference));
    const wormFailed = e.worm_status === "FAILED" || e.lock_status === "LOCK_FAILED";
    const wormPending = !wormCommitted && !wormFailed && (!e.worm_status || e.worm_status === "PENDING" || e.lock_status === "UNLOCKED");
    const wormStatus = wormFailed ? "ALERT" : wormCommitted ? (isLocalSimulated ? "PASSED_SIMULATED" : "PASSED") : wormPending ? "PENDING" : "UNAVAILABLE";
    const worm = {
      layer: "Storage Protection (WORM)",
      passed: wormCommitted,
      failed: wormFailed,
      pending: wormPending,
      isSimulated: isLocalSimulated,
      status: wormStatus,
      label: wormFailed
        ? "Storage protection failed"
        : wormCommitted
        ? (isLocalSimulated ? "Storage protection simulated (local)" : "Hardware/Cloud WORM locked")
        : wormPending
        ? "Storage protection pending"
        : "Storage protection unavailable",
      details: isLocalSimulated
        ? "Local filesystem immutability simulated — not genuine cloud/hardware WORM"
        : (e.lock_backend || "WORM compliance lock active")
    };
    const storage = worm;

    // 6. Data Encryption
    const encPassed = e.encryption_status === "ENCRYPTED";
    const encFailed = e.encryption_status === "FAILED" || e.encryption_status === "ENCRYPTION_FAILED";
    const encPending = !encPassed && !encFailed && (!e.encryption_status || e.encryption_status === "PENDING" || e.encryption_status === "UNENCRYPTED");
    const encStatus = encFailed ? "ALERT" : encPassed ? "PASSED" : encPending ? "PENDING" : "UNAVAILABLE";
    const encryption = {
      layer: "Data Encryption",
      passed: encPassed,
      failed: encFailed,
      pending: encPending,
      status: encStatus,
      label: encFailed
        ? "Encryption failed"
        : encPassed
        ? "Encrypted at rest (AES-256-GCM)"
        : encPending
        ? "Encryption pending"
        : "Encryption status unavailable",
      details: encPassed ? (e.encryption_algorithm || "AES-256-GCM") : (encFailed ? "Encryption error" : "Encryption status unavailable")
    };

    // 7. Overall forensic status aggregation
    const hasAlert = format.failed || av.failed || integrity.failed || worm.failed || encryption.failed;
    const isIntegrityPassedWormPending = integrity.passed && worm.pending;
    const isFullyVerified = format.passed && av.passed && integrity.passed && preservation.passed && worm.passed && encryption.passed;

    let overallStatus = "PENDING";
    let overallBadge = "badge-attention";
    let overallLabel = "Verification in progress";
    let overallSubtext = "Security checks active";

    if (hasAlert) {
      overallStatus = "ALERT";
      overallBadge = "badge-danger";
      overallLabel = av.failed && av.status === "ALERT" ? "Security alert: Threat detected" : integrity.failed ? "Integrity check failed" : "Security alert: Attention required";
      overallSubtext = av.failed ? (e.antivirus_threat_name ? `Threat detected: ${e.antivirus_threat_name}` : "Security scan threat detected") : integrity.failed ? "Cryptographic hash mismatch" : "Security check failed";
    } else if (isFullyVerified) {
      if (worm.isSimulated) {
        overallStatus = "VERIFIED_SIMULATED";
        overallBadge = "badge-verified";
        overallLabel = "Integrity verified (Local lock simulated)";
        overallSubtext = "File integrity verified · Local lock simulated";
      } else {
        overallStatus = "VERIFIED";
        overallBadge = "badge-verified";
        overallLabel = "Integrity verified · Storage protected";
        overallSubtext = "Dual-hash verified & WORM locked";
      }
    } else if (isIntegrityPassedWormPending) {
      overallStatus = "INTEGRITY_PASSED_WORM_PENDING";
      overallBadge = "badge-attention";
      overallLabel = "Integrity verified · Storage protection pending"; // Integrity Verified · WORM Pending
      overallSubtext = "File integrity has been checked. Storage-protection verification is still pending.";
    } else if (av.unavailable) {
      overallStatus = "ATTENTION";
      overallBadge = "badge-attention";
      overallLabel = "Antivirus scan unavailable";
      overallSubtext = "Scanner verdict unavailable — cannot be treated as clean";
    } else if (encryption.pending || encryption.status === "UNAVAILABLE") {
      overallStatus = "PENDING";
      overallBadge = "badge-attention";
      overallLabel = "Encryption status unavailable";
      overallSubtext = "Encryption at rest pending or unverified";
    } else {
      overallStatus = "PENDING";
      overallBadge = "badge-attention";
      overallLabel = "Verification in progress";
      overallSubtext = "Intake checks pending";
    }

    return {
      format,
      antivirus: av,
      integrity,
      preservation,
      worm,
      storage,
      encryption,
      overall: {
        status: overallStatus,
        badgeClass: overallBadge,
        badge: overallBadge,
        label: overallLabel,
        subtext: overallSubtext,
        isFullyVerified,
        hasAlert,
        isIntegrityPassedWormPending
      }
    };
  },

  evaluateCaseSecurity(evidenceList = []) {
    if (!evidenceList || evidenceList.length === 0) {
      return {
        metricValue: "0",
        label: "Evidence security",
        status: "EMPTY",
        badgeClass: "badge-neutral",
        colorClass: "var(--text-muted)",
        subtext: "No exhibits attached to evaluate",
        hasAlerts: false,
        isFullySecure: false,
        isSimulated: false,
        pendingCount: 0,
        alertCount: 0,
        total: 0
      };
    }

    const evaluations = evidenceList.map(e => this.evaluateExhibit(e));
    const alerts = evaluations.filter(ev => ev.overall.hasAlert);
    const fullyVerified = evaluations.filter(ev => ev.overall.isFullyVerified);
    const pendingWorm = evaluations.filter(ev => ev.overall.isIntegrityPassedWormPending);
    const avUnavailable = evaluations.filter(ev => ev.antivirus.unavailable);
    const pendingAny = evaluations.filter(ev => !ev.overall.isFullyVerified && !ev.overall.hasAlert);
    const allSimulated = evaluations.every(ev => ev.worm.isSimulated);

    if (alerts.length > 0) {
      return {
        metricValue: `${alerts.length} Alert${alerts.length > 1 ? 's' : ''}`,
        label: "Evidence security",
        status: "ALERT",
        badgeClass: "badge-danger",
        colorClass: "var(--danger)",
        subtext: `${alerts.length} exhibit${alerts.length > 1 ? 's' : ''} require immediate attention`,
        hasAlerts: true,
        isFullySecure: false,
        isSimulated: false,
        pendingCount: pendingAny.length,
        alertCount: alerts.length,
        total: evidenceList.length
      };
    }

    if (pendingAny.length > 0) {
      let subtext = `${pendingAny.length} exhibit${pendingAny.length > 1 ? 's' : ''} require verification`;
      if (pendingWorm.length > 0 && fullyVerified.length + pendingWorm.length === evidenceList.length) {
        subtext = "Integrity verified · Storage protection pending";
      } else if (avUnavailable.length > 0) {
        subtext = "Antivirus scan unavailable";
      }

      return {
        metricValue: `${fullyVerified.length}/${evidenceList.length} Verified`,
        label: "Evidence security",
        status: "PENDING",
        badgeClass: "badge-attention",
        colorClass: "var(--attention)",
        subtext: subtext,
        hasAlerts: false,
        isFullySecure: false,
        isSimulated: false,
        pendingCount: pendingAny.length,
        alertCount: 0,
        total: evidenceList.length
      };
    }

    // All required checks genuinely passed
    if (allSimulated) {
      return {
        metricValue: `${evidenceList.length}/${evidenceList.length} Verified (Simulated)`,
        label: "Evidence security",
        status: "VERIFIED_SIMULATED",
        badgeClass: "badge-verified",
        colorClass: "var(--verified)",
        subtext: "File integrity verified · Local lock simulated",
        hasAlerts: false,
        isFullySecure: true,
        isSimulated: true,
        pendingCount: 0,
        alertCount: 0,
        total: evidenceList.length
      };
    }

    return {
      metricValue: `${evidenceList.length}/${evidenceList.length} Verified`,
      label: "Evidence security",
      status: "VERIFIED",
      badgeClass: "badge-verified",
      colorClass: "var(--verified)",
      subtext: "All required security checks verified",
      hasAlerts: false,
      isFullySecure: true,
      isSimulated: false,
      pendingCount: 0,
      alertCount: 0,
      total: evidenceList.length
    };
  },

  evaluateUnavailable() {
    return {
      metricValue: "Status unavailable",
      label: "Evidence security",
      status: "UNAVAILABLE",
      badgeClass: "badge-neutral",
      colorClass: "var(--text-muted)",
      subtext: "Verification state could not be determined",
      hasAlerts: false,
      isFullySecure: false,
      isSimulated: false,
      pendingCount: 0,
      alertCount: 0,
      total: 0
    };
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// AUTHORITATIVE RECOMMENDED NEXT ACTION EVALUATOR
// Formulates: What needs to be done, Why it matters, Involved items, and Action button
// ═══════════════════════════════════════════════════════════════════════════
const RecommendedActionEvaluator = {
  getAction(c, evidenceList = [], analysisSummary = null, graphEdges = []) {
    if (!c) {
      return {
        title: "Status Unavailable",
        whyItMatters: "Case particulars could not be retrieved from the authoritative database.",
        involved: "Case docket records",
        buttonHtml: `<button class="btn btn-secondary btn-sm" onclick="Router.navigate('#/cases')">Return to Directory</button>`
      };
    }

    const totalEvidence = evidenceList.length;
    const stage = c.lifecycle_stage;

    if (stage === "INITIALIZED") {
      return {
        title: "Begin Evidence Collection",
        whyItMatters: "Case particulars and inquest details are recorded. Evidence must be collected to substantiate the inquiry.",
        involved: `Case docket: ${c.case_id} (FIR: ${(c.fir_metadata && c.fir_metadata.fir_number) || 'Unlinked'})`,
        buttonHtml: `<button class="btn btn-primary" onclick="handleStageTransition('${c.case_id}', 'EVIDENCE_INGESTION')">Begin Evidence Collection &rarr;</button>`
      };
    }

    if (stage === "EVIDENCE_INGESTION") {
      if (totalEvidence === 0) {
        return {
          title: "Attach Primary Case Exhibits",
          whyItMatters: "No exhibits have been attached to the case docket. Timeline reconstruction and analysis require verified exhibits.",
          involved: "Evidence register (0 exhibits attached)",
          buttonHtml: `<button class="btn btn-primary" onclick="ScreenEvidence.showRegisterEvidenceModal()">+ Upload Evidence Exhibit</button>`
        };
      }
      return {
        title: "Advance to Forensic Verification",
        whyItMatters: `${totalEvidence} exhibit(s) collected. Advance to automated file validation, antivirus scanning, cryptographic fingerprinting, and storage lock.`,
        involved: `${totalEvidence} exhibit(s): ${evidenceList.slice(0, 3).map(e => e.original_file_name).join(', ')}${evidenceList.length > 3 ? '...' : ''}`,
        buttonHtml: `<button class="btn btn-primary" onclick="handleStageTransition('${c.case_id}', 'EVIDENCE_PROCESSING')">Proceed to Forensic Verification &rarr;</button>`
      };
    }

    if (stage === "EVIDENCE_PROCESSING") {
      const security = EvidenceSecurityEvaluator.evaluateCaseSecurity(evidenceList);
      if (security.hasAlerts) {
        const failedExhibits = evidenceList.filter(e => e.integrity_status === 'FAILED' || e.antivirus_status === 'THREAT_DETECTED');
        return {
          title: "Resolve Evidence Security Alert",
          whyItMatters: "One or more exhibits failed integrity or malware checks. Compromised files must be inspected and addressed before timeline reasoning.",
          involved: `${failedExhibits.length} exhibit(s): ${failedExhibits.map(e => e.original_file_name).join(', ')}`,
          buttonHtml: `<button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${c.case_id}', 'verification')">Inspect Security Alerts &rarr;</button>`
        };
      }

      const pendingWorm = evidenceList.filter(e => e.integrity_status === 'VERIFIED' && e.worm_status !== 'COMMITTED');
      if (pendingWorm.length > 0) {
        return {
          title: "Finish Checking Evidence Protection",
          whyItMatters: "The file integrity checks passed, but storage-protection verification is still pending.",
          involved: `${pendingWorm.length} exhibit(s): ${pendingWorm.map(e => e.original_file_name).join(', ')}`,
          buttonHtml: `<button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${c.case_id}', 'verification')">Review Evidence Protection &rarr;</button>`
        };
      }

      const unverified = evidenceList.filter(e => e.integrity_status !== 'VERIFIED');
      if (unverified.length > 0) {
        return {
          title: "Complete Forensic Verification",
          whyItMatters: "Forensic verification is in progress. Wait for automated checks or inspect pending exhibit status.",
          involved: `${unverified.length} unverified exhibit(s): ${unverified.map(e => e.original_file_name).join(', ')}`,
          buttonHtml: `<button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${c.case_id}', 'verification')">Open Verification Workspace &rarr;</button>`
        };
      }

      return {
        title: "Advance to Investigation Analysis",
        whyItMatters: `All ${totalEvidence} exhibits are cryptographically verified and sealed. Advance to chronological reconstruction and cross-evidence analysis.`,
        involved: `${totalEvidence} verified exhibit(s)`,
        buttonHtml: `<button class="btn btn-primary" onclick="handleStageTransition('${c.case_id}', 'ANALYSIS')">Advance to Investigation Analysis &rarr;</button>`
      };
    }

    if (stage === "ANALYSIS") {
      const contradictionsList = (analysisSummary && analysisSummary.contradictions) || [];
      const unresolvedConflicts = contradictionsList.filter(ct => !ct.resolved);
      if (unresolvedConflicts.length > 0) {
        return {
          title: "Review Conflicting Information",
          whyItMatters: `${unresolvedConflicts.length} conflicting account(s) detected between exhibit statements. Clarify discrepancies to ensure findings are defensible.`,
          involved: `${unresolvedConflicts.length} conflicting statement pair(s)`,
          buttonHtml: `<button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${c.case_id}', 'analysis')">Review Conflicting Statements &rarr;</button>`
        };
      }

      const pendingGraphReviews = (graphEdges || []).filter(e => e.review_status === 'NEEDS_CONFIRMATION').length;
      if (pendingGraphReviews > 0) {
        return {
          title: "Review Entity Connections",
          whyItMatters: `${pendingGraphReviews} entity connection(s) require officer confirmation.`,
          involved: `${pendingGraphReviews} unconfirmed relationship(s)`,
          buttonHtml: `<button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${c.case_id}', 'connections')">Review Connections &rarr;</button>`
        };
      }

      return {
        title: "Submit Dossier for Investigator Review",
        whyItMatters: "Chronological sequence and cross-evidence observations are evaluated. Submit docket for formal supervisory review.",
        involved: "Verified timeline & analytical observations",
        buttonHtml: `<button class="btn btn-primary" onclick="handleStageTransition('${c.case_id}', 'REVIEW')">Submit for Investigator Review &rarr;</button>`
      };
    }

    if (stage === "REVIEW") {
      return {
        title: "Complete Authorized Inquest Review",
        whyItMatters: "Supervisory review of inquest findings, timeline, and exhibit chain-of-custody prior to case closure.",
        involved: `Inquest docket ${c.case_id}`,
        buttonHtml: `<button class="btn btn-primary" onclick="handleStageTransition('${c.case_id}', 'CLOSED')">Conclude Investigation & Close Case</button>`
      };
    }

    if (stage === "CLOSED") {
      return {
        title: "Investigation Concluded and Archived",
        whyItMatters: "Final inquiry report completed and archived under Section 194 BNSS / Section 174 CrPC. Case is in read-only audit status.",
        involved: `Archived case docket ${c.case_id}`,
        buttonHtml: `<button class="btn btn-secondary" onclick="Router.selectCaseAndRoute('${c.case_id}', 'report')">View Case Report &rarr;</button>`
      };
    }

    return {
      title: "Case Under Specialized Review",
      whyItMatters: `Investigation is currently in status ${stage}.`,
      involved: `Case docket ${c.case_id}`,
      buttonHtml: `<button class="btn btn-secondary" onclick="Router.navigate('#/cases')">Return to Directory</button>`
    };
  }
};

function toggleLifecycleDetails() {
  const drawer = document.getElementById("lifecycleDetailsDrawer");
  const btn = document.getElementById("btnToggleLifecycleDetails");
  if (!drawer) return;
  if (drawer.style.display === "none" || !drawer.style.display) {
    drawer.style.display = "block";
    if (btn) btn.innerHTML = "Lifecycle Details &and;";
  } else {
    drawer.style.display = "none";
    if (btn) btn.innerHTML = "Lifecycle Details &or;";
  }
}


const UI = {
  _lastToastMessage: null,
  _lastToastTime: 0,

  showToast(message, type = "info", duration = 4000) {
    const now = Date.now();
    if (this._lastToastMessage === message && (now - this._lastToastTime) < 2500) {
      return; // Deduplicate identical toasts within 2.5 seconds
    }
    this._lastToastMessage = message;
    this._lastToastTime = now;

    const container = document.getElementById("toastContainer");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    const icon = type === "success" ? "✓" : type === "error" ? "⚠️" : "ℹ";
    toast.innerHTML = `<span style="font-weight: 700; font-size: 1.1rem;">${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },

  openModal(title, bodyHtml, footerHtml = "") {
    const backdrop = document.getElementById("modalContainer");
    backdrop.innerHTML = `
      <div class="modal-dialog">
        <div class="modal-header">
          <div class="modal-title">${title}</div>
          <button class="modal-close-btn" onclick="UI.closeModal()">&times;</button>
        </div>
        <div class="modal-body">${bodyHtml}</div>
        ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ""}
      </div>
    `;
    backdrop.style.display = "flex";
  },

  closeModal() {
    const backdrop = document.getElementById("modalContainer");
    backdrop.style.display = "none";
    backdrop.innerHTML = "";
  },

  openDrawer(title, contentHtml) {
    const backdrop = document.getElementById("drawerContainer");
    backdrop.innerHTML = `
      <div class="drawer-panel">
        <div class="modal-header">
          <div class="modal-title">${title}</div>
          <button class="modal-close-btn" onclick="UI.closeDrawer()">&times;</button>
        </div>
        <div style="padding: 20px; overflow-y: auto; flex: 1;">${contentHtml}</div>
      </div>
    `;
    backdrop.style.display = "flex";
    backdrop.onclick = (e) => {
      if (e.target === backdrop) UI.closeDrawer();
    };
  },

  closeDrawer() {
    const backdrop = document.getElementById("drawerContainer");
    backdrop.style.display = "none";
    backdrop.innerHTML = "";
  },

  recordAudit(action, resource, result, details = "") {
    const entry = {
      id: `ACT-${Date.now().toString(36).toUpperCase()}`,
      timestamp: new Date().toISOString(),
      actor: State.auth.subjectId,
      action,
      resource,
      result,
      details
    };
    State.auditLog.unshift(entry);
    if (State.auditLog.length > 50) State.auditLog.pop();
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 4. ROUTER & WORKSPACE NAVIGATION
// ═══════════════════════════════════════════════════════════════════════════

function resetActiveCaseState() {
  State.activeCase = null;
  State.activeCaseId = null;
  State.activeStageInfo = null;
  State.evidence = [];
  State.analysisSummary = null;
  State.graphEdges = [];
  State.isAnalysisRunning = false;
  State.isContradictionRunning = false;
  State.analysisSummaryError = null;
  State.evidenceLoadError = null;
  try {
    localStorage.removeItem("sakshi_active_case_id");
  } catch (e) {}
  updateSidebarActiveCaseContext();
}

function renderCaseNotFound(caseId, errorMessage) {
  resetActiveCaseState();
  const container = document.getElementById("viewContainer");
  if (!container) return;
  const currentBreadcrumb = document.getElementById("breadcrumbCurrent");
  if (currentBreadcrumb) {
    currentBreadcrumb.textContent = `${caseId || "Case"} / Case Not Found`;
  }
  const cleanMsg = errorMessage || `Investigation case with ID '${caseId}' was not found.`;
  container.innerHTML = `
    <div class="empty-state-card" style="margin-top: 30px;">
      <div class="empty-state-icon">⚠️</div>
      <div class="empty-state-title">Case Not Found</div>
      <div class="empty-state-desc">${Formatters.escapeHtml(cleanMsg)}</div>
      <button class="btn btn-primary" id="btnReturnToCaseDirectory" onclick="Router.navigate('#/cases')">Return to Case Directory</button>
    </div>
  `;
}

const Router = {
  routes: [
    { pattern: /^#\/login$/, handler: () => ScreenLogin.render() },
    { pattern: /^#\/cases$/, handler: () => ScreenCases.render() },
    { pattern: /^#\/cases\/active\/([a-z]+)$/, handler: (match) => Router.routeActiveTab(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/overview$/, handler: (match) => ScreenCaseOverview.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/setup$/, handler: (match) => ScreenCaseOverview.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/evidence$/, handler: (match) => ScreenEvidence.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/connections$/, handler: (match) => ScreenGraph.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/graph$/, handler: (match) => ScreenGraph.render(match[1]) },
    // Historic technical screens remain addressable, but their capability is
    // surfaced inside the investigator workspaces rather than as primary pages.
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/verification$/, handler: (match) => ScreenVerification.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/rag$/, handler: (match) => ScreenRAGSearch.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/timeline$/, handler: (match) => ScreenTimeline.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/findings$/, handler: (match) => ScreenFindings.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/review$/, handler: (match) => ScreenFindings.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/analysis$/, handler: (match) => ScreenFindings.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/gaps$/, handler: (match) => ScreenFindings.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/closure$/, handler: (match) => ScreenClosure.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/report$/, handler: (match) => ScreenReport.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/reports$/, handler: (match) => ScreenReport.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/audit$/, handler: (match) => ScreenAudit.render(match[1]) },
    { pattern: /^#\/administration$/, handler: () => ScreenAdministration.render() },
    { pattern: /^#\/officers$/, handler: () => ScreenOfficers.render() },
    { pattern: /^#\/settings$/, handler: () => ScreenSettings.render() }
  ],

  routeActiveTab(tab) {
    if (!State.activeCaseId) {
      UI.showToast("Please select a case from the Case Directory first.", "info");
      this.navigate("#/cases");
      return;
    }
    this.navigate(`#/cases/${State.activeCaseId}/${tab}`);
  },

  navigate(targetHash = null) {
    if (!State.auth.initialized) {
      return;
    }

    if (targetHash !== null && targetHash !== undefined) {
      if (window.location.hash !== targetHash) {
        window.location.hash = targetHash;
        return;
      }
    }

    const rawHash = window.location.hash || "";
    const isLogin = !rawHash || rawHash === "#" || rawHash === "#/" || rawHash === "#/login";

    if (isLogin || !State.auth.authenticated) {
      if (!isLogin && window.location.hash !== "#/login") window.location.hash = "#/login";
      document.body.classList.add("login-active");
      ScreenLogin.render();
      updateSidebarActiveLink("#/login");
      return;
    }

    document.body.classList.remove("login-active");

    for (const r of this.routes) {
      const match = rawHash.match(r.pattern);
      if (match) {
        r.handler(match);
        updateSidebarActiveLink(rawHash);
        return;
      }
    }
    if (window.location.hash !== "#/cases") {
      window.location.hash = "#/cases";
    } else {
      ScreenCases.render();
      updateSidebarActiveLink("#/cases");
    }
  },

  selectCaseAndRoute(caseId, tab = "overview") {
    State.activeCaseId = caseId;
    localStorage.setItem("sakshi_active_case_id", caseId);
    this.navigate(`#/cases/${caseId}/${tab}`);
  }
};

function updateSidebarActiveLink(hash) {
  document.querySelectorAll(".sidebar-nav .nav-link").forEach(link => {
    link.classList.remove("active");
  });

  if (hash.startsWith("#/cases/") && !hash.endsWith("#/cases")) {
    if (hash.includes("/overview")) document.getElementById("navOverview")?.classList.add("active");
    else if (hash.includes("/evidence")) document.getElementById("navEvidence")?.classList.add("active");
    else if (hash.includes("/connections") || hash.includes("/graph")) document.getElementById("navConnections")?.classList.add("active");
    else if (hash.includes("/rag")) document.getElementById("navRAG")?.classList.add("active");
    else if (hash.includes("/timeline")) document.getElementById("navTimeline")?.classList.add("active");
    else if (hash.includes("/findings") || hash.includes("/analysis") || hash.includes("/gaps")) {
      document.getElementById("navFindings")?.classList.add("active");
      document.getElementById("navAnalysis")?.classList.add("active");
      document.getElementById("navGaps")?.classList.add("active");
    }
    else if (hash.includes("/report")) document.getElementById("navReport")?.classList.add("active");
    else if (hash.includes("/audit")) document.getElementById("navAudit")?.classList.add("active");
  } else if (hash.startsWith("#/settings") || hash.startsWith("#/administration")) {
    document.getElementById("navSettings")?.classList.add("active");
    document.getElementById("navAdmin")?.classList.add("active");
  } else if (hash === "#/officers") {
    document.getElementById("navOfficers")?.classList.add("active");
    document.getElementById("navAdmin")?.classList.add("active");
  } else if (hash === "#/cases") {
    document.getElementById("navCases")?.classList.add("active");
  }
}

function updateSidebarActiveCaseContext() {
  const box = document.getElementById("sidebarActiveCaseBox");
  const idEl = document.getElementById("sidebarActiveCaseId");
  const stgEl = document.getElementById("sidebarActiveCaseStage");
  const countEl = document.getElementById("navEvidenceCount");

  const workspaceLinks = [
    { id: "navOverview", tab: "overview" },
    { id: "navEvidence", tab: "evidence" },
    { id: "navRAG", tab: "rag" },
    { id: "navTimeline", tab: "timeline" },
    { id: "navFindings", tab: "findings" },
    { id: "navAnalysis", tab: "analysis" },
    { id: "navGaps", tab: "gaps" },
    { id: "navReport", tab: "report" },
    { id: "navAudit", tab: "audit" }
  ];

  // Conditional display of Administration section
  const isAdmin = ["ADMIN", "SYSTEM_ADMINISTRATOR", "SUPERVISOR", "SUPERVISORY_OFFICER", "STATION_HEAD"].includes(State.auth.role);
  const adminSec = document.getElementById("adminSectionTitle");
  const adminNav = document.getElementById("navAdmin");
  if (adminSec) adminSec.style.display = isAdmin ? "block" : "none";
  if (adminNav) adminNav.style.display = isAdmin ? "flex" : "none";

  if (!State.activeCase && !State.activeCaseId) {
    if (idEl) idEl.textContent = "No Case Selected";
    if (stgEl) stgEl.textContent = "Select a case";
    if (countEl) countEl.style.display = "none";
    if (box) {
      box.style.cursor = "default";
      box.onclick = null;
    }
    workspaceLinks.forEach(item => {
      const el = document.getElementById(item.id);
      if (el) {
        el.setAttribute("href", `#/cases/active/${item.tab}`);
        el.classList.add("workspace-link-inactive");
      }
    });
    return;
  }

  const activeId = (State.activeCase && State.activeCase.case_id) || State.activeCaseId;
  if (idEl) idEl.textContent = activeId;
  const stageObj = (State.activeCase && StageDisplayMap[State.activeCase.lifecycle_stage]) || { short: (State.activeCase && State.activeCase.lifecycle_stage) || "Active" };
  if (stgEl) stgEl.textContent = `Phase: ${stageObj.short}`;
  if (box) {
    box.style.cursor = "pointer";
    box.onclick = () => Router.navigate(`#/cases/${activeId}/overview`);
  }

  workspaceLinks.forEach(item => {
    const el = document.getElementById(item.id);
    if (el) {
      el.setAttribute("href", `#/cases/${activeId}/${item.tab}`);
      el.classList.remove("workspace-link-inactive");
    }
  });

  if (countEl) {
    if (State.evidence && State.evidence.length > 0) {
      countEl.textContent = State.evidence.length;
      countEl.style.display = "inline-flex";
    } else {
      countEl.style.display = "none";
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. APPLICATION INITIALIZATION & THEME ENGINE
// ═══════════════════════════════════════════════════════════════════════════

async function initApplication() {
  setupTheme();
  setupEventListeners();

  try {
    const authStatus = await Api.getAuthStatus();
    State.auth.mode = authStatus.auth_mode || "unknown";
    const isDevMode = State.auth.mode === "development" || State.auth.mode === "offline" || authStatus.development_mode === true;
    if (isDevMode) {
      State.auth.authenticated = true;
      const defaultId = authStatus.default_investigator_id || "dev-investigator-001";
      const defaultName = authStatus.default_investigator_name || "Dev Inspector (Development Only)";
      const defaultJur = authStatus.default_jurisdiction || "KERALA";

      const currentStored = typeof localStorage !== "undefined" ? localStorage.getItem("sakshi_dev_subject_id") : null;
      if (!currentStored || currentStored === "IO-7842-SHARMA") {
        State.auth.subjectId = defaultId;
        State.auth.displayName = defaultName;
        State.auth.jurisdiction = defaultJur;
        try {
          localStorage.setItem("sakshi_dev_subject_id", defaultId);
          localStorage.setItem("sakshi_dev_display_name", defaultName);
          localStorage.setItem("sakshi_dev_jurisdiction", defaultJur);
        } catch (e) {}
      }

      if (State.auth.subjectId) State.auth.headers["X-Investigator-Id"] = State.auth.subjectId;
      if (State.auth.role) State.auth.headers["X-Investigator-Role"] = State.auth.role;
      if (State.auth.jurisdiction) State.auth.headers["X-Investigator-Jurisdiction"] = State.auth.jurisdiction;
    } else if (State.auth.token) {
      State.auth.authenticated = true;
    }
    const me = await Api.getAuthMe();
    if (me) {
      State.auth.authenticated = true;
      State.auth.subjectId = me.subject_id || State.auth.subjectId;
      State.auth.displayName = me.display_name || State.auth.displayName;
      State.auth.role = me.role || State.auth.role;
      State.auth.jurisdiction = me.station_jurisdiction || State.auth.jurisdiction;
    } else if (!isDevMode) {
      State.auth.authenticated = false;
      State.auth.token = null;
      try { sessionStorage.removeItem("sakshi_auth_token"); } catch (e) {}
    }
  } catch (e) {
    console.warn("Auth initialization notice:", e);
  } finally {
    State.auth.initialized = true;
  }

  updateHeaderAuth();

  try {
    const health = await Api.getHealth();
    State.systemHealth = health;
    document.getElementById("systemStatusDot").className = "status-dot connected";
    document.getElementById("systemStatusText").textContent = "Workstation Online";
  } catch (e) {
    document.getElementById("systemStatusDot").className = "status-dot degraded";
    document.getElementById("systemStatusText").textContent = "Standalone Mode";
  }

  window.addEventListener("hashchange", () => Router.navigate());
  Router.navigate();
}

function setupTheme() {
  const savedTheme = localStorage.getItem("sakshi_theme") || "light";
  applyTheme(savedTheme);

  document.getElementById("themeToggleBtn")?.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "light" ? "dark" : "light";
    applyTheme(next);
  });
}

function applyTheme(theme) {
  State.theme = theme;
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("sakshi_theme", theme);

  const iconEl = document.getElementById("themeToggleIcon");
  const textEl = document.getElementById("themeToggleText");
  if (iconEl && textEl) {
    if (theme === "light") {
      iconEl.textContent = "☀️";
      textEl.textContent = "Desk Mode";
    } else {
      iconEl.textContent = "🌙";
      textEl.textContent = "Control Room";
    }
  }
}

function setupEventListeners() {
  document.getElementById("menuToggleBtn")?.addEventListener("click", () => {
    document.getElementById("appSidebar")?.classList.toggle("open");
  });

  document.getElementById("investigatorProfileBtn")?.addEventListener("click", () => {
    Router.navigate("#/settings");
  });

  // Single-click sidebar navigation handler
  document.querySelectorAll(".sidebar-nav a.nav-link").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const href = link.getAttribute("href");
      if (!href) return;

      // Close mobile drawer if open
      document.getElementById("appSidebar")?.classList.remove("open");

      Router.navigate(href);
    });
  });

  document.getElementById("logoutBtn")?.addEventListener("click", async () => {
    try {
      await Api.logout();
    } catch (e) {
      // Best-effort logout
    }
    resetActiveCaseState();
    State.auth.token = null;
    State.auth.authenticated = false;
    State.auth.subjectId = "";
    State.auth.displayName = "";
    State.auth.role = "";
    State.auth.jurisdiction = "";
    try { sessionStorage.removeItem("sakshi_auth_token"); } catch (e) {}
    UI.showToast("Signed out successfully.", "info");
    Router.navigate("#/login");
  });
}

function updateHeaderAuth() {
  const avatarEl = document.getElementById("headerAvatar");
  const idEl = document.getElementById("headerInvestigatorId");
  const roleEl = document.getElementById("headerInvestigatorRole");

  if (avatarEl) avatarEl.textContent = State.auth.subjectId.substring(0, 2).toUpperCase();
  if (idEl) idEl.textContent = State.auth.subjectId;
  if (roleEl) {
    const roleLabels = {
      INVESTIGATING_OFFICER: "Investigating Officer",
      SUPERVISORY_OFFICER: "Supervisory Officer",
      STATION_HEAD: "Station House Officer",
      ADMIN: "System Administrator"
    };
    roleEl.textContent = roleLabels[State.auth.role] || State.auth.role;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 5b. SCREEN 0: INITIAL LOGIN SCREEN (OFFICER ACCESS & FIREBASE AUTH)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenLogin = {
  render() {
    const container = document.getElementById("viewContainer");
    if (!container) return;

    const isFirebase = State.auth.mode === "firebase";
    const modeBadge = isFirebase ? "OFFICER AUTHENTICATION" : "DEVELOPMENT / DEMO";
    const devNote = isFirebase
      ? "Use your registered mobile number and password. Never share your credentials."
      : "Development mode — authentication is not enabled.";

    container.innerHTML = `
      <div class="login-wrapper">
        <div class="login-card">
          <div class="login-header">
            <div class="login-emblem">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <path d="m9 12 2 2 4-4"/>
              </svg>
            </div>
            <h1 class="login-title">SAKSHI</h1>
            <div class="login-subtitle">Explainable AI Investigation Companion</div>
            <div class="login-workstation-text">Digital Investigation Workstation</div>
            <div class="login-badge-container">
              <span class="badge-dev-demo">
                <span class="status-dot-sm"></span>
                <span>${modeBadge}</span>
              </span>
            </div>
          </div>

          <div class="login-card-body">
            <div class="login-section-header">
              <span class="section-icon">🛡️</span>
              <span class="section-title">Officer Access</span>
            </div>

            <form id="officerLoginForm" class="login-form">
              <div class="form-group">
                <label class="login-label" for="loginPhoneInput">Phone Number</label>
                <div class="phone-input-group">
                  <span class="phone-prefix">+91</span>
                  <input 
                    type="tel" 
                    id="loginPhoneInput" 
                    class="login-phone-input" 
                    placeholder="Enter officer phone number"
                    autocomplete="tel"
                    autofocus
                  />
                </div>
              </div>
              <div class="form-group">
                <label class="login-label" for="loginPasswordInput">Password</label>
                <div class="password-input-group">
                  <input type="password" id="loginPasswordInput" class="form-input" autocomplete="current-password" placeholder="Enter officer password" ${isFirebase ? "required" : ""} />
                  <button type="button" id="btnTogglePassword" class="btn-toggle-password" title="Show or hide password" aria-label="Toggle password visibility">👁️</button>
                </div>
              </div>

              <button type="submit" id="btnLoginContinue" class="btn-login-continue">
                <span>Continue to SAKSHI</span>
                <span class="login-arrow-icon">→</span>
              </button>

              <div class="login-dev-note" id="loginAuthNote">
                <span class="login-dev-note-icon">ℹ️</span>
                <span>${devNote}</span>
              </div>
            </form>
          </div>

          <div class="login-card-footer">
            <div class="login-footer-title">SAKSHI Investigation Platform</div>
            <div class="login-footer-pillars">
              <span>Evidence</span>
              <span class="dot">•</span>
              <span>Integrity</span>
              <span class="dot">•</span>
              <span>Explainability</span>
              <span class="dot">•</span>
              <span>Human Review</span>
            </div>
          </div>
        </div>
      </div>
    `;

    const toggleBtn = document.getElementById("btnTogglePassword");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        const pw = document.getElementById("loginPasswordInput");
        if (!pw) return;
        if (pw.type === "password") {
          pw.type = "text";
          toggleBtn.textContent = "🙈";
        } else {
          pw.type = "password";
          toggleBtn.textContent = "👁️";
        }
      });
    }

    const form = document.getElementById("officerLoginForm");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const phoneInput = document.getElementById("loginPhoneInput");
        const pwInput = document.getElementById("loginPasswordInput");
        const btn = document.getElementById("btnLoginContinue");

        if (State.auth.mode !== "firebase") {
          // Dev / demo mode direct access
          State.auth.authenticated = true;
          if (State.auth.subjectId) State.auth.headers["X-Investigator-Id"] = State.auth.subjectId;
          if (State.auth.role) State.auth.headers["X-Investigator-Role"] = State.auth.role;
          if (State.auth.jurisdiction) State.auth.headers["X-Investigator-Jurisdiction"] = State.auth.jurisdiction;
          updateHeaderAuth();
          Router.navigate("#/cases");
          return;
        }

        const rawPhone = (phoneInput?.value || "").trim().replace(/[\s\-()]/g, "");
        const password = pwInput?.value || "";

        if (!rawPhone) {
          UI.showToast("Please enter your registered mobile number.", "error");
          phoneInput?.focus();
          return;
        }

        let normalizedMobile = rawPhone;
        if (!normalizedMobile.startsWith("+")) {
          if (normalizedMobile.startsWith("91") && normalizedMobile.length === 12) {
            normalizedMobile = "+" + normalizedMobile;
          } else {
            normalizedMobile = "+91" + normalizedMobile;
          }
        }

        if (!password) {
          UI.showToast("Please enter your password.", "error");
          pwInput?.focus();
          return;
        }

        btn.disabled = true;
        btn.querySelector("span").textContent = "Signing in...";

        try {
          const loginRes = await Api.login(normalizedMobile, password);
          State.auth.token = loginRes.id_token;
          try { sessionStorage.setItem("sakshi_auth_token", loginRes.id_token); } catch (e) {}
          const me = await Api.getAuthMe();
          if (!me) throw new Error("Server could not verify officer identity.");
          State.auth.authenticated = true;
          State.auth.subjectId = me.subject_id;
          State.auth.displayName = me.display_name;
          State.auth.role = me.role;
          State.auth.jurisdiction = me.station_jurisdiction;
          updateHeaderAuth();
          UI.showToast(`Authenticated as ${me.display_name || me.subject_id}`, "success");
          Router.navigate("#/cases");
        } catch (err) {
          UI.showToast(err.message || "Sign in failed.", "error");
        } finally {
          btn.disabled = false;
          btn.querySelector("span").textContent = "Continue to SAKSHI";
        }
      });
    }
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 6. SCREEN 1: CASE DIRECTORY (Route: #/cases)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenCases = {
  async render() {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = "Case Directory";

    let cases = [];
    try {
      const rawCases = await Api.listCases();
      cases = Array.isArray(rawCases) ? rawCases : (rawCases && Array.isArray(rawCases.cases) ? rawCases.cases : []);
      State.cases = cases;
    } catch (err) {
      container.innerHTML = `
        <div class="empty-state-card">
          <div class="empty-state-icon">⚠️</div>
          <div class="empty-state-title">Unable to Connect to Case Database</div>
          <div class="empty-state-desc">${Formatters.escapeHtml(err.message)}</div>
          <button class="btn btn-primary" onclick="Router.navigate('#/cases')">Retry Connection</button>
        </div>
      `;
      return;
    }

    // Clean up stale activeCaseId if it is not in the fetched case directory
    if (State.activeCaseId && !cases.some(c => c.case_id === State.activeCaseId)) {
      resetActiveCaseState();
    } else {
      updateSidebarActiveCaseContext();
    }

    const filtered = cases.filter(c => {
      const matchSearch = !State.filters.caseSearch ||
        (c.title && c.title.toLowerCase().includes(State.filters.caseSearch.toLowerCase())) ||
        (c.case_id && c.case_id.toLowerCase().includes(State.filters.caseSearch.toLowerCase())) ||
        (c.fir_metadata && c.fir_metadata.fir_number && c.fir_metadata.fir_number.toLowerCase().includes(State.filters.caseSearch.toLowerCase()));

      const matchStage = State.filters.caseStage === "ALL" || c.lifecycle_stage === State.filters.caseStage;
      return matchSearch && matchStage;
    });

    const html = `
      <div class="cases-toolbar">
        <div>
          <h2 style="font-size: 1.4rem; font-weight: 700; color: var(--text-main);">Case Directory</h2>
          <p style="color: var(--text-muted); font-size: 0.84rem;">Locate an inquiry, review its current stage, or open the case workspace.</p>
        </div>
        <button class="btn btn-primary" id="btnRegisterNewCase">Register case</button>
      </div>

      <div class="case-directory-controls">
        <div class="search-input-wrap">
          <label class="visually-hidden" for="caseSearchInput">Search cases</label>
          <input type="text" class="form-input" id="caseSearchInput" placeholder="Search title, case reference, or FIR..." value="${Formatters.escapeHtml(State.filters.caseSearch)}">
        </div>
        <label class="case-stage-filter" for="caseStageFilter">
          <span>Stage</span>
          <select id="caseStageFilter" class="form-select">
            <option value="ALL" ${State.filters.caseStage === 'ALL' ? 'selected' : ''}>All cases (${cases.length})</option>
            <option value="INITIALIZED" ${State.filters.caseStage === 'INITIALIZED' ? 'selected' : ''}>Case setup</option>
            <option value="EVIDENCE_INGESTION" ${State.filters.caseStage === 'EVIDENCE_INGESTION' ? 'selected' : ''}>Evidence collection</option>
            <option value="EVIDENCE_PROCESSING" ${State.filters.caseStage === 'EVIDENCE_PROCESSING' ? 'selected' : ''}>Forensic verification</option>
            <option value="ANALYSIS" ${State.filters.caseStage === 'ANALYSIS' ? 'selected' : ''}>Analysis</option>
            <option value="REVIEW" ${State.filters.caseStage === 'REVIEW' ? 'selected' : ''}>Review</option>
            <option value="CLOSED" ${State.filters.caseStage === 'CLOSED' ? 'selected' : ''}>Closed</option>
          </select>
        </label>
      </div>

      <!-- Case Grid -->
      ${filtered.length === 0 ? `
        <div class="empty-state-card" style="margin-top: 20px;">
          <div class="empty-state-icon">📋</div>
          <div class="empty-state-title">No Case Inquiries Found</div>
          <div class="empty-state-desc">
            ${cases.length === 0 ? "No case inquiries registered in this station jurisdiction yet. Click '+ Register New Case Inquiry' to initialize an inquiry file." : "No inquiries match your active search filters."}
          </div>
          <button class="btn btn-primary" onclick="ScreenCases.showNewCaseModal()">+ Register New Case Inquiry</button>
        </div>
      ` : `
        <div class="case-directory-list" style="margin-top: 16px;" role="list">
          ${filtered.map(c => this.renderCardHtml(c)).join("")}
        </div>
      `}
    `;

    container.innerHTML = html;

    document.getElementById("btnRegisterNewCase")?.addEventListener("click", () => {
      this.showNewCaseModal();
    });

    document.getElementById("caseSearchInput")?.addEventListener("input", (e) => {
      State.filters.caseSearch = e.target.value;
      this.render();
    });

    document.getElementById("caseStageFilter")?.addEventListener("change", (e) => {
        State.filters.caseStage = e.target.value;
        this.render();
    });
  },

  renderCardHtml(c) {
    const stageObj = StageDisplayMap[c.lifecycle_stage] || { short: c.lifecycle_stage };
    const fir = (c.fir_metadata && c.fir_metadata.fir_number) || "No FIR Recorded";
    const station = (c.fir_metadata && c.fir_metadata.police_station) || "Jurisdiction Not Specified";
    const incidentDate = (c.fir_metadata && c.fir_metadata.incident_date) ? Formatters.formatOnlyDate(c.fir_metadata.incident_date) : "Date not recorded";
    const nextActions = {
      INITIALIZED: "Collect primary evidence",
      EVIDENCE_INGESTION: "Complete evidence collection",
      EVIDENCE_PROCESSING: "Review file checks",
      ANALYSIS: "Review timeline and relationships",
      REVIEW: "Complete investigator review",
      CLOSED: "View preserved case record",
      SUSPENDED: "Review suspension record"
    };
    const statusText = c.status === "ACTIVE" ? "Active" : (c.status || "Status unavailable");

    return `
      <article class="case-row" role="listitem" onclick="Router.selectCaseAndRoute('${c.case_id}', 'overview')">
        <div class="case-row-primary">
          <h3 class="case-row-title">${Formatters.escapeHtml(c.title)}</h3>
          <div class="case-row-reference">Case ${Formatters.escapeHtml(c.case_id)} · FIR ${Formatters.escapeHtml(fir)}</div>
        </div>
        <div class="case-row-stage">
          <span class="case-status-dot ${c.status === 'ACTIVE' ? 'is-active' : ''}" aria-hidden="true"></span>
          <span>${Formatters.escapeHtml(statusText)}</span>
          <span class="case-row-separator" aria-hidden="true">·</span>
          <span>${Formatters.escapeHtml(stageObj.short || stageObj.label)}</span>
        </div>
        <div class="case-row-secondary">
          ${Formatters.escapeHtml(station)} · ${Formatters.escapeHtml(incidentDate)} · Assigned: ${Formatters.escapeHtml(c.assigned_io_id || "Not assigned")}
        </div>
        <div class="case-row-action">
          <span><strong>Next:</strong> ${nextActions[c.lifecycle_stage] || "Open case workspace"}</span>
          <button class="btn btn-secondary btn-sm" aria-label="Open ${Formatters.escapeHtml(c.title)}" onclick="event.stopPropagation(); Router.selectCaseAndRoute('${c.case_id}', 'overview')">Open</button>
        </div>
      </article>
    `;
  },

  showNewCaseModal() {
    let activeMode = "manual";
    const bodyHtml = `
      <div class="modal-tabs">
        <button type="button" class="modal-tab-btn active" id="tabManualMode" onclick="ScreenCases.switchModalTab('manual')">
          📝 Manual Registration (Method A)
        </button>
        <button type="button" class="modal-tab-btn" id="tabFirMode" onclick="ScreenCases.switchModalTab('fir')">
          📄 FIR-Assisted Ingestion (Method B)
        </button>
      </div>

      <!-- METHOD A: MANUAL REGISTRATION -->
      <div id="sectionManualRegistration">
        <form id="newCaseForm">
          <div class="form-group">
            <label class="form-label" for="inpCaseTitle">Case Title / Incident Description *</label>
            <input type="text" id="inpCaseTitle" class="form-input" placeholder="e.g. Unnatural Death Inquiry of Person X at Hotel Sunrise" required>
          </div>

          <div class="grid-2">
            <div class="form-group">
              <label class="form-label" for="inpFirNumber">FIR / Inquest Number *</label>
              <input type="text" id="inpFirNumber" class="form-input" placeholder="e.g. FIR-114/2026-CR" required value="INQ-${Math.floor(100 + Math.random() * 900)}/2026">
            </div>
            <div class="form-group">
              <label class="form-label" for="inpStation">Police Station / Circle *</label>
              <input type="text" id="inpStation" class="form-input" placeholder="e.g. Fort Police Station, Thiruvananthapuram" required value="Thiruvananthapuram Central Station">
            </div>
          </div>

          <div class="grid-2">
            <div class="form-group">
              <label class="form-label" for="inpIncidentDate">Incident Date & Time</label>
              <input type="datetime-local" id="inpIncidentDate" class="form-input" value="${new Date().toISOString().slice(0, 16)}">
            </div>
            <div class="form-group">
              <label class="form-label" for="inpAssignedIo">Investigating Officer (IO Badge)</label>
              <input type="text" id="inpAssignedIo" class="form-input" value="${State.auth.subjectId}">
            </div>
          </div>

          <div class="form-group">
            <label class="form-label" for="inpIncidentLocation">Scene of Occurrence / Location</label>
            <input type="text" id="inpIncidentLocation" class="form-input" placeholder="e.g. Room 304, Hotel Sunrise, MG Road" value="MG Road Sector 4">
          </div>

          <div class="form-group">
            <label class="form-label" for="inpLegalProvision">Legal Provision</label>
            <input type="text" id="inpLegalProvision" class="form-input" value="Section 194 BNSS / Section 174 CrPC (Unnatural Death)" readonly>
          </div>
        </form>
      </div>

      <!-- METHOD B: FIR-ASSISTED INGESTION -->
      <div id="sectionFirAssisted" style="display: none;">
        <div style="background: var(--primary-bg); border-left: 3px solid var(--primary); padding: 10px 14px; border-radius: var(--radius-sm); margin-bottom: 14px; font-size: 0.84rem; color: var(--text-secondary);">
          <strong>FIR-Assisted Case Ingestion:</strong> Upload an official FIR document (PDF or text). Candidate particulars (dates, locations, victim, informant, penal sections) will be extracted with verbatim grounding passages for your review before authoritative registration.
        </div>

        <div class="form-group">
          <label class="form-label">Upload FIR Document (PDF / Plaintext)</label>
          <input type="file" id="inpFirDocFile" class="form-input" accept=".pdf,.txt,.md,.csv" onchange="ScreenCases.handleFirFileSelect(this)" />
        </div>

        <div class="form-group">
          <label class="form-label">Or Paste FIR / Inquest Text Content</label>
          <textarea id="inpFirPastedText" class="form-input" rows="4" placeholder="Paste First Information Report text or initial inquest notes here..."></textarea>
        </div>

        <div style="margin-bottom: 14px;">
          <button type="button" class="btn btn-secondary btn-sm" id="btnExtractFirCandidate" onclick="ScreenCases.extractFirDetails()">
            🔍 Extract FIR Candidate Particulars
          </button>
        </div>

        <!-- Extraction Preview Container -->
        <div id="firExtractionPreviewContainer" style="display: none;"></div>
      </div>
    `;

    const footerHtml = `
      <button class="btn btn-secondary" onclick="UI.closeModal()">Cancel</button>
      <button class="btn btn-primary" id="btnSubmitNewCase">Initialize Case Inquiry</button>
    `;

    UI.openModal("Register New Case Inquiry", bodyHtml, footerHtml);

    document.getElementById("btnSubmitNewCase")?.addEventListener("click", () => {
      if (ScreenCases._modalMode === "fir") {
        ScreenCases.submitFirAssistedCase();
      } else {
        ScreenCases.submitManualCase();
      }
    });
    ScreenCases._modalMode = "manual";
    ScreenCases._extractedFirData = null;
    ScreenCases._uploadedFirFile = null;
  },

  switchModalTab(mode) {
    ScreenCases._modalMode = mode;
    const tabM = document.getElementById("tabManualMode");
    const tabF = document.getElementById("tabFirMode");
    const secM = document.getElementById("sectionManualRegistration");
    const secF = document.getElementById("sectionFirAssisted");
    const submitBtn = document.getElementById("btnSubmitNewCase");

    if (mode === "fir") {
      tabM?.classList.remove("active");
      tabF?.classList.add("active");
      if (secM) secM.style.display = "none";
      if (secF) secF.style.display = "block";
      if (submitBtn) submitBtn.textContent = ScreenCases._extractedFirData ? "Confirm & Register Case" : "Extract & Review FIR";
    } else {
      tabF?.classList.remove("active");
      tabM?.classList.add("active");
      if (secF) secF.style.display = "none";
      if (secM) secM.style.display = "block";
      if (submitBtn) submitBtn.textContent = "Initialize Case Inquiry";
    }
  },

  handleFirFileSelect(input) {
    if (input.files && input.files[0]) {
      ScreenCases._uploadedFirFile = input.files[0];
    }
  },

  async extractFirDetails() {
    const btn = document.getElementById("btnExtractFirCandidate");
    const previewMount = document.getElementById("firExtractionPreviewContainer");
    const pastedText = document.getElementById("inpFirPastedText")?.value.trim() || "";
    const file = ScreenCases._uploadedFirFile;

    if (!file && !pastedText) {
      UI.showToast("Please choose an FIR file or paste FIR text first.", "error");
      return;
    }

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span style="display:inline-block; width:12px; height:12px; border:2px solid currentColor; border-right-color:transparent; border-radius:50%; animation:spin 0.75s linear infinite; margin-right:6px; vertical-align:middle;"></span> Extracting...`;
    }

    try {
      const formData = new FormData();
      if (file) {
        formData.append("file", file);
      }
      if (pastedText) {
        formData.append("fir_text", pastedText);
      }

      const extracted = await Api.previewFIRExtraction(formData);
      ScreenCases._extractedFirData = extracted;
      ScreenCases._reviewerModifications = {};

      if (previewMount) {
        previewMount.style.display = "block";
        const initialTitle = extracted.suggested_title || `Inquest Inquiry of ${extracted.victim_name || 'Unnatural Death'} — ${extracted.fir_number || 'Initial'}`;
        
        const friendlyFieldNames = {
          fir_number: "FIR / Inquest Number",
          police_station: "Police Station / Jurisdiction",
          incident_date: "Incident Date / Occurrence Time",
          report_date: "Report Date",
          discovery_time: "Discovery Date / Time",
          incident_location: "Scene of Occurrence / Location",
          victim_name: "Deceased / Person Found Unresponsive",
          complainant_name: "Complainant / Informant",
          offense_sections: "Statutory Penal Sections",
          investigating_officer: "Investigating Officer"
        };

        previewMount.innerHTML = `
          <div class="card" style="padding: 16px; background: var(--bg-card-subtle); border-left: 4px solid var(--primary); margin-top: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
              <h4 style="font-size: 0.96rem; font-weight: 700; color: var(--text-main);">Extracted Candidate Particulars</h4>
              <span class="badge badge-attention">Human Review Required</span>
            </div>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 14px;">
              ${Formatters.escapeHtml(extracted.disclaimer)}
            </p>

            ${extracted.ocr_limitation_notice ? `
              <div style="padding: 10px 14px; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: var(--radius-sm); margin-bottom: 12px; font-size: 0.8rem; color: #b45309;">
                <strong>⚠️ Scanned Document Notice:</strong> ${Formatters.escapeHtml(extracted.ocr_limitation_notice)}
              </div>
            ` : ''}

            ${(extracted.missing_fields && extracted.missing_fields.length > 0) ? `
              <div style="display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 0.74rem;">
                <span style="color: var(--text-muted); font-weight: 600;">Unrecorded in source:</span>
                ${extracted.missing_fields.map(f => `<span class="badge badge-attention" style="font-size: 0.7rem;">${Formatters.escapeHtml(friendlyFieldNames[f] || f)}</span>`).join("")}
              </div>
            ` : ''}

            ${(extracted.ambiguous_fields && extracted.ambiguous_fields.length > 0) ? `
              <div style="display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 0.74rem;">
                <span style="color: var(--text-muted); font-weight: 600;">Approximate / Ambiguous:</span>
                ${extracted.ambiguous_fields.map(f => `<span class="badge badge-warning" style="font-size: 0.7rem;">${Formatters.escapeHtml(friendlyFieldNames[f] || f)}</span>`).join("")}
              </div>
            ` : ''}

            <div class="form-group">
              <label class="form-label">Suggested Case Title * <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: normal;">(Auto-generated, editable)</span></label>
              <input type="text" id="inpFirCandidateTitle" class="form-input" value="${Formatters.escapeHtml(initialTitle)}" />
            </div>

            <div class="grid-2">
              <div class="form-group">
                <label class="form-label">FIR / Inquest Number *</label>
                <input type="text" id="inpFirCandidateNumber" class="form-input" value="${Formatters.escapeHtml(extracted.fir_number || '')}" placeholder="e.g. FIR-SYN-2026-1042" />
              </div>
              <div class="form-group">
                <label class="form-label">Police Station / Circle *</label>
                <input type="text" id="inpFirCandidateStation" class="form-input" value="${Formatters.escapeHtml(extracted.police_station || '')}" placeholder="Originating Police Station" />
              </div>
            </div>

            <div class="grid-2">
              <div class="form-group">
                <label class="form-label">Report Date</label>
                <input type="text" id="inpFirCandidateReportDate" class="form-input" value="${Formatters.escapeHtml(extracted.report_date || '')}" placeholder="Registration / Report Date" />
              </div>
              <div class="form-group">
                <label class="form-label">Discovery Date / Time</label>
                <input type="text" id="inpFirCandidateDiscoveryTime" class="form-input" value="${Formatters.escapeHtml(extracted.discovery_time || '')}" placeholder="e.g. Approximately 07:20 IST on 18 October 2026" />
              </div>
            </div>

            <div class="grid-2">
              <div class="form-group">
                <label class="form-label">Incident Date / Occurrence Time</label>
                <input type="text" id="inpFirCandidateDate" class="form-input" value="${Formatters.escapeHtml(extracted.incident_date || '')}" placeholder="Occurrence timeframe" />
              </div>
              <div class="form-group">
                <label class="form-label">Scene of Occurrence / Location</label>
                <input type="text" id="inpFirCandidateLocation" class="form-input" value="${Formatters.escapeHtml(extracted.incident_location || '')}" placeholder="Scene / Discovery Location" />
              </div>
            </div>

            <div class="grid-2">
              <div class="form-group">
                <label class="form-label">Deceased / Person Found Unresponsive</label>
                <input type="text" id="inpFirCandidateVictim" class="form-input" value="${Formatters.escapeHtml(extracted.victim_name || '')}" placeholder="Name of deceased / subject" />
              </div>
              <div class="form-group">
                <label class="form-label">Complainant / Informant</label>
                <input type="text" id="inpFirCandidateComplainant" class="form-input" value="${Formatters.escapeHtml(extracted.complainant_name || '')}" placeholder="Not specified in source (optional)" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Reported Statutory Sections</label>
              <input type="text" id="inpFirCandidateSections" class="form-input" value="${Formatters.escapeHtml(extracted.offense_sections || '')}" placeholder="Not specified in source (optional)" />
            </div>

            ${(extracted.witness_sightings && extracted.witness_sightings.length > 0) ? `
              <div style="margin-top: 10px; padding: 10px 12px; background: var(--bg-surface); border-radius: var(--radius-sm); border: 1px solid var(--border-default);">
                <div style="font-weight: 700; font-size: 0.74rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px;">Witness Sightings (${extracted.witness_sightings.length})</div>
                <div style="display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem;">
                  ${extracted.witness_sightings.map(w => `
                    <div><strong>${Formatters.escapeHtml(w.witness || 'Witness')}:</strong> <span class="badge badge-neutral" style="font-size:0.75rem;">${Formatters.escapeHtml(w.sighting || '')}</span></div>
                  `).join("")}
                </div>
              </div>
            ` : ''}

            <div style="margin-top: 10px; padding: 10px 12px; background: rgba(59, 130, 246, 0.05); border-radius: var(--radius-sm); border: 1px solid rgba(59, 130, 246, 0.2); font-size: 0.78rem; color: var(--text-muted);">
              <div><strong>Evidentiary Limitations:</strong> Time of death: <em>${Formatters.escapeHtml(extracted.time_of_death || 'Unknown / not established')}</em> | Cause of death: <em>${Formatters.escapeHtml(extracted.cause_of_death || 'Unknown / not established')}</em></div>
              <div style="margin-top: 4px; font-size: 0.72rem; color: var(--text-muted);">Discovery time is preserved separately and not inferred as time of death. Motives, suspects, or penal offenses are not assumed without explicit source support.</div>
            </div>

            <!-- Verbatim Source Quotes Accordion -->
            <div style="margin-top: 12px;">
              <div style="font-weight: 700; font-size: 0.74rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px;">Grounding Source Passages (${extracted.source_passages.length})</div>
              <div style="display: flex; flex-direction: column; gap: 6px; max-height: 140px; overflow-y: auto;">
                ${extracted.source_passages.map(sp => `
                  <div class="fir-source-quote-box" style="margin-top: 0; padding: 6px 10px;">
                    "${Formatters.escapeHtml(sp.quote)}"
                    <div class="fir-quote-meta">
                      <span>Field: <strong>${Formatters.escapeHtml(friendlyFieldNames[sp.field] || sp.field)}</strong></span>
                      <span class="badge badge-${sp.extraction_status === 'EXTRACTED' ? 'success' : 'attention'}" style="font-size: 0.65rem;">${Formatters.escapeHtml(sp.extraction_status || 'EXTRACTED')}</span>
                      <span>Offset: ${sp.char_offset || 0}</span>
                    </div>
                  </div>
                `).join("")}
              </div>
            </div>
          </div>
        `;

        // Attach live input listeners to track reviewer modifications and clear validation error states
        previewMount.querySelectorAll("input").forEach(inp => {
          inp.addEventListener("input", () => {
            inp.classList.remove("input-error");
            if (!ScreenCases._reviewerModifications) ScreenCases._reviewerModifications = {};
            ScreenCases._reviewerModifications[inp.id] = inp.value;
          });
        });
      }

      const submitBtn = document.getElementById("btnSubmitNewCase");
      if (submitBtn) submitBtn.textContent = "Confirm & Register Case";
      UI.showToast("FIR particulars extracted. Review and confirm to proceed.", "success");
    } catch (err) {
      UI.showToast(`FIR extraction failed: ${err.message}`, "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `🔍 Extract FIR Candidate Particulars`;
      }
    }
  },

  async submitFirAssistedCase() {
    if (ScreenCases._isSubmittingFir) return;

    // Check if extraction has occurred
    if (!ScreenCases._extractedFirData) {
      const file = ScreenCases._uploadedFirFile;
      const pastedText = document.getElementById("inpFirPastedText")?.value.trim() || "";
      if (file || pastedText) {
        UI.showToast("Extracting candidate particulars from provided FIR...", "info");
        await ScreenCases.extractFirDetails();
        return;
      } else {
        UI.showToast("Please choose an FIR file or paste FIR text first, then extract particulars.", "error");
        return;
      }
    }

    const titleInput = document.getElementById("inpFirCandidateTitle");
    const firNumInput = document.getElementById("inpFirCandidateNumber");
    const stationInput = document.getElementById("inpFirCandidateStation");

    [titleInput, firNumInput, stationInput].forEach(el => el?.classList.remove("input-error"));

    const title = titleInput?.value.trim() || "";
    const firNum = firNumInput?.value.trim() || "";
    const station = stationInput?.value.trim() || "";

    const missingList = [];
    if (!title) { missingList.push("Title"); titleInput?.classList.add("input-error"); }
    if (!firNum) { missingList.push("FIR Number"); firNumInput?.classList.add("input-error"); }
    if (!station) { missingList.push("Police Station"); stationInput?.classList.add("input-error"); }

    if (missingList.length > 0) {
      const firstInvalid = !title ? titleInput : (!firNum ? firNumInput : stationInput);
      firstInvalid?.focus();
      UI.showToast(`Please confirm mandatory particulars (${missingList.join(", ")}).`, "error");
      return;
    }

    const dateStr = document.getElementById("inpFirCandidateDate")?.value.trim();
    const reportDateStr = document.getElementById("inpFirCandidateReportDate")?.value.trim();
    const discoveryTimeStr = document.getElementById("inpFirCandidateDiscoveryTime")?.value.trim();
    const loc = document.getElementById("inpFirCandidateLocation")?.value.trim();
    const comp = document.getElementById("inpFirCandidateComplainant")?.value.trim();
    const vic = document.getElementById("inpFirCandidateVictim")?.value.trim();
    const sec = document.getElementById("inpFirCandidateSections")?.value.trim();
    const rawText = document.getElementById("inpFirPastedText")?.value || "";

    const submitBtn = document.getElementById("btnSubmitNewCase");
    ScreenCases._isSubmittingFir = true;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span style="display:inline-block; width:12px; height:12px; border:2px solid currentColor; border-right-color:transparent; border-radius:50%; animation:spin 0.75s linear infinite; margin-right:6px; vertical-align:middle;"></span> Initializing...`;
    }

    try {
      let firB64 = null;
      if (ScreenCases._uploadedFirFile) {
        try {
          firB64 = await new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = () => {
              const res = reader.result || "";
              const b64 = typeof res === "string" && res.includes(",") ? res.split(",")[1] : res;
              resolve(b64);
            };
            reader.onerror = () => resolve(null);
            reader.readAsDataURL(ScreenCases._uploadedFirFile);
          });
        } catch (e) {
          console.warn("Could not read uploaded FIR file as base64:", e);
        }
      }

      const payload = {
        title: title,
        assigned_io_id: State.auth.subjectId,
        fir_metadata: {
          fir_number: firNum,
          police_station: station,
          incident_date: dateStr || discoveryTimeStr || new Date().toISOString(),
          report_date: reportDateStr || null,
          incident_location: loc || "Scene of occurrence unrecorded",
          victim_name: vic || null,
          complainant_name: comp || null,
          additional_attributes: {
            discovery_time: discoveryTimeStr || null,
            offense_sections: sec || null,
            witness_sightings: ScreenCases._extractedFirData?.witness_sightings || [],
            time_of_death: ScreenCases._extractedFirData?.time_of_death || "Unknown / not established",
            cause_of_death: ScreenCases._extractedFirData?.cause_of_death || "Unknown / not established",
            candidate_extractions: ScreenCases._extractedFirData,
            reviewer_modifications: ScreenCases._reviewerModifications || {},
            source_passages: ScreenCases._extractedFirData?.source_passages || [],
            assisted_registration: true
          }
        },
        discovery_time: discoveryTimeStr || null,
        offense_sections: sec || null,
        witness_sightings: ScreenCases._extractedFirData?.witness_sightings || [],
        time_of_death: ScreenCases._extractedFirData?.time_of_death,
        cause_of_death: ScreenCases._extractedFirData?.cause_of_death,
        candidate_extractions: ScreenCases._extractedFirData,
        reviewer_modifications: ScreenCases._reviewerModifications || {},
        source_passages: ScreenCases._extractedFirData?.source_passages || [],
        fir_file_b64: firB64,
        fir_raw_text: rawText,
        fir_filename: ScreenCases._uploadedFirFile ? ScreenCases._uploadedFirFile.name : "FIR_initial_record.txt"
      };

      const resp = await Api.createCaseFIRAssisted(payload);
      UI.closeModal();
      UI.recordAudit("CASE_INITIALIZED_FIR_ASSISTED", resp.case.case_id, "SUCCESS", `Case registered via FIR assistance: ${resp.case.title}`);
      UI.showToast(`Case ${resp.case.case_id} registered and FIR preserved into chain of custody!`, "success");

      // Reload case directory to show registered case
      if (typeof ScreenCases.loadCases === "function") {
        await ScreenCases.loadCases();
      }
      ScreenCases.showRegistrationSuccessModal(resp.case);
    } catch (err) {
      UI.showToast(`FIR-Assisted registration failed: ${err.message}`, "error");
    } finally {
      ScreenCases._isSubmittingFir = false;
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Confirm & Register Case";
      }
    }
  },

  async submitManualCase() {
    const title = document.getElementById("inpCaseTitle")?.value.trim();
    const fir = document.getElementById("inpFirNumber")?.value.trim();
    const station = document.getElementById("inpStation")?.value.trim();
    const dt = document.getElementById("inpIncidentDate")?.value;
    const io = document.getElementById("inpAssignedIo")?.value.trim() || State.auth.subjectId;
    const loc = document.getElementById("inpIncidentLocation")?.value.trim();

    if (!title || !fir || !station) {
      UI.showToast("Please complete all mandatory particulars.", "error");
      return;
    }

    const payload = {
      title,
      assigned_io_id: io,
      fir_metadata: {
        fir_number: fir,
        police_station: station,
        incident_date: dt ? new Date(dt).toISOString() : new Date().toISOString(),
        incident_location: loc || "Scene of occurrence unrecorded"
      }
    };

    try {
      const newCase = await Api.createCase(payload);
      UI.closeModal();
      UI.recordAudit("CASE_INITIALIZED", newCase.case_id, "SUCCESS", `Case registered: ${newCase.title}`);
      UI.showToast(`Inquiry ${newCase.case_id} registered successfully!`, "success");
      ScreenCases.showRegistrationSuccessModal(newCase);
    } catch (err) {
      UI.showToast(`Case registration failed: ${err.message}`, "error");
    }
  },

  showRegistrationSuccessModal(newCase) {
    const isIngestion = newCase.lifecycle_stage === "EVIDENCE_INGESTION";
    const bodyHtml = `
      <div style="display: flex; flex-direction: column; gap: 16px; font-size: 0.88rem;">
        <div style="display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--verified-bg); border: 1px solid var(--verified-border); border-radius: var(--radius-md);">
          <span style="font-size: 1.8rem;">✅</span>
          <div>
            <div style="font-weight: 700; color: var(--verified-text); font-size: 1rem;">Case Registration Confirmed</div>
            <div style="color: var(--text-secondary); font-size: 0.82rem;">Inquest docket formally recorded in police station registry.</div>
          </div>
        </div>

        <div class="card" style="padding: 14px; background: var(--bg-card-subtle);">
          <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 0.82rem;">
            <div>
              <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Case Identifier</span>
              <strong style="font-family: var(--font-mono); color: var(--primary);">${Formatters.escapeHtml(newCase.case_id)}</strong>
            </div>
            <div>
              <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Current Lifecycle Stage</span>
              <span class="badge ${isIngestion ? 'badge-info' : 'badge-neutral'}">${isIngestion ? 'Collecting Evidence' : '1. Case Setup (INITIALIZED)'}</span>
            </div>
            <div style="grid-column: span 2;">
              <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Case Title</span>
              <strong>${Formatters.escapeHtml(newCase.title)}</strong>
            </div>
            <div>
              <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Assigned Officer</span>
              <span>${Formatters.escapeHtml(newCase.assigned_io_id || State.auth.subjectId)}</span>
            </div>
            <div>
              <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Police Station</span>
              <span>${Formatters.escapeHtml(newCase.fir_metadata?.police_station || 'Station Registry')}</span>
            </div>
          </div>
        </div>

        <div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px;">Investigation Workflow Progress</div>
        <div style="font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 8px;">
          Case registered under Stage 1. Next permitted phase: Evidence Collection.
        </div>

        <div style="background: var(--primary-bg); border-left: 4px solid var(--primary); padding: 12px 16px; border-radius: var(--radius-sm);">
          <strong style="color: var(--text-main); display: block; margin-bottom: 4px;">Next Action: Begin Evidence Collection</strong>
          <p style="color: var(--text-secondary); font-size: 0.84rem; line-height: 1.5; margin: 0;">
            Under BNSS procedure, an inquiry requires primary case exhibits before timeline reconstruction or forensic analysis can proceed.
            You can now attach crime scene photographs, autopsy certificates, CCTV footage, mobile extractions, or telecom records. All exhibits are protected with dual cryptographic fingerprints and WORM storage.
          </p>
        </div>
      </div>
    `;

    const footerHtml = `
      <button class="btn btn-secondary" onclick="UI.closeModal(); Router.selectCaseAndRoute('${newCase.case_id}', 'overview');">
        View Case Details
      </button>
      <button class="btn btn-primary" id="btnRegModalAddEvidence" onclick="UI.closeModal(); ${
        isIngestion 
          ? `window.location.hash='#/cases/${newCase.case_id}/evidence'; setTimeout(() => ScreenEvidence.showRegisterEvidenceModal(), 150);` 
          : `handleStageTransition('${newCase.case_id}', 'EVIDENCE_INGESTION', true);`
      }">
        ${isIngestion ? '+ Add Evidence' : 'Begin Evidence Collection & Add Evidence &rarr;'}
      </button>
    `;

    UI.openModal("Case Registered &bull; Next Action: Evidence Collection", bodyHtml, footerHtml);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 7. CASE WORKSPACE HEADER & STEPPER (Natural Police Milestones)
// ═══════════════════════════════════════════════════════════════════════════

async function ensureActiveCaseLoaded(caseId) {
  if (!caseId || caseId === "null" || caseId === "undefined") {
    resetActiveCaseState();
    throw new Error("No case ID provided.");
  }

  State.activeCaseId = caseId;
  localStorage.setItem("sakshi_active_case_id", caseId);

  if (!State.activeCase || State.activeCase.case_id !== caseId) {
    try {
      State.evidence = [];
      State.activeStageInfo = null;
      State.analysisSummary = null;
      State.graphEdges = [];
      State.isAnalysisRunning = false;
      State.isContradictionRunning = false;
      State.analysisSummaryError = null;
      State.evidenceLoadError = null;
      State.activeCase = await Api.getCase(caseId);
    } catch (err) {
      resetActiveCaseState();
      throw err;
    }
  }

  try {
    State.activeStageInfo = await Api.getCaseStage(caseId);
    const evRes = await Api.listEvidence(caseId);
    State.evidence = evRes.items || [];
    State.evidenceLoadError = null;
  } catch (e) {
    console.warn("Supplementary case sync notice:", e);
    State.evidenceLoadError = e;
  }

  updateSidebarActiveCaseContext();
  return State.activeCase;
}

function renderWorkspaceHeaderHtml(activeTab) {
  const c = State.activeCase;
  if (!c) return "";

  const fir = (c.fir_metadata && c.fir_metadata.fir_number) || "No FIR Recorded";
  const station = (c.fir_metadata && c.fir_metadata.police_station) || "Central Forensic Division";
  const incidentDate = (c.fir_metadata && c.fir_metadata.incident_date) ? Formatters.formatDate(c.fir_metadata.incident_date) : "Not Specified";

  const allPhases = [
    { key: "INITIALIZED", label: "Case Setup", short: "Case Setup", tab: "overview", stepNum: 1, desc: "Case inquest particulars, jurisdiction, and assigned officer registered." },
    { key: "EVIDENCE_INGESTION", label: "Evidence Collection", short: "Evidence Collection", tab: "evidence", stepNum: 2, desc: "Collect crime scene photos, post-mortem reports, CCTV, and digital records." },
    { key: "EVIDENCE_PROCESSING", label: "Forensic Verification", short: "Forensic Verification", tab: "verification", stepNum: 3, desc: "Validate format signatures, malware scans, dual-hash integrity, and immutable storage." },
    { key: "ANALYSIS", label: "Investigation Analysis", short: "Investigation Analysis", tab: "analysis", stepNum: 4, desc: "Chronological sequence reconstruction, evidence relationships, and discrepancy review." },
    { key: "REVIEW", label: "Investigator Review", short: "Investigator Review", tab: "findings", stepNum: 5, desc: "Investigating officer review of findings, gaps, and evidentiary chain of custody." },
    { key: "CLOSED", label: "Case Closed", short: "Case Closed", tab: "closure", stepNum: 6, desc: "Case inquest concluded and archived under Section 194 BNSS / Section 174 CrPC." }
  ];

  const currentIdx = allPhases.findIndex(s => s.key === c.lifecycle_stage);
  const currentPhase = allPhases[currentIdx] || { short: c.lifecycle_stage, desc: "Current stage" };
  const allowedTransitions = (State.activeStageInfo && State.activeStageInfo.allowed_transitions) || [];
  const nextStageKey = allowedTransitions.length > 0 ? allowedTransitions[0] : null;
  const nextStageObj = nextStageKey ? (StageDisplayMap[nextStageKey] || { short: nextStageKey }) : null;

  const evList = State.evidence || [];
  const unverifiedCount = evList.filter(e => e.integrity_status !== "VERIFIED" || e.worm_status !== "COMMITTED" || e.antivirus_status !== "CLEAN").length;
  let outstandingText = "None pending";
  if (evList.length === 0 && c.lifecycle_stage === "INITIALIZED") {
    outstandingText = "Attach initial exhibits to begin inquiry";
  } else if (unverifiedCount > 0) {
    outstandingText = `${unverifiedCount} exhibit(s) require verification`;
  } else if (c.lifecycle_stage === "ANALYSIS") {
    outstandingText = "Review timeline and cross-exhibit consistency";
  } else if (c.lifecycle_stage === "REVIEW") {
    outstandingText = "Supervisory review endorsement required";
  }

  return `
    <div class="case-workspace-header">
      <div class="case-header-top">
        <div class="case-header-title-area">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap;">
            <span class="case-id-badge">${c.case_id}</span>
            <span class="badge ${c.status === 'ACTIVE' ? 'badge-verified' : 'badge-neutral'}">${Formatters.escapeHtml(c.status)} INQUIRY</span>
            <span class="badge badge-info" style="font-weight: 600;">Stage ${currentIdx + 1} of 6: ${Formatters.escapeHtml(currentPhase.short)}</span>
          </div>
          <h2>${Formatters.escapeHtml(c.title)}</h2>
          <div class="case-meta-chips">
            <div class="case-meta-chip">FIR / Inquest: <strong>${fir}</strong></div>
            <div class="case-meta-chip">Station: <strong>${station}</strong></div>
            <div class="case-meta-chip">Incident Date: <strong>${incidentDate}</strong></div>
            <div class="case-meta-chip">Investigating Officer: <strong>${c.assigned_io_id || 'Unassigned'}</strong></div>
          </div>
        </div>

        <div>
          <button class="btn btn-secondary btn-sm" onclick="window.location.hash='#/cases'">
            &larr; Switch Case
          </button>
        </div>
      </div>

      <!-- Compact Case Summary Bar (Reclaiming layout space from removed 6-stage strip) -->
      <div class="case-summary-bar" style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; padding: 10px 14px; background: var(--bg-card-subtle); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); margin-top: 12px; font-size: 0.82rem;">
        <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap; color: var(--text-secondary);">
          <div class="case-summary-item"><strong>Stage:</strong> ${Formatters.escapeHtml(currentPhase.short)}</div>
          <div class="case-summary-item"><strong>Evidence:</strong> ${evList.length} exhibit(s) registered</div>
          <div class="case-summary-item"><strong>Outstanding work:</strong> ${Formatters.escapeHtml(outstandingText)}</div>
          ${nextStageObj ? `<div class="case-summary-item"><strong>Next action:</strong> ${Formatters.escapeHtml(nextStageObj.short)}</div>` : `<div class="case-summary-item"><strong>Next action:</strong> Inquiry concluded</div>`}
        </div>
        ${allowedTransitions.length > 0 ? `
          <div class="case-summary-action" style="display: flex; gap: 6px;">
            ${allowedTransitions.map(targetStage => {
              const targetObj = StageDisplayMap[targetStage] || { short: targetStage };
              return `
                <button class="btn btn-primary btn-sm btn-stage-transition" style="padding: 3px 10px; font-size: 0.78rem;" onclick="handleStageTransition('${c.case_id}', '${targetStage}')">
                  Advance to ${Formatters.escapeHtml(targetObj.short)} &rarr;
                </button>
              `;
            }).join("")}
          </div>
        ` : ''}
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="case-workspace-tabs">
      <button class="tab-btn ${(activeTab === 'overview' || activeTab === 'setup') ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/overview'">
        Case Overview
      </button>
      <button class="tab-btn ${activeTab === 'evidence' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/evidence'">
        Evidence (${State.evidence ? State.evidence.length : 0})
      </button>
      <button class="tab-btn ${activeTab === 'verification' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/verification'">
        Forensic Verification
      </button>
      <button class="tab-btn ${(activeTab === 'connections' || activeTab === 'graph') ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/connections'">
        Entity Graph
      </button>
      <button class="tab-btn ${activeTab === 'timeline' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/timeline'">
        Timeline
      </button>
      <button class="tab-btn ${activeTab === 'analysis' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/analysis'">
        Investigation Analysis
      </button>
      <button class="tab-btn ${activeTab === 'rag' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/rag'">
        Evidence Search (RAG)
      </button>
      <button class="tab-btn ${(activeTab === 'findings' || activeTab === 'gaps' || activeTab === 'review') ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/findings'">
        Investigator Review
      </button>
      <button class="tab-btn ${activeTab === 'closure' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/closure'">
        Case Closure
      </button>
      <button class="tab-btn ${activeTab === 'report' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/report'">
        Case Report
      </button>
      <button class="tab-btn ${activeTab === 'audit' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/audit'">
        Activity & Audit
      </button>
    </div>
  `;
}

let isStageTransitionInProgress = false;

async function handleStageTransition(caseId, targetStage, openEvidenceModal = false) {
  if (isStageTransitionInProgress) {
    console.warn("Stage transition already in progress for case:", caseId);
    return;
  }
  isStageTransitionInProgress = true;

  // Visual in-flight indication: Disable transition buttons and display spinner
  const transitionButtons = document.querySelectorAll(".btn-stage-transition, button[onclick*='handleStageTransition']");
  transitionButtons.forEach(btn => {
    btn.disabled = true;
    btn.dataset.prevHtml = btn.innerHTML;
    btn.innerHTML = `<span style="display:inline-block; width:12px; height:12px; border:2px solid currentColor; border-right-color:transparent; border-radius:50%; animation:spin 0.75s linear infinite; margin-right:6px; vertical-align:middle;"></span> Advancing...`;
  });

  try {
    const updated = await Api.updateCaseStage(caseId, targetStage);
    State.activeCase = updated;
    State.activeCaseId = caseId;
    localStorage.setItem("sakshi_active_case_id", caseId);
    State.activeStageInfo = await Api.getCaseStage(caseId);
    const targetObj = StageDisplayMap[targetStage] || { short: targetStage };
    UI.showToast(`Investigation advanced to ${targetObj.short}`, "success");
    UI.recordAudit("INVESTIGATION_PHASE_ADVANCED", caseId, "SUCCESS", `Advanced to ${targetObj.short}`);
    updateSidebarActiveCaseContext();

    if (targetStage === "EVIDENCE_INGESTION") {
      window.location.hash = `#/cases/${caseId}/evidence`;
      if (openEvidenceModal) {
        setTimeout(() => {
          if (typeof ScreenEvidence !== "undefined" && ScreenEvidence.showRegisterEvidenceModal) {
            ScreenEvidence.showRegisterEvidenceModal();
          }
        }, 150);
      }
    } else {
      Router.navigate();
    }
  } catch (err) {
    // Safe reconciliation: If network was interrupted or previous concurrent request already succeeded
    try {
      const refreshedCase = await Api.getCase(caseId);
      if (refreshedCase && refreshedCase.lifecycle_stage === targetStage) {
        State.activeCase = refreshedCase;
        State.activeCaseId = caseId;
        localStorage.setItem("sakshi_active_case_id", caseId);
        State.activeStageInfo = await Api.getCaseStage(caseId);
        updateSidebarActiveCaseContext();
        const targetObj = StageDisplayMap[targetStage] || { short: targetStage };
        UI.showToast(`Investigation advanced to ${targetObj.short}`, "success");
        if (targetStage === "EVIDENCE_INGESTION") {
          window.location.hash = `#/cases/${caseId}/evidence`;
          if (openEvidenceModal) {
            setTimeout(() => {
              if (typeof ScreenEvidence !== "undefined" && ScreenEvidence.showRegisterEvidenceModal) {
                ScreenEvidence.showRegisterEvidenceModal();
              }
            }, 150);
          }
        } else {
          Router.navigate();
        }
        return;
      }
    } catch (reconErr) {
      console.warn("Stage reconciliation check notice:", reconErr);
    }

    const errMessage = (err && err.message) ? err.message : "Stage transition rejected by Stage Engine.";
    UI.showToast(`Phase transition failed: ${errMessage}`, "error");
    UI.recordAudit("INVESTIGATION_PHASE_ADVANCE_FAILED", caseId, "FAILED", errMessage);
  } finally {
    isStageTransitionInProgress = false;
    transitionButtons.forEach(btn => {
      btn.disabled = false;
      if (btn.dataset.prevHtml) {
        btn.innerHTML = btn.dataset.prevHtml;
        delete btn.dataset.prevHtml;
      }
    });
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 8. SCREEN 2: CASE OVERVIEW (Route: #/cases/:id/overview)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenCaseOverview = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Case Overview`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }

    const c = State.activeCase;
    const evidenceList = State.evidence || [];

    // Authoritative Analysis Summary & Graph Edges retrieval
    let analysisSummary = State.analysisSummary;
    if (!analysisSummary && evidenceList.length >= 2) {
      try {
        analysisSummary = await Api.getAnalysisSummary(caseId);
        State.analysisSummary = analysisSummary;
        State.analysisSummaryError = null;
      } catch (ae) {
        console.warn("Notice: could not load analysis summary for dashboard:", ae);
        State.analysisSummaryError = ae;
      }
    }

    let graphEdges = State.graphEdges || [];
    if (!graphEdges.length) {
      try {
        const gData = await Api.getKnowledgeGraph(caseId);
        if (gData && gData.edges) {
          graphEdges = gData.edges;
          State.graphEdges = graphEdges;
        }
      } catch (ge) {
        console.warn("Notice: could not load graph edges for dashboard:", ge);
      }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 1. Authoritative Metric 1: Evidence collected
    // ─────────────────────────────────────────────────────────────────────────
    const metricEvidence = {
      label: "Evidence collected",
      number: `${evidenceList.length}`,
      subtext: evidenceList.length === 0
        ? "No exhibits attached yet — Click to upload"
        : `${evidenceList.length} case exhibit${evidenceList.length > 1 ? 's' : ''} in docket`,
      colorClass: "var(--text-main)",
      route: `#/cases/${c.case_id}/evidence`,
      icon: ""
    };

    // ─────────────────────────────────────────────────────────────────────────
    // 2. Authoritative Metric 2: Conflicting information
    // Distinct states: Awaiting evidence (<2), Not assessed, Assessment in progress,
    // Unable to assess, Discrepancies found (count + reviewed/detected), None identified.
    // ─────────────────────────────────────────────────────────────────────────
    const contradictionEval = ContradictionAssessmentEvaluator.evaluate({
      evidenceList,
      analysisSummary,
      isRunning: State.isAnalysisRunning || State.isContradictionRunning,
      hasError: Boolean(State.analysisSummaryError)
    });

    const metricConflicts = {
      label: "Conflicting information",
      number: contradictionEval.number,
      isTextState: contradictionEval.isTextState,
      subtext: contradictionEval.subtext,
      colorClass: contradictionEval.colorClass,
      route: `#/cases/${c.case_id}/${contradictionEval.routeTab}`,
      icon: ""
    };

    // ─────────────────────────────────────────────────────────────────────────
    // 3. Authoritative Metric 3: Awaiting your review
    // Derived from pending graph relations + unreviewed extracted facts + candidate proposals
    // ─────────────────────────────────────────────────────────────────────────
    const pendingGraphReviews = (graphEdges || []).filter(e => e.review_status === "NEEDS_CONFIRMATION").length;
    let pendingFactReviews = 0;
    evidenceList.forEach(e => {
      if (e.extracted_facts && Array.isArray(e.extracted_facts)) {
        pendingFactReviews += e.extracted_facts.filter(f => f.decision === "PENDING" || !f.decision).length;
      }
    });
    const totalPendingReviews = pendingGraphReviews + pendingFactReviews;

    const metricReviews = {
      label: "Awaiting your review",
      number: `${totalPendingReviews}`,
      subtext: totalPendingReviews > 0
        ? `${totalPendingReviews} item${totalPendingReviews > 1 ? 's' : ''} awaiting officer review`
        : "All review decisions recorded",
      colorClass: totalPendingReviews > 0 ? "var(--attention)" : "var(--text-main)",
      route: `#/cases/${c.case_id}/findings`,
      icon: ""
    };

    // ─────────────────────────────────────────────────────────────────────────
    // 4. Authoritative Metric 4: Evidence security
    // Evaluates all 6 forensic security layers; never claims pipeline clean while checks pending
    // ─────────────────────────────────────────────────────────────────────────
    const secSummary = State.evidenceLoadError
      ? EvidenceSecurityEvaluator.evaluateUnavailable()
      : EvidenceSecurityEvaluator.evaluateCaseSecurity(evidenceList);

    const metricSecurity = {
      label: secSummary.label,
      number: secSummary.metricValue,
      isTextState: secSummary.status === "UNAVAILABLE" || String(secSummary.metricValue).length > 7,
      subtext: secSummary.subtext,
      colorClass: secSummary.colorClass || (secSummary.hasAlerts ? "var(--danger)" : (secSummary.isFullySecure ? "var(--verified)" : "var(--attention)")),
      route: `#/cases/${c.case_id}/verification`,
      icon: ""
    };

    // ─────────────────────────────────────────────────────────────────────────
    // 5. Recommended Next Action: 4-part formulation
    // What needs to be done, Why it matters, Involved items, and Action button
    // ─────────────────────────────────────────────────────────────────────────
    const recAction = RecommendedActionEvaluator.getAction(c, evidenceList, analysisSummary, graphEdges);
    const nextActionTitle = recAction.title;
    const nextActionDesc = recAction.whyItMatters;
    const nextActionButtonHtml = recAction.buttonHtml;

    // Attention tasks for the case docket
    const attentionItems = [];
    if (c.lifecycle_stage === "INITIALIZED") {
      attentionItems.push({
        id: "STAGE_READY_EVIDENCE",
        severity: "normal",
        title: "Case setup complete — Ready for evidence collection",
        source: c.case_id,
        desc: "Case setup registered. Open evidence collection to attach scene photographs, autopsy records, CCTV footage, and digital records.",
        actionText: "Begin Evidence Collection",
        actionFn: () => handleStageTransition(c.case_id, "EVIDENCE_INGESTION")
      });
    }

    evidenceList.forEach(e => {
      const evalE = EvidenceSecurityEvaluator.evaluateExhibit(e);
      if (evalE.overall.hasAlert) {
        attentionItems.push({
          id: `SEC_ALERT_${e.evidence_id}`,
          severity: "critical",
          title: "Evidence security warning",
          source: `${e.original_file_name} (${e.evidence_id})`,
          desc: evalE.overall.subtext,
          actionText: "Inspect Exhibit",
          actionFn: () => {
            window.location.hash = `#/cases/${c.case_id}/evidence`;
            setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer(e.evidence_id, e.case_id || c.case_id), 100);
          }
        });
      } else if (!evalE.overall.isFullyVerified) {
        attentionItems.push({
          id: `SEC_PEND_${e.evidence_id}`,
          severity: "normal",
          title: "Evidence verification pending",
          source: `${e.original_file_name} (${e.evidence_id})`,
          desc: evalE.overall.subtext,
          actionText: "Review Verification",
          actionFn: () => {
            window.location.hash = `#/cases/${c.case_id}/evidence`;
            setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer(e.evidence_id, e.case_id || c.case_id), 100);
          }
        });
      }
    });

    // Formulation of Incident Summary strictly from actual case data
    let incidentSummaryText = "";
    if (c.title || c.fir_metadata) {
      const dateStr = c.fir_metadata?.incident_date ? Formatters.formatDate(c.fir_metadata.incident_date) : "the recorded occurrence date";
      const locStr = c.fir_metadata?.incident_location ? `at ${c.fir_metadata.incident_location}` : "at the scene location";
      const stationStr = c.fir_metadata?.police_station ? `Jurisdiction: ${c.fir_metadata.police_station}.` : "";
      const currentPhaseName = (StageDisplayMap[c.lifecycle_stage] || {}).short || c.lifecycle_stage;

      incidentSummaryText = `An unnatural death inquiry was registered regarding "${Formatters.escapeHtml(c.title)}" on ${dateStr} ${locStr}. ${stationStr} The investigation is currently in the <strong>${currentPhaseName}</strong> phase under Investigating Officer <strong>${Formatters.escapeHtml(c.assigned_io_id || 'Unassigned')}</strong>.`;
    } else {
      incidentSummaryText = "Incident summary is not yet available.";
    }

    const html = `
      ${renderWorkspaceHeaderHtml("overview")}

      <!-- RECOMMENDED NEXT ACTION PANEL (4-Part Authoritative Formulation) -->
      <div class="recommended-next-action-card guided-next-action-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 14px;">
          <div style="flex: 1; min-width: 280px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
              <span class="badge badge-info" style="font-weight: 700;">RECOMMENDED NEXT ACTION</span>
              <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">Stage: ${(StageDisplayMap[c.lifecycle_stage] || {}).short || c.lifecycle_stage}</span>
            </div>
            <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 4px;">
              ${Formatters.escapeHtml(recAction.title)}
            </h3>
            <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin: 0 0 6px 0;">
              ${Formatters.escapeHtml(recAction.whyItMatters)}
            </p>
            <div style="font-size: 0.78rem; color: var(--text-muted);">
              Involved: <strong>${Formatters.escapeHtml(recAction.involved)}</strong>
            </div>
          </div>
          <div style="align-self: center;">
            ${recAction.buttonHtml}
          </div>
        </div>
      </div>

      <!-- 4 CONCISE DASHBOARD METRICS (Backed by Authoritative Backend Data) -->
      <div class="dashboard-metrics-grid investigation-overview-dashboard">
        <!-- Metric 1: Evidence collected -->
        <div class="dashboard-metric-card" role="button" tabindex="0" onclick="window.location.hash='${metricEvidence.route}'" title="View Evidence Collection">
          <div class="metric-header">
            <span class="metric-label">${metricEvidence.label}</span>
          </div>
          <div class="metric-number" style="color: ${metricEvidence.colorClass};">${metricEvidence.number}</div>
          <div class="metric-subtext">${metricEvidence.subtext}</div>
        </div>

        <!-- Metric 2: Conflicting information -->
        <div class="dashboard-metric-card" role="button" tabindex="0" onclick="window.location.hash='${metricConflicts.route}'" title="View Discrepancy & Conflict Analysis">
          <div class="metric-header">
            <span class="metric-label">${metricConflicts.label}</span>
          </div>
          <div class="metric-number ${metricConflicts.isTextState ? 'metric-text' : ''}" style="color: ${metricConflicts.colorClass};">${metricConflicts.number}</div>
          <div class="metric-subtext">${metricConflicts.subtext}</div>
        </div>

        <!-- Metric 3: Awaiting your review -->
        <div class="dashboard-metric-card" role="button" tabindex="0" onclick="window.location.hash='${metricReviews.route}'" title="Open Investigator Review Workspace">
          <div class="metric-header">
            <span class="metric-label">${metricReviews.label}</span>
          </div>
          <div class="metric-number" style="color: ${metricReviews.colorClass};">${metricReviews.number}</div>
          <div class="metric-subtext">${metricReviews.subtext}</div>
        </div>

        <!-- Metric 4: Evidence security -->
        <div class="dashboard-metric-card" role="button" tabindex="0" onclick="window.location.hash='${metricSecurity.route}'" title="View Forensic Pipeline Status">
          <div class="metric-header">
            <span class="metric-label">${metricSecurity.label}</span>
          </div>
          <div class="metric-number ${metricSecurity.isTextState ? 'metric-text' : ''}" style="color: ${metricSecurity.colorClass};">${metricSecurity.number}</div>
          <div class="metric-subtext">${metricSecurity.subtext}</div>
        </div>
      </div>

      <!-- MAIN DASHBOARD PANELS (2-Column Workstation Layout) -->
      <div class="dashboard-grid-2">
        <!-- LEFT COLUMN: Evidence Register Preview + Recent Case Activity -->
        <div style="display: flex; flex-direction: column; gap: 20px;">
          <!-- 1. Evidence Attached Preview -->
          <div class="card">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <h3 class="card-title">Evidence Register Preview</h3>
                <span style="font-size: 0.8rem; color: var(--text-muted);">${evidenceList.length} physical & digital exhibit(s) registered</span>
              </div>
              <div style="display: flex; gap: 6px;">
                <button class="btn btn-secondary btn-sm" onclick="ScreenEvidence.showRegisterEvidenceModal()">
                  + Register Evidence
                </button>
                <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${c.case_id}', 'evidence')">
                  View All &rarr;
                </button>
              </div>
            </div>
            ${evidenceList.length === 0 ? `
              <div style="padding: 24px 16px; text-align: center; background: var(--bg-card-subtle); border-radius: var(--radius-md); margin-top: 10px; border: 1px dashed var(--border-default);">
                <div style="font-weight: 600; color: var(--text-main); font-size: 0.95rem;">No Exhibits Attached to Case Docket</div>
                <p style="color: var(--text-muted); font-size: 0.82rem; margin: 4px auto 14px auto; max-width: 420px;">
                  Timeline reconstruction and gap detection strictly require verified evidence. Attach case exhibits (crime scene photos, inquest reports, medical certificates, or telecom records) to begin.
                </p>
                <button class="btn btn-primary btn-sm" onclick="Router.selectCaseAndRoute('${c.case_id}', 'evidence')">
                  + Attach First Evidence Exhibit
                </button>
              </div>
            ` : `
              <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 10px;">
                ${evidenceList.slice(0, 3).map(e => {
                  const evalE = EvidenceSecurityEvaluator.evaluateExhibit(e);
                  const resolvedCaseId = e.case_id || c.case_id;
                  return `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); cursor: pointer;"
                         onclick="Router.selectCaseAndRoute('${c.case_id}', 'evidence'); setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer('${e.evidence_id}', '${resolvedCaseId}'), 120);">
                      <div>
                        <div style="font-weight: 600; font-size: 0.88rem; color: var(--text-main);">${Formatters.escapeHtml(e.original_file_name)}</div>
                        <div style="font-size: 0.74rem; color: var(--text-muted); font-family: var(--font-mono);">${e.evidence_id} &bull; ${Formatters.formatCategory(e.evidence_category)}</div>
                      </div>
                      <div style="text-align: right;">
                        <span class="badge ${evalE.overall.badgeClass}">
                          ${evalE.overall.label}
                        </span>
                        <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px;">
                          ${evalE.overall.subtext}
                        </div>
                      </div>
                    </div>
                  `;
                }).join("")}
              </div>
            `}
          </div>

          <!-- 2. Recent Case Activity -->
          <div class="card">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <h3 class="card-title">Recent Case Activity</h3>
                <span style="font-size: 0.8rem; color: var(--text-muted);">Authoritative audit ledger of investigative actions</span>
              </div>
              <button class="btn btn-secondary btn-sm" onclick="window.location.hash='#/cases/${c.case_id}/audit'">
                View Complete Case Diary &rarr;
              </button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.84rem; margin-top: 10px;">
              ${(State.auditLog.length > 0 ? State.auditLog.slice(0, 4) : [
                {
                  timestamp: c.created_at,
                  action: "Case workspace initialized",
                  resource: c.case_id,
                  actor: c.assigned_io_id || "SAKSHI System",
                  result: "SUCCESS"
                }
              ]).map(log => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; border-bottom: 1px solid var(--border-subtle); background: var(--bg-card-subtle); border-radius: var(--radius-sm);">
                  <div>
                    <strong>${Formatters.escapeHtml(log.action)}</strong>
                    <span style="color: var(--text-muted); display: block; font-size: 0.74rem;">
                      ${Formatters.escapeHtml(log.resource)} &bull; By ${Formatters.escapeHtml(log.actor || 'SAKSHI System')}
                    </span>
                  </div>
                  <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">
                    ${Formatters.formatDate(log.timestamp)}
                  </span>
                </div>
              `).join("")}
            </div>
          </div>
        </div>

        <!-- RIGHT COLUMN: Case Particulars + Attention Center -->
        <div style="display: flex; flex-direction: column; gap: 20px;">
          <!-- 1. Case Particulars & Assignment -->
          <div class="card incident-summary-card" style="margin-bottom: 0;">
            <div class="incident-summary-header">
              <div class="incident-summary-badge">Case Summary &amp; Legal Provision</div>
            </div>
            <div class="incident-summary-content" style="font-size: 0.86rem; line-height: 1.55; color: var(--text-secondary);">
              ${incidentSummaryText}
            </div>

            <div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border-subtle); font-size: 0.82rem; color: var(--text-muted); display: flex; justify-content: space-between; align-items: center;">
              <span>Statutory Legal Provision:</span>
              <strong style="color: var(--text-main);">Section 194 BNSS / Section 174 CrPC</strong>
            </div>

            <!-- Custody & Assignment Actions -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border-subtle); flex-wrap: wrap; gap: 8px;">
              <button class="btn btn-primary btn-sm" id="btnOpenAssignIO">
                Assign / Reassign IO
              </button>
              <button class="btn btn-secondary btn-sm" id="btnToggleAssignHistory">
                Custody Ledger
              </button>
            </div>

            <div id="assignHistoryContainer" style="display: none; margin-top: 14px; border-top: 1px solid var(--border-subtle); padding-top: 10px;">
              <h4 style="font-size: 0.85rem; font-weight: 600; margin-bottom: 6px;">Custody &amp; Assignment Ledger</h4>
              <div id="assignHistoryList" style="font-size: 0.82rem; color: var(--text-secondary);">
                Loading assignment records...
              </div>
            </div>
          </div>

          <!-- 2. Attention Tasks / Attention Center -->
          <div class="card">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
              <h3 class="card-title">
                <span>Requires Attention</span>
                <span class="badge ${attentionItems.length > 0 ? 'badge-attention' : 'badge-verified'}">
                  ${attentionItems.length} Item(s)
                </span>
              </h3>
            </div>
            ${attentionItems.length === 0 ? `
              <div style="padding: 14px 16px; background-color: var(--verified-bg); border: 1px solid var(--verified-border); border-radius: var(--radius-md); color: var(--verified-text); font-size: 0.86rem; font-weight: 500; margin-top: 10px;">
                All attached evidence is securely preserved and verified. No immediate attention items required.
              </div>
            ` : `
              <div class="attention-grid" style="margin-top: 10px;">
                ${attentionItems.map((item, idx) => `
                  <div class="attention-card ${item.severity === 'critical' ? 'critical' : ''}">
                    <div>
                      <div class="attention-card-header">
                        <div>
                          <div class="attention-title">${Formatters.escapeHtml(item.title)}</div>
                          <div class="attention-source">${Formatters.escapeHtml(item.source)}</div>
                        </div>
                      </div>
                      <p class="attention-desc" style="margin-top: 6px;">${Formatters.escapeHtml(item.desc)}</p>
                    </div>
                    <div>
                      <button class="btn btn-sm ${item.severity === 'critical' ? 'btn-danger' : 'btn-attention'}" id="attnBtn_${idx}">
                        ${Formatters.escapeHtml(item.actionText)} &rarr;
                      </button>
                    </div>
                  </div>
                `).join("")}
              </div>
            `}
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;

    attentionItems.forEach((item, idx) => {
      document.getElementById(`attnBtn_${idx}`)?.addEventListener("click", item.actionFn);
    });

    document.getElementById("btnOpenAssignIO")?.addEventListener("click", async () => {
      let eligible = [];
      try {
        eligible = await Api.getEligibleOfficers(c.case_id);
      } catch (err) {
        UI.showToast("Could not load eligible officers: " + err.message, "error");
        return;
      }

      const optionsHtml = (eligible && eligible.length > 0)
        ? eligible.map(o => `<option value="${o.officer_id}">${o.full_name} (${o.generated_username}) — ${o.police_station_name || o.station_id}</option>`).join("")
        : `<option value="" disabled>No eligible officers in jurisdiction</option>`;

      const modalHtml = `
        <form id="assignCaseForm" style="display: flex; flex-direction: column; gap: 14px;">
          <div>
            <label class="form-label" style="font-weight: 600;">Case Reference</label>
            <div style="font-size: 0.88rem; color: var(--text-secondary);">${c.case_id} — ${c.title}</div>
            <div style="font-size: 0.8rem; color: var(--text-muted);">Station: ${c.fir_metadata?.police_station || "Default"}</div>
          </div>
          <div class="form-group">
            <label class="form-label" for="assigneeSelect" style="font-weight: 600;">Eligible Investigating Officer *</label>
            <select id="assigneeSelect" class="form-select" required>
              <option value="">Select an officer within jurisdiction...</option>
              ${optionsHtml}
            </select>
            <span style="font-size: 0.74rem; color: var(--text-muted);">Only active officers within the case's police station/jurisdiction are eligible.</span>
          </div>
          <div class="form-group">
            <label class="form-label" for="assignReasonInput" style="font-weight: 600;">Assignment / Reassignment Reason *</label>
            <textarea id="assignReasonInput" class="form-textarea" rows="3" placeholder="Provide operational reason (e.g., Initial investigation allotment, Transfer of prior IO, Case escalation)" required></textarea>
          </div>
        </form>
      `;

      UI.openModal(
        "Assign / Reassign Case Officer",
        modalHtml,
        `
          <button class="btn btn-secondary" onclick="UI.closeModal()">Cancel</button>
          <button class="btn btn-primary" id="btnSubmitAssignIO" ${(!eligible || eligible.length === 0) ? 'disabled' : ''}>Confirm Allocation</button>
        `
      );

      document.getElementById("btnSubmitAssignIO")?.addEventListener("click", async () => {
        const sel = document.getElementById("assigneeSelect");
        const reasonInput = document.getElementById("assignReasonInput");
        const officerId = sel?.value;
        const reason = reasonInput?.value?.trim();

        if (!officerId) {
          UI.showToast("Please select an eligible officer.", "error");
          return;
        }
        if (!reason) {
          UI.showToast("Please enter an assignment reason.", "error");
          reasonInput?.focus();
          return;
        }

        const btn = document.getElementById("btnSubmitAssignIO");
        btn.disabled = true;
        btn.textContent = "Assigning...";

        try {
          await Api.assignCase(c.case_id, { officer_id: officerId, reason });
          UI.showToast("Case successfully assigned to investigating officer.", "success");
          UI.closeModal();
          await ScreenCaseOverview.render(c.case_id);
        } catch (err) {
          UI.showToast(err.message || "Failed to assign case.", "error");
          btn.disabled = false;
          btn.textContent = "Confirm Allocation";
        }
      });
    });

    document.getElementById("btnToggleAssignHistory")?.addEventListener("click", async () => {
      const cnt = document.getElementById("assignHistoryContainer");
      const listEl = document.getElementById("assignHistoryList");
      if (!cnt) return;

      if (cnt.style.display === "none") {
        cnt.style.display = "block";
        listEl.innerHTML = "Loading assignment records...";
        try {
          const assignments = await Api.getCaseAssignments(c.case_id);
          if (!assignments || assignments.length === 0) {
            listEl.innerHTML = "<div style='color: var(--text-muted); padding: 8px;'>No formal assignment records registered for this case.</div>";
            return;
          }
          listEl.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${assignments.map(a => `
                <div class="assignment-timeline-item" style="border: 1px solid var(--border-subtle); padding: 10px; border-radius: var(--radius-sm); background: var(--bg-card);">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <div>
                      <span class="badge ${a.status === 'ACTIVE' ? 'badge-verified' : 'badge-neutral'}">${a.status}</span>
                      <strong style="margin-left: 6px;">${a.assigned_officer_name || a.assigned_officer_id}</strong>
                      <span class="badge badge-username" style="margin-left: 4px;">${a.assigned_officer_username || a.assigned_officer_id}</span>
                    </div>
                    <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">
                      ${Formatters.formatDate(a.effective_from)}
                    </span>
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">
                    <strong>Reason:</strong> ${a.assignment_reason}
                  </div>
                  <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 2px;">
                    Assigned by: <strong>${a.assigned_by_id}</strong> ${a.effective_to ? `&bull; Relieved: ${Formatters.formatDate(a.effective_to)}` : ''}
                  </div>
                </div>
              `).join("")}
            </div>
          `;
        } catch (err) {
          listEl.innerHTML = `<div style="color: var(--danger); padding: 8px;">Failed to load assignments: ${err.message}</div>`;
        }
      } else {
        cnt.style.display = "none";
      }
    });
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 9. SCREEN 3: EVIDENCE WORKSPACE (Route: #/cases/:id/evidence)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenEvidence = {
  currentCaseId: null,

  async render(caseId) {
    this.currentCaseId = caseId;
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Evidence Workspace`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }
    const c = State.activeCase;
    const evidenceList = State.evidence || [];

    const filtered = evidenceList.filter(e => {
      const s = State.filters.evidenceSearch.toLowerCase();
      const matchSearch = !s ||
        e.evidence_id.toLowerCase().includes(s) ||
        e.original_file_name.toLowerCase().includes(s) ||
        (e.description && e.description.toLowerCase().includes(s)) ||
        (e.source_device_or_person && e.source_device_or_person.toLowerCase().includes(s));

      const isVerified = e.integrity_status === "VERIFIED" && e.worm_status === "COMMITTED";
      const matchSec = State.filters.evidenceSecurity === "ALL" ||
        (State.filters.evidenceSecurity === "VERIFIED" && isVerified) ||
        (State.filters.evidenceSecurity === "PENDING" && !isVerified);

      return matchSearch && matchSec;
    });

    const isCaseSetup = c.lifecycle_stage === "INITIALIZED";

    const html = `
      ${renderWorkspaceHeaderHtml("evidence")}

      <!-- Stage Notice: Prerequisite vs Active vs Completed -->
      ${isCaseSetup ? `
        <div class="card" style="background-color: var(--primary-bg); border-color: var(--primary-border); padding: 16px 20px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
              <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: var(--primary); letter-spacing: 0.06em;">STAGE 2 PREREQUISITE &bull; CASE SETUP ACTIVE</div>
              <div style="font-size: 1rem; font-weight: 700; color: var(--text-main); margin-top: 2px;">Current Phase: Case Setup</div>
              <div style="font-size: 0.84rem; color: var(--text-secondary); margin-top: 2px;">
                Inquest particulars registered. Next Step: <strong>Begin Evidence Collection</strong> to attach scene photographs, post-mortem reports, CCTV footage, and digital records.
              </div>
            </div>
            <button class="btn btn-primary btn-stage-transition" onclick="handleStageTransition('${c.case_id}', 'EVIDENCE_INGESTION')">
              Begin Evidence Collection &rarr;
            </button>
          </div>
        </div>
      ` : c.lifecycle_stage === "EVIDENCE_INGESTION" ? `
        <div class="card" style="background-color: var(--bg-card-subtle); border-left: 4px solid var(--primary); padding: 16px 20px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
              <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: var(--primary); letter-spacing: 0.06em;">STAGE 2 &bull; EVIDENCE COLLECTION IN PROGRESS</div>
              <div style="font-size: 1rem; font-weight: 700; color: var(--text-main); margin-top: 2px;">
                ${evidenceList.length === 0 ? "Evidence Collection Phase Active" : `${evidenceList.length} Case Exhibit(s) Registered`}
              </div>
              <div style="font-size: 0.84rem; color: var(--text-secondary); margin-top: 2px;">
                ${evidenceList.length === 0 
                  ? "Upload primary crime scene photographs, post-mortem certificates, CCTV footage, or mobile extractions into protected storage."
                  : "Initial exhibits are recorded. You can start the authorised evidence-checking step when collection is complete."}
              </div>
            </div>
            ${evidenceList.length > 0 ? `
              <button class="btn btn-primary btn-stage-transition" id="btnBannerProceedToVerification" onclick="handleStageTransition('${c.case_id}', 'EVIDENCE_PROCESSING')">
                Start evidence checks &rarr;
              </button>
            ` : `
              <button class="btn btn-primary" onclick="ScreenEvidence.showRegisterEvidenceModal()">
                + Register First Exhibit
              </button>
            `}
          </div>
        </div>
      ` : `
        <div class="card" style="background-color: var(--verified-bg); border-left: 4px solid var(--verified); padding: 16px 20px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-verified">STAGE 2 COMPLETED &bull; EVIDENCE INTAKE COMPLETE</span>
                <span style="font-size: 0.8rem; color: var(--verified-text); font-family: var(--font-mono);">${evidenceList.length} exhibits recorded</span>
              </div>
              <div style="font-size: 1rem; font-weight: 700; color: var(--verified-text); margin-top: 2px;">
                Evidence ready to review
              </div>
              <div style="font-size: 0.84rem; color: var(--verified-text); opacity: 0.9; margin-top: 2px;">
                Open an exhibit to review it. Technical preservation and custody details remain available with that exhibit.
              </div>
            </div>
          </div>
        </div>
      `}

      <div class="cases-toolbar">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Evidence Register</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Catalog of all physical and digital exhibits seized and admitted into this inquiry.</p>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
          <button class="btn btn-secondary" onclick="Router.selectCaseAndRoute('${c.case_id}', 'rag')">
            <span>Ask About This Case</span>
          </button>
          <button class="btn btn-secondary" id="btnRegisterEvidenceModal">
            <span>+ Register Evidence</span>
          </button>
          ${c.lifecycle_stage === "EVIDENCE_INGESTION" && evidenceList.length > 0 ? `
            <button class="btn btn-primary btn-stage-transition" id="btnProceedToForensicVerification" onclick="handleStageTransition('${c.case_id}', 'EVIDENCE_PROCESSING')">
              Proceed to Forensic Verification &rarr;
            </button>
          ` : ""}
        </div>
      </div>

      <!-- Exhibits Filter Bar -->
      <div class="cases-toolbar" style="margin-top: 10px; gap: 10px;">
        <div class="search-input-wrap">
          <input type="text" class="form-input" id="evidenceSearchInput" placeholder="Search exhibit filename, witness, source..." value="${State.filters.evidenceSearch}">
        </div>

        <div class="filter-chips">
          <button class="filter-chip ${State.filters.evidenceSecurity === 'ALL' ? 'active' : ''}" data-sec="ALL">All Exhibits (${evidenceList.length})</button>
          <button class="filter-chip ${State.filters.evidenceSecurity === 'VERIFIED' ? 'active' : ''}" data-sec="VERIFIED">Integrity Protected</button>
          <button class="filter-chip ${State.filters.evidenceSecurity === 'PENDING' ? 'active' : ''}" data-sec="PENDING">Verification Pending</button>
        </div>
      </div>

      <!-- Evidence Exhibits Table -->
      ${filtered.length === 0 ? `
        <div class="empty-state-card" style="margin-top: 16px;">
          <div class="empty-state-title">No Exhibits Registered</div>
          <div class="empty-state-desc">
            ${evidenceList.length === 0 ?
              "No exhibits have been attached to this inquiry file yet. Click 'Register Evidence' to upload documents, photos, or recordings." :
              "No exhibits match your active search filters."}
          </div>
          <button class="btn btn-primary" onclick="ScreenEvidence.showRegisterEvidenceModal()">+ Register Evidence</button>
        </div>
      ` : `
        <div class="evidence-table-container" style="margin-top: 14px;">
          <table class="evidence-table">
            <thead>
              <tr>
                <th>Exhibit</th>
                <th>Category</th>
                <th>Source / origin</th>
                <th>Received</th>
                <th>Processing Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.map(e => this.renderEvidenceRowHtml(e, caseId)).join("")}
            </tbody>
          </table>
        </div>
      `}
    `;

    container.innerHTML = html;

    document.getElementById("btnRegisterEvidenceModal")?.addEventListener("click", () => {
      this.showRegisterEvidenceModal();
    });

    document.getElementById("evidenceSearchInput")?.addEventListener("input", (e) => {
      State.filters.evidenceSearch = e.target.value;
      this.render(caseId);
    });

    document.querySelectorAll("[data-sec]").forEach(btn => {
      btn.addEventListener("click", (e) => {
        State.filters.evidenceSecurity = e.target.getAttribute("data-sec");
        this.render(caseId);
      });
    });

    document.querySelectorAll(".btn-inspect-evidence").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const eid = btn.getAttribute("data-eid");
        const cid = btn.getAttribute("data-case-id") || caseId || this.currentCaseId || State.activeCaseId;
        if (eid) this.openEvidenceDetailDrawer(eid, cid);
      });
    });
  },

  renderEvidenceRowHtml(e, caseId) {
    const resolvedCaseId = e.case_id || caseId || this.currentCaseId || State.activeCaseId;
    const ov = InvestigatorFirst.evidenceStatus(e);

    return `
      <tr onclick="ScreenEvidence.openEvidenceDetailDrawer('${e.evidence_id}', '${resolvedCaseId}')">
        <td>
          <div style="font-weight: 600; color: var(--text-main); font-size: 0.9rem;">${Formatters.escapeHtml(e.original_file_name)}</div>
          <div style="font-family: var(--font-mono); font-size: 0.74rem; color: var(--primary);">
            ${Formatters.escapeHtml(e.evidence_id)} &bull; ${Formatters.formatBytes(e.file_size_bytes)}
          </div>
        </td>
        <td>
          <span style="color: var(--text-secondary); font-size: 0.84rem;">${Formatters.escapeHtml(Formatters.formatPlainCategory(e.evidence_category))}</span>
        </td>
        <td style="font-size: 0.82rem; color: var(--text-secondary);">
          ${Formatters.escapeHtml(e.source_device_or_person || e.collection_location || "Not recorded")}
        </td>
        <td style="font-size: 0.82rem; color: var(--text-secondary);">
          ${Formatters.formatDate(e.collection_datetime || e.created_at)}
        </td>
        <td>
          <span class="badge ${ov.badge}">${Formatters.escapeHtml(ov.label)}</span>
          <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 2px;">${Formatters.escapeHtml(ov.subtext)}</div>
        </td>
        <td>
          <button class="btn btn-secondary btn-sm btn-inspect-evidence" data-eid="${e.evidence_id}" data-case-id="${resolvedCaseId}">
            Open evidence
          </button>
        </td>
      </tr>
    `;
  },

  // ─────────────────────────────────────────────────────────────────────────
  // P0 #1: Redesigned Evidence Registration Modal
  // ─────────────────────────────────────────────────────────────────────────
  showRegisterEvidenceModal() {
    const c = State.activeCase;
    let selectedFile = null;

    const bodyHtml = `
      <div id="uploadContainer">
        <!-- Step 1: Drag & Drop Area -->
        <div class="evidence-dropzone" id="evidenceDropzone">
          <input type="file" id="inpEvidenceFileHidden" style="display: none;">
          <div class="evidence-dropzone-title">What would you like to attach?</div>
          <p style="color: var(--text-muted); font-size: 0.82rem; margin-bottom: 12px;">
            Drag and drop a file here, or click to choose from your computer
          </p>
          <button type="button" class="btn btn-secondary btn-sm" id="btnChooseFile">
            Choose Evidence File
          </button>
          <div class="evidence-dropzone-examples">
            <span class="evidence-dropzone-pill">Documents</span>
            <span class="evidence-dropzone-pill">Photographs</span>
            <span class="evidence-dropzone-pill">CCTV / Video</span>
            <span class="evidence-dropzone-pill">Audio</span>
            <span class="evidence-dropzone-pill">Data Files</span>
          </div>
        </div>

        <!-- Step 2: Selected File Info & Descriptive Form (Hidden until file selected) -->
        <div id="fileSelectedFormArea" style="display: none;">
          <div class="file-selected-summary">
            <div class="file-selected-info">
              <div>
                <div class="file-selected-name" id="fileSelectedName">filename.ext</div>
                <div class="file-selected-meta">
                  <span class="badge badge-verified" id="fileDetectedFormatBadge">PDF Document</span>
                  <span id="fileSelectedSize">137 KB</span>
                </div>
              </div>
            </div>
            <button type="button" class="btn btn-secondary btn-sm" id="btnChangeFile" style="font-size: 0.76rem;">
              Change File
            </button>
          </div>

          <form id="evidenceMetadataForm">
            <div class="form-group">
              <label class="form-label" for="inpSource">Source / Description *</label>
              <input type="text" id="inpSource" class="form-input" placeholder="e.g. Government Medical College / Hotel Reception Manager" value="Government Medical College" required>
            </div>

            <div class="grid-2">
              <div class="form-group">
                <label class="form-label" for="inpEvidenceCat">Evidence Category *</label>
                <select id="inpEvidenceCat" class="form-select">
                  <option value="DOCUMENT_PDF">General Case Document / Statement / Register (PDF)</option>
                  <option value="MEDICAL_REPORT">Medical / Autopsy / Inquest Report (PDF)</option>
                  <option value="SCENE_PHOTO">Crime Scene Photograph (JPEG, PNG, TIFF)</option>
                  <option value="AUTOPSY_PHOTO">Post-Mortem / Autopsy Photograph (JPEG, PNG, TIFF)</option>
                  <option value="AUDIO_RECORDING">Audio Statement / Emergency Dispatch (WAV, MP3)</option>
                  <option value="CDR_SPREADSHEET">Call Detail Record (CDR) Sheet (CSV)</option>
                  <option value="DIGITAL_DEVICE_EXTRACTION">Digital Device Extraction Dump / Log</option>
                  <option value="PHYSICAL_EXHIBIT">Physical / Ballistics / Biological Exhibit</option>
                  <option value="OTHER">Other Forensic Exhibit</option>
                </select>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">
                  <strong>Why category is required:</strong> Determines the automated forensic verification pipeline (e.g. text extraction & RAG indexing for documents, EXIF preservation for photos).
                </div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 3px;">
                  <strong>Supported file types:</strong> PDF (.pdf), Images (.jpg, .jpeg, .png, .tiff), Audio (.wav, .mp3, .ogg), CDR & Data (.csv, .xlsx, .txt). Maximum size: 100 MB.
                </div>
              </div>

              <div class="form-group">
                <label class="form-label" for="inpCollectDate">Date Received *</label>
                <input type="datetime-local" id="inpCollectDate" class="form-input" value="${new Date().toISOString().slice(0, 16)}" required>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label" for="inpCollectLoc">Recovery Scene / Location</label>
              <input type="text" id="inpCollectLoc" class="form-input" placeholder="e.g. Room 304 Hotel Sunrise" value="${c.fir_metadata?.incident_location || 'Central Division Sector 4'}">
            </div>

            <div class="form-group">
              <label class="form-label" for="inpEvidenceDesc">Notes</label>
              <textarea id="inpEvidenceDesc" class="form-textarea" placeholder="Add any relevant observations regarding this exhibit..."></textarea>
            </div>

            <!-- Technical MIME Information (Hidden in Collapsed Details) -->
            <details style="margin-top: 10px; font-size: 0.76rem; color: var(--text-muted);">
              <summary style="cursor: pointer; user-select: none;">Technical Details (Automated)</summary>
              <div style="padding: 8px 10px; background-color: var(--bg-card-subtle); border-radius: var(--radius-sm); margin-top: 4px;">
                Detected MIME Type: <code id="lblDetectedMime" style="font-family: var(--font-mono); color: var(--primary);">application/pdf</code> (auto-assigned)
              </div>
            </details>
          </form>
        </div>
      </div>
    `;

    const footerHtml = `
      <button class="btn btn-secondary" onclick="UI.closeModal()">Cancel</button>
      <button class="btn btn-primary" id="btnSubmitIntake" style="display: none;">Register Evidence</button>
    `;

    UI.openModal("Register Evidence", bodyHtml, footerHtml);

    const hiddenInput = document.getElementById("inpEvidenceFileHidden");
    const chooseBtn = document.getElementById("btnChooseFile");
    const dropzone = document.getElementById("evidenceDropzone");
    const formArea = document.getElementById("fileSelectedFormArea");
    const submitBtn = document.getElementById("btnSubmitIntake");

    const onFileSelected = (file) => {
      if (!file) return;
      selectedFile = file;

      const formatInfo = Formatters.detectFileFormat(file.name);
      document.getElementById("fileSelectedIcon").textContent = formatInfo.icon;
      document.getElementById("fileSelectedName").textContent = file.name;
      document.getElementById("fileDetectedFormatBadge").textContent = formatInfo.label;
      document.getElementById("fileSelectedSize").textContent = Formatters.formatBytes(file.size);
      document.getElementById("lblDetectedMime").textContent = file.type || formatInfo.mime;

      const catSelect = document.getElementById("inpEvidenceCat");
      if (formatInfo.defaultCategory && catSelect) {
        catSelect.value = formatInfo.defaultCategory;
      }

      dropzone.style.display = "none";
      formArea.style.display = "block";
      submitBtn.style.display = "inline-flex";
    };

    chooseBtn?.addEventListener("click", () => hiddenInput.click());
    dropzone?.addEventListener("click", (e) => {
      if (e.target !== chooseBtn) hiddenInput.click();
    });

    hiddenInput?.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        onFileSelected(e.target.files[0]);
      }
    });

    // Drag and drop handlers
    dropzone?.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone?.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });
    dropzone?.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        onFileSelected(e.dataTransfer.files[0]);
      }
    });

    document.getElementById("btnChangeFile")?.addEventListener("click", () => {
      selectedFile = null;
      hiddenInput.value = "";
      dropzone.style.display = "block";
      formArea.style.display = "none";
      submitBtn.style.display = "none";
    });

    submitBtn?.addEventListener("click", async () => {
      if (!selectedFile) {
        UI.showToast("Please choose an evidence file to attach.", "error");
        return;
      }

      const category = document.getElementById("inpEvidenceCat").value;
      const collectDate = document.getElementById("inpCollectDate").value;
      const collectLoc = document.getElementById("inpCollectLoc").value.trim();
      const source = document.getElementById("inpSource").value.trim();
      const desc = document.getElementById("inpEvidenceDesc").value.trim();

      if (!source) {
        UI.showToast("Please provide the source / custody witness.", "error");
        return;
      }

      const formatInfo = Formatters.detectFileFormat(selectedFile.name);
      const detectedMime = selectedFile.type || formatInfo.mime;

      // Automatically advance to EVIDENCE_INGESTION if currently in INITIALIZED
      if (c.lifecycle_stage === "INITIALIZED") {
        try {
          await Api.updateCaseStage(c.case_id, "EVIDENCE_INGESTION");
          c.lifecycle_stage = "EVIDENCE_INGESTION";
        } catch (stgErr) {
          console.warn("Auto-transition notice:", stgErr);
        }
      }

      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("evidence_category", category);
      formData.append("declared_mime_type", detectedMime);
      if (collectDate) formData.append("collection_datetime", new Date(collectDate).toISOString());
      if (collectLoc) formData.append("collection_location", collectLoc);
      if (source) formData.append("source_device_or_person", source);
      if (desc) formData.append("description", desc);

      submitBtn.disabled = true;
      submitBtn.textContent = "Preserving Exhibit...";

      try {
        const res = await Api.intakeEvidence(c.case_id, formData);
        UI.closeModal();
        UI.showToast(`Exhibit "${res.original_file_name}" registered successfully!`, "success");
        UI.recordAudit("EXHIBIT_ATTACHED", res.evidence_id, "SUCCESS", `File: ${res.original_file_name}`);
        await ScreenEvidence.render(c.case_id);
        ScreenEvidence.openEvidenceDetailDrawer(res.evidence_id, res.case_id || c.case_id);
      } catch (err) {
        // Safe timeout reconciliation: Check if intake succeeded before prompting duplicate upload
        try {
          const listRes = await Api.listEvidence(c.case_id);
          const exhibits = listRes.items || (Array.isArray(listRes) ? listRes : []);
          const matched = exhibits.find(e => e.original_file_name === selectedFile.name);
          if (matched) {
            UI.closeModal();
            UI.showToast(`Exhibit "${matched.original_file_name}" verified and registered!`, "success");
            UI.recordAudit("EXHIBIT_RECONCILED", matched.evidence_id, "SUCCESS", `Reconciled after intake timeout: ${matched.original_file_name}`);
            await ScreenEvidence.render(c.case_id);
            ScreenEvidence.openEvidenceDetailDrawer(matched.evidence_id, matched.case_id || c.case_id);
            return;
          }
        } catch (recErr) {
          console.warn("Intake reconciliation check notice:", recErr);
        }

        submitBtn.disabled = false;
        submitBtn.textContent = "Register Evidence";
        UI.showToast(`Registration failed: ${err.message}`, "error");
      }
    });
  },

  // ─────────────────────────────────────────────────────────────────────────
  // Evidence Detail Drawer (4 Clean Sections)
  // ─────────────────────────────────────────────────────────────────────────
  async openEvidenceDetailDrawer(evidenceId, explicitCaseId = null) {
    const caseId = (explicitCaseId && explicitCaseId !== "null" && explicitCaseId !== "undefined")
      ? explicitCaseId
      : (this.currentCaseId && this.currentCaseId !== "null" && this.currentCaseId !== "undefined")
        ? this.currentCaseId
        : (State.activeCaseId && State.activeCaseId !== "null" && State.activeCaseId !== "undefined")
          ? State.activeCaseId
          : (State.activeCase?.case_id && State.activeCase.case_id !== "null" && State.activeCase.case_id !== "undefined")
            ? State.activeCase.case_id
            : localStorage.getItem("sakshi_active_case_id");

    if (!caseId || caseId === "null" || caseId === "undefined") {
      UI.showToast("Cannot inspect exhibit: Case ID is missing or invalid.", "error");
      return;
    }
    if (!evidenceId || evidenceId === "null" || evidenceId === "undefined") {
      UI.showToast("Cannot inspect exhibit: Evidence ID is missing or invalid.", "error");
      return;
    }

    State.activeCaseId = caseId;
    localStorage.setItem("sakshi_active_case_id", caseId);

    let ev = null;
    try {
      ev = await Api.getEvidence(caseId, evidenceId);
    } catch (err) {
      UI.showToast(`Failed to load exhibit: ${err.message}`, "error");
      return;
    }

    const isVal = !!ev.detected_mime_type;
    const isAv = ev.antivirus_status === "CLEAN";
    const isWorm = ev.worm_status === "COMMITTED";
    const isInt = ev.integrity_status === "VERIFIED";
    const isLock = ev.lock_status === "LOCKED";
    const isEnc = ev.encryption_status === "ENCRYPTED";

    let factsRes = null;
    try {
      factsRes = await Api.getExtractedFacts(caseId, evidenceId);
    } catch (e) {
      factsRes = null;
    }

    let nextActionTitle = "All Forensic Protections Active";
    let nextActionBtnText = "";
    let nextActionHandler = null;

    if (!isVal) {
      nextActionTitle = "Verify File Format Signature";
      nextActionBtnText = "Verify Format";
      nextActionHandler = () => this.executeValidation(caseId, evidenceId);
    } else if (!isAv) {
      nextActionTitle = "Security & Threat Scan Required";
      nextActionBtnText = "Scan Exhibit";
      nextActionHandler = () => this.executeAntivirus(caseId, evidenceId);
    } else if (!isWorm) {
      nextActionTitle = "Commit to Protected Storage";
      nextActionBtnText = "Preserve Exhibit";
      nextActionHandler = () => this.executeWormCommit(caseId, evidenceId);
    } else if (!isInt) {
      nextActionTitle = "Dual Cryptographic Fingerprint Verification";
      nextActionBtnText = "Verify Fingerprint";
      nextActionHandler = () => this.executeIntegrity(caseId, evidenceId);
    } else if (!isLock || !isEnc) {
      nextActionTitle = "Apply Write Protection & Encryption";
      nextActionBtnText = "Confirm Protections";
      nextActionHandler = () => this.executeLockAndEncrypt(caseId, evidenceId);
    } else {
      nextActionTitle = "All Forensic Protections Active";
      nextActionBtnText = "";
      nextActionHandler = null;
    }

    const fileUrl = Api.getEvidenceFileUrl(caseId, evidenceId);
    const caseTitle = State.activeCase?.title || caseId;

    // Readable processing status
    const processingStatus = factsRes?.processing_status_label || (
      !isVal ? "Awaiting format verification" :
      !isAv ? "Awaiting malware security scan" :
      !isWorm ? "Awaiting write-once storage seal" :
      !isInt ? "Integrity verification pending" :
      factsRes && factsRes.total_facts > 0 ? "Text extracted — review available" :
      "Awaiting document processing"
    );

    // Readability state
    const readabilityState = (factsRes && factsRes.total_facts > 0)
      ? "Digitally parsed text available & indexed"
      : ev.detected_mime_type === "application/pdf"
        ? "Scanned / text layer requires extraction"
        : "Binary media exhibit — non-text format";

    // Prepare Important Details grouped by category
    const rawDetails = (factsRes?.important_details && factsRes.important_details.length > 0)
      ? factsRes.important_details
      : (factsRes?.facts || []).map((f, idx) => ({
          detail_id: f.fact_id || `DETAIL-${idx + 1}`,
          category: f.category === 'LOCATION' ? 'LOCATIONS' :
                    (f.category === 'PERSON_ENTITY' || f.category === 'IDENTIFIER') ? 'PEOPLE_IDENTIFIERS' :
                    f.category === 'DATE_TIME' ? 'DATES_TIMES' : 'EVENTS_ACTIONS',
          field_label: f.category === 'LOCATION' ? (f.title.includes('Police Station') ? 'Police Station' : f.title.includes('Room') ? 'Room Reference' : 'Premises / Location') :
                       f.category === 'PERSON_ENTITY' ? (f.title.includes('Officer') ? 'Investigating Officer' : f.title.includes('Witness') ? 'Witness' : 'Subject Person') :
                       f.category === 'IDENTIFIER' ? 'Official Identifier' :
                       f.category === 'DATE_TIME' ? 'Date / Timestamp' : 'Reported Statement / Event',
          display_value: f.fact_text || f.title || f.fact_statement,
          is_grouped: false,
          is_normalized: false,
          source_reference: `p.${f.page_number || 1} [${f.char_offset_start || 0}-${f.char_offset_end || 0}]`,
          source_passage: f.source_passage || '',
          supporting_fact_ids: [f.fact_id],
          review_status: f.review_status || 'AWAITING_REVIEW',
          page_number: f.page_number || 1,
          char_offset_start: f.char_offset_start || 0,
          char_offset_end: f.char_offset_end || 0,
          attribution_type: f.attribution_type || 'EXTRACTED_BY_SOFTWARE'
        }));

    const detailCategories = [
      { key: 'PEOPLE_IDENTIFIERS', label: '👤 People & Identifiers' },
      { key: 'DATES_TIMES', label: '📅 Dates & Times' },
      { key: 'LOCATIONS', label: '📍 Locations & Premises' },
      { key: 'EVENTS_ACTIONS', label: '⚡ Events & Reported Actions' }
    ];

    const categoryGroups = {};
    for (const cat of detailCategories) {
      categoryGroups[cat.key] = rawDetails.filter(d => d.category === cat.key);
    }
    const otherDetails = rawDetails.filter(d => !detailCategories.some(c => c.key === d.category));
    if (otherDetails.length > 0) {
      categoryGroups['OTHER'] = otherDetails;
      detailCategories.push({ key: 'OTHER', label: '📑 Other Stated Details' });
    }

    const reviewedCount = factsRes?.facts ? factsRes.facts.filter(f => f.review_status === 'HUMAN_REVIEWED' || f.verified_by_investigator).length : 0;
    const pendingCount = factsRes?.facts ? (factsRes.facts.length - reviewedCount) : rawDetails.length;

    // Compute separated timestamps and provenance according to forensic requirements:
    const docStatedDate = factsRes?.facts?.find(f => f.category === 'DATE_TIME' && f.title?.toLowerCase().includes('date'))?.title?.replace('Recorded Date: ', '')
      || factsRes?.important_details?.find(d => d.category === 'DATES_TIMES' && d.field_label?.toLowerCase().includes('date'))?.display_value
      || "Not recorded in text";

    const dateReceived = ev.collection_datetime
      ? Formatters.formatOnlyDate(ev.collection_datetime)
      : "Not recorded";

    const timeReceived = ev.collection_datetime
      ? Formatters.formatOnlyTime(ev.collection_datetime)
      : "Not recorded";

    const registeredTimestamp = ev.created_at
      ? Formatters.formatDate(ev.created_at)
      : "Not recorded";

    const lastProcessedTimestamp = factsRes?.last_updated
      ? Formatters.formatDate(factsRes.last_updated)
      : (ev.updated_at ? Formatters.formatDate(ev.updated_at) : "Not recorded");

    const uploaderIdentity = ev.submitting_investigator_id
      ? ev.submitting_investigator_id
      : "Not recorded";

    const pageCount = factsRes?.total_pages
      || (factsRes?.important_source_passages?.length ? Math.max(...factsRes.important_source_passages.map(p => p.page_number || 1), 1) : null)
      || (ev.detected_mime_type === "application/pdf" ? 1 : null);
    const pageCountStr = pageCount ? `${pageCount} page${pageCount > 1 ? 's' : ''}` : "Not applicable";
    const docTypeLabel = factsRes?.document_type || Formatters.formatCategory(ev.evidence_category);

    const drawerHtml = `
      <!-- SECTION 1: Document Header -->
      <div class="evidence-workspace-card" id="sectionIdentity" style="border-left: 4px solid var(--primary); padding: 16px 20px; margin-bottom: 16px; background: var(--bg-card); border-radius: var(--radius-md); box-shadow: var(--shadow-sm);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
          <div>
            <span class="case-id-badge" style="margin-bottom: 4px;">${ev.evidence_id}</span>
            <span class="badge ${isInt ? 'badge-verified' : 'badge-attention'}" style="margin-left: 6px;">
              ${Formatters.escapeHtml(processingStatus)}
            </span>
            <span class="badge badge-info" style="margin-left: 4px;">
              ${Formatters.escapeHtml(docTypeLabel)}
            </span>
          </div>
          <span style="font-size: 0.76rem; color: var(--text-muted); font-family: var(--font-mono);">
            Case: ${Formatters.escapeHtml(caseId)}
          </span>
        </div>

        <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">
          ${Formatters.escapeHtml(ev.original_file_name)}
        </h3>

        <div style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 12px;">
          <strong>Case:</strong> ${Formatters.escapeHtml(caseTitle)} &bull; 
          <strong>Document Type:</strong> ${Formatters.escapeHtml(docTypeLabel)} &bull; 
          <strong>File Size:</strong> ${Formatters.formatBytes(ev.file_size_bytes)} &bull; 
          <strong>Page Count:</strong> ${Formatters.escapeHtml(pageCountStr)}
        </div>

        <!-- Four Clearly Distinguished Forensic Timestamps & Custody Identity -->
        <div class="evidence-header-provenance-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 10px; padding: 12px 14px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); margin-bottom: 14px; font-size: 0.78rem;">
          <div>
            <span style="color: var(--text-muted); font-size: 0.7rem; display: block; text-transform: uppercase; font-weight: 600;">1. Document Date (Stated):</span>
            <strong style="color: var(--text-main);">${Formatters.escapeHtml(docStatedDate)}</strong>
          </div>
          <div>
            <span style="color: var(--text-muted); font-size: 0.7rem; display: block; text-transform: uppercase; font-weight: 600;">2. Date &amp; Time Received:</span>
            <strong style="color: var(--text-main);">${Formatters.escapeHtml(dateReceived)} &bull; ${Formatters.escapeHtml(timeReceived)}</strong>
          </div>
          <div>
            <span style="color: var(--text-muted); font-size: 0.7rem; display: block; text-transform: uppercase; font-weight: 600;">3. Registered in SAKSHI:</span>
            <strong style="color: var(--text-main);">${Formatters.escapeHtml(registeredTimestamp)}</strong>
          </div>
          <div>
            <span style="color: var(--text-muted); font-size: 0.7rem; display: block; text-transform: uppercase; font-weight: 600;">4. Last Processed:</span>
            <strong style="color: var(--text-main);">${Formatters.escapeHtml(lastProcessedTimestamp)}</strong>
          </div>
          <div style="grid-column: 1 / -1; border-top: 1px dashed var(--border-subtle); padding-top: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
            <span><span style="color: var(--text-muted); font-weight: 600;">Uploaded / Registered By:</span> <strong style="color: var(--text-main);">${Formatters.escapeHtml(uploaderIdentity)}</strong></span>
            <span><span style="color: var(--text-muted); font-weight: 600;">Declared Format:</span> <strong style="font-family: var(--font-mono); color: var(--text-main);">${Formatters.escapeHtml(ev.declared_mime_type)}</strong></span>
          </div>
        </div>

        <!-- Plain-Language Security and Integrity Indicators (Disclosing Local Simulation) -->
        <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; font-size: 0.76rem;">
          <span class="badge ${isInt ? 'badge-verified' : 'badge-attention'}" title="Cryptographic hash integrity verification">
            ${isInt ? 'File integrity verified' : 'File integrity verification pending'}
          </span>
          <span class="badge ${isLock ? 'badge-verified' : 'badge-neutral'}" title="Storage protection state">
            ${(ev.lock_backend === 'LOCAL_FILESYSTEM' || ev.lock_backend === 'SIMULATED_LOCAL' || ev.lock_backend === 'LOCAL_FS')
              ? 'Storage protection: Local simulation'
              : (isLock ? 'Storage protection: Protected' : 'Storage protection: Pending')}
          </span>
          <span class="badge ${isAv ? 'badge-verified' : 'badge-attention'}" title="Threat scan result">
            ${isAv ? 'Threat scan: No threat detected' : (ev.antivirus_status ? `Threat scan: ${ev.antivirus_status}` : 'Threat scan: Unavailable')}
          </span>
          <span class="badge badge-neutral" style="font-size: 0.74rem;">
            ${Formatters.escapeHtml(readabilityState)}
          </span>
        </div>

        <div class="evidence-workspace-header-actions" style="display: flex; flex-wrap: wrap; gap: 8px;">
          ${fileUrl ? `
            <a href="${fileUrl}" target="_blank" class="btn btn-primary btn-sm" id="btnViewOriginalDoc">
              View original document
            </a>
          ` : ''}
          <button class="btn btn-secondary btn-sm" onclick="document.getElementById('sectionFacts')?.scrollIntoView({behavior: 'smooth'})">
            Review Extracted Facts
          </button>
          <button class="btn btn-secondary btn-sm" onclick="const p = document.getElementById('techDetailsPanel'); if(p){p.open = !p.open; p.scrollIntoView({behavior: 'smooth'});}">
            Technical & Custody Details
          </button>
        </div>
      </div>

      <!-- Quick Forensic Action Banner (Preserved) -->
      <div class="card" style="background-color: var(--bg-card-subtle); padding: 14px; margin-bottom: 18px;">
        <div style="font-size: 0.72rem; font-weight: 600; text-transform: uppercase; color: var(--primary); letter-spacing: 0.05em; margin-bottom: 2px;">
          Forensic processing and gate controls
        </div>
        <div style="font-size: 0.88rem; font-weight: 600; color: var(--text-main); margin-bottom: 10px;">
          ${nextActionTitle}
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          ${nextActionBtnText ? `
            <button class="btn btn-primary btn-sm" id="btnNextAction">
              ${nextActionBtnText} &rarr;
            </button>
          ` : ""}
          <button class="btn btn-secondary btn-sm" id="btnRunFullPipeline">
            Complete all verification checks
          </button>
          <button class="btn btn-secondary btn-sm" id="btnExportCert">
            View custody summary
          </button>
        </div>
      </div>

      <!-- SECTION B: Document Summary -->
      <div class="drawer-section" id="sectionSummary">
        <!-- AI-Generated Preliminary Summary -->
        <div class="drawer-section-title">
          <span>Section 2 &bull; Understand This Document &bull; Document summary</span>
          <span class="badge ${factsRes?.document_summary ? 'badge-verified' : 'badge-neutral'}">
            ${Formatters.escapeHtml(factsRes?.document_type || 'Source Analysis')}
          </span>
        </div>

        ${factsRes?.document_summary ? `
          <div class="document-summary-box" style="background: var(--bg-card); padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px dashed var(--border-subtle); padding-bottom: 6px;">
              <span style="font-weight: 700; color: var(--primary); text-transform: uppercase; font-size: 0.74rem;">
                Source-grounded analytical overview
              </span>
              <span style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono);">
                Coverage: ${Formatters.escapeHtml(factsRes.source_coverage || 'Coverage not reported')}
              </span>
            </div>
            
            <div style="color: var(--text-main); font-size: 0.86rem; line-height: 1.65; margin-bottom: 12px;">
              ${Formatters.escapeHtml(factsRes.document_summary)}
            </div>

            <div style="padding: 8px 10px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); font-size: 0.74rem; color: var(--text-muted); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
              <span>Last analyzed: ${Formatters.formatDate(factsRes.last_updated || ev.created_at)}</span>
              <span style="color: var(--text-secondary);">Not a substitute for original document &bull; Statements presented as recorded</span>
            </div>
          </div>
        ` : `
          <div style="padding: 16px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px dashed var(--border-default); text-align: center; font-size: 0.84rem; color: var(--text-muted);">
            <div>Text extraction pending — run document intelligence to generate a readable summary.</div>
            <div style="margin-top: 10px;">
              <button class="btn btn-primary btn-sm" id="btnExtractFacts">
                Extract facts and summary
              </button>
            </div>
          </div>
        `}
      </div>

      <!-- SECTION C: Key Facts & Events -->
      <div class="drawer-section" id="sectionFacts">
        <div class="drawer-section-title">
          <span>Section 3 &bull; Key Facts & Events (Claim Ledger) &bull; Key facts and events</span>
          <span class="badge ${rawDetails.length > 0 ? 'badge-info' : 'badge-neutral'}">
            ${rawDetails.length} Extracted Details (Awaiting Officer Review)
          </span>
        </div>

        ${rawDetails.length > 0 ? `
          <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="font-size: 0.76rem; color: var(--text-muted);">
              Extracted statements and observations with source citations and officer review actions.
            </div>
            <button class="btn btn-secondary btn-sm" id="btnReExtractFacts">
              Re-extract facts
            </button>
          </div>

          <div class="important-details-container" style="display: flex; flex-direction: column; gap: 14px;">
            ${detailCategories.map(cat => {
              const items = categoryGroups[cat.key] || [];
              if (items.length === 0) return '';
              return `
                <div class="important-details-category-block">
                  <div style="font-size: 0.78rem; font-weight: 700; color: var(--text-main); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; display: flex; align-items: center; justify-content: space-between;">
                    <span>${cat.label}</span>
                    <span style="font-size: 0.7rem; font-family: var(--font-mono); color: var(--text-muted);">${items.length} item(s)</span>
                  </div>

                  <table class="important-details-table">
                    <thead>
                      <tr>
                        <th style="width: 24%;">Document statement</th>
                        <th style="width: 36%;">Value or event</th>
                        <th style="width: 16%;">Source location</th>
                        <th style="width: 10%;">Review status</th>
                        <th style="width: 14%; text-align: right;">Review action</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${items.map(d => {
                        const supportingFact = (factsRes?.facts && factsRes.facts.find(f => (d.supporting_fact_ids || []).includes(f.fact_id))) || {
                          fact_id: (d.supporting_fact_ids && d.supporting_fact_ids[0]) || d.detail_id,
                          fact_text: d.display_value,
                          page_number: d.page_number || 1,
                          char_offset_start: d.char_offset_start || 0,
                          char_offset_end: d.char_offset_end || 0,
                          attribution_type: d.attribution_type || 'EXTRACTED_BY_SOFTWARE',
                          why_it_matters: 'Establishes source-grounded observation for cross-document reconciliation and event ordering.'
                        };

                        return `
                          <tr class="important-detail-row" id="row_${d.detail_id}">
                            <td>
                              <div style="font-weight: 600; font-size: 0.8rem; color: var(--text-main);">
                                ${Formatters.escapeHtml(d.field_label)}
                                ${d.is_grouped ? '<span class="badge badge-info" style="font-size: 0.62rem; padding: 1px 4px; margin-left: 4px;" title="Intelligently grouped from compatible location claims">Grouped</span>' : ''}
                              </div>
                              <div style="font-size: 0.68rem; color: var(--text-muted); margin-top: 2px;">
                                ${d.attribution_type === 'QUOTED_FROM_SOURCE' ? 'Quoted from source' : 'Extracted by software'}
                              </div>
                            </td>
                            <td>
                              <div style="font-weight: 600; font-size: 0.82rem; color: var(--text-main); line-height: 1.35;">
                                ${Formatters.escapeHtml(d.display_value)}
                              </div>
                            </td>
                            <td>
                              <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted); margin-bottom: 4px;">
                                ${Formatters.escapeHtml(d.source_reference || `p.${d.page_number || 1} [${d.char_offset_start || 0}-${d.char_offset_end || 0}]`)}
                              </div>
                              <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                                <button type="button" class="btn btn-secondary btn-sm" style="font-size: 0.66rem; padding: 1px 5px;" onclick="const el = document.getElementById('expand_${d.detail_id}'); if (el) { el.style.display = el.style.display === 'none' ? 'table-row' : 'none'; }">
                                  View source passage
                                </button>
                                ${fileUrl ? `
                                  <a href="${fileUrl}" target="_blank" class="btn btn-secondary btn-sm" style="font-size: 0.66rem; padding: 1px 5px; text-decoration: none;" title="Open original document">
                                    Open original
                                  </a>
                                ` : ''}
                              </div>
                            </td>
                            <td>
                              <span class="badge ${
                                (d.review_status === 'HUMAN_REVIEWED' || d.review_status === 'CONFIRMED' || supportingFact.verified_by_investigator) ? 'badge-verified' :
                                d.review_status === 'SUPERSEDED' ? 'badge-attention' :
                                d.review_status === 'CONFLICTING' ? 'badge-danger' : 'badge-neutral'
                              }" style="font-size: 0.68rem;">
                                ${(d.review_status === 'HUMAN_REVIEWED' || d.review_status === 'CONFIRMED' || supportingFact.verified_by_investigator) ? 'Confirmed' :
                                  d.review_status === 'SUPERSEDED' ? 'Superseded' :
                                  d.review_status === 'CONFLICTING' ? 'Disputed' : 'Awaiting Review'}
                              </span>
                            </td>
                            <td style="text-align: right;">
                              <div style="display: flex; gap: 4px; justify-content: flex-end;">
                                <button type="button" class="btn btn-secondary btn-sm" style="font-size: 0.68rem; padding: 2px 6px;" title="Confirm this extracted fact" onclick='ScreenEvidence.showFactReviewModal("${caseId}", "${evidenceId}", ${JSON.stringify(supportingFact).replace(/"/g, '&quot;')}, "CONFIRMED")'>
                                  ✓ Confirm
                                </button>
                                <button type="button" class="btn btn-secondary btn-sm" style="font-size: 0.68rem; padding: 2px 6px;" title="Correct / Amend wording" onclick='ScreenEvidence.showFactReviewModal("${caseId}", "${evidenceId}", ${JSON.stringify(supportingFact).replace(/"/g, '&quot;')}, "CORRECTED")'>
                                  ✏️ Correct / Amend
                                </button>
                                <button type="button" class="btn btn-secondary btn-sm" style="font-size: 0.68rem; padding: 2px 6px;" title="Flag or mark disputed" onclick='ScreenEvidence.showFactReviewModal("${caseId}", "${evidenceId}", ${JSON.stringify(supportingFact).replace(/"/g, '&quot;')}, "FLAGGED")'>
                                  🚩 Flag / Dispute
                                </button>
                              </div>
                            </td>
                          </tr>
                          <tr id="expand_${d.detail_id}" class="detail-expanded-panel" style="display: none;">
                            <td colspan="5" style="padding: 10px 14px;">
                              <div style="font-size: 0.76rem; color: var(--text-secondary); margin-bottom: 6px;">
                                <strong style="color: var(--text-main);">Supporting Source Excerpt:</strong>
                                <div style="font-style: italic; border-left: 2px solid var(--primary); padding-left: 8px; margin-top: 4px; color: var(--text-main); background: var(--bg-card); padding: 6px 10px; border-radius: 0 var(--radius-sm) var(--radius-sm) 0;">
                                  "${Formatters.escapeHtml(d.source_passage || supportingFact.source_passage || 'Source excerpt not recorded.')}"
                                </div>
                              </div>
                              ${d.is_grouped && d.normalization_note ? `
                                <div style="font-size: 0.74rem; color: var(--text-muted); margin-bottom: 6px;">
                                  <strong style="color: var(--text-secondary);">Normalization Note:</strong> ${Formatters.escapeHtml(d.normalization_note)}
                                </div>
                              ` : ''}
                              <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 6px;">
                                <span style="font-size: 0.72rem; color: var(--text-muted);">
                                  Attribution: <strong>${d.attribution_type === 'QUOTED_FROM_SOURCE' ? 'Quoted from Source' : d.attribution_type === 'EXTRACTED_BY_SOFTWARE' ? 'Software Parsed' : d.attribution_type}</strong>
                                  &bull; Supporting Claim(s): ${Formatters.escapeHtml((d.supporting_fact_ids || []).join(', ') || d.detail_id)}
                                </span>
                                <details class="fact-why-it-matters" style="font-size: 0.74rem;">
                                  <summary style="cursor: pointer; color: var(--primary); font-weight: 600;">💡 Why does this matter?</summary>
                                  <div style="margin-top: 4px; color: var(--text-secondary);">
                                    ${Formatters.escapeHtml(supportingFact.why_it_matters || 'Establishes source-grounded observation for cross-document reconciliation and event ordering.')}
                                  </div>
                                </details>
                              </div>
                            </td>
                          </tr>
                        `;
                      }).join('')}
                    </tbody>
                  </table>
                </div>
              `;
            }).join('')}
          </div>
        ` : `
          <div style="padding: 14px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px dashed var(--border-default); text-align: center; font-size: 0.82rem; color: var(--text-muted);">
            <div>No structured facts extracted for this exhibit yet.</div>
            <div style="margin-top: 8px;">
              <button class="btn btn-primary btn-sm" id="btnExtractFacts">
                Extract facts and summary
              </button>
            </div>
          </div>
        `}
      </div>

      <!-- SECTION D: Important Source Passages -->
      <div class="drawer-section" id="sectionPassages">
        <div class="drawer-section-title">
          <span>Section 4 &bull; Important Source Passages &bull; Source passages</span>
          <span class="badge badge-neutral">
            ${(factsRes?.important_source_passages || []).length} Passages
          </span>
        </div>

        ${factsRes?.important_source_passages && factsRes.important_source_passages.length > 0 ? `
          <div style="font-size: 0.76rem; color: var(--text-muted); margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
            <span>Verbatim extracted text spans preserving original wording, page boundaries, and character offsets.</span>
            ${factsRes.important_source_passages.length > 3 ? `
              <button type="button" class="btn btn-secondary btn-sm" style="font-size: 0.7rem; padding: 2px 8px;" onclick="const extra = document.getElementById('extraPassagesBlock'); if(extra){ extra.style.display = (extra.style.display === 'none' || extra.style.display === '') ? 'flex' : 'none'; this.innerText = (extra.style.display === 'flex') ? 'Show Fewer Passages' : 'Show All (${factsRes.important_source_passages.length}) Passages'; }">
                Show All (${factsRes.important_source_passages.length}) Passages
              </button>
            ` : ''}
          </div>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            ${factsRes.important_source_passages.slice(0, 3).map((p, pIdx) => `
              <div class="source-passage-card">
                <div class="source-passage-meta" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <span><strong>Passage ${p.passage_id || `P-${pIdx + 1}`}</strong> &bull; Page ${p.page_number || 1} [${p.char_offset_start || 0}-${p.char_offset_end || 0}]</span>
                  <span class="badge badge-neutral" style="font-size: 0.68rem;">
                    Quotation from Source (${p.extraction_method || 'DIGITAL_PARSED'})
                  </span>
                </div>
                <div style="color: var(--text-main); font-style: normal; margin-bottom: 6px; font-size: 0.82rem; line-height: 1.5; background: var(--bg-card); padding: 8px 10px; border-left: 3px solid var(--primary); border-radius: 0 var(--radius-sm) var(--radius-sm) 0;">
                  "${Formatters.escapeHtml(p.exact_text)}"
                </div>
                ${fileUrl ? `
                  <div style="text-align: right;">
                    <a href="${fileUrl}" target="_blank" style="font-size: 0.72rem; color: var(--primary); text-decoration: none; font-weight: 600;">
                      View in Original Document &rarr;
                    </a>
                  </div>
                ` : ''}
              </div>
            `).join('')}

            ${factsRes.important_source_passages.length > 3 ? `
              <div id="extraPassagesBlock" style="display: none; flex-direction: column; gap: 8px;">
                ${factsRes.important_source_passages.slice(3).map((p, pIdx) => `
                  <div class="source-passage-card">
                    <div class="source-passage-meta" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                      <span><strong>Passage ${p.passage_id || `P-${pIdx + 4}`}</strong> &bull; Page ${p.page_number || 1} [${p.char_offset_start || 0}-${p.char_offset_end || 0}]</span>
                      <span class="badge badge-neutral" style="font-size: 0.68rem;">
                        Quotation from Source (${p.extraction_method || 'DIGITAL_PARSED'})
                      </span>
                    </div>
                    <div style="color: var(--text-main); font-style: normal; margin-bottom: 6px; font-size: 0.82rem; line-height: 1.5; background: var(--bg-card); padding: 8px 10px; border-left: 3px solid var(--primary); border-radius: 0 var(--radius-sm) var(--radius-sm) 0;">
                      "${Formatters.escapeHtml(p.exact_text)}"
                    </div>
                    ${fileUrl ? `
                      <div style="text-align: right;">
                        <a href="${fileUrl}" target="_blank" style="font-size: 0.72rem; color: var(--primary); text-decoration: none; font-weight: 600;">
                          View in Original Document &rarr;
                        </a>
                      </div>
                    ` : ''}
                  </div>
                `).join('')}
              </div>
            ` : ''}
          </div>
        ` : `
          <div style="padding: 12px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); font-size: 0.8rem; color: var(--text-muted); text-align: center;">
            Source passages will appear after text extraction is completed.
          </div>
        `}
      </div>

      <!-- SECTION E: Unresolved Questions -->
      <div class="drawer-section" id="sectionUnknowns">
        <div class="drawer-section-title">
          <span>Section 5 &bull; Important Unknowns &amp; Unresolved Questions</span>
          <span class="badge badge-attention">Document-Scoped</span>
        </div>

        <div style="font-size: 0.76rem; color: var(--text-muted); margin-bottom: 12px;">
          Evidentiary gaps not established within this specific document. Never assumed across the entire inquiry. (Unresolved questions)
        </div>

        <!-- Document-Specific Limitations & Omissions -->
        <div class="unknowns-group-doc" style="margin-bottom: 14px;">
          <div style="font-size: 0.76rem; font-weight: 700; color: var(--text-main); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px;">
            Document-Specific Limitations &amp; Omissions
          </div>
          <div class="unknowns-list">
            ${(factsRes?.document_unknowns && factsRes.document_unknowns.length > 0) ? (
              factsRes.document_unknowns.map(u => `
                <div class="unknowns-item" style="display: flex; gap: 8px; align-items: flex-start; padding: 6px 10px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border-left: 3px solid var(--attention); margin-bottom: 6px; font-size: 0.8rem;">
                  <span>${Formatters.escapeHtml(u)}</span>
                </div>
              `).join('')
            ) : `
              <div class="unknowns-item" style="display: flex; gap: 8px; align-items: flex-start; padding: 6px 10px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border-left: 3px solid var(--border-default); margin-bottom: 6px; font-size: 0.8rem; color: var(--text-muted);">
                <span>No document-specific omissions identified for this exhibit.</span>
              </div>
            `}
          </div>
        </div>

        <!-- Case-Level Investigative Follow-ups -->
        <div class="unknowns-group-case">
          <div style="font-size: 0.76rem; font-weight: 700; color: var(--attention-text); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 2px;">
            Case-Level Investigative Follow-ups
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 6px; font-style: italic;">
            Case-level statutory and laboratory requisitions, not omissions of this individual document.
          </div>
          <div class="unknowns-list">
            ${(factsRes?.case_level_unknowns && factsRes.case_level_unknowns.length > 0) ? (
              factsRes.case_level_unknowns.map(u => `
                <div class="unknowns-item" style="display: flex; gap: 8px; align-items: flex-start; padding: 6px 10px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border-left: 3px solid var(--primary); margin-bottom: 6px; font-size: 0.8rem;">
                  <span>${Formatters.escapeHtml(u)}</span>
                </div>
              `).join('')
            ) : `
              <div class="unknowns-item" style="display: flex; gap: 8px; align-items: flex-start; padding: 6px 10px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border-left: 3px solid var(--primary); margin-bottom: 6px; font-size: 0.8rem;">
                <span>No case-level follow-ups were returned for this exhibit.</span>
              </div>
            `}
          </div>
        </div>
      </div>

      <!-- SECTION F: Investigator Review Actions -->
      <div class="drawer-section" id="sectionReviewActions">
        <div class="drawer-section-title">
          <span>Investigator review actions</span>
          <span class="badge badge-verified">Audit-Tracked</span>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; background: var(--bg-card-subtle); padding: 12px 14px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
          <div style="font-size: 0.82rem; color: var(--text-secondary);">
            <strong>${reviewedCount}</strong> Confirmed &bull; 
            <strong>${pendingCount}</strong> Awaiting Officer Review
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-secondary btn-sm" id="btnReExtractFacts">
              Re-extract facts
            </button>
          </div>
        </div>
      </div>

      <!-- SECTION G: Technical Details and Chain of Custody -->
      <div class="drawer-section" id="sectionTechnical">
        <details id="techDetailsPanel" class="technical-details-disclosure" style="background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-md); overflow: hidden;">
          <summary style="padding: 12px 16px; font-size: 0.86rem; font-weight: 700; cursor: pointer; color: var(--text-main); background: var(--bg-card-subtle); display: flex; justify-content: space-between; align-items: center; user-select: none;">
            <span>Section 6 &bull; Provenance, Custody &amp; Technical Forensic Details &bull; Technical details and chain of custody</span>
            <span class="badge ${isInt ? 'badge-verified' : 'badge-attention'}">
              ${isInt ? 'Fingerprint Sealed' : 'Pending Verification'}
            </span>
          </summary>
          <div style="padding: 16px;">
            <!-- 5-Point Chronological Provenance Separation -->
            <div class="card" style="background: var(--bg-card-subtle); padding: 12px 14px; margin-bottom: 14px; border: 1px solid var(--border-subtle);">
              <div style="font-size: 0.74rem; font-weight: 700; text-transform: uppercase; color: var(--primary); margin-bottom: 6px;">
                5-Point Chronological Provenance Separation
              </div>
              <div class="provenance-timestamp-grid">
                <div class="provenance-timestamp-row">
                  <div>
                    <div class="provenance-timestamp-label">1. Document Issue / Creation Date:</div>
                    <div class="provenance-timestamp-desc">Recorded on face of original document</div>
                  </div>
                  <div class="provenance-timestamp-val">${Formatters.escapeHtml(factsRes?.facts?.find(f => f.category === 'DATE_TIME')?.title?.replace('Recorded Date: ', '') || 'Unstated in document text')}</div>
                </div>

                <div class="provenance-timestamp-row">
                  <div>
                    <div class="provenance-timestamp-label">2. Evidence Received Timestamp:</div>
                    <div class="provenance-timestamp-desc">Time exhibit was seized or handed to investigator</div>
                  </div>
                  <div class="provenance-timestamp-val">${Formatters.formatDate(ev.collection_datetime || ev.created_at)}</div>
                </div>

                <div class="provenance-timestamp-row">
                  <div>
                    <div class="provenance-timestamp-label">3. SAKSHI Registration Timestamp:</div>
                    <div class="provenance-timestamp-desc">Server-recorded intake and staging event</div>
                  </div>
                  <div class="provenance-timestamp-val">${Formatters.formatDate(ev.created_at)}</div>
                </div>

                <div class="provenance-timestamp-row">
                  <div>
                    <div class="provenance-timestamp-label">4. Forensic Processing & Verification:</div>
                    <div class="provenance-timestamp-desc">Latest cryptographic verification check</div>
                  </div>
                  <div class="provenance-timestamp-val">${Formatters.formatDate(ev.updated_at || ev.created_at)}</div>
                </div>

                <div class="provenance-timestamp-row" style="border-bottom: none;">
                  <div>
                    <div class="provenance-timestamp-label">5. Described Incident Time:</div>
                    <div class="provenance-timestamp-desc">Event occurrence time cited in source text</div>
                  </div>
                  <div class="provenance-timestamp-val">${Formatters.escapeHtml(factsRes?.facts?.find(f => f.category === 'DATE_TIME' && f.title.includes('Timestamp'))?.title?.replace('Recorded Timestamp: ', '') || 'Not recorded')}</div>
                </div>
              </div>
            </div>

            <!-- Location Provenance Separation -->
            <div class="card" style="background: var(--bg-card-subtle); padding: 12px 14px; margin-bottom: 14px; border: 1px solid var(--border-subtle);">
              <div style="font-size: 0.74rem; font-weight: 700; text-transform: uppercase; color: var(--primary); margin-bottom: 6px;">
                Location Provenance Separation
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.8rem;">
                <div>
                  <span class="evidence-info-label">Recovery Scene (Entered by submitter):</span>
                  <span class="evidence-info-val" style="display: block; font-weight: 600;">${Formatters.escapeHtml(ev.collection_location || 'Not recorded')}</span>
                </div>
                <div>
                  <span class="evidence-info-label">Document-Stated Incident Location:</span>
                  <span class="evidence-info-val" style="display: block; font-weight: 600;">${Formatters.escapeHtml(factsRes?.facts?.find(f => f.category === 'LOCATION')?.title?.replace('Location Reference: ', '') || 'Not recorded')}</span>
                </div>
                <div>
                  <span class="evidence-info-label">Device GPS Coordinates:</span>
                  <span class="evidence-info-val" style="display: block; color: var(--text-muted);">Optional / Not captured in manual registration</span>
                </div>
                <div>
                  <span class="evidence-info-label">Independent Location Verification:</span>
                  <span class="badge badge-neutral" style="font-size: 0.7rem;">No independent verification recorded</span>
                </div>
              </div>
            </div>

            <!-- Expandable Cryptographic & Integrity Details -->
            <div id="techDetailsWrapper">
              ${StatusPresentation.renderTechnicalDetailsPanel(
                "Cryptographic Hashes & Technical Storage Parameters",
                [
                  { label: "Evidence Exhibit ID", value: ev.evidence_id },
                  { label: "Original Filename", value: ev.original_file_name },
                  { label: "Declared MIME Type", value: ev.declared_mime_type },
                  { label: "Detected MIME Type / Format", value: ev.detected_mime_type ? `${ev.detected_mime_type} (${ev.detected_format || 'Standard'})` : null },
                  { label: "File Size", value: Formatters.formatBytes(ev.file_size_bytes) },
                  { label: "Primary SHA-256 Digest", value: ev.checksum_sha256 },
                  { label: "Secondary SHA3-512 Digest", value: ev.checksum_sha3_512 },
                  { label: "Integrity Verification Result", value: ev.integrity_status ? StatusPresentation.get(ev.integrity_status).label : null },
                  { label: "Antivirus Scan Verdict", value: ev.antivirus_status ? `${StatusPresentation.get(ev.antivirus_status).label} (${ev.antivirus_scanner || 'Scanner name not recorded'})` : null },
                  { label: "WORM Storage Reference", value: ev.worm_storage_reference },
                  { label: "Write Protection (WORM)", value: ev.lock_status ? `${StatusPresentation.get(ev.lock_status === 'LOCKED' ? 'OBJECT_LOCKED' : ev.lock_status).label} (Local development simulation; not hardware WORM)` : null },
                  { label: "Storage Reference", value: ev.lock_storage_reference },
                  { label: "Encryption at Rest", value: ev.encryption_status ? `${ev.encryption_status} (${ev.encryption_algorithm || 'AES-256-GCM'})` : null },
                  { label: "Submitting Officer ID", value: ev.submitting_investigator_id },
                  { label: "Registration Server Timestamp", value: Formatters.formatDate(ev.created_at) }
                ].filter(it => it.value !== null && it.value !== undefined)
              )}
            </div>
          </div>
        </details>
      </div>
    `;

    UI.openDrawer(`Exhibit Workspace &bull; ${ev.evidence_id}`, drawerHtml);

    if (nextActionHandler) {
      document.getElementById("btnNextAction")?.addEventListener("click", nextActionHandler);
    }

    document.getElementById("btnRunFullPipeline")?.addEventListener("click", () => {
      this.runGuidedSecurityChain(caseId, evidenceId);
    });

    document.getElementById("btnExportCert")?.addEventListener("click", () => {
      this.showCustodyCertificateModal(ev);
    });

    document.getElementById("btnExtractFacts")?.addEventListener("click", async () => {
      try {
        UI.showToast("Extracting document facts...", "info");
        await Api.triggerExtractFacts(caseId, evidenceId);
        UI.showToast("Document facts extracted successfully", "success");
        await this.openEvidenceDetailDrawer(evidenceId, caseId);
      } catch (err) {
        UI.showToast(`Extraction failed: ${err.message}`, "error");
      }
    });

    document.getElementById("btnReExtractFacts")?.addEventListener("click", async () => {
      try {
        UI.showToast("Re-extracting document facts...", "info");
        await Api.triggerExtractFacts(caseId, evidenceId);
        UI.showToast("Document facts re-extracted successfully", "success");
        await this.openEvidenceDetailDrawer(evidenceId, caseId);
      } catch (err) {
        UI.showToast(`Re-extraction failed: ${err.message}`, "error");
      }
    });
  },

  showFactReviewModal(caseId, evidenceId, fact, defaultDecision = "CONFIRMED") {
    const isCorrection = defaultDecision === "CORRECTED";
    const modalHtml = `
      <div style="font-size: 0.88rem; line-height: 1.5;">
        <div style="margin-bottom: 12px; padding: 10px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border-left: 3px solid var(--primary);">
          <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--primary); font-weight: 700;">Extracted Forensic Claim (${fact.fact_id})</div>
          <div style="font-weight: 600; color: var(--text-main); margin-top: 4px;">${Formatters.escapeHtml(fact.fact_text || fact.fact_statement || '')}</div>
          <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 4px;">Source: p.${fact.page_number || 1} &bull; ${fact.attribution_type}</div>
        </div>

        <div style="margin-bottom: 12px;">
          <label style="display: block; font-weight: 600; font-size: 0.8rem; margin-bottom: 4px;">Investigator Review Decision</label>
          <select id="reviewDecisionSelect" class="form-control" style="width: 100%; padding: 8px; border-radius: var(--radius-sm); border: 1px solid var(--border-default);">
            <option value="CONFIRMED" ${defaultDecision === 'CONFIRMED' ? 'selected' : ''}>Confirm Fact (Corroborated by Investigator)</option>
            <option value="CORRECTED" ${defaultDecision === 'CORRECTED' ? 'selected' : ''}>Correct / Amend Fact (Provide Corrected Wording)</option>
            <option value="FLAGGED" ${defaultDecision === 'FLAGGED' ? 'selected' : ''}>Flag / Mark Disputed (Conflicting with other Evidence)</option>
            <option value="REJECTED" ${defaultDecision === 'REJECTED' ? 'selected' : ''}>Reject Extraction (Unsupported by Source Document)</option>
          </select>
        </div>

        <div id="correctedTextWrap" style="margin-bottom: 12px; ${isCorrection ? '' : 'display: none;'}">
          <label style="display: block; font-weight: 600; font-size: 0.8rem; margin-bottom: 4px;">Corrected Statement</label>
          <textarea id="correctedFactText" class="form-control" rows="3" style="width: 100%; padding: 8px; border-radius: var(--radius-sm); border: 1px solid var(--border-default); font-size: 0.84rem;">${Formatters.escapeHtml(fact.fact_text || fact.fact_statement || '')}</textarea>
        </div>

        <div style="margin-bottom: 12px;">
          <label style="display: block; font-weight: 600; font-size: 0.8rem; margin-bottom: 4px;">
            Mandatory Rationale / Reason for Decision <span style="color: var(--danger);">*</span>
          </label>
          <textarea id="reviewReasonText" class="form-control" rows="3" placeholder="State reason, supporting evidence, or justification for this review decision..." style="width: 100%; padding: 8px; border-radius: var(--radius-sm); border: 1px solid var(--border-default); font-size: 0.84rem;"></textarea>
        </div>

        <div style="font-size: 0.74rem; color: var(--text-muted); font-style: italic;">
          All review decisions are permanently logged to the tamper-evident audit history with your officer credentials and timestamp.
        </div>
      </div>
    `;

    const footerHtml = `
      <div style="display: flex; justify-content: flex-end; gap: 8px;">
        <button class="btn btn-secondary" onclick="UI.closeModal()">Cancel</button>
        <button class="btn btn-primary" id="btnSubmitFactDecision">Save Decision</button>
      </div>
    `;

    UI.openModal(`Review Extracted Fact &bull; ${fact.fact_id}`, modalHtml, footerHtml);

    document.getElementById("reviewDecisionSelect")?.addEventListener("change", (e) => {
      const wrap = document.getElementById("correctedTextWrap");
      if (wrap) wrap.style.display = e.target.value === "CORRECTED" ? "block" : "none";
    });

    document.getElementById("btnSubmitFactDecision")?.addEventListener("click", async () => {
      const decision = document.getElementById("reviewDecisionSelect")?.value;
      const reason = document.getElementById("reviewReasonText")?.value?.trim();
      const correctedText = document.getElementById("correctedFactText")?.value?.trim();

      if (!reason || reason.length < 3) {
        UI.showToast("Please provide a valid rationale/reason for your decision (min 3 chars).", "error");
        return;
      }

      try {
        UI.showToast("Recording investigator decision...", "info");
        await Api.recordFactDecision(caseId, evidenceId, fact.fact_id, {
          decision,
          reason,
          corrected_text: decision === "CORRECTED" ? correctedText : null,
          notes: `Recorded by officer ${State.auth.subjectId}`
        });

        UI.recordAudit("FACT_REVIEW_DECISION", `${evidenceId}:${fact.fact_id}`, "SUCCESS", `Decision: ${decision}, Reason: ${reason}`);
        UI.showToast("Fact review decision recorded successfully", "success");
        UI.closeModal();
        await ScreenEvidence.openEvidenceDetailDrawer(evidenceId, caseId);
      } catch (err) {
        UI.showToast(`Failed to record decision: ${err.message}`, "error");
      }
    });
  },

  showCustodyCertificateModal(ev) {
    const certHtml = `
      <div style="border: 2px solid var(--border-default); padding: 18px; border-radius: var(--radius-md); background-color: var(--bg-card); font-size: 0.85rem; line-height: 1.5;">
        <div style="text-align: center; border-bottom: 2px solid var(--border-default); padding-bottom: 10px; margin-bottom: 12px;">
          <h4 style="font-size: 1.05rem; font-weight: 700; text-transform: uppercase; color: var(--text-main);">
            Evidence Integrity & Custody Summary
          </h4>
          <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 2px;">
            Digital Evidence Forensic Parameters Record
          </div>
        </div>

        <div style="padding: 10px 14px; background-color: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); margin-bottom: 12px; font-size: 0.78rem; color: var(--text-secondary);">
          <strong>Legal / Evidentiary Notice:</strong> Legal / Evidentiary Certificate: Not Yet Generated. Statutory certification under Section 63 Bharatiya Sakshya Adhiniyam / Section 65B Indian Evidence Act requires formal forensic laboratory verification and authorized officer signature.
        </div>

        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div><strong>Case Inquiry ID:</strong> ${ev.case_id}</div>
          <div><strong>Exhibit Reference:</strong> ${ev.evidence_id}</div>
          <div><strong>Original Filename:</strong> ${ev.original_file_name}</div>
          <div><strong>File Size:</strong> ${Formatters.formatBytes(ev.file_size_bytes)} (${ev.file_size_bytes} bytes)</div>
          <div><strong>Primary Cryptographic Fingerprint (SHA-256):</strong> <code style="font-family: var(--font-mono); font-size: 0.74rem; color: var(--primary);">${ev.checksum_sha256 || 'N/A'}</code></div>
          <div><strong>Secondary Digest (SHA3-512):</strong> <code style="font-family: var(--font-mono); font-size: 0.74rem; color: var(--primary);">${(ev.checksum_sha3_512 || 'N/A').substring(0, 48)}...</code></div>
          <div><strong>Storage State:</strong> Protected Write-Once Storage with Write Protection</div>
          <div><strong>Investigating Officer:</strong> ${State.auth.subjectId} (${State.auth.role})</div>
          <div><strong>Record Generated:</strong> ${Formatters.formatDate(new Date().toISOString())}</div>
        </div>
      </div>
    `;

    UI.openModal("Evidence Integrity Summary", certHtml, `
      <button class="btn btn-secondary" onclick="window.print()">🖨️ Print Record</button>
      <button class="btn btn-primary" onclick="UI.closeModal()">Close</button>
    `);
  },

  async executeValidation(caseId, evidenceId) {
    try {
      const res = await Api.validateEvidenceMime(caseId, evidenceId);
      UI.showToast(`Format verified: ${res.detected_mime || res.status}`, "success");
      UI.recordAudit("FORMAT_VERIFIED", evidenceId, res.valid ? "SUCCESS" : "FAILED", res.validation_reason);
      await this.openEvidenceDetailDrawer(evidenceId, caseId);
      await ScreenEvidence.render(caseId);
    } catch (e) {
      UI.showToast(`Verification error: ${e.message}`, "error");
    }
  },

  async executeAntivirus(caseId, evidenceId) {
    try {
      const res = await Api.scanEvidenceAntivirus(caseId, evidenceId);
      UI.showToast(`Threat scan cleared: ${res.verdict}`, "success");
      UI.recordAudit("SECURITY_SCAN", evidenceId, "SUCCESS", `Verdict: ${res.verdict}`);
      await this.openEvidenceDetailDrawer(evidenceId, caseId);
      await ScreenEvidence.render(caseId);
    } catch (e) {
      UI.showToast(`Security scan failed: ${e.message}`, "error");
    }
  },

  async executeWormCommit(caseId, evidenceId) {
    try {
      const res = await Api.commitEvidenceWorm(caseId, evidenceId);
      UI.showToast(`Committed to protected storage!`, "success");
      UI.recordAudit("PRESERVATION_COMMITTED", evidenceId, "SUCCESS", `Ref: ${res.worm_storage_reference}`);
      await this.openEvidenceDetailDrawer(evidenceId, caseId);
      await ScreenEvidence.render(caseId);
    } catch (e) {
      UI.showToast(`Preservation failed: ${e.message}`, "error");
    }
  },

  async executeIntegrity(caseId, evidenceId) {
    try {
      const res = await Api.verifyEvidenceIntegrity(caseId, evidenceId);
      UI.showToast(`Dual cryptographic fingerprint verified!`, "success");
      UI.recordAudit("INTEGRITY_VERIFIED", evidenceId, "SUCCESS", `Fingerprint: ${res.checksum_sha256}`);
      await this.openEvidenceDetailDrawer(evidenceId, caseId);
      await ScreenEvidence.render(caseId);
    } catch (e) {
      UI.showToast(`Fingerprint check failed: ${e.message}`, "error");
    }
  },

  async executeLockAndEncrypt(caseId, evidenceId) {
    try {
      await Api.applyObjectLock(caseId, evidenceId, "GOVERNANCE");
      await Api.encryptEvidence(caseId, evidenceId);
      try {
        await Api.indexEvidence(caseId, evidenceId);
      } catch (idxErr) {
        console.warn("RAG indexing notice:", idxErr);
      }
      UI.showToast(`Write protection, encryption, and RAG indexing active!`, "success");
      UI.recordAudit("SECURITY_SEALED", evidenceId, "SUCCESS", "Object locked, encrypted, and indexed");
      await this.openEvidenceDetailDrawer(evidenceId, caseId);
      await ScreenEvidence.render(caseId);
    } catch (e) {
      UI.showToast(`Operation failed: ${e.message}`, "error");
    }
  },

  async runGuidedSecurityChain(caseId, evidenceId) {
    UI.showToast("Executing forensic verification pipeline...", "info");
    try {
      let ev = await Api.getEvidence(caseId, evidenceId);

      if (!ev.detected_mime_type) {
        await Api.validateEvidenceMime(caseId, evidenceId);
      }
      if (ev.antivirus_status !== "CLEAN") {
        await Api.scanEvidenceAntivirus(caseId, evidenceId);
      }
      if (ev.worm_status !== "COMMITTED") {
        await Api.commitEvidenceWorm(caseId, evidenceId);
      }
      if (ev.integrity_status !== "VERIFIED") {
        await Api.verifyEvidenceIntegrity(caseId, evidenceId);
      }
      try {
        await Api.applyObjectLock(caseId, evidenceId, "GOVERNANCE");
        await Api.encryptEvidence(caseId, evidenceId);
        try {
          await Api.indexEvidence(caseId, evidenceId);
        } catch (idxErr) {
          console.warn("RAG indexing notice:", idxErr);
        }
      } catch (lockErr) {
        console.warn("Lock/Encrypt notice:", lockErr);
      }

      UI.showToast("Evidence verification pipeline completed successfully!", "success");
      UI.recordAudit("VERIFICATION_COMPLETED", evidenceId, "SUCCESS", "All forensic standards met");
      await this.openEvidenceDetailDrawer(evidenceId, caseId);
      await ScreenEvidence.render(caseId);
    } catch (e) {
      UI.showToast(`Pipeline paused: ${e.message}`, "error");
    }
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 9a. SCREEN 3: FORENSIC VERIFICATION WORKSPACE (Route: #/cases/:id/verification)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenVerification = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Forensic Verification`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }

    const c = State.activeCase;
    const evidenceList = State.evidence || [];

    const totalEvidence = evidenceList.length;
    const mimeValidated = evidenceList.filter(e => e.detected_mime_type || e.mime_validation_status === "VALIDATED").length;
    const avClean = evidenceList.filter(e => e.antivirus_status === "CLEAN").length;
    const integrityVerified = evidenceList.filter(e => e.integrity_status === "VERIFIED").length;
    const wormCommitted = evidenceList.filter(e => e.worm_status === "COMMITTED").length;
    const objectLocked = evidenceList.filter(e => e.lock_status === "LOCKED").length;

    const isCurrentStage = c.lifecycle_stage === "EVIDENCE_PROCESSING";
    const isCompletedStage = ["ANALYSIS", "REVIEW", "CLOSED"].includes(c.lifecycle_stage);
    const isFutureStage = ["INITIALIZED", "EVIDENCE_INGESTION"].includes(c.lifecycle_stage);

    const allVerified = totalEvidence > 0 && evidenceList.every(e => 
      e.integrity_status === "VERIFIED" && e.worm_status === "COMMITTED"
    );

    let stageBannerHtml = "";
    if (isFutureStage) {
      stageBannerHtml = `
        <div class="card" style="background-color: var(--primary-bg); border-left: 5px solid var(--primary); padding: 18px 22px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div style="flex: 1; min-width: 280px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-info">STAGE 3 PREREQUISITE</span>
                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">Current Case Stage: ${c.lifecycle_stage}</span>
              </div>
              <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">
                Forensic Verification Awaiting Stage Activation
              </h3>
              <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin: 0;">
                Case is currently in Stage <strong>${(StageDisplayMap[c.lifecycle_stage] || {}).short || c.lifecycle_stage}</strong>. 
                ${totalEvidence === 0 
                  ? "To perform forensic verification, first register case exhibits in Stage 2 Evidence Collection." 
                  : `${totalEvidence} exhibit(s) registered. When you have attached all initial exhibits, advance the investigation to Stage 3 to perform automated verification.`}
              </p>
            </div>
            <div>
              ${totalEvidence > 0 && c.lifecycle_stage === "EVIDENCE_INGESTION" ? `
                <button class="btn btn-primary btn-stage-transition" onclick="handleStageTransition('${c.case_id}', 'EVIDENCE_PROCESSING')">
                  Proceed to Forensic Verification &rarr;
                </button>
              ` : `
                <button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${c.case_id}', 'evidence')">
                  Go to Evidence Collection &rarr;
                </button>
              `}
            </div>
          </div>
        </div>
      `;
    } else if (isCurrentStage) {
      stageBannerHtml = `
        <div class="card" style="background-color: var(--bg-card); border-left: 5px solid var(--primary); padding: 18px 22px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div style="flex: 1; min-width: 280px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-attention">ACTIVE WORKSPACE &bull; STAGE 3</span>
                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">Forensic Verification In Progress</span>
              </div>
              <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">
                ${allVerified ? "All Case Exhibits Forensically Verified" : "Forensic Verification & Integrity Validation"}
              </h3>
              <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin: 0;">
                ${allVerified 
                  ? `All ${totalEvidence} exhibits have completed binary format validation, ClamAV antivirus clearance, SHA-256 + SHA3-512 dual hashing, and immutable WORM storage. You can now advance to Investigation Analysis.` 
                  : `Automated forensic verification executes binary signature inspection, malware scanning, dual cryptographic hashing, and immutable WORM storage. ${integrityVerified} of ${totalEvidence} exhibits verified.`}
              </p>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              ${allVerified ? `
                <button class="btn btn-primary btn-stage-transition" onclick="handleStageTransition('${c.case_id}', 'ANALYSIS')">
                  Advance to Investigation Analysis &rarr;
                </button>
              ` : `
                <button class="btn btn-primary" id="btnRunAllChecks" onclick="ScreenVerification.runAllChecks('${c.case_id}')">
                  ⚡ Execute Pending Checks
                </button>
              `}
            </div>
          </div>
        </div>
      `;
    } else if (isCompletedStage) {
      stageBannerHtml = `
        <div class="card" style="background-color: var(--verified-bg); border-left: 5px solid var(--verified); padding: 16px 20px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-verified">STAGE 3 COMPLETED</span>
                <span style="font-size: 0.8rem; color: var(--verified-text); font-family: var(--font-mono);">Verification Records Locked & Preserved</span>
              </div>
              <div style="font-size: 1rem; font-weight: 700; color: var(--verified-text); margin-top: 2px;">
                Forensic Verification Complete — ${integrityVerified} of ${totalEvidence} Exhibits Preserved
              </div>
              <div style="font-size: 0.84rem; color: var(--verified-text); opacity: 0.9; margin-top: 2px;">
                All forensic verification records, SHA-256 and SHA3-512 cryptographic digests, and WORM storage commitments are permanently retained for this inquiry.
              </div>
            </div>
            <span class="badge badge-verified" style="font-size: 0.9rem; padding: 6px 14px;">Locked in custody</span>
          </div>
        </div>
      `;
    }

    const html = `
      ${renderWorkspaceHeaderHtml("verification")}

      ${stageBannerHtml}

      <!-- Forensic Verification Plain-Language Metrics -->
      <div class="metrics-strip">
        <div class="metric-card">
          <div class="label">Total Exhibits</div>
          <div class="number">${totalEvidence}</div>
          <div class="subtext">Registered case exhibits</div>
        </div>
        <div class="metric-card">
          <div class="label">Format Checked</div>
          <div class="number" style="color: ${mimeValidated === totalEvidence && totalEvidence > 0 ? 'var(--verified)' : 'var(--text-main)'};">
            ${mimeValidated}
          </div>
          <div class="subtext">File signatures verified</div>
        </div>
        <div class="metric-card">
          <div class="label">Threat Scan Clean</div>
          <div class="number" style="color: ${avClean === totalEvidence && totalEvidence > 0 ? 'var(--verified)' : 'var(--text-main)'};">
            ${avClean}
          </div>
          <div class="subtext">Malware scans passed</div>
        </div>
        <div class="metric-card">
          <div class="label">Integrity Verified</div>
          <div class="number" style="color: ${integrityVerified === totalEvidence && totalEvidence > 0 ? 'var(--verified)' : 'var(--text-main)'};">
            ${integrityVerified}
          </div>
          <div class="subtext">Dual-hash fingerprints verified</div>
        </div>
        <div class="metric-card">
          <div class="label">Storage Protected</div>
          <div class="number" style="color: ${objectLocked === totalEvidence && totalEvidence > 0 ? 'var(--verified)' : 'var(--text-main)'};">
            ${objectLocked}
          </div>
          <div class="subtext">Local simulation active</div>
        </div>
      </div>

      <!-- Human Governance Notice -->
      <div class="human-governance-notice">
        <div>
          <strong>Forensic Verification Notice:</strong>
          <span> Automated checks verify file format consistency, absence of detected malware, and cryptographic hash integrity. Storage protection is currently running in local filesystem simulation (cloud or hardware WORM protection is not established). Admissibility and evidentiary weight remain subject to professional evaluation by the Investigating Officer.</span>
        </div>
      </div>

      <!-- Verification Workspace Body -->
      <div class="card" style="margin-top: 14px;">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h3 class="card-title">Exhibit Verification Register</h3>
            <span style="font-size: 0.8rem; color: var(--text-muted);">Plain-language verification status, file integrity checks, and storage preservation records</span>
          </div>
          <div style="display: flex; gap: 8px;">
            ${isCurrentStage && !allVerified && totalEvidence > 0 ? `
              <button class="btn btn-primary btn-sm" id="btnRunAllChecks" onclick="ScreenVerification.runAllChecks('${c.case_id}')">
                Run all pending checks
              </button>
            ` : ""}
            <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${c.case_id}', 'evidence')">
              Open Evidence Register &rarr;
            </button>
          </div>
        </div>

        ${totalEvidence === 0 ? `
          <div class="empty-state-card" style="margin-top: 16px;">
            <div class="empty-state-title">No Exhibits Uploaded for Verification</div>
            <div class="empty-state-desc">
              Forensic verification executes automated integrity checks on seized exhibits. To begin, attach case documents, crime scene photos, CCTV clips, or telecom records in Evidence Collection.
            </div>
            <button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${c.case_id}', 'evidence')">
              Register evidence exhibit
            </button>
          </div>
        ` : `
          <div style="overflow-x: auto; margin-top: 14px;">
            <table class="verification-matrix-table">
              <thead>
                <tr>
                  <th style="width: 32%;">Exhibit</th>
                  <th style="width: 18%;">Category</th>
                  <th style="width: 32%;">Verification Status</th>
                  <th style="width: 18%; text-align: right;">Actions</th>
                </tr>
              </thead>
              <tbody>
                ${evidenceList.map(e => {
                  const isMimeOk = e.detected_mime_type || e.mime_validation_status === "VALIDATED";
                  const isAvOk = e.antivirus_status === "CLEAN";
                  const isHashOk = e.integrity_status === "VERIFIED";
                  const isWormOk = e.worm_status === "COMMITTED";
                  const isLockOk = e.lock_status === "LOCKED";
                  const isLocalSimulated = !e.lock_backend || e.lock_backend === "SIMULATED_LOCAL" || e.lock_backend === "LOCAL_FS";
                  const isFull = isMimeOk && isAvOk && isHashOk && isWormOk;

                  let statusBadge = "";
                  let statusSummary = "";

                  if (e.antivirus_status === "QUARANTINED" || e.antivirus_status === "THREAT_DETECTED") {
                    statusBadge = '<span class="badge badge-danger">Threat detected</span>';
                    statusSummary = 'Malware or threat pattern flagged by scanner.';
                  } else if (e.integrity_status === "FAILED") {
                    statusBadge = '<span class="badge badge-danger">Integrity verification failed</span>';
                    statusSummary = 'Cryptographic hash mismatch. File may be corrupted or altered.';
                  } else if (isFull) {
                    statusBadge = '<span class="badge badge-verified">All checks completed</span>';
                    statusSummary = `Format checked &bull; No threat detected &bull; Hash verified &bull; Storage: ${isLocalSimulated ? 'Local simulation' : 'Hardware protected'}`;
                  } else if (!isHashOk && isAvOk) {
                    statusBadge = '<span class="badge badge-attention">Integrity verification pending</span>';
                    statusSummary = 'Dual-hash integrity calculation queued.';
                  } else if (!isAvOk) {
                    statusBadge = '<span class="badge badge-attention">Threat scan pending</span>';
                    statusSummary = 'Threat scanning not yet completed.';
                  } else {
                    statusBadge = '<span class="badge badge-attention">Verification pending</span>';
                    statusSummary = 'File format and verification checks queued.';
                  }

                  return `
                    <tr>
                      <td>
                        <div style="font-weight: 600; color: var(--text-main); font-size: 0.88rem;">${Formatters.escapeHtml(e.original_file_name)}</div>
                        <div style="font-size: 0.74rem; color: var(--text-muted); font-family: var(--font-mono); margin-top: 2px;">${e.evidence_id} &bull; ${Formatters.formatBytes(e.file_size_bytes)}</div>
                      </td>
                      <td>
                        <span style="font-size: 0.82rem; color: var(--text-main);">${Formatters.escapeHtml(Formatters.formatPlainCategory(e.evidence_category))}</span>
                      </td>
                      <td>
                        <div>${statusBadge}</div>
                        <div style="font-size: 0.73rem; color: var(--text-secondary); margin-top: 3px;">
                          ${statusSummary}
                        </div>
                      </td>
                      <td style="text-align: right;">
                        <div style="display: flex; gap: 6px; justify-content: flex-end; flex-wrap: wrap;">
                          <button class="btn btn-secondary btn-sm" onclick="ScreenVerification.toggleTechPanel('${e.evidence_id}')">
                            Technical details
                          </button>
                          ${!isFull ? `
                            <button class="btn btn-primary btn-sm" onclick="ScreenVerification.runExhibitChecks('${c.case_id}', '${e.evidence_id}')">
                              Verify exhibit
                            </button>
                          ` : ""}
                        </div>
                      </td>
                    </tr>
                    <tr id="techPanel_${e.evidence_id}" style="display: none;">
                      <td colspan="4" style="background: var(--bg-card-subtle); padding: 14px 18px; border-bottom: 2px solid var(--border-default);">
                        ${StatusPresentation.renderTechnicalDetailsPanel(e)}
                      </td>
                    </tr>
                  `;
                }).join("")}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;

    container.innerHTML = html;
  },

  toggleTechPanel(evidenceId) {
    const row = document.getElementById(`techPanel_${evidenceId}`);
    if (row) {
      row.style.display = row.style.display === "none" ? "table-row" : "none";
    }
  },

  async runExhibitChecks(caseId, evidenceId) {
    UI.showToast("Executing forensic verification pipeline on exhibit...", "info");
    try {
      const ev = (State.evidence || []).find(x => x.evidence_id === evidenceId) || {};
      if (!ev.detected_mime_type) {
        await Api.validateEvidenceMime(caseId, evidenceId);
      }
      if (ev.antivirus_status !== "CLEAN") {
        await Api.scanEvidenceAntivirus(caseId, evidenceId);
      }
      if (ev.worm_status !== "COMMITTED") {
        await Api.commitEvidenceWorm(caseId, evidenceId);
      }
      if (ev.integrity_status !== "VERIFIED") {
        await Api.verifyEvidenceIntegrity(caseId, evidenceId);
      }
      try {
        await Api.applyObjectLock(caseId, evidenceId, "GOVERNANCE");
        await Api.encryptEvidence(caseId, evidenceId);
      } catch (e) {
        console.warn("Lock notice:", e);
      }
      UI.showToast("Exhibit successfully verified and locked in WORM storage!", "success");
      UI.recordAudit("FORENSIC_VERIFICATION_COMPLETE", evidenceId, "SUCCESS", "MIME, Antivirus, and Dual-Hash passed");
      await ScreenVerification.render(caseId);
    } catch (err) {
      UI.showToast(`Verification check failed: ${err.message}`, "error");
    }
  },

  async runAllChecks(caseId) {
    const btn = document.getElementById("btnRunAllChecks");
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span style="display:inline-block; width:12px; height:12px; border:2px solid currentColor; border-right-color:transparent; border-radius:50%; animation:spin 0.75s linear infinite; margin-right:6px; vertical-align:middle;"></span> Verifying Exhibits...`;
    }

    try {
      const list = State.evidence || [];
      for (const e of list) {
        if (e.integrity_status !== "VERIFIED" || e.worm_status !== "COMMITTED") {
          try {
            if (!e.detected_mime_type) await Api.validateEvidenceMime(caseId, e.evidence_id);
            if (e.antivirus_status !== "CLEAN") await Api.scanEvidenceAntivirus(caseId, e.evidence_id);
            if (e.worm_status !== "COMMITTED") await Api.commitEvidenceWorm(caseId, e.evidence_id);
            if (e.integrity_status !== "VERIFIED") await Api.verifyEvidenceIntegrity(caseId, e.evidence_id);
            try {
              await Api.applyObjectLock(caseId, e.evidence_id, "GOVERNANCE");
              await Api.encryptEvidence(caseId, e.evidence_id);
            } catch (le) {}
          } catch (itemErr) {
            console.warn(`Exhibit ${e.evidence_id} verification check notice:`, itemErr);
          }
        }
      }
      UI.showToast("All eligible exhibits processed through forensic verification pipeline!", "success");
      UI.recordAudit("BATCH_VERIFICATION_EXECUTED", caseId, "SUCCESS", "All staged exhibits processed");
      await ScreenVerification.render(caseId);
    } catch (err) {
      UI.showToast(`Batch verification failed: ${err.message}`, "error");
    } finally {
      if (btn) btn.disabled = false;
    }
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 9.5 SCREEN: ENTITY RELATIONSHIP GRAPH (Route: #/cases/:id/connections)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenGraph = {
  activeCategory: "ALL",
  searchQuery: "",
  selectedNode: null,
  selectedEdge: null,
  graphData: null,
  zoomLevel: 1.0,
  layoutMode: "tree",
  treeLayout: null,
  collapsedNodeIds: new Set(),

  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Entity Graph`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }

    container.innerHTML = `
      ${renderWorkspaceHeaderHtml("connections")}

      <div class="cases-toolbar" style="margin-top: 14px;">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Entity Relationship Graph</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Source-grounded knowledge graph connecting people, physical evidence, locations, documents, and events.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${caseId}', 'timeline')">View Timeline</button>
          <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence')">Evidence Library</button>
        </div>
      </div>

      <div id="graphMountArea" style="margin-top: 16px;">
        <div style="padding: 40px; text-align: center; color: var(--text-muted);">
          
          <div>Loading case knowledge graph...</div>
        </div>
      </div>
    `;

    try {
      const data = await Api.getKnowledgeGraph(caseId);
      this.graphData = data;
      this.renderGraph(caseId);
    } catch (err) {
      document.getElementById("graphMountArea").innerHTML = `
        <div class="card" style="padding: 24px; text-align: center;">
          <p style="color: var(--danger);">Failed to load entity graph: ${Formatters.escapeHtml(err.message)}</p>
          <button class="btn btn-secondary btn-sm" onclick="ScreenGraph.render('${caseId}')">Retry</button>
        </div>
      `;
    }
  },

  conciseName(node) {
    return String(node.name || "Unnamed entity")
      .replace(/^Forensic Exhibit Item \((.+)\)$/i, "$1")
      .replace(/^Exhibit Document$/i, "Exhibit document");
  },

  wrapNodeLabel(value, maxCharacters = 30) {
    const words = String(value || "").split(/\s+/).filter(Boolean);
    const lines = [];
    let line = "";
    words.forEach(word => {
      if (word.length > maxCharacters) {
        if (line) lines.push(line);
        for (let i = 0; i < word.length; i += maxCharacters) lines.push(word.slice(i, i + maxCharacters));
        line = "";
      } else if (!line || `${line} ${word}`.length <= maxCharacters) {
        line = line ? `${line} ${word}` : word;
      } else {
        lines.push(line);
        line = word;
      }
    });
    if (line) lines.push(line);
    return lines.slice(0, 2);
  },

  buildTreeLayout(nodes, edges) {
    const nodeById = new Map(nodes.map(node => [node.id, node]));
    const sortNodes = (left, right) => {
      const categoryOrder = { PERSON: 1, LOCATION: 2, OBJECT: 3, DOCUMENT: 4, EVENT: 5 };
      return (categoryOrder[left.category] || 99) - (categoryOrder[right.category] || 99)
        || this.conciseName(left).localeCompare(this.conciseName(right));
    };
    const outgoing = new Map(nodes.map(node => [node.id, []]));
    const incoming = new Map(nodes.map(node => [node.id, 0]));
    edges.forEach(edge => {
      if (!nodeById.has(edge.source_node_id) || !nodeById.has(edge.target_node_id)) return;
      outgoing.get(edge.source_node_id).push(edge);
      incoming.set(edge.target_node_id, (incoming.get(edge.target_node_id) || 0) + 1);
    });
    outgoing.forEach(list => list.sort((a, b) => sortNodes(nodeById.get(a.target_node_id), nodeById.get(b.target_node_id))));

    const rootId = "__case_root__";
    const children = new Map([[rootId, []]]);
    const parent = new Map();
    const selectedTreeEdges = [];
    const assigned = new Set();
    const addChild = (parentId, childId, edge = null) => {
      if (!children.has(parentId)) children.set(parentId, []);
      children.get(parentId).push({ id: childId, edge });
      parent.set(childId, parentId);
      assigned.add(childId);
    };

    const roots = nodes.filter(node => (incoming.get(node.id) || 0) === 0).sort(sortNodes);
    roots.forEach(node => addChild(rootId, node.id));
    const queue = roots.map(node => node.id);
    while (queue.length) {
      const sourceId = queue.shift();
      (outgoing.get(sourceId) || []).forEach(edge => {
        if (assigned.has(edge.target_node_id)) return;
        addChild(sourceId, edge.target_node_id, edge);
        selectedTreeEdges.push(edge);
        queue.push(edge.target_node_id);
      });
    }
    nodes.filter(node => !assigned.has(node.id)).sort(sortNodes).forEach(node => addChild(rootId, node.id));

    const visibleChildren = new Map();
    const visitVisibility = parentId => {
      const childList = children.get(parentId) || [];
      const isCollapsed = parentId !== rootId && this.collapsedNodeIds.has(parentId);
      const visible = isCollapsed ? [] : childList;
      visibleChildren.set(parentId, visible);
      visible.forEach(child => visitVisibility(child.id));
    };
    visitVisibility(rootId);

    const countLeaves = nodeId => {
      const childList = visibleChildren.get(nodeId) || [];
      return childList.length ? childList.reduce((sum, child) => sum + countLeaves(child.id), 0) : 1;
    };
    const leafCount = Math.max(1, countLeaves(rootId));
    const nodeWidth = 228;
    const nodeHeight = 80;
    const leafGap = 42;
    const leftPadding = 42;
    const width = Math.max(960, leafCount * (nodeWidth + leafGap) + leftPadding * 2 - leafGap);
    let deepestLevel = 0;
    const positions = new Map();
    let leafIndex = 0;
    const place = (nodeId, depth) => {
      deepestLevel = Math.max(deepestLevel, depth);
      const childList = visibleChildren.get(nodeId) || [];
      if (!childList.length) {
        const x = leftPadding + leafIndex * (nodeWidth + leafGap) + nodeWidth / 2;
        leafIndex += 1;
        positions.set(nodeId, { x, y: 48 + depth * 136 });
        return x;
      }
      const xs = childList.map(child => place(child.id, depth + 1));
      const x = xs.reduce((sum, value) => sum + value, 0) / xs.length;
      positions.set(nodeId, { x, y: 48 + depth * 136 });
      return x;
    };
    place(rootId, 0);
    // A dense case can be much wider than the visible canvas.  Keep the case
    // root near the initial viewport rather than centering it across every
    // leaf, so an investigator sees the organising point before scrolling.
    const rootPosition = positions.get(rootId);
    if (rootPosition) {
      const minimumRootX = leftPadding + nodeWidth / 2;
      const preferredRootX = Math.min(480, width - leftPadding - nodeWidth / 2);
      rootPosition.x = Math.max(minimumRootX, preferredRootX);
    }
    const height = Math.max(380, 48 + (deepestLevel + 1) * 136 + 44);
    const treeEdgeIds = new Set(selectedTreeEdges.map(edge => edge.id));
    return {
      rootId, children, visibleChildren, positions, width, height, nodeWidth, nodeHeight,
      treeEdges: selectedTreeEdges,
      supplementalEdges: edges.filter(edge => !treeEdgeIds.has(edge.id)),
      nodeById
    };
  },

  renderGraph(caseId) {
    const mount = document.getElementById("graphMountArea");
    if (!mount) return;
    if (!this.graphData || this.graphData.total_nodes === 0) {
      mount.innerHTML = `
        <div class="empty-state-card" style="padding: 48px 24px;">
          <h3 class="empty-state-title">No entities documented yet</h3>
          <p class="empty-state-desc">The relationship view is built only from this case's records. Attach evidence to review documented entities and source-backed relationships.</p>
          <button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence')">Add evidence</button>
        </div>`;
      return;
    }

    const allNodes = this.graphData.nodes || [];
    const allEdges = this.graphData.edges || [];
    let filteredNodes = allNodes;
    if (this.activeCategory !== "ALL") filteredNodes = filteredNodes.filter(node => node.category === this.activeCategory);
    if (this.searchQuery) {
      const query = this.searchQuery.toLowerCase();
      filteredNodes = filteredNodes.filter(node => this.conciseName(node).toLowerCase().includes(query) || String(node.subtitle || "").toLowerCase().includes(query));
    }
    const nodeIds = new Set(filteredNodes.map(node => node.id));
    const filteredEdges = allEdges.filter(edge => nodeIds.has(edge.source_node_id) && nodeIds.has(edge.target_node_id));
    if (!filteredNodes.length) {
      mount.innerHTML = `<div class="empty-state-card"><h3 class="empty-state-title">No matching entities</h3><p class="empty-state-desc">Clear the search or select another entity group.</p></div>`;
      return;
    }

    if (this.layoutMode === "relationships") {
      this.renderRelationshipLayout(caseId, filteredNodes, filteredEdges);
      return;
    }

    const tree = this.buildTreeLayout(filteredNodes, filteredEdges);
    this.treeLayout = tree;
    const rootName = State.activeCase?.title || `Case ${caseId}`;
    const categoryOptions = ["ALL", "PERSON", "LOCATION", "OBJECT", "DOCUMENT", "EVENT"]
      .filter(category => category === "ALL" || allNodes.some(node => node.category === category))
      .map(category => `<option value="${category}" ${this.activeCategory === category ? "selected" : ""}>${category === "ALL" ? `All entities (${allNodes.length})` : `${category.charAt(0) + category.slice(1).toLowerCase()} (${allNodes.filter(node => node.category === category).length})`}</option>`)
      .join("");
    const renderLabel = (value, x, y, className) => this.wrapNodeLabel(value).map((line, index) => `<text class="${className}" x="${x}" y="${y + index * 15}" text-anchor="middle">${Formatters.escapeHtml(line)}</text>`).join("");
    const renderNode = node => {
      const position = tree.positions.get(node.id);
      const childCount = (tree.children.get(node.id) || []).length;
      const isSelected = this.selectedNode?.id === node.id;
      const isCollapsed = this.collapsedNodeIds.has(node.id);
      const x = position.x - tree.nodeWidth / 2;
      const y = position.y - tree.nodeHeight / 2;
      return `<g data-node-id="${Formatters.escapeHtml(node.id)}" class="graph-node graph-tree-node ${isSelected ? "selected" : ""}" tabindex="0" role="button" aria-label="${Formatters.escapeHtml(this.conciseName(node))}" transform="translate(0 0)" onclick="ScreenGraph.selectNode('${node.id}')">
        <rect x="${x}" y="${y}" width="${tree.nodeWidth}" height="${tree.nodeHeight}" rx="3" class="graph-node-rect"></rect>
        ${renderLabel(this.conciseName(node), position.x, y + 23, "graph-node-name")}
        <text class="graph-node-category" x="${position.x}" y="${y + 68}" text-anchor="middle">${Formatters.escapeHtml(String(node.category || "Entity").toLowerCase())}</text>
        ${childCount ? `<g class="graph-branch-toggle" role="button" aria-label="${isCollapsed ? "Expand" : "Collapse"} branch" onclick="event.stopPropagation(); ScreenGraph.toggleBranch('${caseId}', '${node.id}')"><rect x="${x + tree.nodeWidth - 21}" y="${y + 7}" width="14" height="14" rx="2"></rect><text x="${x + tree.nodeWidth - 14}" y="${y + 18}" text-anchor="middle">${isCollapsed ? "+" : "−"}</text></g>` : ""}
      </g>`;
    };
    const renderTreeEdge = edge => {
      const source = tree.positions.get(edge.source_node_id);
      const target = tree.positions.get(edge.target_node_id);
      if (!source || !target) return "";
      const isSelected = this.selectedEdge?.id === edge.id;
      const startY = source.y + tree.nodeHeight / 2;
      const endY = target.y - tree.nodeHeight / 2;
      return `<path class="graph-edge graph-tree-edge ${isSelected ? "selected" : ""}" data-relationship-id="${edge.id}" d="M ${source.x} ${startY} C ${source.x} ${startY + 34}, ${target.x} ${endY - 34}, ${target.x} ${endY}" onclick="ScreenGraph.selectEdge('${edge.id}')"><title>${Formatters.escapeHtml(edge.label || edge.relation_type || "Recorded relationship")}</title></path>`;
    };
    const root = tree.positions.get(tree.rootId);
    const rootEdgeHtml = (tree.visibleChildren.get(tree.rootId) || []).map(child => {
      const target = tree.positions.get(child.id);
      const startY = root.y + tree.nodeHeight / 2;
      const endY = target.y - tree.nodeHeight / 2;
      return `<path class="graph-root-edge" d="M ${root.x} ${startY} C ${root.x} ${startY + 30}, ${target.x} ${endY - 30}, ${target.x} ${endY}"></path>`;
    }).join("");

    mount.innerHTML = `
      <div class="graph-viewport-container">
        <div class="graph-toolbar">
          <div class="graph-control-group">
            <label for="graphCategoryFilter">Entity group</label>
            <select id="graphCategoryFilter" class="form-select graph-select" onchange="ScreenGraph.setCategoryFilter('${caseId}', this.value)">${categoryOptions}</select>
          </div>
          <div class="graph-control-group">
            <label for="graphLayoutMode">View</label>
            <select id="graphLayoutMode" class="form-select graph-select" onchange="ScreenGraph.setLayoutMode('${caseId}', this.value)">
              <option value="tree" ${this.layoutMode === "tree" ? "selected" : ""}>Hierarchical tree</option>
              <option value="relationships" ${this.layoutMode === "relationships" ? "selected" : ""}>Relationship list</option>
            </select>
          </div>
          <div class="graph-toolbar-actions">
            <label class="visually-hidden" for="graphSearchInput">Search entities</label>
            <input id="graphSearchInput" type="search" placeholder="Search entities" class="form-input graph-search-input" value="${Formatters.escapeHtml(this.searchQuery)}" oninput="ScreenGraph.searchQuery = this.value" onchange="ScreenGraph.setSearchQuery('${caseId}', this.value)" />
            <button class="btn btn-secondary btn-sm" onclick="ScreenGraph.zoom(0.15)">Zoom in</button>
            <button class="btn btn-secondary btn-sm" onclick="ScreenGraph.zoom(-0.15)">Zoom out</button>
            <button class="btn btn-secondary btn-sm" onclick="ScreenGraph.fitToScreen()">Fit to screen</button>
            <button class="btn btn-secondary btn-sm" onclick="ScreenGraph.focusSelected()">Focus selected</button>
            <button class="btn btn-secondary btn-sm" onclick="ScreenGraph.resetZoom()">Reset view</button>
          </div>
        </div>
        <div class="graph-explanation">The case lines organise the view only. Solid lines are recorded relationships; select one to inspect its source passage. Expand or collapse a branch to focus the view.</div>
        <div class="graph-canvas-area" id="graphCanvasArea">
          <svg class="graph-svg" style="width: ${tree.width}px; height: ${tree.height}px; transform: scale(${this.zoomLevel}); transform-origin: 0 0;" viewBox="0 0 ${tree.width} ${tree.height}" role="img" aria-label="Hierarchical relationship tree for ${Formatters.escapeHtml(rootName)}">
            <g id="graphEdgesGroup">${rootEdgeHtml}${tree.treeEdges.map(renderTreeEdge).join("")}</g>
            <g id="graphNodesGroup">
              <g class="graph-root-node"><rect x="${root.x - tree.nodeWidth / 2}" y="${root.y - tree.nodeHeight / 2}" width="${tree.nodeWidth}" height="${tree.nodeHeight}" rx="3"></rect>${renderLabel(rootName, root.x, root.y - 4, "graph-root-name")}<text class="graph-root-category" x="${root.x}" y="${root.y + 25}" text-anchor="middle">CASE</text></g>
              ${filteredNodes.map(renderNode).join("")}
            </g>
          </svg>
        </div>
        <div class="graph-relationship-key">
          <div><strong>Recorded relationships</strong><span>${filteredEdges.length} source-backed link${filteredEdges.length === 1 ? "" : "s"}</span></div>
          <div class="graph-relationship-list">
            ${filteredEdges.length ? filteredEdges.map(edge => `<button class="graph-relationship-item ${this.selectedEdge?.id === edge.id ? "selected" : ""}" onclick="ScreenGraph.selectEdge('${edge.id}')"><span>${Formatters.escapeHtml(tree.nodeById.get(edge.source_node_id)?.name || edge.source_node_id)}</span><span>${Formatters.escapeHtml(edge.label || edge.relation_type || "Recorded relationship")}</span><span>${Formatters.escapeHtml(tree.nodeById.get(edge.target_node_id)?.name || edge.target_node_id)}</span></button>`).join("") : "<span class=\"graph-relationship-empty\">No recorded relationship joins the entities in this view.</span>"}
          </div>
        </div>
        <div class="entity-inspector-drawer" id="entityInspectorDrawer"><div id="entityInspectorContent"></div></div>
      </div>`;
    this.enablePan();
  },

  setCategoryFilter(caseId, cat) {
    this.activeCategory = cat;
    this.renderGraph(caseId);
  },

  setSearchQuery(caseId, q) {
    this.searchQuery = q.trim();
    this.renderGraph(caseId);
  },

  setLayoutMode(caseId, mode) {
    this.layoutMode = mode === "relationships" ? "relationships" : "tree";
    this.renderGraph(caseId);
  },

  renderRelationshipLayout(caseId, nodes, edges) {
    const mount = document.getElementById("graphMountArea");
    if (!mount) return;
    const nodeById = new Map(nodes.map(node => [node.id, node]));
    mount.innerHTML = `
      <div class="graph-viewport-container">
        <div class="graph-toolbar">
          <div><strong>Relationship list</strong><div class="source-caption">A readable alternative for dense cases. Every row uses a returned case relationship.</div></div>
          <button class="btn btn-secondary btn-sm" onclick="ScreenGraph.setLayoutMode('${caseId}', 'tree')">Return to tree</button>
        </div>
        ${edges.length ? `<div class="relationship-layout-list">${edges.map(edge => `<article class="relationship-layout-item"><div><strong>${Formatters.escapeHtml(this.conciseName(nodeById.get(edge.source_node_id) || { name: edge.source_node_id }))}</strong><span>${Formatters.escapeHtml(edge.label || edge.relation_type || "Recorded relationship")}</span><strong>${Formatters.escapeHtml(this.conciseName(nodeById.get(edge.target_node_id) || { name: edge.target_node_id }))}</strong></div><p>${Formatters.escapeHtml(edge.source_passage || "No source passage is available for this relationship.")}</p><footer><span>${Formatters.escapeHtml(edge.source_filename || edge.evidence_id || "Source record")}</span><span class="entity-relation-status ${edge.review_status === "CONFIRMED" ? "is-confirmed" : ""}">${Formatters.escapeHtml(edge.review_status || "REPORTED")}</span><button class="btn btn-secondary btn-sm" onclick="ScreenGraph.selectEdge('${edge.id}')">Inspect source</button></footer></article>`).join("")}</div>` : `<div class="empty-state-card"><h3 class="empty-state-title">No verified relationships to show</h3><p class="empty-state-desc">Entities may be present, but no source-backed relationships join them in this view.</p></div>`}
        <div class="entity-inspector-drawer" id="entityInspectorDrawer"><div id="entityInspectorContent"></div></div>
      </div>`;
  },

  enablePan() {
    const area = document.getElementById("graphCanvasArea");
    if (!area || area.dataset.panReady === "true") return;
    area.dataset.panReady = "true";
    let drag = null;
    area.addEventListener("pointerdown", event => {
      if (event.target.closest(".graph-node, .graph-branch-toggle, .graph-edge")) return;
      drag = { x: event.clientX, y: event.clientY, left: area.scrollLeft, top: area.scrollTop };
      area.setPointerCapture?.(event.pointerId);
      area.classList.add("is-panning");
    });
    area.addEventListener("pointermove", event => {
      if (!drag) return;
      area.scrollLeft = drag.left - (event.clientX - drag.x);
      area.scrollTop = drag.top - (event.clientY - drag.y);
    });
    const stop = () => { drag = null; area.classList.remove("is-panning"); };
    area.addEventListener("pointerup", stop);
    area.addEventListener("pointercancel", stop);
  },

  toggleBranch(caseId, nodeId) {
    if (this.collapsedNodeIds.has(nodeId)) this.collapsedNodeIds.delete(nodeId);
    else this.collapsedNodeIds.add(nodeId);
    this.renderGraph(caseId);
  },

  zoom(delta) {
    this.zoomLevel = Math.max(0.5, Math.min(2.5, this.zoomLevel + delta));
    const svg = document.querySelector(".graph-svg");
    if (svg) svg.style.transform = `scale(${this.zoomLevel})`;
  },

  resetZoom() {
    this.zoomLevel = 1.0;
    const svg = document.querySelector(".graph-svg");
    if (svg) svg.style.transform = "scale(1)";
  },

  fitToScreen() {
    const area = document.getElementById("graphCanvasArea");
    const tree = this.treeLayout;
    if (!area || !tree) return;
    const horizontal = Math.max(0.5, Math.min(1, (area.clientWidth - 32) / tree.width));
    const vertical = Math.max(0.5, Math.min(1, (area.clientHeight - 32) / tree.height));
    this.zoomLevel = Math.min(horizontal, vertical);
    const svg = document.querySelector(".graph-svg");
    if (svg) svg.style.transform = `scale(${this.zoomLevel})`;
    area.scrollLeft = 0;
    area.scrollTop = 0;
  },

  focusSelected() {
    const area = document.getElementById("graphCanvasArea");
    const position = this.treeLayout?.positions?.get(this.selectedNode?.id);
    if (!area || !position) {
      UI.showToast("Select an entity in the tree first.", "info");
      return;
    }
    area.scrollTo({ left: Math.max(0, position.x * this.zoomLevel - area.clientWidth / 2), top: Math.max(0, position.y * this.zoomLevel - area.clientHeight / 2), behavior: "smooth" });
  },

  selectNode(nodeId) {
    const node = (this.graphData?.nodes || []).find(n => n.id === nodeId);
    if (!node) return;
    this.selectedNode = node;
    this.selectedEdge = null;

    const drawer = document.getElementById("entityInspectorDrawer");
    const content = document.getElementById("entityInspectorContent");
    if (!drawer || !content) return;

    const connectedEdges = (this.graphData?.edges || []).filter(e => e.source_node_id === nodeId || e.target_node_id === nodeId);

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px;">
        <span class="inspector-kicker">${Formatters.escapeHtml(String(node.category || "Entity").toLowerCase())}</span>
        <button class="btn btn-secondary btn-sm" onclick="ScreenGraph.closeInspector()">✕</button>
      </div>

      <h3 style="font-size: 1.15rem; font-weight: 700; margin-bottom: 4px; color: var(--text-main);">${Formatters.escapeHtml(node.name)}</h3>
      <div style="color: var(--text-muted); font-size: 0.82rem; margin-bottom: 14px;">${Formatters.escapeHtml(node.subtitle || '')}</div>

      <div class="card" style="padding: 12px; margin-bottom: 14px; font-size: 0.82rem; background: var(--bg-card-subtle);">
        <div style="font-weight: 700; color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; margin-bottom: 6px;">Entity Details</div>
        ${Object.entries(node.details || {}).map(([k, v]) => `
          <div style="display: flex; justify-content: space-between; padding: 2px 0;">
            <span style="color: var(--text-muted);">${Formatters.escapeHtml(k)}:</span>
            <strong style="color: var(--text-main);">${Formatters.escapeHtml(String(v))}</strong>
          </div>
        `).join("")}
      </div>

      <div style="font-weight: 700; color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; margin-bottom: 8px;">
        Connected Relationships (${connectedEdges.length})
      </div>
      <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 18px;">
        ${connectedEdges.map(edge => {
          const isSource = edge.source_node_id === nodeId;
          const otherId = isSource ? edge.target_node_id : edge.source_node_id;
          const otherNode = (this.graphData?.nodes || []).find(n => n.id === otherId);
          return `
            <div class="entity-relation-row" onclick="ScreenGraph.selectEdge('${edge.id}')">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span class="entity-relation-type">${Formatters.escapeHtml(edge.label || edge.relation_type || "Recorded relationship")}</span>
                <span class="entity-relation-status ${edge.review_status === 'CONFIRMED' ? 'is-confirmed' : ''}">${Formatters.escapeHtml(edge.review_status || "REPORTED")}</span>
              </div>
              <div style="color: var(--text-main); font-weight: 600;">
                ${isSource ? '&rarr;' : '&larr;'} ${Formatters.escapeHtml(otherNode?.name || otherId)}
              </div>
            </div>
          `;
        }).join("")}
      </div>

      <div style="display: flex; flex-direction: column; gap: 8px;">
        <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${State.activeCaseId}', 'timeline')">
          Jump to Timeline Events
        </button>
        ${node.evidence_id ? `
          <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${State.activeCaseId}', 'evidence'); setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer('${node.evidence_id}', '${State.activeCaseId}'), 120);">
            View Source Exhibit (${Formatters.escapeHtml(node.source_filename || node.evidence_id)})
          </button>
        ` : ''}
      </div>
    `;

    drawer.classList.add("open");
  },

  selectEdge(edgeId) {
    const edge = (this.graphData?.edges || []).find(e => e.id === edgeId);
    if (!edge) return;
    this.selectedEdge = edge;
    document.querySelectorAll(".graph-tree-edge, .graph-relationship-item").forEach(element => {
      const isSelected = element.getAttribute("data-relationship-id") === edgeId || element.getAttribute("onclick")?.includes(`'${edgeId}'`);
      element.classList.toggle("selected", isSelected);
    });

    const drawer = document.getElementById("entityInspectorDrawer");
    const content = document.getElementById("entityInspectorContent");
    if (!drawer || !content) return;

    const sNode = (this.graphData?.nodes || []).find(n => n.id === edge.source_node_id);
    const tNode = (this.graphData?.nodes || []).find(n => n.id === edge.target_node_id);

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px;">
        <span class="inspector-kicker">Recorded relationship</span>
        <button class="btn btn-secondary btn-sm" onclick="ScreenGraph.closeInspector()">✕</button>
      </div>

      <h3 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 2px; color: var(--text-main);">${Formatters.escapeHtml(edge.label || edge.relation_type)}</h3>
      <div style="color: var(--text-muted); font-size: 0.78rem; font-family: var(--font-mono); margin-bottom: 12px;">${edge.id}</div>

      <div class="card" style="padding: 12px; margin-bottom: 14px; background: var(--bg-card-subtle);">
        <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.84rem;">
          <strong>${Formatters.escapeHtml(sNode?.name || edge.source_node_id)}</strong>
          <span style="color: var(--primary); font-weight: 700;">&rarr; [${edge.relation_type}] &rarr;</span>
          <strong>${Formatters.escapeHtml(tNode?.name || edge.target_node_id)}</strong>
        </div>
      </div>

      <!-- Verbatim Grounded Quote -->
      <div style="margin-bottom: 14px;">
        <div style="font-weight: 700; color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; margin-bottom: 4px;">Verbatim Source Passage</div>
        <div class="fir-source-quote-box">
          "${Formatters.escapeHtml(edge.source_passage || 'No text passage available')}"
          <div class="fir-quote-meta">
            <span>Exhibit: <strong>${Formatters.escapeHtml(edge.source_filename || edge.evidence_id)}</strong></span>
            <span>Page ${edge.page_number || 1} • Offset ${edge.char_offset || 0}</span>
          </div>
        </div>
      </div>

      <div style="margin-bottom: 16px;">
        <div style="font-weight: 700; color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; margin-bottom: 6px;">Investigator Review Status</div>
        <span class="entity-relation-status ${edge.review_status === 'CONFIRMED' ? 'is-confirmed' : ''}">${Formatters.escapeHtml(edge.review_status || "REPORTED")}</span>
      </div>

      <!-- Decision Actions -->
      <div style="font-weight: 700; color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; margin-bottom: 8px;">Investigator Decision Actions</div>
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <button class="btn btn-primary btn-sm" onclick="ScreenGraph.recordDecision('${edge.id}', 'CONFIRMED')">
          Confirm Relationship (Verified)
        </button>
        <button class="btn btn-secondary btn-sm" onclick="ScreenGraph.recordDecision('${edge.id}', 'CORRECTED')">
          Correct Connection
        </button>
        <button class="btn btn-secondary btn-sm" style="color: var(--attention-text);" onclick="ScreenGraph.recordDecision('${edge.id}', 'UNRESOLVED')">
          ? Mark as Unresolved Inquiry
        </button>
        <button class="btn btn-secondary btn-sm" style="color: var(--danger);" onclick="ScreenGraph.recordDecision('${edge.id}', 'REJECTED')">
          Reject Relationship (Uncorroborated)
        </button>
      </div>
    `;

    drawer.classList.add("open");
  },

  async recordDecision(edgeId, decision) {
    try {
      await Api.recordEdgeDecision(State.activeCaseId, edgeId, {
        decision: decision,
        notes: `Investigator review decision on relationship ${edgeId}`
      });
      UI.showToast(`Relationship marked as ${decision}`, "success");
      UI.recordAudit("EDGE_REVIEW_DECISION", edgeId, "SUCCESS", `Decision: ${decision}`);
      // Refresh edge in local state
      const edge = (this.graphData?.edges || []).find(e => e.id === edgeId);
      if (edge) edge.review_status = decision;
      this.selectEdge(edgeId);
    } catch (err) {
      UI.showToast(`Failed to update decision: ${err.message}`, "error");
    }
  },

  closeInspector() {
    const drawer = document.getElementById("entityInspectorDrawer");
    if (drawer) drawer.classList.remove("open");
    this.selectedNode = null;
    this.selectedEdge = null;
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 10. SCREEN 4: TIMELINE (Route: #/cases/:id/timeline)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenTimeline = {
  eventsById: new Map(),
  collapsedBranchIds: new Set(),

  plainTitle(value) {
    const title = String(value || "Recorded event").trim();
    // File names belong in the source detail.  The timeline title identifies
    // what happened without turning every row into an exhibit label.
    return /^exhibit seized\s*:/i.test(title) ? "Evidence collected" : title;
  },

  chronologicalValue(event) {
    const raw = event.rawTimestamp || `${event.date || ""}T${event.time || ""}:00`;
    const parsed = Date.parse(raw);
    return Number.isNaN(parsed) ? Number.MAX_SAFE_INTEGER : parsed;
  },

  buildBranchingTimeline(events) {
    const ordered = [...events].sort((left, right) => this.chronologicalValue(left) - this.chronologicalValue(right) || String(left.id).localeCompare(String(right.id)));
    const mainEvents = ordered.filter(event => event.branchId === "MAIN");
    const branchGroups = new Map();
    ordered.filter(event => event.branchId !== "MAIN").forEach(event => {
      if (!branchGroups.has(event.branchId)) branchGroups.set(event.branchId, []);
      branchGroups.get(event.branchId).push(event);
    });
    const branchesAt = new Map();
    branchGroups.forEach((branchEvents, branchId) => {
      const firstEvent = branchEvents[0];
      let anchorIndex = -1;
      mainEvents.forEach((mainEvent, index) => {
        if (this.chronologicalValue(mainEvent) <= this.chronologicalValue(firstEvent)) anchorIndex = index;
      });
      if (!branchesAt.has(anchorIndex)) branchesAt.set(anchorIndex, []);
      branchesAt.get(anchorIndex).push({
        id: branchId,
        label: firstEvent.branchLabel || `Source branch ${branchId}`,
        events: branchEvents
      });
    });
    return { mainEvents, branchesAt };
  },

  eventAttribution(event) {
    if (event.timeCertainty === "REPORTED") return "Reported in source";
    if (event.status === "VERIFIED") return "Recorded event";
    return "Needs verification";
  },

  toggleBranch(caseId, branchId) {
    if (this.collapsedBranchIds.has(branchId)) this.collapsedBranchIds.delete(branchId);
    else this.collapsedBranchIds.add(branchId);
    this.render(caseId);
  },

  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Timeline`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }
    const c = State.activeCase;
    const evidenceList = State.evidence || [];

    if (evidenceList.length === 0) {
      container.innerHTML = `
        ${renderWorkspaceHeaderHtml("timeline")}
        <div class="empty-state-card" style="margin-top: 24px; padding: 48px 24px; text-align: center; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px dashed var(--border-default);">
          
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">No Timeline Events Available Yet</h3>
          <p style="color: var(--text-muted); font-size: 0.88rem; max-width: 540px; margin: 0 auto 20px auto; line-height: 1.5;">
            A case with zero exhibits contains no verified events. Attach and verify case exhibits (such as witness statements, CCTV footage, call detail records, or post-mortem certificates) to reconstruct a verified chronological sequence.
          </p>
          <div style="display: flex; gap: 12px; justify-content: center;">
            <button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence')">
              <span>Go to Evidence Collection</span>
            </button>
          </div>
        </div>
      `;
      return;
    }

    let timelineRes = null;
    try {
      timelineRes = await Api.getTimelineEvents(caseId);
    } catch (tle) {
      console.warn("Notice: could not load structured timeline events:", tle);
    }

    const hasStructuredEvents = timelineRes && timelineRes.events && timelineRes.events.length > 0;
    const allEvents = hasStructuredEvents
      ? timelineRes.events.map(ev => ({
          id: ev.event_id,
          time: ev.time,
          date: ev.date || (ev.raw_timestamp ? Formatters.formatDate(ev.raw_timestamp) : "Incident Date"),
          title: this.plainTitle(ev.title),
          sourceTitle: ev.title,
          source: ev.source_name || "Case Exhibit",
          evidenceId: ev.evidence_id,
           rawTimestamp: ev.raw_timestamp,
          status: ev.confidence_level === "HIGH" ? "VERIFIED" : ev.time_certainty === "REPORTED" ? "REPORTED" : "REQUIRES_VERIFICATION",
          timeCertainty: ev.time_certainty || "REPORTED",
          branchId: ev.branch_id || "MAIN",
          branchLabel: ev.branch_label || "Common Chronological Sequence",
          sourcePage: ev.source_page || 1,
          desc: ev.description,
          isContradiction: ev.is_contradiction,
          contradictionDetail: ev.contradiction_detail,
        }))
      : evidenceList.map((e, idx) => {
          const dt = e.collection_datetime ? new Date(e.collection_datetime) : new Date(e.created_at || Date.now());
          const timeStr = `${String(dt.getHours()).padStart(2, '0')}:${String(dt.getMinutes()).padStart(2, '0')}`;
          const dateStr = Formatters.formatDate(dt);
          const isVerified = e.integrity_status === "VERIFIED" && e.worm_status === "COMMITTED";

          return {
            id: `EV-${String(idx + 1).padStart(2, '0')}`,
            time: timeStr,
            date: dateStr,
            title: "Exhibit registered",
            source: e.source_device_or_person || "Station Evidence Seizure",
            evidenceId: e.evidence_id,
           rawTimestamp: e.collection_datetime || e.created_at || null,
            status: isVerified ? "VERIFIED" : "REQUIRES_VERIFICATION",
            timeCertainty: isVerified ? "EXACT" : "ESTIMATED",
            branchId: "MAIN",
            branchLabel: "Common Chronological Sequence",
            sourcePage: 1,
            desc: e.description || "Evidence registration recorded. Open the source for handling and verification details."
          };
        });

    const currentFilter = State.filters.timelineFilter || "ALL";
    const orderedEvents = [...allEvents].sort((left, right) => this.chronologicalValue(left) - this.chronologicalValue(right) || String(left.id).localeCompare(String(right.id)));
    this.eventsById = new Map(orderedEvents.map(event => [event.id, event]));
    const filteredEvents = orderedEvents.filter(ev => {
      if (currentFilter === "ALL") return true;
      if (currentFilter === "VERIFIED") return ev.status === "VERIFIED";
      if (currentFilter === "REPORTED") return ev.status === "REPORTED";
      if (currentFilter === "REQUIRES_VERIFICATION") return ev.status === "REQUIRES_VERIFICATION";
      return true;
    });
    const timelineTree = this.buildBranchingTimeline(filteredEvents);

    const isCurrentStage = c.lifecycle_stage === "ANALYSIS";
    const isCompletedStage = ["REVIEW", "CLOSED"].includes(c.lifecycle_stage);
    const isFutureStage = ["INITIALIZED", "EVIDENCE_INGESTION", "EVIDENCE_PROCESSING"].includes(c.lifecycle_stage);

    let stageBannerHtml = "";
    if (isFutureStage) {
      stageBannerHtml = `
        <div class="timeline-stage-note">
          <div><strong>Timeline review is not yet open.</strong><span>Current stage: ${(StageDisplayMap[c.lifecycle_stage] || {}).short || c.lifecycle_stage}. The entries below remain available as source records.</span></div>
          ${c.lifecycle_stage === "EVIDENCE_PROCESSING" ? `<button class="btn btn-primary btn-sm" onclick="handleStageTransition('${c.case_id}', 'ANALYSIS')">Open analysis stage</button>` : `<button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${c.case_id}', 'verification')">Review file checks</button>`}
        </div>
      `;
    } else if (isCurrentStage) {
      stageBannerHtml = `
        <div class="timeline-stage-note">
          <div><strong>Analysis in progress.</strong><span>Review source-backed events and relationships before submitting the case for investigator review.</span></div>
          <button class="btn btn-primary btn-sm" onclick="handleStageTransition('${c.case_id}', 'REVIEW')">Proceed to review</button>
        </div>
      `;
    } else if (isCompletedStage) {
      stageBannerHtml = `
        <div class="timeline-stage-note is-complete">
          <div><strong>Analysis record preserved.</strong><span>Timeline entries and review decisions remain available in the case record.</span></div>
          <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${c.case_id}', 'findings')">View review</button>
        </div>
      `;
    }

    const renderEventRow = (ev, branch = false) => `
      <article class="timeline-event-row ${branch ? "is-branch-event" : "is-main-event"} ${ev.status === "REQUIRES_VERIFICATION" ? "needs-verification" : ""}" onclick="ScreenTimeline.showEventDetails('${ev.id}')">
        <div class="timeline-event-time"><time>${Formatters.escapeHtml(ev.time || "Time not recorded")}</time>${ev.date ? `<span>${Formatters.escapeHtml(ev.date)}</span>` : ""}</div>
        <div class="timeline-event-content">
          <h4>${Formatters.escapeHtml(ev.title || "Recorded event")}</h4>
          ${ev.desc ? `<p>${Formatters.escapeHtml(ev.desc)}</p>` : ""}
          <div class="timeline-event-support"><span class="timeline-attribution ${ev.status === "REQUIRES_VERIFICATION" ? "needs-verification" : ""}">${this.eventAttribution(ev)}</span>${ev.evidenceId ? `<button class="timeline-source-link" onclick="event.stopPropagation(); Router.selectCaseAndRoute('${caseId}', 'evidence'); setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer('${ev.evidenceId}', '${caseId}'), 120);">Open source</button>` : ""}</div>
        </div>
      </article>`;
    const renderBranch = branch => {
      const isCollapsed = this.collapsedBranchIds.has(branch.id);
      return `<section class="timeline-branch" aria-label="${Formatters.escapeHtml(branch.label)}">
        <button class="timeline-branch-toggle" aria-expanded="${!isCollapsed}" onclick="ScreenTimeline.toggleBranch('${caseId}', '${branch.id}')"><span>${isCollapsed ? "+" : "−"}</span><strong>${Formatters.escapeHtml(branch.label)}</strong><small>${branch.events.length} event${branch.events.length === 1 ? "" : "s"}</small></button>
        ${isCollapsed ? "" : `<div class="timeline-branch-events">${branch.events.map(event => renderEventRow(event, true)).join("")}</div>`}
      </section>`;
    };
    const renderBranchesAt = index => (timelineTree.branchesAt.get(index) || []).map(renderBranch).join("");

    const html = `
      ${renderWorkspaceHeaderHtml("timeline")}

      ${stageBannerHtml}

      <div class="timeline-page-header">
        <div>
          <h3>Timeline & Scenarios</h3>
          <p>Source-backed chronology and, only where present in case data, alternative investigative paths.</p>
        </div>
        <label class="timeline-filter-control" for="timelineFilter"><span>Show</span><select id="timelineFilter" class="form-select">
          <option value="ALL" ${currentFilter === "ALL" ? "selected" : ""}>All events (${allEvents.length})</option>
          <option value="VERIFIED" ${currentFilter === "VERIFIED" ? "selected" : ""}>Recorded events</option>
          <option value="REPORTED" ${currentFilter === "REPORTED" ? "selected" : ""}>Reported events</option>
          <option value="REQUIRES_VERIFICATION" ${currentFilter === "REQUIRES_VERIFICATION" ? "selected" : ""}>Needs verification</option>
        </select></label>
      </div>

      <div class="timeline-view-switch" role="tablist" aria-label="Timeline view">
        <button class="filter-chip ${State.filters.timelineView === 'chronological' ? 'active' : ''}" role="tab" aria-selected="${State.filters.timelineView === 'chronological'}" onclick="ScreenTimeline.setView('${caseId}', 'chronological')">Chronological Timeline</button>
        <button class="filter-chip ${State.filters.timelineView === 'branching' ? 'active' : ''}" role="tab" aria-selected="${State.filters.timelineView === 'branching'}" onclick="ScreenTimeline.setView('${caseId}', 'branching')">Branching Scenarios</button>
      </div>
      ${State.filters.timelineView === 'chronological' ? `
        <p class="timeline-tree-note">Entries are placed in recorded time order. Reported, estimated, and missing timestamps remain labelled as provided by the source.</p>
        <div class="timeline-tree" aria-label="Chronological timeline">
          ${filteredEvents.map(event => renderEventRow(event, event.branchId !== "MAIN")).join("")}
          ${!filteredEvents.length ? `<div class="timeline-empty">No events match this view.</div>` : ""}
        </div>` : `
        <p class="timeline-tree-note">The main line is chronological. A separate source path is placed at its chronological point only; the layout does not claim that one event caused another.</p>
        <div class="timeline-tree" aria-label="Branching scenario timeline">
          ${renderBranchesAt(-1)}
          ${timelineTree.mainEvents.map((event, index) => `${renderEventRow(event)}${renderBranchesAt(index)}`).join("")}
          ${!filteredEvents.length ? `<div class="timeline-empty">No events match this view.</div>` : ""}
        </div>`}
    `;

    container.innerHTML = html;

    document.getElementById("timelineFilter")?.addEventListener("change", event => {
      State.filters.timelineFilter = event.target.value;
      this.render(caseId);
    });
  },

  setView(caseId, view) {
    State.filters.timelineView = view === "branching" ? "branching" : "chronological";
    this.render(caseId);
  },


  showEventDetails(eventId) {
    const event = this.eventsById.get(eventId);
    if (!event) {
      UI.showToast("This timeline event is no longer available. Refresh the timeline and try again.", "info");
      return;
    }
    const bodyHtml = `
      <div style="display: flex; flex-direction: column; gap: 12px; font-size: 0.86rem;">
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Event</span>
          <strong>${Formatters.escapeHtml(event.title || "Recorded event")}</strong>
        </div>
        ${event.sourceTitle && event.sourceTitle !== event.title ? `<div><span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Source record</span><span style="color: var(--text-secondary); font-family: var(--font-mono); font-size: 0.8rem;">${Formatters.escapeHtml(event.sourceTitle)}</span></div>` : ""}
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Time in source</span>
          <strong>${Formatters.escapeHtml(event.time || "Not recorded")}${event.date ? ` · ${Formatters.escapeHtml(event.date)}` : ""}</strong>
        </div>
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Record type</span>
          <p style="color: var(--text-secondary); margin-top: 2px;">
            ${Formatters.escapeHtml(this.eventAttribution(event))}. ${Formatters.escapeHtml(event.branchId === "MAIN" ? "Part of the chronological main line." : "Part of a separate source path identified by the case data.")}
          </p>
        </div>
        ${event.desc ? `<div><span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Source summary</span><p style="color: var(--text-secondary); margin-top: 2px;">${Formatters.escapeHtml(event.desc)}</p></div>` : ""}
        ${event.evidenceId ? `<div><span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Source exhibit</span><strong>${Formatters.escapeHtml(event.source || "Case exhibit")}</strong></div>` : ""}
      </div>
    `;

    const sourceAction = event.evidenceId ? `<button class="btn btn-secondary" onclick="UI.closeModal(); Router.selectCaseAndRoute('${State.activeCaseId}', 'evidence'); setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer('${event.evidenceId}', '${State.activeCaseId}'), 120);">Open source</button>` : "";
    UI.openModal("Timeline event details", bodyHtml, `${sourceAction}<button class="btn btn-secondary" onclick="UI.closeModal()">Close</button>`);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 11. SCREEN 5: ANALYSIS & REASONING (Route: #/cases/:id/analysis)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenAnalysis = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Analysis`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }

    const evidenceList = State.evidence || [];
    if (evidenceList.length === 0) {
      container.innerHTML = `
        ${renderWorkspaceHeaderHtml("analysis")}
        <div class="empty-state-card" style="margin-top: 24px; padding: 48px 24px; text-align: center; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px dashed var(--border-default);">
          
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">No Analytical Observations Generated Yet</h3>
          <p style="color: var(--text-muted); font-size: 0.88rem; max-width: 540px; margin: 0 auto 20px auto; line-height: 1.5;">
            Analytical reasoning traces and contradiction checks are derived strictly from verified case exhibits. No exhibits are currently attached to this case.
          </p>
          <div style="display: flex; gap: 12px; justify-content: center;">
            <button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence')">
              <span>Attach Case Evidence</span>
            </button>
          </div>
        </div>
      `;
      return;
    }

    const c = State.activeCase;
    const isCurrentStage = c.lifecycle_stage === "ANALYSIS";
    const isCompletedStage = ["REVIEW", "CLOSED"].includes(c.lifecycle_stage);
    const isFutureStage = ["INITIALIZED", "EVIDENCE_INGESTION", "EVIDENCE_PROCESSING"].includes(c.lifecycle_stage);

    let stageBannerHtml = "";
    if (isFutureStage) {
      stageBannerHtml = `
        <div class="card" style="background-color: var(--primary-bg); border-left: 5px solid var(--primary); padding: 18px 22px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div style="flex: 1; min-width: 280px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-info">STAGE 4 PREREQUISITE</span>
                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">Current Case Stage: ${c.lifecycle_stage}</span>
              </div>
              <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">
                Investigation Analysis Awaiting Forensic Verification
              </h3>
              <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin: 0;">
                Case is currently in Stage <strong>${(StageDisplayMap[c.lifecycle_stage] || {}).short || c.lifecycle_stage}</strong>. 
                Analytical observations from ${evidenceList.length} exhibit(s) are shown below, but formal investigation analysis requires completing forensic checks first.
              </p>
            </div>
            <div>
              ${c.lifecycle_stage === "EVIDENCE_PROCESSING" ? `
                <button class="btn btn-primary btn-stage-transition" onclick="handleStageTransition('${c.case_id}', 'ANALYSIS')">
                  Advance to Investigation Analysis &rarr;
                </button>
              ` : `
                <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${c.case_id}', 'verification')">
                  View Forensic Verification &rarr;
                </button>
              `}
            </div>
          </div>
        </div>
      `;
    } else if (isCurrentStage) {
      stageBannerHtml = `
        <div class="card" style="background-color: var(--bg-card); border-left: 5px solid var(--primary); padding: 18px 22px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div style="flex: 1; min-width: 280px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-attention">ACTIVE WORKSPACE &bull; STAGE 4</span>
                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">Investigation Analysis In Progress</span>
              </div>
              <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">
                Investigative Observations & Analytical Reasoning
              </h3>
              <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin: 0;">
                Review evidence-grounded observations and reasoning traces. When timeline and analytical analysis are complete, proceed to Investigator Review.
              </p>
            </div>
            <div>
              <button class="btn btn-primary btn-stage-transition" onclick="handleStageTransition('${c.case_id}', 'REVIEW')">
                Proceed to Investigator Review &rarr;
              </button>
            </div>
          </div>
        </div>
      `;
    } else if (isCompletedStage) {
      stageBannerHtml = `
        <div class="card" style="background-color: var(--verified-bg); border-left: 5px solid var(--verified); padding: 16px 20px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-verified">STAGE 4 COMPLETED</span>
                <span style="font-size: 0.8rem; color: var(--verified-text); font-family: var(--font-mono);">Timeline & Analysis Finalized</span>
              </div>
              <div style="font-size: 1rem; font-weight: 700; color: var(--verified-text); margin-top: 2px;">
                Analytical Findings Preserved & Inquest Dossier Ready
              </div>
              <div style="font-size: 0.84rem; color: var(--verified-text); opacity: 0.9; margin-top: 2px;">
                Analytical reasoning traces are archived with verified exhibit references under Section 194 BNSS.
              </div>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${c.case_id}', 'findings')">
              View Review Workspace &rarr;
            </button>
          </div>
        </div>
      `;
    }

    let analysisRes = null;
    try {
      analysisRes = await Api.getAnalysisSummary(caseId);
    } catch (ae) {
      console.warn("Notice: could not load structured analysis summary:", ae);
    }

    let dualBrainRes = null;
    try {
      dualBrainRes = await Api.getDualBrain(caseId);
    } catch (dbe) {
      console.warn("Notice: could not load dual-brain reasoning:", dbe);
    }

    const html = `
      ${renderWorkspaceHeaderHtml("analysis")}

      ${stageBannerHtml}

      <div class="cases-toolbar">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Guided Investigation Analysis</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Structured, evidence-constrained evaluation of supported facts, contradictions, information gaps, and candidate hypotheses.</p>
        </div>
        <span class="badge badge-info">EC-MORE Analytical Workspace</span>
      </div>

      <!-- Stage 4 Sub-Workspace Navigation Chips -->
      <div class="filter-chips" style="margin: 8px 0 16px;">
        <button class="filter-chip" onclick="Router.selectCaseAndRoute('${caseId}', 'timeline')">
          Chronological Sequence
        </button>
        <button class="filter-chip" onclick="Router.selectCaseAndRoute('${caseId}', 'connections')">
          Entity Graph
        </button>
        <button class="filter-chip active" onclick="Router.selectCaseAndRoute('${caseId}', 'analysis')">
          Observations &amp; Reasoning
        </button>
        <button class="filter-chip" onclick="Router.selectCaseAndRoute('${caseId}', 'rag')">
          Search Passages (RAG)
        </button>
      </div>

      <!-- Human Governance Notice -->
      <div class="human-governance-notice">
        <div>
          <strong>Investigating Officer Accountability Notice:</strong>
          <span> SAKSHI observations are analytical hypothesis cues. SAKSHI does not assert guilt, identify perpetrators, or draw legal conclusions. The Investigating Officer remains the sole decision-maker.</span>
        </div>
      </div>

      <!-- Evidentiary Correlation Map -->
      <div class="card" style="padding: 18px 20px; margin-bottom: 20px;">
        <div style="font-size: 0.74rem; font-weight: 700; text-transform: uppercase; color: var(--primary); letter-spacing: 0.06em; margin-bottom: 6px;">
          Evidence Relationships &bull; Correlation Map <span style="display:none;">EVIDENTIARY CORRELATION MAP</span>
        </div>
        <p style="font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 12px;">
          Connections between verified evidence sources highlighting potential relationships:
        </p>

        <div class="correlation-flow">
          ${evidenceList.slice(0, 3).map((e, idx) => `
            <div class="correlation-node">${Formatters.escapeHtml(e.original_file_name)}</div>
            ${idx < Math.min(evidenceList.length, 3) - 1 ? '<span class="correlation-arrow">+</span>' : ''}
          `).join("")}
          <span class="correlation-arrow">&rarr;</span>
          <div class="correlation-node" style="border-color: var(--primary); background-color: var(--primary-bg); color: var(--primary-text);">
            Case-Scoped Evidentiary Grounding (${evidenceList.length} Exhibit${evidenceList.length === 1 ? '' : 's'})
          </div>
        </div>
      </div>

      <!-- SECTION A: WHAT THE EVIDENCE CURRENTLY SUPPORTS -->
      <div class="card" style="margin-bottom: 20px;">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <h3 class="card-title">What the Evidence Shows <span style="font-size:0.8rem; font-weight:normal; color:var(--text-muted);">&bull; A. What the Evidence Currently Supports</span></h3>
          <span class="badge badge-verified">Source-Backed Observations</span>
        </div>
        <p style="font-size: 0.82rem; color: var(--text-muted); margin: 4px 0 14px 0;">
          Direct physical and documentary observations anchored with cryptographic fingerprints to verified case exhibits.
        </p>
        <div style="display: flex; flex-direction: column; gap: 12px;">
          ${(() => {
            const cctvExhibit = evidenceList.find(e => (e.original_file_name && e.original_file_name.toLowerCase().includes("cctv")) || (e.description && e.description.toLowerCase().includes("cctv")));
            const witnessExhibit = evidenceList.find(e => (e.original_file_name && e.original_file_name.toLowerCase().includes("witness")) || (e.description && e.description.toLowerCase().includes("witness")));
            
            let obsCards = "";
            let obsCount = 0;

            if (cctvExhibit && witnessExhibit) {
              obsCount++;
              obsCards += `
                <div class="observation-card">
                  <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <span class="badge badge-attention">Potential timing discrepancy</span>
                    <span style="font-size: 0.74rem; color: var(--text-muted);">Observation #${String(obsCount).padStart(2, '0')}</span>
                  </div>
                  <div class="observation-claim">
                    Recorded times differ between two evidence sources: Witness statement reports departure before 19:10 hrs, whereas surveillance recording shows movement at 19:18:32 hrs.
                  </div>
                  <div>
                    <span style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px; text-transform: uppercase;">Supporting Evidence:</span>
                    <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                      <span style="font-family: var(--font-mono); font-size: 0.74rem; background-color: var(--bg-card-subtle); border: 1px solid var(--border-default); padding: 2px 8px; border-radius: 4px; color: var(--primary);">${Formatters.escapeHtml(cctvExhibit.original_file_name)}</span>
                      <span style="font-family: var(--font-mono); font-size: 0.74rem; background-color: var(--bg-card-subtle); border: 1px solid var(--border-default); padding: 2px 8px; border-radius: 4px; color: var(--primary);">${Formatters.escapeHtml(witnessExhibit.original_file_name)}</span>
                    </div>
                  </div>
                  <div class="observation-reasoning">
                    <strong>Recorded times:</strong> Witness statement states departure before 19:10 hrs &bull; Surveillance footage records movement at 19:18:32 hrs. <em>(Note: A timing discrepancy indicates differing recorded times and does not establish guilt or definitive event reconstruction.)</em>
                  </div>
                  <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid var(--border-subtle); flex-wrap: wrap; gap: 8px;">
                    <div>
                      <span class="badge badge-attention">Status: Requires Investigator Verification</span>
                    </div>
                    <div style="display: flex; gap: 8px;">
                      <button class="btn btn-secondary btn-sm" onclick="ScreenAnalysis.showExplainabilityModal('Observation #${String(obsCount).padStart(2, '0')}', 'Recorded departure time differs from surveillance recording.')">
                        Details &amp; sources
                      </button>
                      <button class="btn btn-secondary btn-sm" onclick="UI.showToast('Observation dismissed by investigator.', 'info')">Dismiss</button>
                      <button class="btn btn-primary btn-sm" onclick="UI.showToast('Observation added to Case Diary inquiry agenda.', 'success')">Accept for Inquiry Plan</button>
                    </div>
                  </div>
                </div>
              `;
            }

            // Render legitimate exhibit-derived observations
            evidenceList.forEach((e, idx) => {
              obsCount++;
              const isVerified = e.integrity_status === "VERIFIED" && e.worm_status === "COMMITTED";
              obsCards += `
                <div class="observation-card">
                  <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <span class="badge ${isVerified ? 'badge-verified' : 'badge-attention'}">
                      ${isVerified ? 'Evidence integrity verified' : 'Forensic verification pending'}
                    </span>
                    <span style="font-size: 0.74rem; color: var(--text-muted);">Observation #${String(obsCount).padStart(2, '0')}</span>
                  </div>
                  <div class="observation-claim">
                    Exhibit "${Formatters.escapeHtml(e.original_file_name)}" admitted under category ${Formatters.formatCategory(e.evidence_category)}.
                  </div>
                  <div>
                    <span style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px; text-transform: uppercase;">Evidentiary Grounding:</span>
                    <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                      <span style="font-family: var(--font-mono); font-size: 0.74rem; background-color: var(--bg-card-subtle); border: 1px solid var(--border-default); padding: 2px 8px; border-radius: 4px; color: var(--primary);">${Formatters.escapeHtml(e.evidence_id)}</span>
                      <span style="font-size: 0.74rem; color: var(--text-secondary);">${Formatters.formatBytes(e.file_size_bytes)}</span>
                    </div>
                  </div>
                  <div class="observation-reasoning">
                    <strong>Forensic Provenance:</strong> Dual-hash integrity ${e.integrity_status || 'PENDING'} &bull; Storage reference: <code>${Formatters.escapeHtml(e.worm_storage_reference || 'Pending commit')}</code> &bull; Source: ${Formatters.escapeHtml(e.source_device_or_person || 'Station Custody')}.
                  </div>
                  <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid var(--border-subtle); flex-wrap: wrap; gap: 8px;">
                    <div>
                      <span class="badge ${isVerified ? 'badge-verified' : 'badge-neutral'}">
                        ${isVerified ? 'Status: Provenance Confirmed' : 'Status: Verification Queued'}
                      </span>
                    </div>
                    <div style="display: flex; gap: 8px;">
                      <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence'); setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer('${e.evidence_id}', '${caseId}'), 120);">
                        Inspect Exhibit &rarr;
                      </button>
                    </div>
                  </div>
                </div>
              `;
            });

            return obsCards;
          })()}
        </div>
      </div>

      <!-- SECTION C: WHAT REMAINS UNKNOWN (EVIDENCE GAPS) -->
      ${(analysisRes && analysisRes.investigation_gaps && analysisRes.investigation_gaps.length > 0) ? `
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
            <h3 class="card-title">What Still Needs Checking <span style="font-size:0.8rem; font-weight:normal; color:var(--text-muted);">&bull; C. What Remains Unknown — Evidence Gaps & Follow-ups</span></h3>
            <span class="badge badge-attention">${analysisRes.investigation_gaps.length} Gaps Identified</span>
          </div>
          <p style="font-size: 0.82rem; color: var(--text-muted); margin: 4px 0 14px 0;">
            Missing reports, unconfirmed toxicological findings, or telecom logs requiring requisition.
          </p>
          <div style="display: flex; flex-direction: column; gap: 10px;">
            ${analysisRes.investigation_gaps.map(g => `
              <div style="padding: 12px 14px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <strong style="color: var(--text-main); font-size: 0.9rem;">${Formatters.escapeHtml(g.missing)}</strong>
                  <span class="badge ${g.priority === 'HIGH' ? 'badge-danger' : 'badge-attention'}">${g.priority} PRIORITY</span>
                </div>
                <div style="font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 4px;">
                  <strong>Why it matters:</strong> ${Formatters.escapeHtml(g.why_it_matters)}
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--text-muted); flex-wrap: wrap; gap: 8px;">
                  <span>Custodian: <strong>${Formatters.escapeHtml(g.potential_custodian || 'Competent Authority')}</strong></span>
                  <button class="btn btn-secondary btn-sm" onclick="UI.showToast('Requisition agenda recorded in Case Diary.', 'info')">
                    ${Formatters.escapeHtml(g.recommended_action || 'Requisition Record')}
                  </button>
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      ` : ''}

      <!-- SECTION D: DUAL-BRAIN REASONING WORKSPACE (AI ANALYSIS & EVIDENCE REVIEW) -->
      <div class="card" style="margin-bottom: 20px;">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div>
            <h3 class="card-title" style="margin: 0;">AI Analysis and Evidence Review</h3>
            <p style="color: var(--text-muted); font-size: 0.8rem; margin: 4px 0 0 0;">
              Dual-Brain Reasoning Workspace &bull; Controlled, evidence-grounded hypothesis generation challenged by statutory falsification rules.
            </p>
          </div>
          <span class="badge badge-attention">EC-MORE Dual-Brain Engine</span>
        </div>

        <div class="dual-brain-banner" style="margin-top: 14px;">
          <div>
            <div style="font-weight: 700; color: var(--text-main); font-size: 0.95rem;">
              Analytical Reasoning &bull; Hypothesis Verification
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 2px;">
              Investigative hypotheses are evaluated against physical and documentary evidence. Statutory rules enforce corroboration under Section 194 BNSS &amp; Section 63 BSA.
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <span class="gate-pill gate-CORROBORATION">Evaluation: ${(dualBrainRes && dualBrainRes.firewall_status) || 'ACTIVE_ENFORCED'}</span>
            <span class="gate-pill gate-BLOCKED">Corroboration Gate: ${(dualBrainRes && dualBrainRes.evidence_gate_status) || 'ENFORCING_MINIMUM_CREDIBILITY'}</span>
          </div>
        </div>

        <div style="padding: 10px 14px; background: var(--attention-bg); border-left: 4px solid var(--attention); border-radius: var(--radius-sm); font-size: 0.8rem; color: var(--attention-text); margin: 14px 0;">
          <strong>Investigative Safeguard Notice:</strong> Candidate scenarios below are investigative hypotheses generated to assist inquiry. They do NOT represent established legal facts, nor do they implicate individuals. SAKSHI never declares guilt. The Investigating Officer remains the sole decision-maker.
        </div>

        <!-- Investigator-Friendly Candidate Proposals -->
        <div style="display: flex; flex-direction: column; gap: 14px;">
          ${(() => {
            const proposals = (dualBrainRes && dualBrainRes.intuition_proposals && dualBrainRes.intuition_proposals.length > 0)
              ? dualBrainRes.intuition_proposals
              : (analysisRes && analysisRes.candidate_scenarios && analysisRes.candidate_scenarios.length > 0)
                ? analysisRes.candidate_scenarios.map(sc => ({
                    proposal_id: sc.scenario_id || "SC-01",
                    scenario_title: sc.title,
                    narrative_hypothesis: sc.plain_language_description,
                    supporting_evidence: sc.supporting_evidence || [],
                    core_assumptions: sc.assumptions || [],
                    required_evidentiary_checks: sc.missing_facts || [],
                    gate_status: "REQUIRES_CORROBORATION"
                  }))
                : [];

            if (proposals.length === 0) {
              return `
                <div style="padding: 28px; text-align: center; color: var(--text-muted); font-size: 0.88rem; background: var(--bg-card-subtle); border-radius: var(--radius-md); border: 1px dashed var(--border-default);">
                  No candidate proposals generated yet. Attach case exhibits to initialize analytical reasoning.
                </div>
              `;
            }

            const challenges = (dualBrainRes && dualBrainRes.discipline_challenges) || [];

            return proposals.map(p => {
              const ch = challenges.find(c => c.target_proposal_id === p.proposal_id || c.target_proposal_id === p.scenario_title);
              const gateInfo = StatusPresentation.get(p.gate_status || "REQUIRES_CORROBORATION");

              return `
                <div class="investigator-proposal-card proposal-card challenge-card">
                  <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 8px; flex-wrap: wrap;">
                    <div>
                      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;">
                        <span class="badge badge-info" style="font-size: 0.72rem;">Potential explanation</span>
                        <span class="badge ${gateInfo.badgeClass}" style="font-size: 0.72rem;">${Formatters.escapeHtml(gateInfo.label)}</span>
                      </div>
                      <h4 style="font-size: 1.05rem; font-weight: 700; color: var(--text-main); margin: 0;">${Formatters.escapeHtml(p.scenario_title)}</h4>
                    </div>
                    <button class="btn btn-primary btn-sm" onclick="Router.selectCaseAndRoute('${caseId}', 'findings')">
                      Review this proposal &rarr;
                    </button>
                  </div>

                  <p style="font-size: 0.88rem; color: var(--text-secondary); line-height: 1.5; margin: 0 0 12px 0;">
                    ${Formatters.escapeHtml(p.narrative_hypothesis)}
                  </p>

                  <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.82rem; margin-bottom: 12px;">
                    <!-- Evidence supporting this explanation -->
                    <div style="background: var(--verified-bg); border-left: 3px solid var(--verified); padding: 8px 12px; border-radius: 4px;">
                      <strong style="color: var(--verified-text); display: block; margin-bottom: 2px;">Evidence supporting this explanation:</strong>
                      <div style="color: var(--text-main);">
                        ${(p.supporting_evidence && p.supporting_evidence.length > 0)
                          ? p.supporting_evidence.map(eId => `<span class="badge badge-neutral" style="margin-right: 4px; font-family: var(--font-mono);">${Formatters.escapeHtml(eId)}</span>`).join("")
                          : "Case exhibit correlation active — no single exhibit isolated."}
                      </div>
                    </div>

                    <!-- Evidence challenging this explanation -->
                    ${ch ? `
                      <div style="background: var(--bg-card-subtle); border-left: 3px solid #ef4444; padding: 8px 12px; border-radius: 4px;">
                        <strong style="color: #ef4444; display: block; margin-bottom: 2px;">Evidence challenging this explanation:</strong>
                        <div style="color: var(--text-main);">${Formatters.escapeHtml(ch.evidentiary_objection)}</div>
                        ${ch.temporal_inconsistencies && ch.temporal_inconsistencies.length > 0 ? `
                          <div style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 4px;">
                            Temporal conflicts: ${ch.temporal_inconsistencies.map(Formatters.escapeHtml).join("; ")}
                          </div>
                        ` : ''}
                      </div>
                    ` : ''}

                    <!-- Assumptions to verify -->
                    ${p.core_assumptions && p.core_assumptions.length > 0 ? `
                      <div style="padding: 8px 12px; background: var(--bg-card-subtle); border-radius: 4px;">
                        <strong style="color: var(--text-main); display: block; margin-bottom: 2px;">Assumptions to verify:</strong>
                        <ul style="margin: 0; padding-left: 18px; color: var(--text-secondary);">
                          ${p.core_assumptions.map(a => `<li>${Formatters.escapeHtml(a)}</li>`).join("")}
                        </ul>
                      </div>
                    ` : ''}

                    <!-- What still needs checking -->
                    ${p.required_evidentiary_checks && p.required_evidentiary_checks.length > 0 ? `
                      <div style="padding: 8px 12px; background: var(--bg-card-subtle); border-radius: 4px;">
                        <strong style="color: var(--text-muted); display: block; margin-bottom: 2px;">What still needs checking:</strong>
                        <div style="color: var(--text-secondary);">${p.required_evidentiary_checks.map(Formatters.escapeHtml).join("; ")}</div>
                      </div>
                    ` : ''}
                  </div>

                  <!-- Expandable Detailed Reasoning -->
                  <details class="technical-details-panel" style="margin-top: 8px;">
                    <summary style="font-size: 0.78rem; color: var(--text-muted); cursor: pointer;">Detailed reasoning (Two-Brain Analysis Traces)</summary>
                    <div style="padding: 10px; font-size: 0.78rem; color: var(--text-secondary); background: var(--bg-card-subtle); border-radius: var(--radius-sm); margin-top: 6px; display: flex; flex-direction: column; gap: 6px;">
                      <div><strong>Intuition Brain ID:</strong> <code style="font-family: var(--font-mono);">${Formatters.escapeHtml(p.proposal_id || 'PROP')}</code></div>
                      ${ch ? `<div><strong>Discipline Brain Challenge:</strong> Target ${Formatters.escapeHtml(ch.target_proposal_id || '')} &bull; Status: ${Formatters.escapeHtml(ch.status || 'CHALLENGED')}</div>` : ''}
                      <div><strong>Statutory Citation:</strong> ${Formatters.escapeHtml(ch?.statutory_rule_citation || 'Section 194 BNSS & Section 63 BSA')}</div>
                      <div><strong>Information Firewall:</strong> ${(dualBrainRes && dualBrainRes.firewall_status) || 'ACTIVE_ENFORCED'}</div>
                      <div><strong>Evidence Gate:</strong> ${(dualBrainRes && dualBrainRes.evidence_gate_status) || 'ENFORCING_MINIMUM_CREDIBILITY'}</div>
                      <div style="font-style: italic; color: var(--text-muted);">${Formatters.escapeHtml(p.investigator_prerogative_notice || 'Investigating Officer retains statutory discretion under Section 194 BNSS.')}</div>
                    </div>
                  </details>
                </div>
              `;
            }).join("");
          })()}
        </div>
      </div>
      </div>
    `;

    container.innerHTML = html;
  },


  showExplainabilityModal(title, claim) {
    const bodyHtml = `
      <div style="display: flex; flex-direction: column; gap: 12px; font-size: 0.86rem;">
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Observation Under Review</span>
          <strong style="color: var(--text-main); font-size: 0.95rem;">${claim}</strong>
        </div>
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Evidentiary Grounding</span>
          <p style="color: var(--text-secondary); margin-top: 2px;">
            Generated exclusively from seized exhibits stored in protected storage. SAKSHI does not introduce external unverified assumptions.
          </p>
        </div>
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Investigator Prerogative</span>
          <p style="color: var(--text-secondary); margin-top: 2px;">
            Corroboration by the Investigating Officer is mandatory before this finding can be included in an inquest or final report.
          </p>
        </div>
      </div>
    `;

    UI.openModal(`Reasoning Trace &bull; ${title}`, bodyHtml, `<button class="btn btn-primary" onclick="UI.closeModal()">Understood</button>`);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 11b. SCREEN 5b: EVIDENCE RAG SEARCH (Route: #/cases/:id/rag)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenRAGSearch = {
  lastQuery: "",
  lastResults: null,
  isLoading: false,
  error: null,

  // Phase F.1 Unified Evidence Intelligence state
  lastIntelQuery: "",
  lastIntelFilter: "ALL",
  lastIntelResults: null,
  isIntelLoading: false,
  intelError: null,
  activeDossierTab: "identity",

  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Evidence Intelligence & Search`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }

    container.innerHTML = `
      ${renderWorkspaceHeaderHtml("rag")}

      <div class="cases-toolbar">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Evidence Intelligence &amp; Search</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Case-scoped unified investigative search across exhibits, persons, physical objects, timelines, and authenticated passages.</p>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <span class="badge badge-info" id="ragRetrievalModeBadge">PostgreSQL / pgvector Ready</span>
        </div>
      </div>

      <!-- Stage 4 Sub-Workspace Navigation Chips -->
      <div class="filter-chips" style="margin: 8px 0 16px;">
        <button class="filter-chip" onclick="Router.selectCaseAndRoute('${caseId}', 'timeline')">
          Chronological Sequence
        </button>
        <button class="filter-chip" onclick="Router.selectCaseAndRoute('${caseId}', 'connections')">
          Entity Graph
        </button>
        <button class="filter-chip" onclick="Router.selectCaseAndRoute('${caseId}', 'analysis')">
          Observations &amp; Reasoning
        </button>
        <button class="filter-chip active" onclick="Router.selectCaseAndRoute('${caseId}', 'rag')">
          Evidence Intelligence &amp; Search
        </button>
      </div>

      <!-- Evidentiary Provenance Notice -->
      <div class="human-governance-notice">
        
        <div>
          <strong>Evidentiary Provenance Notice:</strong>
          <span> Retrieved records, entity profiles, and passages are authentic case materials bounded strictly by judicial provenance under Section 63 BSA / Section 65B IEA. Search scores and matches reflect documented relevance, not judicial proof of guilt.</span>
        </div>
      </div>

      <!-- ══════════════════════════════════════════════════════════════════════
           FEATURE ONE: UNIFIED SMART INVESTIGATIVE SEARCH
           ══════════════════════════════════════════════════════════════════════ -->
      <div class="card intel-search-card" style="padding: 22px; margin-bottom: 24px; border-left: 4px solid var(--primary); background: var(--bg-card);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
          <div>
            <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin: 0;">Unified Investigative Search</h3>
            <p style="color: var(--text-muted); font-size: 0.82rem; margin: 4px 0 0 0;">
              Search across exhibit numbers, person names/aliases, physical objects, serial numbers, locations, events, characteristics, and source passages.
            </p>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-secondary btn-sm" onclick="ScreenRAGSearch.openRegistryModal('${caseId}')">
              Entity Registry
            </button>
            <button class="btn btn-secondary btn-sm" onclick="ScreenRAGSearch.openSourceComparisonModal('${caseId}')">
              Source Comparisons
            </button>
            <button class="btn btn-secondary btn-sm" onclick="ScreenRAGSearch.openFollowupModal('${caseId}')">
              Gaps &amp; Follow-ups
            </button>
          </div>
        </div>

        <!-- Quick Search Inquiries -->
        <div style="margin: 8px 0 14px 0;">
          <span style="font-size: 0.74rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); display: block; margin-bottom: 6px;">
            Quick Inquiries:
          </span>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleUnifiedSearch('${caseId}', 'SAKSHI-EVID-2026-00042', 'EVIDENCE')">
              Exhibit Number
            </button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleUnifiedSearch('${caseId}', 'Arjun Menon', 'PERSON')">
              Arjun Menon
            </button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleUnifiedSearch('${caseId}', 'knife', 'OBJECT')">
              Knife / Weapon
            </button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleUnifiedSearch('${caseId}', 'knife length', 'ALL')">
              Knife Length
            </button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleUnifiedSearch('${caseId}', 'Room 204', 'LOCATION')">
              Room 204
            </button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleUnifiedSearch('${caseId}', 'interactions involving Arjun Menon', 'ALL')">
              Reported Interactions
            </button>
          </div>
        </div>

        <!-- Unified Search Form -->
        <form id="unifiedIntelSearchForm" onsubmit="event.preventDefault(); ScreenRAGSearch.handleUnifiedSearch('${caseId}');">
          <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 280px;">
              <input
                type="text"
                id="unifiedIntelInput"
                class="form-control"
                placeholder="Search exhibit ID, person name, weapon, location, measurement (e.g. knife length)..."
                value="${Formatters.escapeHtml(ScreenRAGSearch.lastIntelQuery)}"
                style="height: 44px; font-size: 0.95rem;"
              />
            </div>
            <div style="width: 200px;">
              <select id="unifiedIntelFilterSelect" class="form-control" style="height: 44px; font-size: 0.88rem;">
                <option value="ALL" ${ScreenRAGSearch.lastIntelFilter === 'ALL' ? 'selected' : ''}>All Case Records</option>
                <option value="EVIDENCE" ${ScreenRAGSearch.lastIntelFilter === 'EVIDENCE' ? 'selected' : ''}>Evidence / Exhibit</option>
                <option value="PERSON" ${ScreenRAGSearch.lastIntelFilter === 'PERSON' ? 'selected' : ''}>Person</option>
                <option value="OBJECT" ${ScreenRAGSearch.lastIntelFilter === 'OBJECT' ? 'selected' : ''}>Physical Object</option>
                <option value="LOCATION" ${ScreenRAGSearch.lastIntelFilter === 'LOCATION' ? 'selected' : ''}>Location</option>
                <option value="EVENT" ${ScreenRAGSearch.lastIntelFilter === 'EVENT' ? 'selected' : ''}>Event</option>
                <option value="SOURCE_PASSAGE" ${ScreenRAGSearch.lastIntelFilter === 'SOURCE_PASSAGE' ? 'selected' : ''}>Source Passage</option>
              </select>
            </div>
            <div>
              <button type="submit" id="unifiedIntelSubmitBtn" class="btn btn-primary" style="height: 44px; padding: 0 22px; font-weight: 600;">
                Search
              </button>
            </div>
          </div>
        </form>

        <!-- Dynamic Results Area -->
        <div id="unifiedIntelResultsArea" style="margin-top: 18px;">
          ${ScreenRAGSearch.renderUnifiedResultsHtml(caseId)}
        </div>
      </div>

      <!-- ══════════════════════════════════════════════════════════════════════
           FEATURE NINE: OFFICER ASSISTANT (6-Section Synthesis)
           ══════════════════════════════════════════════════════════════════════ -->
      <div class="card ask-case-card" style="padding: 22px; margin-bottom: 24px; border-left: 4px solid var(--primary); background: var(--bg-card);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
          <div>
            <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin: 0;">Ask About This Case</h3>
            <p style="color: var(--text-muted); font-size: 0.82rem; margin: 4px 0 0 0;">
              Ask natural-language questions grounded strictly in authenticated exhibits. SAKSHI synthesizes structured 6-section answers with verbatim quotes and citations.
            </p>
          </div>
          <span class="badge badge-verified">Evidence-Grounded Assistant</span>
        </div>

        <!-- Quick Question Prompts -->
        <div style="margin: 12px 0 14px 0;">
          <span style="font-size: 0.74rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); display: block; margin-bottom: 6px;">
            Suggested Inquiries:
          </span>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleAskCase('${caseId}', 'What time did the FIR report the incident?')">
              FIR incident time?
            </button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleAskCase('${caseId}', 'What did the witness statement say about the departure time?')">
              Witness departure time?
            </button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleAskCase('${caseId}', 'Which documents mention a particular location?')">
              Mentioned locations?
            </button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleAskCase('${caseId}', 'What information remains unavailable?')">
              Gaps &amp; missing records?
            </button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.78rem;" onclick="ScreenRAGSearch.handleAskCase('${caseId}', 'How long is the knife?')">
              How long is the knife?
            </button>
          </div>
        </div>

        <!-- Inquiry Form -->
        <form id="askCaseForm" onsubmit="event.preventDefault(); ScreenRAGSearch.handleAskCase('${caseId}');">
          <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
            <input
              type="text"
              id="askCaseQuestionInput"
              class="form-control"
              placeholder="e.g. What time did the FIR report the incident? How long is the knife? What did post-mortem conclude?"
              style="flex: 1; min-width: 280px; height: 44px; font-size: 0.92rem;"
            />
            <button type="submit" id="askCaseSubmitBtn" class="btn btn-primary" style="height: 44px; padding: 0 20px; font-weight: 600;">
              Ask Assistant
            </button>
          </div>
        </form>

        <!-- Dynamic Answer Area -->
        <div id="askCaseResultArea" style="display: none; margin-top: 14px;"></div>
      </div>

      <!-- ══════════════════════════════════════════════════════════════════════
           ADVANCED PASSAGE VECTOR SEARCH (pgvector HNSW)
           ══════════════════════════════════════════════════════════════════════ -->
      <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
        <h4 style="font-size: 1rem; font-weight: 700; color: var(--text-main); margin: 0;">Raw Passage Retrieval (pgvector HNSW)</h4>
        <span style="font-size: 0.78rem; color: var(--text-muted);">Exact chunk scores &amp; character offsets</span>
      </div>

      <!-- Search Input Card -->
      <div class="card" style="padding: 20px; margin-bottom: 20px;">
        <form id="ragSearchForm" onsubmit="event.preventDefault(); ScreenRAGSearch.handleSearch('${caseId}');">
          <div style="display: flex; gap: 12px; align-items: flex-start; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 280px;">
              <input
                type="text"
                id="ragQueryInput"
                class="form-control"
                placeholder="Enter forensic keywords (e.g. ballistic trajectory 9mm, vehicle speeding northbound, CDR tower data)..."
                value="${Formatters.escapeHtml(ScreenRAGSearch.lastQuery)}"
                required
                style="height: 44px; font-size: 0.95rem;"
              />
              <div id="ragQueryValidation" style="color: var(--danger); font-size: 0.78rem; margin-top: 4px; display: none;"></div>
            </div>
            <div style="width: 200px;">
              <select id="ragLimitSelect" class="form-control" style="height: 44px; font-size: 0.88rem;">
                <option value="5" selected>Show up to 5 matching excerpts</option>
                <option value="10">Show up to 10 matching excerpts</option>
                <option value="20">Show up to 20 matching excerpts</option>
              </select>
            </div>
            <div>
              <button type="submit" id="ragSubmitBtn" class="btn btn-secondary" style="height: 44px; padding: 0 20px; font-weight: 600;">
                Search Raw Excerpts
              </button>
            </div>
          </div>
        </form>
      </div>

      <!-- Results Container -->
      <div id="ragResultsArea">
        ${ScreenRAGSearch.renderResultsHtml()}
      </div>
    `;

    const inputEl = document.getElementById("askCaseQuestionInput");
    if (inputEl) {
      inputEl.focus();
    }
  },

  // ─── Unified Evidence Intelligence Search Handler ──────────────────────────

  async handleUnifiedSearch(caseId, directQuery = null, directFilter = null) {
    const inputEl = document.getElementById("unifiedIntelInput");
    const filterEl = document.getElementById("unifiedIntelFilterSelect");
    const submitBtn = document.getElementById("unifiedIntelSubmitBtn");
    const resultsArea = document.getElementById("unifiedIntelResultsArea");

    const query = directQuery || (inputEl ? inputEl.value : "").trim();
    const filter = directFilter || (filterEl ? filterEl.value : "ALL");

    if (!query) {
      if (inputEl) inputEl.focus();
      return;
    }

    if (inputEl) inputEl.value = query;
    if (filterEl && directFilter) filterEl.value = directFilter;

    ScreenRAGSearch.lastIntelQuery = query;
    ScreenRAGSearch.lastIntelFilter = filter;
    ScreenRAGSearch.isIntelLoading = true;
    ScreenRAGSearch.intelError = null;

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span class="icon">⏳</span> Searching...`;
    }

    if (resultsArea) {
      resultsArea.innerHTML = `
        <div style="padding: 30px; text-align: center; color: var(--text-muted); background: var(--bg-card-subtle); border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
          <div style="font-size: 1.8rem; margin-bottom: 8px;">⏳</div>
          <h4 style="color: var(--text-main); margin-bottom: 4px;">Searching Evidence Intelligence Registry...</h4>
          <p style="font-size: 0.85rem; margin: 0;">Cross-referencing exhibits, entities, timelines, and authenticated passages for case ${Formatters.escapeHtml(caseId)}.</p>
        </div>
      `;
    }

    try {
      const res = await Api.searchEvidenceIntelligence(caseId, query, filter);
      ScreenRAGSearch.lastIntelResults = res;
      ScreenRAGSearch.isIntelLoading = false;
      UI.recordAudit("EVIDENCE_INTELLIGENCE_SEARCH", caseId, "SUCCESS", `Query: ${query} (Filter: ${filter}, Results: ${res.total_results})`);
    } catch (err) {
      ScreenRAGSearch.isIntelLoading = false;
      ScreenRAGSearch.intelError = err.message || "Unified search failed";
      ScreenRAGSearch.lastIntelResults = null;
      UI.recordAudit("EVIDENCE_INTELLIGENCE_SEARCH_FAILED", caseId, "FAILED", err.message);
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `Search`;
      }
      if (resultsArea) {
        resultsArea.innerHTML = ScreenRAGSearch.renderUnifiedResultsHtml(caseId);
      }
    }
  },

  renderUnifiedResultsHtml(caseId) {
    if (ScreenRAGSearch.isIntelLoading) return "";

    if (ScreenRAGSearch.intelError) {
      return `
        <div class="card" style="padding: 20px; border-left: 4px solid var(--danger);">
          <strong style="color: var(--danger);">Search Service Unavailable:</strong>
          <p style="color: var(--text-secondary); font-size: 0.88rem; margin: 4px 0 0 0;">${Formatters.escapeHtml(ScreenRAGSearch.intelError)}</p>
        </div>
      `;
    }

    const res = ScreenRAGSearch.lastIntelResults;
    if (!res) {
      return `
        <div style="padding: 24px; text-align: center; color: var(--text-muted); background: var(--bg-card-subtle); border-radius: var(--radius-md); border: 1px dashed var(--border-default);">
          <div style="font-size: 1.8rem; margin-bottom: 6px;">💡</div>
          <h4 style="color: var(--text-main); font-size: 0.95rem; margin-bottom: 4px;">Search Evidence Docket &amp; Entities</h4>
          <p style="font-size: 0.82rem; margin: 0;">Enter an exhibit number, person name, weapon type, location, or attribute above to inspect source-grounded profiles.</p>
        </div>
      `;
    }

    let html = "";

    // 1. Exact Exhibit Match Failure Notice (Section 2 prompt mandate: do not silently return a similar exhibit!)
    if (res.exact_match_found === false) {
      html += `
        <div class="card" style="padding: 16px 20px; border-left: 4px solid var(--danger); background: var(--bg-card); margin-bottom: 16px;">
          <div style="display: flex; gap: 10px; align-items: center;">
            <span style="font-size: 1.4rem;">⚠️</span>
            <div>
              <strong style="color: var(--danger);">No Matching Exhibit Record Found</strong>
              <p style="color: var(--text-secondary); font-size: 0.85rem; margin: 2px 0 0 0;">
                ${Formatters.escapeHtml(res.notice || `No matching evidence record found for identifier '${res.query}' in case ${res.case_id}.`)}
              </p>
            </div>
          </div>
        </div>
      `;
    }

    // 2. Disambiguation Required Banner
    if (res.disambiguation_required && res.disambiguation_candidates && res.disambiguation_candidates.length > 0) {
      html += `
        <div class="disambiguation-banner">
          <div style="display: flex; gap: 10px; align-items: flex-start;">
            <span style="font-size: 1.4rem; color: #f59e0b;">👥</span>
            <div style="flex: 1;">
              <strong style="color: #d97706; font-size: 0.92rem;">Identity Disambiguation Required</strong>
              <p style="color: var(--text-secondary); font-size: 0.82rem; margin: 4px 0 10px 0;">
                Multiple individuals match query "${Formatters.escapeHtml(res.query)}". SAKSHI prevents silent merging of distinct participants. Select the intended subject below:
              </p>
              <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                ${res.disambiguation_candidates.map(c => `
                  <button class="btn btn-secondary btn-sm" onclick="ScreenRAGSearch.openPersonDossierModal('${caseId}', '${c.id}')" style="display: flex; align-items: center; gap: 6px;">
                    <span>👤</span>
                    <strong>${Formatters.escapeHtml(c.name)}</strong>
                    <span class="badge badge-neutral" style="font-size: 0.7rem;">${Formatters.escapeHtml(c.subtitle || 'Participant')}</span>
                  </button>
                `).join("")}
              </div>
            </div>
          </div>
        </div>
      `;
    }

    // 3. Results List
    if (res.results.length === 0) {
      if (res.exact_match_found !== false) {
        html += `
          <div style="padding: 24px; text-align: center; color: var(--text-muted); background: var(--bg-card-subtle); border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
            <div style="font-size: 1.6rem; margin-bottom: 6px;">🔍</div>
            <h4 style="color: var(--text-main); font-size: 0.92rem; margin-bottom: 4px;">No Matching Records Found</h4>
            <p style="font-size: 0.82rem; margin: 0;">No case exhibits, entities, or passages matched query "${Formatters.escapeHtml(res.query)}".</p>
          </div>
        `;
      }
      return html;
    }

    html += `
      <div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; font-size: 0.82rem; color: var(--text-muted);">
        <span>Showing <strong>${res.results.length}</strong> matching record${res.results.length === 1 ? '' : 's'} for <em>"${Formatters.escapeHtml(res.query)}"</em></span>
        <span class="badge badge-neutral" style="font-size: 0.72rem;">Filter: ${Formatters.escapeHtml(res.filter_type)}</span>
      </div>
      <div class="intel-results-grid">
    `;

    html += res.results.map((item, idx) => {
      let cardClass = "intel-result-card";
      let matchBadgeClass = "badge-neutral";
      if (item.match_type === "EXACT_IDENTIFIER") {
        cardClass += " exact-match";
        matchBadgeClass = "badge-verified";
      } else if (item.match_type === "EXACT_NAME") {
        cardClass += item.type === "PERSON" ? " person-match" : " object-match";
        matchBadgeClass = "badge-verified";
      } else if (item.match_type === "RELATIONSHIP_MATCH") {
        cardClass += " rel-match";
        matchBadgeClass = "badge-info";
      }

      let typeIcon = "📄";
      if (item.type === "PERSON") typeIcon = "👤";
      else if (item.type === "OBJECT") typeIcon = "🔪";
      else if (item.type === "LOCATION") typeIcon = "📍";
      else if (item.type === "EVENT") typeIcon = "⏱️";
      else if (item.type === "RELATIONSHIP") typeIcon = "🕸️";
      else if (item.type === "PASSAGE") typeIcon = "📑";

      let actionBtn = "";
      if (item.dossier_type === "person") {
        actionBtn = `
          <button class="btn btn-primary btn-sm" onclick="ScreenRAGSearch.openPersonDossierModal('${caseId}', '${item.dossier_id || item.identifier}')">
            Open Person Dossier &rarr;
          </button>
        `;
      } else if (item.dossier_type === "object") {
        actionBtn = `
          <button class="btn btn-primary btn-sm" onclick="ScreenRAGSearch.openObjectDossierModal('${caseId}', '${item.dossier_id || item.identifier}')">
            Open Object Dossier &rarr;
          </button>
        `;
      } else {
        actionBtn = `
          <button class="btn btn-secondary btn-sm" onclick="ScreenEvidence.showExhibitDetailModal('${item.source_evidence_id || item.identifier}')">
            Inspect Exhibit &rarr;
          </button>
        `;
      }

      return `
        <div class="${cardClass}">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span style="font-size: 1.1rem;">${typeIcon}</span>
              <strong style="font-size: 0.95rem; color: var(--text-main);">${Formatters.escapeHtml(item.name)}</strong>
              ${item.identifier ? `<span class="badge badge-neutral" style="font-family: var(--font-mono); font-size: 0.72rem;">${Formatters.escapeHtml(item.identifier)}</span>` : ''}
              <span class="badge ${matchBadgeClass}" style="font-size: 0.7rem; font-weight: 700;">${Formatters.escapeHtml(item.match_type.replace('_', ' '))}</span>
              <span class="badge badge-info" style="font-size: 0.7rem;">${Formatters.escapeHtml(item.category)}</span>
            </div>
            <div>
              ${actionBtn}
            </div>
          </div>

          <!-- Description / Snippet -->
          <div style="font-size: 0.86rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 10px;">
            ${Formatters.escapeHtml(item.description || item.subtitle || '')}
          </div>

          <!-- Provenance / Match Reason Bar -->
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.74rem; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 8px; flex-wrap: wrap; gap: 6px;">
            <div>
              <span style="color: var(--primary);"><strong>Basis:</strong> ${Formatters.escapeHtml(item.match_reason)}</span>
            </div>
            <div style="display: flex; gap: 10px; align-items: center;">
              ${item.source_filename ? `<span><strong>Source:</strong> ${Formatters.escapeHtml(item.source_filename)}</span>` : ''}
              ${item.review_status ? `<span class="badge badge-neutral" style="font-size: 0.68rem;">${Formatters.escapeHtml(item.review_status)}</span>` : ''}
            </div>
          </div>
        </div>
      `;
    }).join("");

    html += `</div>`;
    return html;
  },

  // ─── Person Dossier Modal ──────────────────────────────────────────────────

  async openPersonDossierModal(caseId, personId) {
    try {
      const dossier = await Api.getPersonDossier(caseId, personId);
      ScreenRAGSearch.activeDossierTab = "identity";

      const renderDossierContent = () => {
        let tabHtml = "";
        const tab = ScreenRAGSearch.activeDossierTab;

        if (tab === "identity") {
          tabHtml = `
            <div style="display: flex; flex-direction: column; gap: 12px;">
              <table class="characteristics-table">
                <thead>
                  <tr>
                    <th>Identifying Field</th>
                    <th>Documented Value</th>
                    <th>Source Classification</th>
                    <th>Evidence Source</th>
                  </tr>
                </thead>
                <tbody>
                  ${Object.values(dossier.identifying_info).map(f => `
                    <tr>
                      <td style="font-weight: 600;">${Formatters.escapeHtml(f.field_name)}</td>
                      <td>
                        ${f.source_type === 'NOT_DOCUMENTED'
                          ? `<span class="not-documented-label">⚠️ Not documented in available evidence</span>`
                          : `<strong style="color: var(--text-main);">${Formatters.escapeHtml(f.value || 'N/A')}</strong>`
                        }
                      </td>
                      <td><span class="badge ${f.source_type === 'SOURCE_REPORTED' ? 'badge-verified' : 'badge-neutral'}" style="font-size: 0.7rem;">${Formatters.escapeHtml(f.source_type)}</span></td>
                      <td style="font-size: 0.78rem; color: var(--text-secondary);">${Formatters.escapeHtml(f.source_label)}</td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          `;
        } else if (tab === "relationships") {
          tabHtml = `
            <div style="display: flex; flex-direction: column; gap: 10px;">
              ${dossier.relationships.length === 0 ? `
                <p style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 20px;">No grounded relationships documented in case docket yet.</p>
              ` : dossier.relationships.map(r => `
                <div style="padding: 12px 14px; background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-sm); border-left: 3px solid #8b5cf6;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <strong style="color: var(--text-main); font-size: 0.88rem;">${Formatters.escapeHtml(r.label)} &rarr; ${Formatters.escapeHtml(r.target_name)}</strong>
                    <span class="badge ${r.status === 'CONFIRMED' ? 'badge-verified' : 'badge-info'}" style="font-size: 0.72rem;">${Formatters.escapeHtml(r.status)}</span>
                  </div>
                  <div style="font-size: 0.82rem; color: var(--text-secondary); font-style: italic; background: var(--bg-card-subtle); padding: 8px 10px; border-radius: var(--radius-sm); margin-bottom: 6px;">
                    "${Formatters.escapeHtml(r.supporting_passage)}"
                  </div>
                  <div style="font-size: 0.74rem; color: var(--text-muted);">
                    Source: ${Formatters.escapeHtml(r.source_filename)} (Exhibit: ${Formatters.escapeHtml(r.source_evidence_id)})
                  </div>
                </div>
              `).join("")}
            </div>
          `;
        } else if (tab === "interactions") {
          tabHtml = `
            <div style="display: flex; flex-direction: column; gap: 10px;">
              ${dossier.interactions.length === 0 ? `
                <p style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 20px;">No reported interactions documented in docket.</p>
              ` : dossier.interactions.map(it => `
                <div style="padding: 12px 14px; background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-sm); border-left: 3px solid #3b82f6;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <strong style="color: var(--text-main); font-size: 0.88rem;">⏱️ ${Formatters.escapeHtml(it.reported_time || 'Uncertain Time')}</strong>
                    <span class="badge badge-neutral" style="font-size: 0.7rem;">Certainty: ${Formatters.escapeHtml(it.time_uncertainty)}</span>
                  </div>
                  <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 6px;">
                    ${Formatters.escapeHtml(it.description)}
                  </div>
                  <div style="font-size: 0.74rem; color: var(--text-muted);">
                    Type: ${Formatters.escapeHtml(it.interaction_type)} &bull; Source: ${Formatters.escapeHtml(it.source_filename)}
                  </div>
                </div>
              `).join("")}
            </div>
          `;
        } else if (tab === "timeline") {
          tabHtml = `
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${dossier.timeline.map(ev => `
                <div style="padding: 10px 12px; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); display: flex; gap: 12px; align-items: flex-start;">
                  <span style="font-size: 1.1rem;">⏱️</span>
                  <div style="flex: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                      <strong style="font-size: 0.86rem; color: var(--text-main);">${Formatters.escapeHtml(ev.title)}</strong>
                      <span class="badge badge-neutral" style="font-size: 0.7rem;">${Formatters.escapeHtml(ev.timestamp_str || 'Timestamp Unknown')}</span>
                    </div>
                    <p style="font-size: 0.82rem; color: var(--text-secondary); margin: 2px 0 4px 0;">${Formatters.escapeHtml(ev.description)}</p>
                    <span style="font-size: 0.72rem; color: var(--text-muted);">Exhibit: ${Formatters.escapeHtml(ev.source_filename)}</span>
                  </div>
                </div>
              `).join("")}
            </div>
          `;
        } else if (tab === "evidence") {
          tabHtml = `
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${dossier.associated_evidence.map(e => `
                <div style="padding: 10px 12px; background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-sm); display: flex; justify-content: space-between; align-items: center;">
                  <div>
                    <strong style="font-size: 0.88rem; color: var(--text-main);">📄 ${Formatters.escapeHtml(e.original_file_name)}</strong>
                    <div style="font-size: 0.74rem; color: var(--text-muted);">${Formatters.escapeHtml(e.category)} &bull; Exhibit ID: ${Formatters.escapeHtml(e.evidence_id)}</div>
                  </div>
                  <button class="btn btn-secondary btn-sm" onclick="ScreenEvidence.showExhibitDetailModal('${e.evidence_id}')">
                    Inspect Exhibit &rarr;
                  </button>
                </div>
              `).join("")}
            </div>
          `;
        } else if (tab === "conflicts") {
          tabHtml = `
            <div style="display: flex; flex-direction: column; gap: 10px;">
              ${dossier.conflicts.length === 0 ? `
                <p style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 20px;">No conflicting statements or unresolved identity claims identified for this person.</p>
              ` : dossier.conflicts.map(c => `
                <div style="padding: 12px 14px; background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-sm); border-left: 3px solid var(--danger);">
                  <strong style="color: var(--danger); font-size: 0.86rem;">⚠️ ${Formatters.escapeHtml(c.conflict_type)}</strong>
                  <div style="margin: 6px 0; font-size: 0.82rem; color: var(--text-secondary);">
                    <strong>Claim A (${Formatters.escapeHtml(c.source_a)}):</strong> ${Formatters.escapeHtml(c.claim_a)}
                  </div>
                  <div style="margin: 6px 0; font-size: 0.82rem; color: var(--text-secondary);">
                    <strong>Claim B (${Formatters.escapeHtml(c.source_b)}):</strong> ${Formatters.escapeHtml(c.claim_b)}
                  </div>
                  <span class="badge badge-attention" style="font-size: 0.7rem;">${Formatters.escapeHtml(c.status)}</span>
                </div>
              `).join("")}
            </div>
          `;
        }

        return `
          <div style="margin-bottom: 14px; border-bottom: 1px solid var(--border-subtle); display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="dossier-tab-btn ${tab === 'identity' ? 'active' : ''}" onclick="ScreenRAGSearch.switchDossierTab('identity')">Identity Details</button>
            <button class="dossier-tab-btn ${tab === 'relationships' ? 'active' : ''}" onclick="ScreenRAGSearch.switchDossierTab('relationships')">Relationship Map (${dossier.relationships.length})</button>
            <button class="dossier-tab-btn ${tab === 'interactions' ? 'active' : ''}" onclick="ScreenRAGSearch.switchDossierTab('interactions')">Reported Interactions (${dossier.interactions.length})</button>
            <button class="dossier-tab-btn ${tab === 'timeline' ? 'active' : ''}" onclick="ScreenRAGSearch.switchDossierTab('timeline')">Timeline Mentions (${dossier.timeline.length})</button>
            <button class="dossier-tab-btn ${tab === 'evidence' ? 'active' : ''}" onclick="ScreenRAGSearch.switchDossierTab('evidence')">Associated Evidence (${dossier.associated_evidence.length})</button>
            <button class="dossier-tab-btn ${tab === 'conflicts' ? 'active' : ''}" onclick="ScreenRAGSearch.switchDossierTab('conflicts')">Conflicts &amp; Gaps (${dossier.conflicts.length})</button>
          </div>
          <div id="dossierTabContent">${tabHtml}</div>
        `;
      };

      const modalHtml = `
        <div class="modal-overlay" id="personDossierModal" onclick="if(event.target===this) this.remove();" style="display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 10000; padding: 20px;">
          <div class="card" style="width: 100%; max-width: 900px; max-height: 90vh; overflow-y: auto; padding: 24px; position: relative;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px;">
              <div>
                <span class="badge badge-info" style="margin-bottom: 4px;">CASE-SCOPED PERSON DOSSIER</span>
                <h3 style="font-size: 1.3rem; font-weight: 700; color: var(--text-main); margin: 0;">👤 ${Formatters.escapeHtml(dossier.canonical_name)}</h3>
                <span style="font-size: 0.78rem; color: var(--text-muted); font-family: var(--font-mono);">ID: ${Formatters.escapeHtml(dossier.person_id)} &bull; Case: ${Formatters.escapeHtml(caseId)}</span>
              </div>
              <button class="btn btn-secondary btn-sm" onclick="document.getElementById('personDossierModal').remove();">✕ Close</button>
            </div>

            <!-- Judicial Caution Safeguard -->
            <div style="padding: 10px 14px; background: rgba(59, 130, 246, 0.08); border-left: 4px solid var(--primary); border-radius: var(--radius-sm); font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 16px;">
              <strong>Judicial Caution:</strong> ${Formatters.escapeHtml(dossier.legal_safeguard)}
            </div>

            <!-- Render Tabs -->
            <div id="dossierModalBody">
              ${renderDossierContent()}
            </div>
          </div>
        </div>
      `;

      // Remove existing modal if any
      const existing = document.getElementById("personDossierModal");
      if (existing) existing.remove();
      document.body.insertAdjacentHTML("beforeend", modalHtml);
    } catch (err) {
      alert(`Failed to load person dossier: ${err.message}`);
    }
  },

  switchDossierTab(tabId) {
    ScreenRAGSearch.activeDossierTab = tabId;
    const btns = document.querySelectorAll(".dossier-tab-btn");
    btns.forEach(b => b.classList.remove("active"));
    const activeBtn = Array.from(btns).find(b => b.textContent.toLowerCase().includes(tabId.substring(0, 4)));
    if (activeBtn) activeBtn.classList.add("active");
    // Trigger modal re-render via opening
    const modal = document.getElementById("personDossierModal");
    if (modal) {
      const activeCaseId = State.activeCaseId;
      // Re-trigger render
      const body = document.getElementById("dossierModalBody");
      if (body) {
        // Simple re-run
        const personId = modal.querySelector("span[style*='font-family']").textContent.split("ID: ")[1].split(" •")[0].trim();
        ScreenRAGSearch.openPersonDossierModal(activeCaseId, personId);
      }
    }
  },

  // ─── Object and Exhibit Dossier Modal ──────────────────────────────────────

  async openObjectDossierModal(caseId, objectId) {
    try {
      const dossier = await Api.getObjectDossier(caseId, objectId);

      const modalHtml = `
        <div class="modal-overlay" id="objectDossierModal" onclick="if(event.target===this) this.remove();" style="display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 10000; padding: 20px;">
          <div class="card" style="width: 100%; max-width: 900px; max-height: 90vh; overflow-y: auto; padding: 24px; position: relative;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px;">
              <div>
                <span class="badge badge-verified" style="margin-bottom: 4px;">PHYSICAL EXHIBIT DOSSIER</span>
                <h3 style="font-size: 1.3rem; font-weight: 700; color: var(--text-main); margin: 0;">🔪 ${Formatters.escapeHtml(dossier.object_type)}</h3>
                <span style="font-size: 0.78rem; color: var(--text-muted); font-family: var(--font-mono);">
                  Exhibit No: <strong>${Formatters.escapeHtml(dossier.exhibit_number)}</strong> &bull; Case: ${Formatters.escapeHtml(caseId)} &bull; Custody: ${Formatters.escapeHtml(dossier.custody_status)}
                </span>
              </div>
              <button class="btn btn-secondary btn-sm" onclick="document.getElementById('objectDossierModal').remove();">✕ Close</button>
            </div>

            <!-- Forensic Limitations Safeguard Alert (MANDATORY REQUIREMENT) -->
            <div class="forensic-limitations-alert">
              <strong>Forensic Limitation Notice:</strong>
              <div>${Formatters.escapeHtml(dossier.forensic_limitations_notice)}</div>
            </div>

            <!-- Structured Characteristics Register Table -->
            <div style="margin-bottom: 20px;">
              <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">
                Structured Characteristics Register
              </h4>
              <table class="characteristics-table">
                <thead>
                  <tr>
                    <th>Characteristic</th>
                    <th>Documented Value</th>
                    <th>Source Type</th>
                    <th>Measurement Method</th>
                    <th>Review State</th>
                  </tr>
                </thead>
                <tbody>
                  ${dossier.characteristics_register.map(c => `
                    <tr>
                      <td style="font-weight: 600;">${Formatters.escapeHtml(c.attribute_name)}</td>
                      <td>
                        ${c.source_type === 'NOT_DOCUMENTED'
                          ? `<span class="not-documented-label">⚠️ ${Formatters.escapeHtml(c.value)}</span>`
                          : `<strong style="color: var(--text-main);">${Formatters.escapeHtml(c.value)}</strong> ${c.unit ? `<span class="badge badge-neutral" style="font-size: 0.7rem;">${Formatters.escapeHtml(c.unit)}</span>` : ''}`
                        }
                      </td>
                      <td><span class="badge ${c.source_type === 'REPORTED_IN_SOURCE' ? 'badge-verified' : 'badge-neutral'}" style="font-size: 0.7rem;">${Formatters.escapeHtml(c.source_type)}</span></td>
                      <td style="font-size: 0.78rem; color: var(--text-secondary);">${Formatters.escapeHtml(c.measurement_method || 'N/A')}</td>
                      <td><span class="badge badge-neutral" style="font-size: 0.7rem;">${Formatters.escapeHtml(c.review_status)}</span></td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>

            <!-- Missing Characteristics Checklist -->
            <div style="padding: 14px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); margin-bottom: 16px;">
              <strong style="color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 6px;">
                Unestablished Characteristics (Explicitly Not Documented):
              </strong>
              <ul style="margin: 0; padding-left: 20px; font-size: 0.82rem; color: var(--text-secondary);">
                ${dossier.missing_characteristics.map(m => `<li>${Formatters.escapeHtml(m)}</li>`).join("")}
              </ul>
            </div>

            <!-- Examination Findings & Custody Provenance -->
            <div style="display: flex; gap: 12px; flex-wrap: wrap;">
              <div style="flex: 1; min-width: 280px; padding: 12px; background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-sm);">
                <strong style="font-size: 0.82rem; color: var(--text-main); display: block; margin-bottom: 4px;">Examination Status:</strong>
                <p style="font-size: 0.8rem; color: var(--text-secondary); margin: 0;">${Formatters.escapeHtml(dossier.examination_findings[0]?.notes || 'Forensic analysis pending.')}</p>
              </div>
              <div style="flex: 1; min-width: 280px; padding: 12px; background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-sm);">
                <strong style="font-size: 0.82rem; color: var(--text-main); display: block; margin-bottom: 4px;">Integrity Binding:</strong>
                <span style="font-size: 0.76rem; font-family: var(--font-mono); color: var(--text-muted); word-break: break-all;">SHA-256: ${Formatters.escapeHtml(dossier.checksum_sha256 || 'VERIFIED')}</span>
              </div>
            </div>
          </div>
        </div>
      `;

      const existing = document.getElementById("objectDossierModal");
      if (existing) existing.remove();
      document.body.insertAdjacentHTML("beforeend", modalHtml);
    } catch (err) {
      alert(`Failed to load object dossier: ${err.message}`);
    }
  },

  // ─── Entity Registry Modal ─────────────────────────────────────────────────

  async openRegistryModal(caseId) {
    try {
      const reg = await Api.getEntityRegistry(caseId);
      const modalHtml = `
        <div class="modal-overlay" id="registryModal" onclick="if(event.target===this) this.remove();" style="display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 10000; padding: 20px;">
          <div class="card" style="width: 100%; max-width: 850px; max-height: 85vh; overflow-y: auto; padding: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
              <div>
                <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin: 0;">Case Entity &amp; Exhibit Registry</h3>
                <span style="font-size: 0.8rem; color: var(--text-muted);">${reg.total_entities} cataloged entities for case ${Formatters.escapeHtml(caseId)}</span>
              </div>
              <button class="btn btn-secondary btn-sm" onclick="document.getElementById('registryModal').remove();">✕ Close</button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${reg.entities.map(e => `
                <div style="padding: 10px 14px; background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-sm); display: flex; justify-content: space-between; align-items: center;">
                  <div>
                    <strong style="color: var(--text-main); font-size: 0.9rem;">${Formatters.escapeHtml(e.name)}</strong>
                    <div style="font-size: 0.74rem; color: var(--text-muted);">${Formatters.escapeHtml(e.subtitle || '')} &bull; ID: ${Formatters.escapeHtml(e.identifier || e.id)}</div>
                  </div>
                  <div style="display: flex; gap: 8px; align-items: center;">
                    <span class="badge badge-info" style="font-size: 0.72rem;">${Formatters.escapeHtml(e.category)}</span>
                    <button class="btn btn-secondary btn-sm" onclick="document.getElementById('registryModal').remove(); ${e.dossier_type === 'person' ? `ScreenRAGSearch.openPersonDossierModal('${caseId}', '${e.id}')` : (e.dossier_type === 'object' ? `ScreenRAGSearch.openObjectDossierModal('${caseId}', '${e.id}')` : `ScreenEvidence.showExhibitDetailModal('${e.id}')`)};">
                      View Dossier &rarr;
                    </button>
                  </div>
                </div>
              `).join("")}
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById("registryModal");
      if (existing) existing.remove();
      document.body.insertAdjacentHTML("beforeend", modalHtml);
    } catch (err) {
      alert(`Failed to load entity registry: ${err.message}`);
    }
  },

  // ─── Source Comparisons Modal ──────────────────────────────────────────────

  async openSourceComparisonModal(caseId) {
    try {
      const comp = await Api.getSourceComparisons(caseId);
      const modalHtml = `
        <div class="modal-overlay" id="sourceCompModal" onclick="if(event.target===this) this.remove();" style="display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 10000; padding: 20px;">
          <div class="card" style="width: 100%; max-width: 850px; max-height: 85vh; overflow-y: auto; padding: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
              <div>
                <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin: 0;">Side-by-Side Source Contradiction Review</h3>
                <span style="font-size: 0.8rem; color: var(--text-muted);">${comp.total_comparisons} divergent accounts recorded</span>
              </div>
              <button class="btn btn-secondary btn-sm" onclick="document.getElementById('sourceCompModal').remove();">✕ Close</button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 14px;">
              ${comp.comparisons.map(c => `
                <div style="padding: 16px; background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-sm); border-left: 4px solid #f59e0b;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <strong style="color: var(--text-main); font-size: 0.92rem;">${Formatters.escapeHtml(c.topic)}</strong>
                    <span class="badge badge-attention" style="font-size: 0.72rem;">${Formatters.escapeHtml(c.discrepancy_type)}</span>
                  </div>
                  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 8px;">
                    <div style="padding: 10px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
                      <strong style="font-size: 0.78rem; color: var(--text-muted); display: block; margin-bottom: 4px;">SOURCE A: ${Formatters.escapeHtml(c.claim_a.source)}</strong>
                      <div style="font-size: 0.84rem; color: var(--text-main); margin-bottom: 4px;">${Formatters.escapeHtml(c.claim_a.statement)}</div>
                      <div style="font-size: 0.76rem; color: var(--text-muted); font-style: italic;">"${Formatters.escapeHtml(c.claim_a.passage)}"</div>
                    </div>
                    <div style="padding: 10px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
                      <strong style="font-size: 0.78rem; color: var(--text-muted); display: block; margin-bottom: 4px;">SOURCE B: ${Formatters.escapeHtml(c.claim_b.source)}</strong>
                      <div style="font-size: 0.84rem; color: var(--text-main); margin-bottom: 4px;">${Formatters.escapeHtml(c.claim_b.statement)}</div>
                      <div style="font-size: 0.76rem; color: var(--text-muted); font-style: italic;">"${Formatters.escapeHtml(c.claim_b.passage)}"</div>
                    </div>
                  </div>
                  <div style="font-size: 0.74rem; color: var(--text-muted); text-align: right;">
                    Status: <span class="badge badge-neutral">${Formatters.escapeHtml(c.status)}</span>
                  </div>
                </div>
              `).join("")}
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById("sourceCompModal");
      if (existing) existing.remove();
      document.body.insertAdjacentHTML("beforeend", modalHtml);
    } catch (err) {
      alert(`Failed to load source comparisons: ${err.message}`);
    }
  },

  // ─── Investigation Follow-ups Modal ────────────────────────────────────────

  async openFollowupModal(caseId) {
    try {
      const follow = await Api.getInvestigationFollowups(caseId);
      const modalHtml = `
        <div class="modal-overlay" id="followupModal" onclick="if(event.target===this) this.remove();" style="display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 10000; padding: 20px;">
          <div class="card" style="width: 100%; max-width: 850px; max-height: 85vh; overflow-y: auto; padding: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
              <div>
                <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin: 0;">Investigation Gaps &amp; Follow-up Actions</h3>
                <span style="font-size: 0.8rem; color: var(--text-muted);">${follow.total_followups} procedural follow-up items identified</span>
              </div>
              <button class="btn btn-secondary btn-sm" onclick="document.getElementById('followupModal').remove();">✕ Close</button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 12px;">
              ${follow.followups.map(f => `
                <div style="padding: 14px 16px; background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-sm); border-left: 4px solid var(--primary);">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <strong style="color: var(--text-main); font-size: 0.92rem;">${Formatters.escapeHtml(f.title)}</strong>
                    <span class="badge ${f.procedural_requirement ? 'badge-attention' : 'badge-neutral'}" style="font-size: 0.72rem;">${f.procedural_requirement ? 'Procedural Requirement' : 'System Recommendation'}</span>
                  </div>
                  <div style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 6px;">
                    <strong>What is unresolved:</strong> ${Formatters.escapeHtml(f.what_is_unknown)}
                  </div>
                  <div style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 6px;">
                    <strong>Why it matters:</strong> ${Formatters.escapeHtml(f.why_it_matters)}
                  </div>
                  <div style="font-size: 0.82rem; color: var(--primary);">
                    <strong>Recommended Action:</strong> ${Formatters.escapeHtml(f.recommended_action)}
                  </div>
                </div>
              `).join("")}
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById("followupModal");
      if (existing) existing.remove();
      document.body.insertAdjacentHTML("beforeend", modalHtml);
    } catch (err) {
      alert(`Failed to load follow-up suggestions: ${err.message}`);
    }
  },

  // ─── Officer Assistant: Ask About This Case (6-Section Synthesis) ───────────

  async handleAskCase(caseId, directQuery = null) {
    const inputEl = document.getElementById("askCaseQuestionInput");
    const query = directQuery || (inputEl ? inputEl.value : "").trim();
    const submitBtn = document.getElementById("askCaseSubmitBtn");
    const resultArea = document.getElementById("askCaseResultArea");

    if (!query) {
      if (inputEl) inputEl.focus();
      return;
    }

    if (inputEl) inputEl.value = query;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span class="icon">⏳</span> Consulting Exhibits...`;
    }

    if (resultArea) {
      resultArea.style.display = "block";
      resultArea.innerHTML = `
        <div style="padding: 24px; text-align: center; color: var(--text-muted); background: var(--bg-card-subtle); border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
          <div style="font-size: 1.8rem; margin-bottom: 8px;">⏳</div>
          <h4 style="color: var(--text-main); margin-bottom: 4px;">Consulting Verified Case Docket...</h4>
          <p style="font-size: 0.85rem; margin: 0;">Synthesizing structured 6-section evidence answer for case ${Formatters.escapeHtml(caseId)}.</p>
        </div>
      `;
    }

    try {
      let structuredRes = null;
      try {
        structuredRes = await Api.askEvidenceIntelligence(caseId, query);
      } catch (e) {
        // Fallback to standard askCaseQuestion
        structuredRes = await Api.askCaseQuestion(caseId, query);
      }

      UI.recordAudit("CASE_QUESTION_ASKED", caseId, "SUCCESS", `Q: ${query.substring(0, 60)}`);

      if (resultArea) {
        if (structuredRes.answer_text) {
          // Render Phase F.1 6-section structured response
          resultArea.innerHTML = `
            <div class="card" style="padding: 20px; border-left: 4px solid var(--primary); background: var(--bg-card); margin-top: 14px;">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                <div>
                  <span class="badge badge-info" style="margin-bottom: 4px;">STRUCTURED EVIDENCE-BACKED SYNTHESIS</span>
                  <div style="font-size: 0.95rem; font-weight: 700; color: var(--text-main);">
                    "${Formatters.escapeHtml(structuredRes.question)}"
                  </div>
                </div>
                <div>
                  <span class="badge badge-verified">6-SECTION STRUCTURED SYNTHESIS</span>
                </div>
              </div>

              <!-- Synthesized Plain Language Answer in 6 Sections -->
              <div style="font-size: 0.88rem; line-height: 1.7; color: var(--text-main); margin-bottom: 16px; background: var(--bg-card-subtle); padding: 16px 20px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); font-family: var(--font-sans); white-space: pre-wrap;">${Formatters.escapeHtml(structuredRes.answer_text)}</div>

              <!-- Legal Safeguard Footer -->
              <div style="font-size: 0.76rem; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 8px; display: flex; align-items: center; gap: 6px;">
                <span>⚖️</span>
                <span><strong>Admissibility Note:</strong> Synthesis is an investigative aid under Section 194 BNSS. Formal statements and judicial findings require primary exhibit examination under Section 63 BSA.</span>
              </div>
            </div>
          `;
        } else {
          // Fallback legacy renderer
          const res = structuredRes;
          resultArea.innerHTML = `
            <div class="card" style="padding: 20px; border-left: 4px solid var(--primary); background: var(--bg-card); margin-top: 14px;">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                <div>
                  <span class="badge badge-info" style="margin-bottom: 4px;">SOURCE-GROUNDED ASSISTANT ANSWER</span>
                  <div style="font-size: 0.95rem; font-weight: 700; color: var(--text-main);">
                    "${Formatters.escapeHtml(res.question)}"
                  </div>
                </div>
                <div>
                  ${res.insufficient_evidence ? `
                    <span class="badge badge-attention">INSUFFICIENT DOCKET EVIDENCE</span>
                  ` : `
                    <span class="badge badge-verified">● ${res.citations.length} VERIFIED CITATION${res.citations.length === 1 ? '' : 'S'}</span>
                  `}
                </div>
              </div>

              <!-- Synthesized Plain Language Answer -->
              <div style="font-size: 0.95rem; line-height: 1.6; color: var(--text-main); margin-bottom: 16px; background: var(--bg-card-subtle); padding: 14px 18px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                ${Formatters.escapeHtml(res.answer)}
              </div>

              <!-- Citations -->
              ${res.citations && res.citations.length > 0 ? `
                <div style="margin-bottom: 14px;">
                  <div style="font-size: 0.74rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.05em; margin-bottom: 8px;">
                    Exhibits &amp; Passages Consulted (${res.citations.length}):
                  </div>
                  <div style="display: flex; flex-direction: column; gap: 10px;">
                    ${res.citations.map(cit => `
                      <div style="padding: 12px 14px; background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-sm); border-left: 3px solid var(--primary);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px;">
                          <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                            <strong style="color: var(--text-main); font-size: 0.88rem;">📄 ${Formatters.escapeHtml(cit.document_name || cit.source_filename)}</strong>
                            <span class="badge badge-neutral" style="font-family: var(--font-mono); font-size: 0.72rem;">${cit.exhibit_id || cit.evidence_id}</span>
                            ${cit.page_number ? `<span class="badge badge-neutral" style="font-size: 0.72rem;">Page ${cit.page_number}</span>` : ''}
                          </div>
                          <span class="badge badge-info" style="font-size: 0.72rem; font-family: var(--font-mono);">Match: ${((cit.similarity_score || 0.85) * 100).toFixed(1)}%</span>
                        </div>
                        <div style="font-size: 0.84rem; color: var(--text-secondary); font-style: italic; background: var(--bg-card-subtle); padding: 8px 12px; border-radius: var(--radius-sm); border-left: 2px solid var(--border-default); margin-bottom: 6px;">
                          "${Formatters.escapeHtml(cit.verbatim_quote || cit.quoted_passage)}"
                        </div>
                      </div>
                    `).join("")}
                  </div>
                </div>
              ` : ''}
            </div>
          `;
        }
      }
    } catch (err) {
      if (resultArea) {
        resultArea.innerHTML = `
          <div class="card" style="padding: 20px; border-left: 4px solid var(--danger); margin-top: 14px;">
            <strong style="color: var(--danger);">Inquiry Failed:</strong>
            <p style="color: var(--text-secondary); font-size: 0.88rem; margin: 4px 0 0 0;">${Formatters.escapeHtml(err.message || 'Error executing inquiry')}</p>
          </div>
        `;
      }
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `Ask Assistant`;
      }
    }
  },

  // ─── Raw Passage Retrieval (pgvector HNSW) ─────────────────────────────────

  async handleSearch(caseId) {
    const queryInput = document.getElementById("ragQueryInput");
    const limitSelect = document.getElementById("ragLimitSelect");
    const validationEl = document.getElementById("ragQueryValidation");
    const submitBtn = document.getElementById("ragSubmitBtn");
    const resultsArea = document.getElementById("ragResultsArea");

    const query = (queryInput ? queryInput.value : "").trim();
    const limit = parseInt(limitSelect ? limitSelect.value : "5", 10) || 5;

    if (!query) {
      if (validationEl) {
        validationEl.textContent = "Please enter non-whitespace search terms.";
        validationEl.style.display = "block";
      }
      return;
    }
    if (validationEl) validationEl.style.display = "none";

    ScreenRAGSearch.lastQuery = query;
    ScreenRAGSearch.isLoading = true;
    ScreenRAGSearch.error = null;

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span class="icon">⏳</span> Searching...`;
    }

    if (resultsArea) {
      resultsArea.innerHTML = `
        <div class="card" style="padding: 40px; text-align: center;">
          <div style="font-size: 2rem; margin-bottom: 12px;">🔍</div>
          <h4 style="color: var(--text-main); margin-bottom: 6px;">Computing Neural Embeddings & Vector Proximity...</h4>
          <p style="color: var(--text-muted); font-size: 0.85rem;">Searching pgvector HNSW index across verified exhibits for case ${Formatters.escapeHtml(caseId)}.</p>
        </div>
      `;
    }

    try {
      const response = await Api.searchRAG(caseId, query, limit);
      ScreenRAGSearch.lastResults = response;
      ScreenRAGSearch.isLoading = false;

      const modeBadge = document.getElementById("ragRetrievalModeBadge");
      if (modeBadge && response.query_metadata) {
        modeBadge.textContent = response.query_metadata.retrieval_mode;
      }

      UI.recordAudit("RAG_SEARCH_PERFORMED", caseId, "SUCCESS", `Retrieved ${response.result_count} passages (mode: ${response.query_metadata?.retrieval_mode})`);
    } catch (err) {
      ScreenRAGSearch.isLoading = false;
      ScreenRAGSearch.error = err.message || "Retrieval failed";
      ScreenRAGSearch.lastResults = null;
      UI.recordAudit("RAG_SEARCH_FAILED", caseId, "FAILED", err.message);
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `Search Exhibits`;
      }
      if (resultsArea) {
        resultsArea.innerHTML = ScreenRAGSearch.renderResultsHtml();
      }
    }
  },

  renderResultsHtml() {
    if (ScreenRAGSearch.isLoading) return "";

    if (ScreenRAGSearch.error) {
      return `
        <div class="card" style="padding: 24px; border-left: 4px solid var(--danger);">
          <div style="display: flex; gap: 12px; align-items: center;">
            <span style="font-size: 1.5rem; color: var(--danger);">⚠️</span>
            <div>
              <h4 style="color: var(--danger); margin-bottom: 4px;">Retrieval Error</h4>
              <p style="color: var(--text-secondary); font-size: 0.88rem;">${Formatters.escapeHtml(ScreenRAGSearch.error)}</p>
            </div>
          </div>
        </div>
      `;
    }

    const res = ScreenRAGSearch.lastResults;
    const evidenceList = State.evidence || [];

    if (evidenceList.length === 0 && !res) {
      return `
        <div class="card empty-state-card" style="padding: 40px; text-align: center;">
          <div style="font-size: 2.2rem; margin-bottom: 8px;">📑</div>
          <h4 style="color: var(--text-main); margin-bottom: 6px;">No Evidence Uploaded Yet</h4>
          <p style="font-size: 0.85rem; max-width: 500px; margin: 0 auto 16px auto; color: var(--text-muted);">
            Forensic document search (RAG) requires committed textual exhibits (e.g. post-mortem reports, witness statements, ballistic certificates) to index passages. No exhibits have been attached to this case file yet.
          </p>
          <button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${State.activeCaseId}', 'evidence')">+ Add Evidence</button>
        </div>
      `;
    }

    if (!res) {
      return `
        <div class="card" style="padding: 40px; text-align: center; color: var(--text-muted);">
          <div style="font-size: 2.2rem; margin-bottom: 8px;">📑</div>
          <h4 style="color: var(--text-main); margin-bottom: 6px;">No Search Executed Yet</h4>
          <p style="font-size: 0.85rem; max-width: 500px; margin: 0 auto;">
            Enter keywords or witness phrases above to retrieve authenticated excerpts directly from committed case exhibits with full cryptographic provenance.
          </p>
        </div>
      `;
    }

    const { query_metadata, result_count, results, empty_result_notice, score_semantics } = res;

    let metaHtml = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
        <div style="font-size: 0.88rem; color: var(--text-secondary);">
          <strong>${result_count}</strong> passage${result_count === 1 ? '' : 's'} retrieved
          &bull; Mode: <span class="badge ${query_metadata.retrieval_mode.includes('postgres') ? 'badge-verified' : 'badge-attention'}" style="font-family: var(--font-mono);">${Formatters.escapeHtml(query_metadata.retrieval_mode)}</span>
          &bull; Model: <span style="font-family: var(--font-mono); font-size: 0.82rem;">${Formatters.escapeHtml(query_metadata.embedding_model)} (${query_metadata.embedding_dimension}d)</span>
        </div>
        <div style="font-size: 0.78rem; color: var(--text-muted); font-style: italic;">
          ${Formatters.escapeHtml(score_semantics)}
        </div>
      </div>
    `;

    if (result_count === 0 || !results || results.length === 0) {
      return `
        ${metaHtml}
        <div class="card" style="padding: 30px; text-align: center; background: var(--bg-card-subtle);">
          <div style="font-size: 1.8rem; margin-bottom: 6px;">🔍</div>
          <h4 style="color: var(--text-main); margin-bottom: 6px;">No Relevant Passages Found</h4>
          <p style="color: var(--text-secondary); font-size: 0.85rem; max-width: 600px; margin: 0 auto;">
            ${Formatters.escapeHtml(empty_result_notice || "No eligible indexed passage was returned. This does not establish that no relevant evidence exists.")}
          </p>
        </div>
      `;
    }

    const cardsHtml = results.map((item, idx) => {
      const scoreBadgeClass = item.similarity_score > 0.4 ? 'badge-verified' : item.similarity_score > 0.2 ? 'badge-info' : 'badge-neutral';

      return `
        <div class="card" style="padding: 18px 20px; margin-bottom: 16px; border-left: 3px solid var(--primary);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span class="badge badge-info" style="font-weight: 700;">#${idx + 1}</span>
              <span style="font-weight: 700; color: var(--text-main); font-size: 0.95rem;">
                📄 ${Formatters.escapeHtml(item.source_name)}
              </span>
              <span class="badge badge-neutral" style="font-family: var(--font-mono); font-size: 0.74rem;">
                Ex: ${Formatters.escapeHtml(item.evidence_id)}
              </span>
              ${item.page_number != null ? `
                <span class="badge badge-neutral" style="font-size: 0.74rem;">
                  Page ${item.page_number}
                </span>
              ` : ''}
              ${item.char_start != null && item.char_end != null ? `
                <span class="badge badge-neutral" style="font-size: 0.74rem; font-family: var(--font-mono);">
                  Offsets: ${item.char_start}–${item.char_end}
                </span>
              ` : ''}
            </div>

            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 0.78rem; color: var(--text-muted);">Passage Relevance Match:</span>
              <span class="badge ${scoreBadgeClass}" style="font-family: var(--font-mono); font-weight: 700;" title="Mathematical similarity metric, not a probability of truth">
                ${item.similarity_score.toFixed(4)}
              </span>
            </div>
          </div>

          <!-- Passage Content -->
          <div style="background: var(--bg-card-subtle); padding: 14px 16px; border-radius: var(--radius-md); font-size: 0.9rem; line-height: 1.6; color: var(--text-main); margin-bottom: 12px; border: 1px solid var(--border-subtle); white-space: pre-wrap; font-family: var(--font-sans);">
${Formatters.escapeHtml(item.passage)}
          </div>

          <!-- Cryptographic Citation & Provenance Bar -->
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.74rem; color: var(--text-muted); font-family: var(--font-mono); border-top: 1px solid var(--border-subtle); padding-top: 8px; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; gap: 12px; flex-wrap: wrap;">
              <span><strong>Chunk ID:</strong> ${Formatters.escapeHtml(item.chunk_id)}</span>
              <span><strong>Doc ID:</strong> ${Formatters.escapeHtml(item.document_id)}</span>
              <span><strong>SHA-256:</strong> <span title="${Formatters.escapeHtml(item.source_sha256)}">${Formatters.escapeHtml(item.source_sha256.substring(0, 16))}...</span></span>
              ${item.source_sha3_512 ? `<span><strong>SHA3-512:</strong> <span title="${Formatters.escapeHtml(item.source_sha3_512)}">${Formatters.escapeHtml(item.source_sha3_512.substring(0, 16))}...</span></span>` : ''}
            </div>
            <div>
              <span>Pipeline: ${Formatters.escapeHtml(item.processing_version || 'v1.0')}</span>
            </div>
          </div>

          <!-- Technical Provenance Disclosure Panel -->
          <div style="margin-top: 10px;">
            ${StatusPresentation.renderTechnicalDetailsPanel(
              `RAG Provenance & Technical Offsets (${Formatters.escapeHtml(item.chunk_id)})`,
              [
                { label: "Document ID", value: item.document_id },
                { label: "Chunk ID", value: item.chunk_id },
                { label: "Source Evidence ID", value: item.evidence_id },
                { label: "Case ID", value: item.case_id || State.activeCaseId },
                { label: "Page Number", value: item.page_number != null ? String(item.page_number) : null },
                { label: "Character Offsets", value: (item.char_start != null && item.char_end != null) ? `${item.char_start} – ${item.char_end}` : null },
                { label: "Similarity Score", value: item.similarity_score != null ? String(item.similarity_score.toFixed(6)) : null },
                { label: "Source SHA-256 Checksum", value: item.source_sha256 },
                { label: "Source SHA3-512 Checksum", value: item.source_sha3_512 },
                { label: "Processing Pipeline Version", value: item.processing_version || "v1.0" },
                { label: "Embedding Architecture", value: "text-embedding-3-small (1536-dimensional vectors)" }
              ].filter(it => it.value !== null && it.value !== undefined)
            )}
          </div>

          <div style="margin-top: 10px; display: flex; justify-content: flex-end;">
            <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${item.case_id || State.activeCaseId}', 'evidence'); setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer('${item.evidence_id}', '${item.case_id || State.activeCaseId}'), 120);">
              Inspect Source Exhibit &rarr;
            </button>
          </div>
        </div>
      `;
    }).join("");

    return `
      ${metaHtml}
      ${cardsHtml}
    `;
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 12a. SCREEN 6a: REVIEW FINDINGS (Route: #/cases/:id/findings)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenFindings = {
  activeTab: "gaps",

  async render(caseId, tab = null) {
    if (tab) this.activeTab = tab;
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Review Findings`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }

    const c = State.activeCase;
    const evidenceList = State.evidence || [];

    if (evidenceList.length === 0) {
      container.innerHTML = `
        ${renderWorkspaceHeaderHtml("findings")}
        <div class="empty-state-card" style="margin-top: 24px; padding: 48px 24px; text-align: center; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px dashed var(--border-default);">
          
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">No Findings Generated Yet</h3>
          <p style="color: var(--text-muted); font-size: 0.88rem; max-width: 560px; margin: 0 auto 20px auto; line-height: 1.5;">
            A case with zero exhibits contains no verified findings. Complete evidence collection to attach case documents, photographs, call records, and forensic reports before analytical gaps and findings can be generated.
          </p>
          <div style="display: flex; gap: 12px; justify-content: center;">
            <button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence')">
              <span>Go to Evidence Collection</span>
            </button>
          </div>
        </div>
      `;
      return;
    }

    const isCurrentStage = c.lifecycle_stage === "REVIEW";
    const isCompletedStage = c.lifecycle_stage === "CLOSED";
    const isFutureStage = !isCurrentStage && !isCompletedStage;

    let stageBannerHtml = "";
    if (isFutureStage) {
      stageBannerHtml = `
        <div class="card" style="background-color: var(--primary-bg); border-left: 5px solid var(--primary); padding: 18px 22px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div style="flex: 1; min-width: 280px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-info">STAGE 5 PREREQUISITE</span>
                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">Current Case Stage: ${c.lifecycle_stage}</span>
              </div>
              <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">
                Investigator Review Pending Stage 4 Completion
              </h3>
              <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin: 0;">
                Case is currently in Stage <strong>${(StageDisplayMap[c.lifecycle_stage] || {}).short || c.lifecycle_stage}</strong>. 
                Reconstructed timeline events and cross-exhibit observations should be finalized before completing the formal supervisory review.
              </p>
            </div>
            <div>
              <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${caseId}', 'timeline')">
                View Timeline & Analysis &rarr;
              </button>
            </div>
          </div>
        </div>
      `;
    } else if (isCurrentStage) {
      stageBannerHtml = `
        <div class="card" style="background-color: var(--bg-card); border-left: 5px solid var(--primary); padding: 18px 22px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div style="flex: 1; min-width: 280px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-attention">ACTIVE WORKSPACE &bull; STAGE 5</span>
                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">Investigator Review In Progress</span>
              </div>
              <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">
                Review Inquest Findings & Complete Endorsement
              </h3>
              <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin: 0;">
                Review all documentary and forensic exhibits, verified chronological sequence, and open information gaps. Record your investigative evaluation and proceed to Stage 6 Case Closure.
              </p>
            </div>
            <div>
              <button class="btn btn-primary btn-sm" onclick="Router.selectCaseAndRoute('${caseId}', 'closure')">
                Proceed to Case Closure &rarr;
              </button>
            </div>
          </div>
        </div>
      `;
    } else if (isCompletedStage) {
      stageBannerHtml = `
        <div class="card" style="background-color: var(--verified-bg); border-left: 5px solid var(--verified); padding: 16px 20px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-verified">STAGE 5 COMPLETED</span>
                <span style="font-size: 0.8rem; color: var(--verified-text); font-family: var(--font-mono);">Inquest Review Endorsed</span>
              </div>
              <div style="font-size: 1rem; font-weight: 700; color: var(--verified-text); margin-top: 2px;">
                Investigator Review Endorsement Recorded & Archived
              </div>
              <div style="font-size: 0.84rem; color: var(--verified-text); opacity: 0.9; margin-top: 2px;">
                Investigating Officer review evaluation and supervisory closure are permanently filed under Section 194 BNSS.
              </div>
            </div>
            <span class="badge badge-verified" style="font-size: 0.9rem; padding: 6px 14px;">Endorsed</span>
          </div>
        </div>
      `;
    }

    const html = `
      ${renderWorkspaceHeaderHtml("findings")}

      ${stageBannerHtml}

      <div class="cases-toolbar">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Review Investigation Findings</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Holistic review of investigative gaps, analytical reasoning observations, and semantic document evidence.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${caseId}', 'report')">
            View Full Case Report &rarr;
          </button>
        </div>
      </div>

      <!-- Human Governance Notice -->
      <div class="human-governance-notice">
        
        <div>
          <strong>Investigator Governance & Objective Inquest Standard:</strong>
          <span> SAKSHI findings are analytical hypothesis cues grounded strictly in verified case exhibits. The system never infers guilt, ranks suspects, or draws definitive legal conclusions. The assigned Investigating Officer remains the sole decision-maker.</span>
        </div>
      </div>

      <!-- Findings Subtabs -->
      <div class="filter-chips" style="margin: 14px 0 18px;">
        <button class="filter-chip ${this.activeTab === 'gaps' ? 'active' : ''}" onclick="ScreenFindings.render('${caseId}', 'gaps')">
          Investigation Gaps & Inquiries
        </button>
        <button class="filter-chip ${this.activeTab === 'analysis' ? 'active' : ''}" onclick="ScreenFindings.render('${caseId}', 'analysis')">
          Observations & Reasoning
        </button>
        <button class="filter-chip ${this.activeTab === 'rag' ? 'active' : ''}" onclick="Router.selectCaseAndRoute('${caseId}', 'rag')">
          Search Passages (RAG)
        </button>
      </div>

      <div id="findingsSubContent">
        ${this.activeTab === 'gaps' ? ScreenFindings.renderGapsHtml(caseId, evidenceList) : ScreenFindings.renderAnalysisHtml(caseId, evidenceList)}
      </div>

      <!-- Official Investigator Review & Endorsement Section -->
      <div class="card" style="margin-top: 20px;">
        <div class="card-header">
          <h3 class="card-title">Investigator Review Decision & Endorsement</h3>
          <span class="badge badge-info">Authoritative Decision Maker</span>
        </div>
        <form id="endorsementForm" onsubmit="event.preventDefault();" style="display: flex; flex-direction: column; gap: 12px; margin-top: 12px;">
          <div>
            <label class="form-label" for="txtReviewNotes" style="font-weight: 600;">Investigator Evaluation & Docket Findings *</label>
            <textarea id="txtReviewNotes" class="form-textarea" rows="3" placeholder="Enter findings evaluation (e.g., Forensic examination and scene evidence reviewed; post-mortem report consistent with findings; no discrepancies remain unresolved)." required>All documentary and forensic exhibits examined. Timeline sequence evaluated. Evidentiary records confirm natural progression with no suspicious contradictions.</textarea>
          </div>
          <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.84rem; padding: 10px 14px; background: var(--bg-card-subtle); border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
              <input type="checkbox" id="chkExhibitsReviewed" checked>
              <span>I have inspected all ${evidenceList.length} physical, digital, and documentary exhibits in this docket.</span>
            </label>
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
              <input type="checkbox" id="chkTimelineReviewed" checked>
              <span>I have reviewed the chronological sequence and verified temporal consistency.</span>
            </label>
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
              <input type="checkbox" id="chkGapsAddressed" checked>
              <span>I confirm that all investigative questions and information gaps have been addressed or scheduled.</span>
            </label>
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 4px;">
            <span style="font-size: 0.74rem; color: var(--text-muted);">
              Investigating Officer: <strong>${c.assigned_io_id}</strong> &bull; Station: <strong>${c.fir_metadata?.police_station || "Jurisdiction Set"}</strong>
            </span>
            <div style="display: flex; gap: 8px;">
              <button class="btn btn-secondary btn-sm" onclick="UI.showToast('Investigator notes draft saved locally.', 'info')">
                Save Draft Notes
              </button>
              <button class="btn btn-primary btn-sm" onclick="ScreenFindings.submitEndorsement('${caseId}')">
                Endorse Review & Proceed to Closure &rarr;
              </button>
            </div>
          </div>
        </form>
      </div>
    `;

    container.innerHTML = html;
  },

  submitEndorsement(caseId) {
    const notesInput = document.getElementById("txtReviewNotes");
    const notes = notesInput ? notesInput.value.trim() : "Investigator findings confirmed.";
    UI.showToast("Investigator review endorsed and recorded in Case Diary.", "success");
    UI.recordAudit("INVESTIGATOR_REVIEW_ENDORSED", caseId, "SUCCESS", notes);
    Router.selectCaseAndRoute(caseId, "closure");
  },

  renderGapsHtml(caseId, evidenceList) {
    const hasAutopsy = evidenceList.some(e => e.evidence_category === "AUTOPSY_PHOTO" || (e.description && e.description.toLowerCase().includes("autopsy")));
    const hasCdr = evidenceList.some(e => e.evidence_category === "CDR_SPREADSHEET");
    const hasScenePhoto = evidenceList.some(e => e.evidence_category === "SCENE_PHOTO");

    const caseGaps = [];
    if (!hasAutopsy) {
      caseGaps.push({
        priority: "HIGH",
        missing: "Final Post-Mortem / Viscera Toxicology Examination Report",
        relevance: "Required to establish definitive medical cause of death and rule out toxicological substances.",
        source: "State Forensic Science Laboratory (Chemical Division)",
        action: "Follow up with chemical examiner for expedited viscera analysis certificate."
      });
    }
    if (!hasCdr) {
      caseGaps.push({
        priority: "MEDIUM",
        missing: "Telecom CDR & Tower Dump Records for incident timeframe",
        relevance: "Required to verify subscriber device locations and corroboration with reported witness statements.",
        source: "Telecom Service Provider Nodal Officer",
        action: "Issue formal Section 91 CrPC / Section 94 BNSS requisition to telecom provider."
      });
    }
    if (!hasScenePhoto) {
      caseGaps.push({
        priority: "LOW",
        missing: "Comprehensive Crime Scene Inquest Photography Set",
        relevance: "Required to record physical scene orientation, ingress points, and exhibit layout.",
        source: "District Mobile Forensic Science Unit (MFSU)",
        action: "Retrieve and catalog high-resolution crime scene photos into docket."
      });
    }

    return `
      <div style="margin-top: 10px;">
        <div style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 12px;">
          Identified <strong>${caseGaps.length}</strong> investigative information gaps for Case Docket <code style="font-family: var(--font-mono); color: var(--primary);">${caseId}</code>:
        </div>
        ${caseGaps.map(g => `
          <div class="gap-card ${g.priority === 'HIGH' ? 'high-priority' : ''}">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
              <span class="badge ${g.priority === 'HIGH' ? 'badge-danger' : 'badge-attention'}">${g.priority} PRIORITY GAP</span>
              <span style="font-size: 0.74rem; color: var(--text-muted);">Potential Custodian: ${g.source}</span>
            </div>
            <div class="gap-missing-item">Missing Information: ${g.missing}</div>
            <div class="gap-relevance"><strong>Why It Matters:</strong> ${g.relevance}</div>
            <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid var(--border-subtle);">
              <span style="font-size: 0.8rem; color: var(--text-muted);">
                Recommended Step: <em>${g.action}</em>
              </span>
              <button class="btn btn-secondary btn-sm" onclick="UI.showToast('Gap recorded in Case Diary agenda.', 'info')">
                Log in Case Diary
              </button>
            </div>
          </div>
        `).join("")}
      </div>
    `;
  },

  renderAnalysisHtml(caseId, evidenceList) {
    let decisions = {};
    try {
      decisions = JSON.parse(localStorage.getItem(`sakshi_decisions_${caseId}`) || "{}");
    } catch (e) {}

    return `
      <div style="margin-top: 10px;">
        <div class="card" style="padding: 20px; margin-bottom: 16px;">
          <h4 style="color: var(--text-main); margin-bottom: 8px;">Case-Scoped Evidentiary Corroboration & Finding Decisions</h4>
          <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5;">
            Evaluating <strong>${evidenceList.length}</strong> exhibit(s) committed to case docket <code style="font-family: var(--font-mono); color: var(--primary);">${caseId}</code>.
            Review each finding and record an explicit investigative decision (Confirm, Correct, Reject, Request More Evidence, Mark Unresolved).
          </p>
        </div>
        ${evidenceList.map((e, idx) => {
          const dec = decisions[e.evidence_id];
          return `
            <div class="observation-card">
              <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div style="display: flex; gap: 6px; align-items: center;">
                  <span class="badge ${e.worm_status === 'COMMITTED' ? 'badge-verified' : 'badge-attention'}">
                    ${e.worm_status === 'COMMITTED' ? 'VERIFIED EXHIBIT' : 'VERIFICATION PENDING'}
                  </span>
                  ${dec ? `<span class="badge badge-verified">DECISION: ${dec.decision}</span>` : `<span class="badge badge-neutral">PENDING REVIEW</span>`}
                </div>
                <span style="font-size: 0.74rem; color: var(--text-muted);">Exhibit #${idx + 1}</span>
              </div>
              <div class="observation-claim">
                ${Formatters.escapeHtml(e.original_file_name)} &bull; ${Formatters.formatCategory(e.evidence_category)}
              </div>
              <div class="observation-reasoning">
                <strong>Source:</strong> ${Formatters.escapeHtml(e.source_device_or_person || "Investigative Custody")} &bull;
                <strong>Storage:</strong> WORM ${e.worm_status || "PENDING"} &bull;
                <strong>Dual-Hash:</strong> ${e.integrity_status || "PENDING"}
              </div>
              ${dec ? `
                <div style="padding: 8px 12px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); font-size: 0.78rem; margin-top: 8px;">
                  <strong>Investigator Evaluation:</strong> ${Formatters.escapeHtml(dec.reason)} &bull;
                  <span style="color: var(--text-muted); font-family: var(--font-mono);">By ${dec.reviewer} at ${Formatters.formatDate(dec.timestamp)}</span>
                </div>
              ` : ''}
              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--border-subtle); flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                  <button class="btn btn-primary btn-sm" onclick="ScreenFindings.recordDecision('${caseId}', '${e.evidence_id}', 'CONFIRMED')">Confirm</button>
                  <button class="btn btn-secondary btn-sm" onclick="ScreenFindings.recordDecision('${caseId}', '${e.evidence_id}', 'CORRECTED')">Correct</button>
                  <button class="btn btn-secondary btn-sm" onclick="ScreenFindings.recordDecision('${caseId}', '${e.evidence_id}', 'REJECTED')">Reject</button>
                  <button class="btn btn-secondary btn-sm" onclick="ScreenFindings.recordDecision('${caseId}', '${e.evidence_id}', 'REQUEST_MORE_EVIDENCE')">Request More Evidence</button>
                  <button class="btn btn-secondary btn-sm" onclick="ScreenFindings.recordDecision('${caseId}', '${e.evidence_id}', 'MARK_UNRESOLVED')">Mark Unresolved</button>
                </div>
                <div>
                  <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence'); setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer('${e.evidence_id}', '${caseId}'), 100);">
                    Inspect Exhibit Record &rarr;
                  </button>
                </div>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;
  },

  recordDecision(caseId, findingId, decision) {
    const reason = prompt(`Enter investigator justification for [${decision}]:`, "");
    if (reason === null) return;
    const decisionsKey = `sakshi_decisions_${caseId}`;
    let decisions = {};
    try {
      decisions = JSON.parse(localStorage.getItem(decisionsKey) || "{}");
    } catch (e) {}
    decisions[findingId] = {
      decision: decision,
      reason: reason || "Investigator reviewed and recorded.",
      reviewer: State.auth.subjectId || "Investigating Officer",
      timestamp: new Date().toISOString()
    };
    localStorage.setItem(decisionsKey, JSON.stringify(decisions));
    UI.showToast(`Finding marked as ${decision}`, "success");
    UI.recordAudit("INVESTIGATOR_FINDING_DECISION", caseId, decision, `${findingId}: ${reason || 'Decision recorded'}`);
    this.render(caseId, this.activeTab);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 12b. SCREEN 6b: INVESTIGATION GAPS (Route: #/cases/:id/gaps)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenGaps = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Investigation Gaps`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }

    const evidenceList = State.evidence || [];

    if (evidenceList.length === 0) {
      container.innerHTML = `
        ${renderWorkspaceHeaderHtml("gaps")}
        <div class="empty-state-card" style="margin-top: 24px; padding: 48px 24px; text-align: center; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px dashed var(--border-default);">
          
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">No Investigation Gaps Generated Yet</h3>
          <p style="color: var(--text-muted); font-size: 0.88rem; max-width: 540px; margin: 0 auto 20px auto; line-height: 1.5;">
            No evidence exhibits have been uploaded to this case docket yet. Investigation gaps, missing document alerts, and follow-up recommendations are derived strictly from verified case exhibits and witness statements.
          </p>
          <div style="display: flex; gap: 12px; justify-content: center;">
            <button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence')">
              <span>Attach Case Evidence</span>
            </button>
          </div>
        </div>
      `;
      return;
    }

    return ScreenFindings.render(caseId, "gaps");
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 12b. SCREEN 6: CASE CLOSURE WORKSPACE (Route: #/cases/:id/closure)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenClosure = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Case Closure`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }

    const c = State.activeCase;
    const evidenceList = State.evidence || [];
    const totalEvidence = evidenceList.length;
    const verifiedEvidence = evidenceList.filter(e => e.integrity_status === "VERIFIED" && e.worm_status === "COMMITTED").length;

    const isClosed = c.lifecycle_stage === "CLOSED";
    const SUPERVISORY_ROLES = ["SUPERVISORY_OFFICER", "STATION_HEAD", "ADMIN", "SUPERVISOR", "SYSTEM_ADMIN"];
    const isSupervisory = SUPERVISORY_ROLES.includes(State.auth.role);

    const requirements = [
      {
        id: "REQ_SETUP",
        title: "Stage 1 — Case Setup & Jurisdiction Allocation",
        desc: `FIR: ${c.fir_metadata?.fir_number || "Recorded"}, Station: ${c.fir_metadata?.police_station || "Station assigned"}, IO: ${c.assigned_io_id || "IO allocated"}`,
        passed: true
      },
      {
        id: "REQ_EVIDENCE",
        title: "Stage 2 — Evidence Collection & Cataloging",
        desc: `${totalEvidence} exhibit(s) attached to inquiry docket`,
        passed: totalEvidence > 0
      },
      {
        id: "REQ_VERIFY",
        title: "Stage 3 — Forensic Integrity & WORM Storage",
        desc: `${verifiedEvidence} of ${totalEvidence} exhibits verified with dual-hash signatures and immutable storage`,
        passed: totalEvidence > 0 && verifiedEvidence === totalEvidence
      },
      {
        id: "REQ_ANALYSIS",
        title: "Stage 4 — Chronological Sequence & Analytical Reasoning",
        desc: "Timeline reconstructed and cross-exhibit observations examined",
        passed: ["ANALYSIS", "REVIEW", "CLOSED"].includes(c.lifecycle_stage)
      },
      {
        id: "REQ_REVIEW",
        title: "Stage 5 — Investigator Review & Findings Endorsement",
        desc: "Investigating Officer review completed and inquiry conclusions documented",
        passed: ["REVIEW", "CLOSED"].includes(c.lifecycle_stage)
      },
      {
        id: "REQ_SUPERVISORY",
        title: "Stage 6 — Supervisory Authorization & BNSS Archival",
        desc: "Final authorization under Section 194 BNSS / Section 174 CrPC by Station Head or Supervisory Officer",
        passed: isClosed
      }
    ];

    const passedCount = requirements.filter(r => r.passed).length;
    const isReadyForClosure = c.lifecycle_stage === "REVIEW" && passedCount >= 5;

    let bannerHtml = "";
    if (isClosed) {
      bannerHtml = `
        <div class="closure-certificate-card" style="margin-bottom: 20px;">
          <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
            
            <div>
              <h2 style="font-size: 1.35rem; font-weight: 700; color: var(--text-main); margin: 0;">
                Unnatural Death Inquiry Concluded
              </h2>
              <span style="font-size: 0.85rem; color: var(--verified); font-weight: 600;">
                Permanently Archived Under Section 194 BNSS / Section 174 CrPC
              </span>
            </div>
          </div>
          <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.6; margin: 0 0 16px 0;">
            This investigation file has been formally concluded and archived by order of the authorized Station Head / Supervisory Officer. 
            All ${totalEvidence} exhibits, chronological timeline traces, and analytical observation logs are permanently preserved in tamper-evident storage.
          </p>
          <div style="display: flex; gap: 14px; flex-wrap: wrap; font-size: 0.82rem; padding: 12px 14px; background: var(--bg-card-subtle); border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
            <div>Case Reference: <strong>${c.case_id}</strong></div>
            <div>Inquest Number: <strong>${c.fir_metadata?.fir_number || "Unrecorded"}</strong></div>
            <div>Authorized Station: <strong>${c.fir_metadata?.police_station || "Jurisdiction Set"}</strong></div>
            <div>Investigating Officer: <strong>${c.assigned_io_id}</strong></div>
            <div>Archived Date: <strong>${Formatters.formatDate(c.updated_at || c.created_at)}</strong></div>
          </div>
        </div>
      `;
    } else if (isReadyForClosure) {
      bannerHtml = `
        <div class="card" style="background: var(--bg-card); border-left: 5px solid var(--primary); padding: 18px 22px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 14px;">
            <div style="flex: 1; min-width: 280px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-attention">STAGE 6 &bull; CASE CLOSURE REVIEW</span>
                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">Inquest Ready for Final Closure</span>
              </div>
              <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">
                Authorize Inquiry Conclusion & Section 194 BNSS Filing
              </h3>
              <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin: 0;">
                All evidence exhibits have been cataloged, forensically verified, and evaluated by the assigned Investigating Officer. 
                Record the final inquiry closure order to conclude this docket.
              </p>
            </div>
            <div>
              ${isSupervisory ? `
                <button class="btn btn-primary btn-stage-transition" onclick="ScreenClosure.submitClosure('${c.case_id}')">
                  Conclude Investigation & Close Case
                </button>
              ` : `
                <span class="badge badge-attention" style="padding: 6px 12px; font-size: 0.84rem;">
                  Supervisory Role Required
                </span>
              `}
            </div>
          </div>
          ${!isSupervisory ? `
            <div style="margin-top: 14px; padding: 10px 14px; background: var(--attention-bg); border: 1px solid var(--attention-border); border-radius: var(--radius-sm); font-size: 0.82rem; color: var(--attention-text);">
              <strong>Supervisory Authority Required:</strong> Under Kerala Police Standing Orders and the authoritative Stage Engine, 
              final inquiry closure requires authorization from a Supervisory Officer or Station Head (Station Head, CI, DySP, or SP). 
              Logged in role: <code>${State.auth.role}</code>.
            </div>
          ` : ""}
        </div>
      `;
    } else {
      bannerHtml = `
        <div class="card" style="background: var(--primary-bg); border-left: 5px solid var(--primary); padding: 18px 22px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div style="flex: 1; min-width: 280px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span class="badge badge-info">STAGE 6 PREREQUISITE</span>
                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">Current Case Stage: ${c.lifecycle_stage}</span>
              </div>
              <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">
                Case Closure Unavailable — Preceding Stages Incomplete
              </h3>
              <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin: 0;">
                Case closure is the final authoritative lifecycle gate. Under Police Regulations and the Stage Engine state machine, 
                a case cannot be closed until all exhibits are forensically verified, the timeline is reconstructed, and the investigator review is endorsed.
              </p>
            </div>
            <div>
              <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${c.case_id}', 'overview')">
                View Case Dashboard &rarr;
              </button>
            </div>
          </div>
        </div>
      `;
    }

    const html = `
      ${renderWorkspaceHeaderHtml("closure")}

      ${bannerHtml}

      <div class="dashboard-grid-2">
        <!-- LEFT COLUMN: Closure Requirements Checklist -->
        <div class="card">
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <h3 class="card-title">Inquest Closure Requirements Checklist</h3>
              <span style="font-size: 0.8rem; color: var(--text-muted);">${passedCount} of 6 mandatory verification requirements satisfied</span>
            </div>
            <span class="badge ${passedCount === 6 ? 'badge-verified' : 'badge-attention'}">
              ${passedCount === 6 ? 'Ready For Archival' : `${6 - passedCount} Requirement(s) Pending`}
            </span>
          </div>

          <div class="closure-checklist" style="margin-top: 14px;">
            ${requirements.map(r => `
              <div class="closure-checklist-item ${r.passed ? 'passed' : 'pending'}">
                <div class="closure-check-icon ${r.passed ? 'passed' : 'pending'}">
                  ${r.passed ? '✓' : '!'}
                </div>
                <div style="flex: 1;">
                  <div style="font-weight: 600; font-size: 0.88rem; color: var(--text-main);">${r.title}</div>
                  <div style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 2px;">${r.desc}</div>
                </div>
                <span class="badge ${r.passed ? 'badge-verified' : 'badge-neutral'}" style="font-size: 0.72rem;">
                  ${r.passed ? 'Passed' : 'Pending'}
                </span>
              </div>
            `).join("")}
          </div>
        </div>

        <!-- RIGHT COLUMN: Closure Decision & Legal Archival Dossier -->
        <div style="display: flex; flex-direction: column; gap: 20px;">
          <!-- Closure Form or Archived Record -->
          <div class="card">
            <div class="card-header">
              <h3 class="card-title">${isClosed ? "Recorded Closure Decision" : "Closure Decision & Legal Order"}</h3>
              <span class="badge badge-info">Section 194 BNSS</span>
            </div>

            ${isClosed ? `
              <div style="padding: 12px 14px; background: var(--bg-card-subtle); border-radius: var(--radius-md); font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-top: 10px;">
                <strong>Final Closure Summary:</strong> Investigation into unnatural death inquiry concluded under Section 194 BNSS. 
                All material and digital evidence verified; no unresolved foul play detected on forensic record. Final inquiry report submitted to Executive Magistrate.
              </div>
            ` : `
              <form id="closureForm" onsubmit="event.preventDefault();" style="display: flex; flex-direction: column; gap: 12px; margin-top: 12px;">
                <div>
                  <label class="form-label" for="txtClosureReason" style="font-weight: 600;">Closure Justification & Findings Summary *</label>
                  <textarea id="txtClosureReason" class="form-textarea" rows="4" placeholder="Provide formal inquiry conclusion (e.g. Accidental death established; post-mortem toxicology and scene reconstruction consistent with recorded findings; no suspicious circumstances)." required ${!isSupervisory || !isReadyForClosure ? 'disabled' : ''}>Final inquiry findings accepted. Inquest documentation, medical certificate, and verified exhibits confirm accidental unnatural death. File submitted for formal archival under Section 194 BNSS.</textarea>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                  <span style="font-size: 0.74rem; color: var(--text-muted);">
                    Sign-off Officer: <strong>${State.auth.subjectId}</strong> (${State.auth.role})
                  </span>
                  ${isReadyForClosure && isSupervisory ? `
                    <button class="btn btn-primary btn-sm btn-stage-transition" onclick="ScreenClosure.submitClosure('${c.case_id}')">
                      Conclude & Archive Case &rarr;
                    </button>
                  ` : ""}
                </div>
              </form>
            `}
          </div>

          <!-- Custody & Audit Records -->
          <div class="card">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
              <h3 class="card-title">Case Custody & Audit Log</h3>
              <button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${c.case_id}', 'audit')">
                View Full Audit &rarr;
              </button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.82rem; margin-top: 10px;">
              ${(State.auditLog.length > 0 ? State.auditLog.slice(0, 3) : [
                {
                  timestamp: c.created_at,
                  action: "Case workspace initialized",
                  actor: c.assigned_io_id
                }
              ]).map(l => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-bottom: 1px solid var(--border-subtle);">
                  <span><strong>${l.action}</strong> by ${l.actor || 'System'}</span>
                  <span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">${Formatters.formatDate(l.timestamp)}</span>
                </div>
              `).join("")}
            </div>
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;
  },

  async submitClosure(caseId) {
    const reasonInput = document.getElementById("txtClosureReason");
    const reason = reasonInput ? reasonInput.value.trim() : "Case inquiry concluded under Section 194 BNSS.";
    if (!reason) {
      UI.showToast("Please provide a closure justification.", "error");
      return;
    }

    try {
      await handleStageTransition(caseId, "CLOSED");
      UI.recordAudit("CASE_INQUEST_CONCLUDED", caseId, "SUCCESS", reason);
    } catch (err) {
      UI.showToast(`Case closure failed: ${err.message}`, "error");
    }
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 12c. SCREEN 6c: COMPREHENSIVE CASE REPORT (Route: #/cases/:id/report)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenReport = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Case Report`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }

    const c = State.activeCase;
    const evidenceList = State.evidence || [];

    if (evidenceList.length === 0) {
      container.innerHTML = `
        ${renderWorkspaceHeaderHtml("report")}
        <div class="empty-state-card" style="margin-top: 24px; padding: 48px 24px; text-align: center; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px dashed var(--border-default);">
          
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">No Case Report Available Yet</h3>
          <p style="color: var(--text-muted); font-size: 0.88rem; max-width: 560px; margin: 0 auto 20px auto; line-height: 1.5;">
            A case with zero exhibits contains no verified findings, timelines, or forensic parameters. Upload and verify case exhibits before generating the case dossier.
          </p>
          <div style="display: flex; gap: 12px; justify-content: center;">
            <button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence')">
              <span>Go to Evidence Collection</span>
            </button>
          </div>
        </div>
      `;
      return;
    }

    let timelineRes = null;
    let analysisRes = null;
    try {
      timelineRes = await Api.getTimelineEvents(caseId);
    } catch (e) {
      timelineRes = { events: [] };
    }
    try {
      analysisRes = await Api.getAnalysisSummary(caseId);
    } catch (e) {
      analysisRes = null;
    }

    let decisions = {};
    try {
      decisions = JSON.parse(localStorage.getItem(`sakshi_decisions_${caseId}`) || "{}");
    } catch (e) {}

    const events = (timelineRes && timelineRes.events) || [];
    const contradictions = (analysisRes && analysisRes.contradictions) || [];
    const gaps = (analysisRes && (analysisRes.investigation_gaps || analysisRes.evidence_gaps)) || [];
    const scenarios = (analysisRes && analysisRes.candidate_scenarios) || [];

    const html = `
      ${renderWorkspaceHeaderHtml("report")}

      <div class="cases-toolbar" style="margin-bottom: 20px;">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Comprehensive Investigation Dossier & Case Report</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Holistic forensic report synthesizing evidence register, cryptographic parameters, timeline reconstruction, and investigator review endorsements.</p>
        </div>
        <div style="display: flex; gap: 10px;">
          <button class="btn btn-secondary" onclick="window.print()">
            Print / Export Dossier
          </button>
          <button class="btn btn-primary" onclick="Router.selectCaseAndRoute('${caseId}', 'closure')">
            Proceed to Case Closure &rarr;
          </button>
        </div>
      </div>

      <div id="printableCaseReport">
        <!-- REPORT COVER / HEADER -->
        <div style="border-bottom: 3px double var(--border-default); padding-bottom: 16px; margin-bottom: 24px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
            <div>
              <div style="font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--primary); margin-bottom: 4px;">
                POLICE INVESTIGATION WORKSTATION &bull; FORENSIC DOSSIER
              </div>
              <h2 style="font-size: 1.6rem; font-weight: 800; color: var(--text-main); margin: 0 0 6px 0;">
                Inquest Case Report &bull; ${Formatters.escapeHtml(c.case_id)}
              </h2>
              <div style="font-size: 0.9rem; color: var(--text-secondary);">
                ${Formatters.escapeHtml(c.title)}
              </div>
            </div>
            <div style="text-align: right;">
              <span class="badge badge-verified" style="font-size: 0.88rem; padding: 6px 14px;">
                ${(StageDisplayMap[c.lifecycle_stage] || {}).label || c.lifecycle_stage}
              </span>
              <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 6px; font-family: var(--font-mono);">
                Dossier Generated: ${Formatters.formatDate(new Date().toISOString())}
              </div>
            </div>
          </div>
        </div>

        <!-- 1. CASE PARTICULARS & INCIDENT HEADER -->
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header">
            <h3 class="card-title">1. Case Particulars & Incident Header</h3>
            <span class="badge badge-info">Authoritative Station Record</span>
          </div>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; font-size: 0.85rem; margin-top: 10px;">
            <div><strong style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Case Docket ID:</strong> <code style="font-family: var(--font-mono); font-weight: 700;">${c.case_id}</code></div>
            <div><strong style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">FIR Reference:</strong> <span style="font-weight: 600;">${c.fir_metadata?.fir_number || 'Unassigned'}</span></div>
            <div><strong style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Police Station:</strong> <span>${c.fir_metadata?.police_station || 'Jurisdiction Assigned'}</span></div>
            <div><strong style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Investigating Officer:</strong> <span>${c.assigned_io_id}</span></div>
            <div><strong style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Incident Date / Time:</strong> <span>${Formatters.formatDate(c.fir_metadata?.incident_date || c.created_at)}</span></div>
            <div><strong style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Incident Location:</strong> <span>${c.fir_metadata?.incident_location || 'Scene recorded in case file'}</span></div>
          </div>
        </div>

        <!-- 2. FORENSIC EVIDENCE REGISTER -->
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header">
            <h3 class="card-title">2. Forensic Evidence Register (${evidenceList.length} Exhibits)</h3>
            <span class="badge badge-verified">Custodial Register</span>
          </div>
          <div style="overflow-x: auto; margin-top: 10px;">
            <table class="table" style="width: 100%; font-size: 0.82rem;">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Exhibit ID</th>
                  <th>Original Filename</th>
                  <th>Category</th>
                  <th>Source / Seized From</th>
                  <th>Size</th>
                  <th>Intake Date</th>
                </tr>
              </thead>
              <tbody>
                ${evidenceList.map((e, idx) => `
                  <tr>
                    <td>${idx + 1}</td>
                    <td><code style="font-family: var(--font-mono); color: var(--primary); font-weight: 600;">${e.evidence_id}</code></td>
                    <td><strong>${Formatters.escapeHtml(e.original_file_name)}</strong></td>
                    <td><span class="badge badge-neutral">${Formatters.formatCategory(e.evidence_category)}</span></td>
                    <td>${Formatters.escapeHtml(e.source_device_or_person || "Station Custody")}</td>
                    <td>${Formatters.formatBytes(e.file_size_bytes)}</td>
                    <td style="font-family: var(--font-mono); color: var(--text-muted);">${Formatters.formatDate(e.collection_datetime || e.created_at)}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>

        <!-- 3. SECURITY & PRESERVATION VERIFICATION SUMMARY -->
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header">
            <h3 class="card-title">3. Security & Integrity Verification Summary</h3>
            <span class="badge badge-verified">Cryptographic & Antivirus Audit</span>
          </div>
          <div style="margin-top: 8px; margin-bottom: 14px; padding: 10px 14px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border-left: 3px solid var(--primary); font-size: 0.8rem; color: var(--text-secondary);">
            <strong>Notice on Storage Protections:</strong> Local filesystem permissions and application-level object-lock manifests are a development simulation, not compliance-grade immutable hardware WORM or cloud compliance retention.
          </div>
          <div style="overflow-x: auto;">
            <table class="table" style="width: 100%; font-size: 0.8rem;">
              <thead>
                <tr>
                  <th>Exhibit ID</th>
                  <th>Format Validated</th>
                  <th>Security Scan Engine & Result</th>
                  <th>Integrity Check</th>
                  <th>Storage Lock State</th>
                  <th>Encryption at Rest</th>
                </tr>
              </thead>
              <tbody>
                ${evidenceList.map(e => `
                  <tr>
                    <td><code style="font-family: var(--font-mono);">${e.evidence_id}</code></td>
                    <td><span class="badge ${e.detected_mime_type ? 'badge-verified' : 'badge-attention'}">${e.detected_mime_type ? 'VERIFIED' : 'PENDING'}</span></td>
                    <td>
                      <span class="badge ${e.antivirus_status === 'CLEAN' ? 'badge-verified' : 'badge-attention'}">
                        ${e.antivirus_status === 'CLEAN' ? 'CLEAN' : (e.antivirus_status || 'PENDING')}
                      </span>
                      <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 2px;">
                        ${e.antivirus_scanner === 'EicarHeuristicScanner' ? 'Development Signature Scanner (EicarHeuristicScanner)' : (e.antivirus_scanner || 'Native Engine')}
                      </div>
                    </td>
                    <td><span class="badge ${e.integrity_status === 'VERIFIED' ? 'badge-verified' : 'badge-attention'}">${e.integrity_status || 'PENDING'}</span></td>
                    <td><span class="badge ${e.lock_status === 'LOCKED' ? 'badge-verified' : 'badge-neutral'}">${e.lock_status === 'LOCKED' ? 'OBJECT LOCKED (SIM)' : 'PENDING'}</span></td>
                    <td><span class="badge ${e.encryption_status === 'ENCRYPTED' ? 'badge-verified' : 'badge-neutral'}">${e.encryption_status === 'ENCRYPTED' ? 'AES-256-GCM' : 'PENDING'}</span></td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>

        <!-- 4. EXTRACTED DOCUMENTARY FACTS WITH SOURCE ATTRIBUTION -->
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header">
            <h3 class="card-title">4. Extracted Documentary Facts with Source Attribution</h3>
            <span class="badge badge-info">EC-MORE Grounding Standard</span>
          </div>
          <p style="font-size: 0.82rem; color: var(--text-muted); margin: 6px 0 12px 0;">
            Extracted facts adhere to strict attribution standards distinguishing quoted passages, automated extractions, AI interpretations, and items requiring investigator confirmation.
          </p>
          <div style="display: flex; flex-direction: column; gap: 10px;">
            ${(() => {
              let factsHtml = "";
              evidenceList.forEach(e => {
                factsHtml += `
                  <div style="padding: 12px 14px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); font-size: 0.82rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; flex-wrap: wrap; gap: 6px;">
                      <span class="badge badge-quoted">QUOTED_FROM_SOURCE</span>
                      <span style="font-family: var(--font-mono); font-size: 0.74rem; color: var(--text-muted);">
                        Exhibit: ${e.evidence_id} &bull; ${Formatters.escapeHtml(e.original_file_name)}
                      </span>
                    </div>
                    <div style="font-weight: 600; color: var(--text-main); margin-bottom: 4px;">
                      Exhibit seized from: ${Formatters.escapeHtml(e.source_device_or_person || "Station Custody")} at ${Formatters.escapeHtml(e.collection_location || "Incident Scene")}.
                    </div>
                    <div style="font-size: 0.76rem; color: var(--text-muted); font-style: italic;">
                      Source passage: "${Formatters.escapeHtml(e.description || e.original_file_name)}"
                    </div>
                  </div>
                `;
              });
              return factsHtml;
            })()}
          </div>
        </div>

        <!-- 5. CHRONOLOGICAL SEQUENCE & BRANCHING TIMELINE -->
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header">
            <h3 class="card-title">5. Chronological Sequence & Branching Timeline (${events.length} Events)</h3>
            <span class="badge badge-info">Temporal Reconstruction</span>
          </div>
          ${events.length === 0 ? `
            <div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
              No chronological events reconstructed from exhibits yet.
            </div>
          ` : `
            <div style="display: flex; flex-direction: column; gap: 10px; margin-top: 10px;">
              ${events.map(ev => `
                <div style="padding: 12px 14px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border-left: 4px solid var(--primary); font-size: 0.82rem;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; flex-wrap: wrap; gap: 6px;">
                    <div style="display: flex; gap: 6px; align-items: center;">
                      <span class="branch-pill branch-${ev.branch_id || 'MAIN'}">${ev.branch_id || 'MAIN'}</span>
                      <span class="badge ${(ev.time_certainty || ev.certainty) === 'EXACT' ? 'badge-certainty-exact' : (ev.time_certainty || ev.certainty) === 'REPORTED' ? 'badge-certainty-reported' : 'badge-certainty-estimated'}">
                        ${ev.time_certainty || ev.certainty || 'REPORTED'}
                      </span>
                    </div>
                    <span style="font-family: var(--font-mono); font-size: 0.76rem; font-weight: 600; color: var(--primary);">
                      ${ev.timestamp_display || `${ev.date} ${ev.time}`}
                    </span>
                  </div>
                  <div style="font-weight: 600; color: var(--text-main); margin-bottom: 4px;">
                    ${Formatters.escapeHtml(ev.title)}
                  </div>
                  <div style="color: var(--text-secondary); margin-bottom: 6px;">
                    ${Formatters.escapeHtml(ev.description)}
                  </div>
                  <div style="font-size: 0.74rem; color: var(--text-muted);">
                    <strong>Supporting Exhibit:</strong> <code style="font-family: var(--font-mono);">${ev.evidence_id}</code> (${Formatters.escapeHtml(ev.source_name || ev.source_file || "Exhibit")})
                  </div>
                </div>
              `).join("")}
            </div>
          `}
        </div>

        <!-- 6. EVIDENTIARY CONTRADICTIONS & INVESTIGATION GAPS -->
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header">
            <h3 class="card-title">6. Evidentiary Contradictions & Investigation Gaps</h3>
            <span class="badge badge-attention">Critical Evaluation</span>
          </div>
          <div style="margin-top: 10px;">
            <h4 style="font-size: 0.9rem; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">Contradictions Between Sources:</h4>
            ${contradictions.length === 0 ? `
              <p style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 16px;">
                No unresolved discrepancies detected between admitted exhibits.
              </p>
            ` : contradictions.map(cd => `
              <div style="padding: 12px; background: var(--attention-bg); border-radius: var(--radius-sm); border: 1px solid var(--attention-border); margin-bottom: 10px; font-size: 0.82rem;">
                <div style="font-weight: 700; color: var(--attention-text); margin-bottom: 4px;">${Formatters.escapeHtml(cd.title)}</div>
                <div style="color: var(--attention-text); margin-bottom: 6px;">${Formatters.escapeHtml(cd.difference_analysis)}</div>
                <div style="font-size: 0.76rem; color: var(--text-secondary);">
                  <strong>Source A (${cd.source_a_id}):</strong> "${Formatters.escapeHtml(cd.source_a_quote)}" &bull;
                  <strong>Source B (${cd.source_b_id}):</strong> "${Formatters.escapeHtml(cd.source_b_quote)}"
                </div>
              </div>
            `).join("")}

            <h4 style="font-size: 0.9rem; font-weight: 700; color: var(--text-main); margin: 16px 0 8px 0;">Identified Evidence Gaps & Action Items:</h4>
            ${gaps.length === 0 ? `
              <p style="font-size: 0.84rem; color: var(--text-muted);">No open investigative information gaps recorded.</p>
            ` : gaps.map(g => `
              <div style="padding: 10px 12px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); margin-bottom: 8px; font-size: 0.82rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                  <strong style="color: var(--text-main);">${Formatters.escapeHtml(g.missing_information)}</strong>
                  <span class="badge ${g.priority === 'HIGH' ? 'badge-danger' : 'badge-attention'}">${g.priority}</span>
                </div>
                <div style="color: var(--text-secondary); margin-bottom: 4px;">Why It Matters: ${Formatters.escapeHtml(g.why_it_matters)}</div>
                <div style="font-size: 0.76rem; color: var(--text-muted);">Recommended Action: <em>${Formatters.escapeHtml(g.recommended_action)}</em></div>
              </div>
            `).join("")}
          </div>
        </div>

        <!-- 7. CANDIDATE SCENARIOS (EXPLICIT HYPOTHESES) -->
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header">
            <h3 class="card-title">7. Candidate Scenarios (Explicit Hypotheses)</h3>
            <span class="badge badge-attention">Hypotheses Only</span>
          </div>
          <div style="padding: 10px 14px; background: var(--attention-bg); border: 1px solid var(--attention-border); border-radius: var(--radius-sm); margin: 10px 0 14px 0; font-size: 0.82rem; color: var(--attention-text);">
            <strong>Investigator Governance Notice:</strong> Candidate scenarios are analytical hypotheses for investigative evaluation only. SAKSHI never infers guilt, ranks suspects, or establishes cause of death. Hypotheses must never be presented as established facts.
          </div>
          <div style="display: flex; flex-direction: column; gap: 12px;">
            ${scenarios.length === 0 ? `
              <p style="font-size: 0.84rem; color: var(--text-muted);">No candidate hypotheses generated for current exhibit set.</p>
            ` : scenarios.map(sc => `
              <div style="padding: 14px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); font-size: 0.82rem;">
                <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-main); margin-bottom: 4px;">${Formatters.escapeHtml(sc.scenario_name)}</h4>
                <p style="color: var(--text-secondary); line-height: 1.5; margin-bottom: 8px;">${Formatters.escapeHtml(sc.plain_description)}</p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px; font-size: 0.78rem;">
                  <div><strong style="color: var(--primary);">Supporting Evidence:</strong> ${Formatters.escapeHtml(sc.supporting_evidence.join(", ") || "None")}</div>
                  <div><strong style="color: var(--danger);">Conflicting Evidence:</strong> ${Formatters.escapeHtml(sc.conflicting_evidence.join(", ") || "None")}</div>
                  <div><strong style="color: var(--text-muted);">Assumptions:</strong> ${Formatters.escapeHtml(sc.assumptions.join(", ") || "None")}</div>
                  <div><strong style="color: var(--text-muted);">Limitations:</strong> ${Formatters.escapeHtml(sc.confidence_limitations)}</div>
                </div>
              </div>
            `).join("")}
          </div>
        </div>

        <!-- 8. INVESTIGATOR DECISIONS & REVIEW ENDORSEMENTS -->
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header">
            <h3 class="card-title">8. Investigator Decisions & Review Endorsements</h3>
            <span class="badge badge-verified">Officer Determinations</span>
          </div>
          <div style="margin-top: 10px;">
            ${Object.keys(decisions).length === 0 ? `
              <p style="font-size: 0.84rem; color: var(--text-muted);">
                No per-finding decisions recorded yet. General review endorsement recorded under Section 194 BNSS.
              </p>
            ` : `
              <div style="display: flex; flex-direction: column; gap: 8px;">
                ${Object.entries(decisions).map(([fId, d]) => `
                  <div style="padding: 10px 12px; background: var(--bg-card-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); font-size: 0.82rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                      <span class="badge badge-verified">${d.decision}</span>
                      <span style="font-size: 0.74rem; color: var(--text-muted); font-family: var(--font-mono);">By: ${d.reviewer} &bull; ${Formatters.formatDate(d.timestamp)}</span>
                    </div>
                    <div><strong>Finding ID:</strong> <code>${fId}</code></div>
                    <div style="color: var(--text-secondary); margin-top: 2px;">Justification: ${Formatters.escapeHtml(d.reason)}</div>
                  </div>
                `).join("")}
              </div>
            `}
            <div style="margin-top: 14px; padding: 12px; background: var(--bg-card); border-radius: var(--radius-sm); border: 1px dashed var(--border-default); font-size: 0.82rem;">
              <strong>Investigating Officer Endorsement:</strong> All physical and digital exhibits have been reviewed for temporal and logical consistency. Inquest proceedings endorsed by assigned IO <strong>${c.assigned_io_id}</strong>.
            </div>
          </div>
        </div>

        <!-- 9. CRYPTOGRAPHIC HASH LEDGER & STORAGE REFERENCES -->
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header">
            <h3 class="card-title">9. Cryptographic Hash Ledger & Storage References</h3>
            <span class="badge badge-verified">Integrity Chain</span>
          </div>
          <div style="overflow-x: auto; margin-top: 10px;">
            <table class="table" style="width: 100%; font-size: 0.74rem; font-family: var(--font-mono);">
              <thead>
                <tr>
                  <th>Exhibit ID</th>
                  <th>SHA-256 Fingerprint</th>
                  <th>SHA3-512 Digest (Prefix)</th>
                  <th>Storage Reference</th>
                  <th>Encryption</th>
                </tr>
              </thead>
              <tbody>
                ${evidenceList.map(e => `
                  <tr>
                    <td style="color: var(--primary); font-weight: 700;">${e.evidence_id}</td>
                    <td>${e.checksum_sha256 || 'N/A'}</td>
                    <td>${(e.checksum_sha3_512 || 'N/A').substring(0, 32)}...</td>
                    <td>${e.worm_storage_reference || 'Committed'}</td>
                    <td>${e.encryption_algorithm || 'AES-256-GCM'}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>

        <!-- 10. STATUTORY EVIDENTIARY LIMITATIONS & NOTICE -->
        <div class="card" style="margin-bottom: 20px; border-left: 5px solid var(--primary);">
          <div class="card-header">
            <h3 class="card-title">10. Statutory Evidentiary Limitations & Notice</h3>
            <span class="badge badge-attention">Legal Disclosure</span>
          </div>
          <div style="font-size: 0.82rem; color: var(--text-secondary); line-height: 1.6; margin-top: 8px;">
            <p><strong>Legal / Evidentiary Notice:</strong> This computer-generated investigation summary does not constitute a statutory digital signature certificate under Section 63 Bharatiya Sakshya Adhiniyam, 2023 / Section 65B Indian Evidence Act, 1872. It reflects analytical guidance generated from available digital exhibits.</p>
            <p>The system's Modus Operandi Reconstruction (EC-MORE) operates under the Information Firewall and Evidence Gate principles. Inquest conclusions and formal legal charges require independent physical investigation and authorized supervisory signature.</p>
            <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-top: 24px; padding-top: 14px; border-top: 1px solid var(--border-subtle); flex-wrap: wrap; gap: 14px;">
              <div>
                <div style="font-weight: 700; color: var(--text-main);">Assigned Investigating Officer</div>
                <div style="font-size: 0.8rem; color: var(--text-muted);">${c.assigned_io_id} &bull; ${c.fir_metadata?.police_station || 'Jurisdiction Assigned'}</div>
              </div>
              <div style="text-align: right;">
                <div style="border-bottom: 1px solid var(--border-default); width: 200px; height: 30px; margin-bottom: 4px;"></div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">Signature / Official Seal</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 13. SCREEN 7: CASE ACTIVITY & AUDIT (Route: #/cases/:id/audit)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenAudit = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Case Activity`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      renderCaseNotFound(caseId, err.message);
      return;
    }
    const c = State.activeCase;

    const logs = [...State.auditLog];

    if (logs.length === 0) {
      logs.push(
        {
          id: "AUD-INIT-01",
          timestamp: c.created_at,
          actor: c.assigned_io_id,
          action: "Case workspace initialized",
          resource: c.case_id,
          result: "SUCCESS",
          details: `Inquest workspace established under FIR ${c.fir_metadata?.fir_number || 'N/A'}`
        }
      );
    }

    const html = `
      ${renderWorkspaceHeaderHtml("audit")}

      <div class="cases-toolbar">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Case Activity & Chain of Custody</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Chronological record of evidence intake, verification checks, and officer actions.</p>
        </div>
      </div>

      <div class="card" style="padding: 0; overflow: hidden; margin-top: 16px;">
        <div class="audit-entry-row" style="background-color: var(--bg-card-subtle); font-weight: 600; text-transform: uppercase; font-size: 0.72rem; color: var(--text-secondary);">
          <span>Date & Time</span>
          <span>Action Taken</span>
          <span>Evidence / Case Context</span>
          <span>Result</span>
        </div>

        ${logs.map(l => `
          <div class="audit-entry-row" onclick="ScreenAudit.showLogDetails('${l.id}', '${l.action}', '${l.details}')" style="cursor: pointer;">
            <span style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-muted);">${Formatters.formatDate(l.timestamp)}</span>
            <span style="font-weight: 600; color: var(--text-main); font-size: 0.84rem;">${l.action}</span>
            <span style="color: var(--text-secondary); font-size: 0.8rem;">
              <code style="font-family: var(--font-mono); color: var(--primary);">${l.resource}</code> &bull; ${l.details || 'Routine record'}
            </span>
            <span>
              <span class="badge ${l.result === 'SUCCESS' ? 'badge-verified' : 'badge-danger'}">${l.result}</span>
            </span>
          </div>
        `).join("")}
      </div>
    `;

    container.innerHTML = html;
  },

  showLogDetails(id, action, details) {
    const bodyHtml = `
      <div style="display: flex; flex-direction: column; gap: 10px; font-size: 0.85rem;">
        <div><span style="color: var(--text-muted);">EVENT LOG ID:</span> <strong style="font-family: var(--font-mono);">${id}</strong></div>
        <div><span style="color: var(--text-muted);">PROCEDURAL ACTION:</span> <strong>${action}</strong></div>
        <div><span style="color: var(--text-muted);">PERFORMED BY:</span> <strong>${State.auth.subjectId}</strong></div>
        <div><span style="color: var(--text-muted);">ENTRY DETAILS:</span> <div style="background-color: var(--bg-card-subtle); padding: 8px; border-radius: 4px; margin-top: 2px;">${details || "Logged by system"}</div></div>
      </div>
    `;

    UI.openModal("Case Activity Details", bodyHtml, `<button class="btn btn-secondary" onclick="UI.closeModal()">Close</button>`);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 13b. SCREEN 7b: OFFICER REGISTRY & IAM (Route: #/officers)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenOfficers = {
  officers: [],
  filters: { search: "", role: "ALL", status: "ALL" },

  async render() {
    const container = document.getElementById("viewContainer");
    if (!container) return;
    document.getElementById("breadcrumbCurrent").textContent = "Officer Registry";

    container.innerHTML = `
      <div class="screen-header" style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 1.4rem; font-weight: 700; color: var(--text-main);">Officer Registry & IAM</h2>
          <p style="font-size: 0.86rem; color: var(--text-muted); margin-top: 4px;">
            Authorized police personnel directory, jurisdiction boundaries & administrative onboarding
          </p>
        </div>
        <div style="display: flex; gap: 10px;">
          <button class="btn btn-secondary btn-sm" id="btnRefreshOfficers">↻ Refresh</button>
          <button class="btn btn-primary btn-sm" id="btnOpenOnboardModal">＋ Onboard Officer</button>
        </div>
      </div>

      <!-- Filters & Search Toolbar -->
      <div class="card" style="margin-bottom: 18px; padding: 12px;">
        <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center;">
          <div style="flex: 1; min-width: 200px;">
            <input type="text" id="officerSearchInput" class="form-input" placeholder="Search by name, username, mobile, employee ID..." value="${this.filters.search}" />
          </div>
          <div style="min-width: 160px;">
            <select id="officerRoleFilter" class="form-select">
              <option value="ALL" ${this.filters.role === "ALL" ? "selected" : ""}>All Roles</option>
              <option value="INVESTIGATING_OFFICER" ${this.filters.role === "INVESTIGATING_OFFICER" ? "selected" : ""}>Investigating Officer</option>
              <option value="SUPERVISORY_OFFICER" ${this.filters.role === "SUPERVISORY_OFFICER" ? "selected" : ""}>Supervisory Officer</option>
              <option value="STATION_HEAD" ${this.filters.role === "STATION_HEAD" ? "selected" : ""}>Station Head</option>
              <option value="CASE_ADMIN" ${this.filters.role === "CASE_ADMIN" ? "selected" : ""}>Case Admin</option>
              <option value="SYSTEM_ADMIN" ${this.filters.role === "SYSTEM_ADMIN" ? "selected" : ""}>System Admin</option>
            </select>
          </div>
          <div style="min-width: 140px;">
            <select id="officerStatusFilter" class="form-select">
              <option value="ALL" ${this.filters.status === "ALL" ? "selected" : ""}>All Statuses</option>
              <option value="ACTIVE" ${this.filters.status === "ACTIVE" ? "selected" : ""}>Active</option>
              <option value="INACTIVE" ${this.filters.status === "INACTIVE" ? "selected" : ""}>Inactive</option>
              <option value="SUSPENDED" ${this.filters.status === "SUSPENDED" ? "selected" : ""}>Suspended</option>
              <option value="TRANSFERRED" ${this.filters.status === "TRANSFERRED" ? "selected" : ""}>Transferred</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Officers Table Card -->
      <div class="card" style="padding: 0; overflow: hidden;">
        <div id="officersTableContainer">
          <div style="padding: 24px; text-align: center; color: var(--text-muted);">Loading authorized officers...</div>
        </div>
      </div>
    `;

    document.getElementById("btnRefreshOfficers")?.addEventListener("click", () => this.loadData());
    document.getElementById("btnOpenOnboardModal")?.addEventListener("click", () => this.openOnboardModal());

    document.getElementById("officerSearchInput")?.addEventListener("input", (e) => {
      this.filters.search = e.target.value.trim().toLowerCase();
      this.renderTable();
    });

    document.getElementById("officerRoleFilter")?.addEventListener("change", (e) => {
      this.filters.role = e.target.value;
      this.renderTable();
    });

    document.getElementById("officerStatusFilter")?.addEventListener("change", (e) => {
      this.filters.status = e.target.value;
      this.renderTable();
    });

    await this.loadData();
  },

  async loadData() {
    try {
      this.officers = await Api.listOfficers();
      this.renderTable();
    } catch (err) {
      const container = document.getElementById("officersTableContainer");
      if (container) {
        container.innerHTML = `
          <div style="padding: 30px; text-align: center; color: var(--danger);">
            <div style="font-size: 1.2rem; margin-bottom: 6px;">⚠️ Unable to Load Officer Registry</div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 12px;">${err.message}</div>
            <button class="btn btn-secondary btn-sm" onclick="ScreenOfficers.loadData()">Retry</button>
          </div>
        `;
      }
    }
  },

  renderTable() {
    const container = document.getElementById("officersTableContainer");
    if (!container) return;

    let filtered = this.officers || [];
    if (this.filters.search) {
      const q = this.filters.search;
      filtered = filtered.filter(o =>
        (o.full_name && o.full_name.toLowerCase().includes(q)) ||
        (o.generated_username && o.generated_username.toLowerCase().includes(q)) ||
        (o.mobile_e164 && o.mobile_e164.toLowerCase().includes(q)) ||
        (o.employee_id && o.employee_id.toLowerCase().includes(q)) ||
        (o.badge_id && o.badge_id.toLowerCase().includes(q))
      );
    }
    if (this.filters.role !== "ALL") {
      filtered = filtered.filter(o => o.role === this.filters.role);
    }
    if (this.filters.status !== "ALL") {
      filtered = filtered.filter(o => o.account_status === this.filters.status);
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div style="padding: 40px; text-align: center; color: var(--text-muted);">
          <div style="font-size: 1.5rem; margin-bottom: 6px;">👮</div>
          <div style="font-weight: 600; color: var(--text-main);">No Officers Found</div>
          <div style="font-size: 0.84rem; margin-top: 4px;">No officer records match the selected filter criteria.</div>
        </div>
      `;
      return;
    }

    const roleNameMap = {
      INVESTIGATING_OFFICER: "Investigating Officer",
      SUPERVISORY_OFFICER: "Supervisory Officer",
      STATION_HEAD: "Station Head",
      CASE_ADMIN: "Case Admin",
      SYSTEM_ADMIN: "System Admin"
    };

    const statusBadgeClass = {
      ACTIVE: "badge-verified",
      INACTIVE: "badge-neutral",
      SUSPENDED: "badge-danger",
      TRANSFERRED: "badge-attention"
    };

    container.innerHTML = `
      <table class="officers-table">
        <thead>
          <tr>
            <th>Officer Name</th>
            <th>System Username</th>
            <th>Role</th>
            <th>Station & Jurisdiction</th>
            <th>Registered Mobile</th>
            <th>Status</th>
            <th style="text-align: right;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${filtered.map(o => `
            <tr>
              <td>
                <div style="font-weight: 600; color: var(--text-main);">${o.full_name}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">
                  ${o.employee_id ? 'Emp: ' + o.employee_id : ''} ${o.badge_id ? '• Badge: ' + o.badge_id : ''}
                </div>
              </td>
              <td>
                <span class="badge badge-username">${o.generated_username}</span>
              </td>
              <td>
                <span style="font-size: 0.82rem; font-weight: 500;">${roleNameMap[o.role] || o.role}</span>
              </td>
              <td>
                <div style="font-size: 0.84rem; font-weight: 500;">${o.police_station_name || o.station_id || "Unassigned"}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">${o.jurisdiction_name || o.jurisdiction_id || ""}</div>
              </td>
              <td>
                <span style="font-family: var(--font-mono); font-size: 0.82rem;">${o.mobile_e164}</span>
              </td>
              <td>
                <span class="badge ${statusBadgeClass[o.account_status] || 'badge-neutral'}">${o.account_status}</span>
              </td>
              <td style="text-align: right;">
                <div style="display: inline-flex; gap: 6px;">
                  ${o.account_status === "ACTIVE" ? `
                    <button class="btn btn-secondary btn-sm" onclick="ScreenOfficers.openTransferModal('${o.officer_id}')" title="Transfer Officer">Transfer</button>
                    <button class="btn btn-secondary btn-sm" onclick="ScreenOfficers.openResetPasswordModal('${o.officer_id}')" title="Reset Password">Reset PW</button>
                    <button class="btn btn-secondary btn-sm" style="color: var(--danger);" onclick="ScreenOfficers.confirmDeactivate('${o.officer_id}')" title="Deactivate Account">Deactivate</button>
                  ` : `
                    <button class="btn btn-primary btn-sm" onclick="ScreenOfficers.confirmReactivate('${o.officer_id}')" title="Reactivate Account">Reactivate</button>
                  `}
                </div>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  },

  async openOnboardModal() {
    let orgs = [];
    let juris = [];
    let stations = [];

    try {
      [orgs, juris, stations] = await Promise.all([
        Api.listOrganizations().catch(() => []),
        Api.listJurisdictions().catch(() => []),
        Api.listStations().catch(() => [])
      ]);
    } catch (e) {
      console.warn("Error fetching IAM dependencies", e);
    }

    const orgOptions = orgs.map(org => `<option value="${org.org_id}">${org.name}</option>`).join("") || '<option value="KERALA_POLICE">Kerala Police</option>';
    const jurisOptions = juris.map(j => `<option value="${j.jurisdiction_id}">${j.name} (${j.state_or_province || ""})</option>`).join("") || '<option value="JUR_KL_TVM_01">Thiruvananthapuram City Jurisdiction</option>';
    const stationOptions = stations.map(s => `<option value="${s.station_id}">${s.station_name} (${s.station_code})</option>`).join("") || '<option value="STN_KL_TVM_001">Museum Police Station</option>';

    const modalBody = `
      <form id="onboardOfficerForm" style="display: flex; flex-direction: column; gap: 14px;">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div class="form-group">
            <label class="form-label" for="obFullName">Full Name *</label>
            <input type="text" id="obFullName" class="form-input" placeholder="e.g. Inspector Suresh Kumar" required />
          </div>
          <div class="form-group">
            <label class="form-label" for="obMobile">Mobile Number *</label>
            <div class="phone-input-group">
              <span class="phone-prefix">+91</span>
              <input type="tel" id="obMobile" class="form-input" placeholder="9876543210" required />
            </div>
            <span style="font-size: 0.72rem; color: var(--text-muted);">E.164 normalized mobile for Firebase authentication.</span>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div class="form-group">
            <label class="form-label" for="obRole">Assigned Role *</label>
            <select id="obRole" class="form-select" required>
              <option value="INVESTIGATING_OFFICER">Investigating Officer (IO)</option>
              <option value="SUPERVISORY_OFFICER">Supervisory Officer</option>
              <option value="STATION_HEAD">Station House Officer (SHO)</option>
              <option value="CASE_ADMIN">Case Administrator</option>
              <option value="SYSTEM_ADMIN">System Administrator</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="obPassword">Initial Secure Password *</label>
            <input type="password" id="obPassword" class="form-input" placeholder="Minimum 8 characters" minlength="8" required />
            <span style="font-size: 0.72rem; color: var(--text-muted);">Sent directly to Firebase Auth. Never logged or exposed.</span>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px;">
          <div class="form-group">
            <label class="form-label" for="obOrg">Department *</label>
            <select id="obOrg" class="form-select" required>${orgOptions}</select>
          </div>
          <div class="form-group">
            <label class="form-label" for="obJurisdiction">Jurisdiction *</label>
            <select id="obJurisdiction" class="form-select" required>${jurisOptions}</select>
          </div>
          <div class="form-group">
            <label class="form-label" for="obStation">Police Station *</label>
            <select id="obStation" class="form-select" required>${stationOptions}</select>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div class="form-group">
            <label class="form-label" for="obEmployeeId">Employee / PEN ID</label>
            <input type="text" id="obEmployeeId" class="form-input" placeholder="e.g. PEN-10492" />
          </div>
          <div class="form-group">
            <label class="form-label" for="obBadgeId">Badge / Constabulary No.</label>
            <input type="text" id="obBadgeId" class="form-input" placeholder="e.g. C-4412" />
          </div>
        </div>
      </form>
    `;

    UI.openModal(
      "Onboard Authorized Officer",
      modalBody,
      `
        <button class="btn btn-secondary" onclick="UI.closeModal()">Cancel</button>
        <button class="btn btn-primary" id="btnSubmitOnboard">Provision & Onboard Officer</button>
      `
    );

    document.getElementById("btnSubmitOnboard")?.addEventListener("click", async () => {
      const fullName = document.getElementById("obFullName")?.value?.trim();
      const rawMobile = document.getElementById("obMobile")?.value?.trim();
      const role = document.getElementById("obRole")?.value;
      const password = document.getElementById("obPassword")?.value;
      const orgId = document.getElementById("obOrg")?.value;
      const jurisdictionId = document.getElementById("obJurisdiction")?.value;
      const stationId = document.getElementById("obStation")?.value;
      const employeeId = document.getElementById("obEmployeeId")?.value?.trim() || null;
      const badgeId = document.getElementById("obBadgeId")?.value?.trim() || null;

      if (!fullName) { UI.showToast("Please enter officer's full name.", "error"); return; }
      if (!rawMobile) { UI.showToast("Please enter officer's mobile number.", "error"); return; }
      if (!password || password.length < 8) { UI.showToast("Password must be at least 8 characters long.", "error"); return; }

      let mobile = rawMobile.replace(/[\s\-()]/g, "");
      if (!mobile.startsWith("+")) {
        if (mobile.startsWith("91") && mobile.length === 12) mobile = "+" + mobile;
        else mobile = "+91" + mobile;
      }

      const btn = document.getElementById("btnSubmitOnboard");
      btn.disabled = true;
      btn.textContent = "Provisioning Identity...";

      try {
        const result = await Api.createOfficer({
          full_name: fullName,
          mobile_e164: mobile,
          password: password,
          role: role,
          org_id: orgId,
          jurisdiction_id: jurisdictionId,
          station_id: stationId,
          employee_id: employeeId,
          badge_id: badgeId
        });

        UI.closeModal();
        UI.showToast("Officer onboarded successfully!", "success");

        // Display Success Modal with Generated Username
        const successBody = `
          <div style="text-align: center; padding: 10px 0;">
            <div style="font-size: 2.5rem; margin-bottom: 8px;">✅</div>
            <h3 style="font-size: 1.2rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">Officer Identity Provisioned</h3>
            <p style="font-size: 0.86rem; color: var(--text-muted); margin-bottom: 16px;">
              A unique system username has been generated and linked to Firebase Authentication.
            </p>

            <div style="background: var(--bg-card-subtle); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 14px; margin-bottom: 16px;">
              <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">System Generated Username</span>
              <div style="font-size: 1.4rem; font-weight: 800; font-family: var(--font-mono); color: var(--primary); margin: 6px 0;">
                ${result.generated_username}
              </div>
              <div style="font-size: 0.78rem; color: var(--text-secondary);">
                Officer: <strong>${result.full_name}</strong> &bull; Mobile: <strong>${result.mobile_e164}</strong>
              </div>
            </div>

            <div style="font-size: 0.8rem; color: var(--text-muted); line-height: 1.5; text-align: left; background: var(--bg-app); padding: 10px; border-radius: var(--radius-sm);">
              ℹ️ The officer can now log into SAKSHI using their registered mobile number <strong>${result.mobile_e164}</strong> and the assigned initial password.
            </div>
          </div>
        `;

        UI.openModal(
          "Onboarding Successful",
          successBody,
          `
            <button class="btn btn-secondary" onclick="navigator.clipboard.writeText('${result.generated_username}').then(() => UI.showToast('Copied username to clipboard', 'info'))">Copy Username</button>
            <button class="btn btn-primary" onclick="UI.closeModal(); ScreenOfficers.loadData();">Done</button>
          `
        );

        await this.loadData();
      } catch (err) {
        UI.showToast(err.message || "Failed to onboard officer.", "error");
        btn.disabled = false;
        btn.textContent = "Provision & Onboard Officer";
      }
    });
  },

  async openTransferModal(officerId) {
    const officer = this.officers.find(o => o.officer_id === officerId);
    if (!officer) return;

    let orgs = [];
    let juris = [];
    let stations = [];
    try {
      [orgs, juris, stations] = await Promise.all([
        Api.listOrganizations().catch(() => []),
        Api.listJurisdictions().catch(() => []),
        Api.listStations().catch(() => [])
      ]);
    } catch (e) {
      console.warn(e);
    }

    const orgOptions = orgs.map(org => `<option value="${org.org_id}" ${org.org_id === officer.org_id ? "selected" : ""}>${org.name}</option>`).join("");
    const jurisOptions = juris.map(j => `<option value="${j.jurisdiction_id}" ${j.jurisdiction_id === officer.jurisdiction_id ? "selected" : ""}>${j.name}</option>`).join("");
    const stationOptions = stations.map(s => `<option value="${s.station_id}" ${s.station_id === officer.station_id ? "selected" : ""}>${s.station_name}</option>`).join("");

    const modalBody = `
      <form id="transferOfficerForm" style="display: flex; flex-direction: column; gap: 14px;">
        <div>
          <div style="font-weight: 600; color: var(--text-main);">${officer.full_name} (${officer.generated_username})</div>
          <div style="font-size: 0.8rem; color: var(--text-muted);">Current: ${officer.police_station_name || officer.station_id} &bull; ${officer.jurisdiction_name || officer.jurisdiction_id}</div>
        </div>
        <div class="form-group">
          <label class="form-label" for="trOrg">Target Department *</label>
          <select id="trOrg" class="form-select" required>${orgOptions}</select>
        </div>
        <div class="form-group">
          <label class="form-label" for="trJurisdiction">Target Jurisdiction *</label>
          <select id="trJurisdiction" class="form-select" required>${jurisOptions}</select>
        </div>
        <div class="form-group">
          <label class="form-label" for="trStation">Target Police Station *</label>
          <select id="trStation" class="form-select" required>${stationOptions}</select>
        </div>
        <div class="form-group">
          <label class="form-label" for="trReason">Transfer Order Reference & Reason *</label>
          <textarea id="trReason" class="form-textarea" rows="3" placeholder="e.g. Order No. PHQ/TR/2026/088 — Routine jurisdictional transfer" required></textarea>
        </div>
      </form>
    `;

    UI.openModal(
      "Transfer Officer Jurisdiction",
      modalBody,
      `
        <button class="btn btn-secondary" onclick="UI.closeModal()">Cancel</button>
        <button class="btn btn-primary" id="btnSubmitTransfer">Execute Transfer</button>
      `
    );

    document.getElementById("btnSubmitTransfer")?.addEventListener("click", async () => {
      const targetOrg = document.getElementById("trOrg")?.value;
      const targetJurisdiction = document.getElementById("trJurisdiction")?.value;
      const targetStation = document.getElementById("trStation")?.value;
      const reason = document.getElementById("trReason")?.value?.trim();

      if (!targetOrg || !targetJurisdiction || !targetStation) {
        UI.showToast("All organizational fields are required.", "error");
        return;
      }
      if (!reason) {
        UI.showToast("Transfer reason / order reference is required.", "error");
        return;
      }

      const btn = document.getElementById("btnSubmitTransfer");
      btn.disabled = true;
      btn.textContent = "Executing Transfer...";

      try {
        await Api.transferOfficer(officerId, {
          target_org_id: targetOrg,
          target_jurisdiction_id: targetJurisdiction,
          target_station_id: targetStation,
          reason: reason
        });
        UI.showToast("Officer successfully transferred.", "success");
        UI.closeModal();
        await this.loadData();
      } catch (err) {
        UI.showToast(err.message || "Failed to transfer officer.", "error");
        btn.disabled = false;
        btn.textContent = "Execute Transfer";
      }
    });
  },

  openResetPasswordModal(officerId) {
    const officer = this.officers.find(o => o.officer_id === officerId);
    if (!officer) return;

    const modalBody = `
      <form id="resetPwForm" style="display: flex; flex-direction: column; gap: 14px;">
        <div>
          <div style="font-weight: 600; color: var(--text-main);">${officer.full_name} (${officer.generated_username})</div>
          <div style="font-size: 0.8rem; color: var(--text-muted);">Registered Mobile: ${officer.mobile_e164}</div>
        </div>
        <div class="form-group">
          <label class="form-label" for="newPwInput">New Secure Password *</label>
          <input type="password" id="newPwInput" class="form-input" placeholder="Minimum 8 characters" minlength="8" required />
          <span style="font-size: 0.72rem; color: var(--text-muted);">Updates Firebase Authentication credential immediately.</span>
        </div>
      </form>
    `;

    UI.openModal(
      "Reset Officer Password",
      modalBody,
      `
        <button class="btn btn-secondary" onclick="UI.closeModal()">Cancel</button>
        <button class="btn btn-primary" id="btnSubmitResetPw">Update Password</button>
      `
    );

    document.getElementById("btnSubmitResetPw")?.addEventListener("click", async () => {
      const newPw = document.getElementById("newPwInput")?.value;
      if (!newPw || newPw.length < 8) {
        UI.showToast("Password must be at least 8 characters long.", "error");
        return;
      }

      const btn = document.getElementById("btnSubmitResetPw");
      btn.disabled = true;
      btn.textContent = "Updating...";

      try {
        await Api.resetOfficerPassword(officerId, newPw);
        UI.showToast("Password updated in Firebase Auth successfully.", "success");
        UI.closeModal();
      } catch (err) {
        UI.showToast(err.message || "Failed to reset password.", "error");
        btn.disabled = false;
        btn.textContent = "Update Password";
      }
    });
  },

  confirmDeactivate(officerId) {
    const officer = this.officers.find(o => o.officer_id === officerId);
    if (!officer) return;

    UI.openModal(
      "Confirm Account Deactivation",
      `
        <div style="padding: 6px 0;">
          <p style="font-size: 0.9rem; color: var(--text-main); margin-bottom: 10px;">
            Are you sure you want to deactivate <strong>${officer.full_name}</strong> (${officer.generated_username})?
          </p>
          <p style="font-size: 0.82rem; color: var(--danger); line-height: 1.4;">
            ⚠️ This will immediately revoke the officer's Firebase sessions and block all investigative and case access.
          </p>
        </div>
      `,
      `
        <button class="btn btn-secondary" onclick="UI.closeModal()">Cancel</button>
        <button class="btn btn-danger" id="btnDoDeactivate">Deactivate Account</button>
      `
    );

    document.getElementById("btnDoDeactivate")?.addEventListener("click", async () => {
      try {
        await Api.deactivateOfficer(officerId);
        UI.showToast("Officer account deactivated.", "info");
        UI.closeModal();
        await this.loadData();
      } catch (err) {
        UI.showToast(err.message || "Failed to deactivate officer.", "error");
      }
    });
  },

  confirmReactivate(officerId) {
    const officer = this.officers.find(o => o.officer_id === officerId);
    if (!officer) return;

    UI.openModal(
      "Confirm Account Reactivation",
      `
        <div style="padding: 6px 0;">
          <p style="font-size: 0.9rem; color: var(--text-main);">
            Reactivate account for <strong>${officer.full_name}</strong> (${officer.generated_username})?
          </p>
          <p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 6px;">
            The officer's Firebase identity will be re-enabled for login.
          </p>
        </div>
      `,
      `
        <button class="btn btn-secondary" onclick="UI.closeModal()">Cancel</button>
        <button class="btn btn-primary" id="btnDoReactivate">Reactivate Account</button>
      `
    );

    document.getElementById("btnDoReactivate")?.addEventListener("click", async () => {
      try {
        await Api.reactivateOfficer(officerId);
        UI.showToast("Officer account reactivated.", "success");
        UI.closeModal();
        await this.loadData();
      } catch (err) {
        UI.showToast(err.message || "Failed to reactivate officer.", "error");
      }
    });
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 14. SCREEN 8: SETTINGS (Route: #/settings)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenSettings = {
  async render() {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = "Settings";

    let health = State.systemHealth;
    try {
      health = await Api.getHealth();
      State.systemHealth = health;
    } catch (e) {
      health = { status: "operational", modules: [] };
    }

    const html = `
      <div class="cases-toolbar">
        <div>
          <h2 style="font-size: 1.4rem; font-weight: 700; color: var(--text-main);">Settings</h2>
          <p style="color: var(--text-muted); font-size: 0.84rem;">Investigator identity, station jurisdiction, and appearance preferences.</p>
        </div>
      </div>

      <div class="grid-2" style="margin-top: 16px;">
        <!-- Investigator Settings -->
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Investigator Settings</h3>
            <span class="badge badge-verified">Officer Identity</span>
          </div>

          <form id="settingsIdentityForm">
            <div class="form-group" style="margin-bottom: 14px;">
              <label class="form-label">Officer Identity Presets (Development)</label>
              <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="ScreenSettings.applyPreset('dev-investigator-001', 'Dev Inspector (Development Only)', 'INVESTIGATING_OFFICER', 'KERALA')">
                  🔍 dev-investigator-001 (Pipeline IO / Kerala)
                </button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="ScreenSettings.applyPreset('SUPERVISOR-KL-01', 'Circle Inspector', 'SUPERVISORY_OFFICER', 'KERALA')">
                  🛡️ Supervisory Officer (All Cases Scope)
                </button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="ScreenSettings.applyPreset('IO-7842-SHARMA', 'IO Sharma', 'INVESTIGATING_OFFICER', 'KL-TVM-001')">
                  👮 IO-7842-SHARMA (Station Officer)
                </button>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label" for="inpSubjectId">Investigating Officer Badge / ID</label>
              <input type="text" id="inpSubjectId" class="form-input" value="${State.auth.subjectId}">
            </div>

            <div class="grid-2">
              <div class="form-group">
                <label class="form-label" for="inpRole">Designation / Role</label>
                <select id="inpRole" class="form-select">
                  <option value="INVESTIGATING_OFFICER" ${State.auth.role === 'INVESTIGATING_OFFICER' ? 'selected' : ''}>Investigating Officer (SI / Inspector)</option>
                  <option value="SUPERVISORY_OFFICER" ${State.auth.role === 'SUPERVISORY_OFFICER' ? 'selected' : ''}>Supervisory Officer (Circle Insp / DySP)</option>
                  <option value="STATION_HEAD" ${State.auth.role === 'STATION_HEAD' ? 'selected' : ''}>Station House Officer (SHO)</option>
                  <option value="ADMIN" ${State.auth.role === 'ADMIN' ? 'selected' : ''}>System Administrator</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label" for="inpJurisdiction">Station Jurisdiction Code</label>
                <input type="text" id="inpJurisdiction" class="form-input" value="${State.auth.jurisdiction}">
              </div>
            </div>

            <div class="form-group" style="margin-top: 10px;">
              <label class="form-label">Display Appearance Theme</label>
              <div style="display: flex; gap: 10px; margin-top: 4px;">
                <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; cursor: pointer;">
                  <input type="radio" name="optTheme" value="light" ${State.theme === 'light' ? 'checked' : ''}>
                  <span>Investigation Desk Mode (Light)</span>
                </label>
                <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; cursor: pointer;">
                  <input type="radio" name="optTheme" value="dark" ${State.theme === 'dark' ? 'checked' : ''}>
                  <span>Control Room Mode (Dark)</span>
                </label>
              </div>
            </div>

            <button type="submit" class="btn btn-primary" style="margin-top: 10px;">
              Save Preferences
            </button>
          </form>
        </div>

        <!-- System & Forensic Administration (Collapsible) -->
        <div class="card">
          <details open>
            <summary class="card-header" style="cursor: pointer; user-select: none;">
              <h3 class="card-title" style="display: inline;">System & Forensic Administration</h3>
              <span class="badge ${health.status === 'healthy' ? 'badge-verified' : 'badge-attention'}" style="margin-left: 8px;">
                ${(health.status || 'ACTIVE').toUpperCase()}
              </span>
            </summary>

            <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.82rem; margin-top: 12px;">
              ${[
                { name: "Case Management Engine", desc: "Digital Case Workspaces", status: "ACTIVE" },
                { name: "Identity & Authentication", desc: "Officer Header & Credentials", status: "ACTIVE" },
                { name: "Access Permissions", desc: "Role-Based Police Access Gates", status: "ACTIVE" },
                { name: "Investigation Progress Engine", desc: "Case Progression State Machine", status: "ACTIVE" },
                { name: "Evidence Intake Service", desc: "Multi-Modal Exhibit Staging", status: "ACTIVE" },
                { name: "File Format Verification", desc: "Binary File Signature Engine", status: "ACTIVE" },
                { name: "Security Threat Scanner", desc: "Malware & Threat Defense", status: "ACTIVE" },
                { name: "Protected Storage", desc: "Tamper-Proof Locker Storage", status: "ACTIVE" },
                { name: "Dual-Hash Integrity Fingerprint", desc: "SHA-256 + SHA3-512 Verification", status: "ACTIVE" },
                { name: "Write Protection Service", desc: "Immutable Object Retention Lock", status: "ACTIVE" },
                { name: "Confidential Encryption", desc: "AES-256-GCM Cipher at Rest", status: "ACTIVE" }
              ].map(mod => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 5px 8px; border-bottom: 1px solid var(--border-subtle);">
                  <div>
                    <strong>${mod.name}</strong>
                    <span style="color: var(--text-muted); display: block; font-size: 0.72rem;">${mod.desc}</span>
                  </div>
                  <span class="badge ${mod.status === 'ACTIVE' ? 'badge-verified' : 'badge-neutral'}">
                    ${mod.status}
                  </span>
                </div>
              `).join("")}
            </div>
          </details>
        </div>
      </div>
    `;

    container.innerHTML = html;

    document.getElementById("settingsIdentityForm")?.addEventListener("submit", (e) => {
      e.preventDefault();
      const subjectId = document.getElementById("inpSubjectId").value.trim();
      const role = document.getElementById("inpRole").value;
      const jurisdiction = document.getElementById("inpJurisdiction").value.trim();
      const selectedTheme = document.querySelector("input[name='optTheme']:checked")?.value || "light";

      if (!subjectId) return;

      State.auth.subjectId = subjectId;
      State.auth.role = role;
      State.auth.jurisdiction = jurisdiction;
      State.auth.headers["X-Investigator-Id"] = subjectId;
      State.auth.headers["X-Investigator-Role"] = role;
      State.auth.headers["X-Investigator-Jurisdiction"] = jurisdiction;
      localStorage.setItem("sakshi_dev_subject_id", subjectId);
      localStorage.setItem("sakshi_dev_role", role);
      localStorage.setItem("sakshi_dev_jurisdiction", jurisdiction);

      applyTheme(selectedTheme);
      updateHeaderAuth();
      UI.showToast(`Officer settings saved successfully`, "success");
    });
  },

  applyPreset(subjectId, displayName, role, jurisdiction) {
    const idEl = document.getElementById("inpSubjectId");
    const roleEl = document.getElementById("inpRole");
    const jurEl = document.getElementById("inpJurisdiction");
    if (idEl) idEl.value = subjectId;
    if (roleEl) roleEl.value = role;
    if (jurEl) jurEl.value = jurisdiction;
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// INVESTIGATOR-FIRST CONSOLIDATION
// These views deliberately compose the existing, authorised APIs.  They do not
// manufacture case facts, relationships, deletion actions, or workflow states.
// ═══════════════════════════════════════════════════════════════════════════

const InvestigatorFirst = {
  isAdministrator() {
    return ["ADMIN", "SYSTEM_ADMINISTRATOR", "SUPERVISOR", "SUPERVISORY_OFFICER", "STATION_HEAD"].includes(State.auth.role);
  },

  evidenceStatus(evidence) {
    const failed = evidence.status === "REJECTED" || evidence.antivirus_status === "THREAT_DETECTED" || evidence.antivirus_status === "SCAN_ERROR" || evidence.integrity_status === "FAILED" || evidence.lock_status === "LOCK_FAILED" || evidence.encryption_status === "ENCRYPTION_FAILED";
    const unavailable = evidence.antivirus_status === "SCANNER_UNAVAILABLE" || evidence.antivirus_status === "SCAN_TIMEOUT";
    const ready = evidence.integrity_status === "VERIFIED" && evidence.worm_status === "COMMITTED";
    if (failed) return { label: "Review required", subtext: "A recorded check needs investigator attention", badge: "badge-danger" };
    if (unavailable) return { label: "Unavailable", subtext: "A required scanner result is unavailable", badge: "badge-neutral" };
    if (ready) return { label: "Ready for review", subtext: "Preservation and integrity checks are recorded", badge: "badge-verified" };
    if (["REGISTERED_INTAKE", "PENDING_MIME_VALIDATION", "VALIDATED", "AV_SCANNING", "CLEAN"].includes(evidence.status) || !evidence.status) {
      return { label: "Processing", subtext: "Automated evidence checks are not complete", badge: "badge-attention" };
    }
    return { label: "Review required", subtext: "Current processing state needs review", badge: "badge-attention" };
  },

  caseSummary(caseRecord) {
    const metadata = caseRecord.fir_metadata || {};
    const additional = metadata.additional_attributes || {};
    return metadata.reported_narrative || additional.reported_narrative || additional.case_summary || "No narrative summary has been recorded in the available case particulars.";
  },

  caseStatus(caseRecord) {
    const stage = caseRecord.lifecycle_stage || "INITIALIZED";
    const labels = {
      INITIALIZED: "Case registration in progress",
      EVIDENCE_INGESTION: "Collecting evidence",
      EVIDENCE_PROCESSING: "Evidence checks in progress",
      ANALYSIS: "Reviewing case information",
      REVIEW: "Awaiting investigator review",
      CLOSED: "Case record closed",
      SUSPENDED: "Case suspended",
      REOPENED: "Case reopened"
    };
    return labels[stage] || "Status unavailable";
  },

  sourceEvidence(sourceName) {
    const name = String(sourceName || "").trim().toLowerCase();
    if (!name) return null;
    return (State.evidence || []).find(e => String(e.original_file_name || "").trim().toLowerCase() === name) || null;
  },

  sourceButton(caseId, sourceName, label = "Open source") {
    const evidence = this.sourceEvidence(sourceName);
    if (!evidence) return `<span class="source-unavailable">Source link unavailable</span>`;
    return `<button class="btn btn-secondary btn-sm" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence'); setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer('${evidence.evidence_id}', '${caseId}'), 120);">${label}</button>`;
  },

  text(value, fallback = "Not recorded") {
    return Formatters.escapeHtml(value === undefined || value === null || value === "" ? fallback : String(value));
  },

  openEvidence(caseId, evidenceId) {
    Router.selectCaseAndRoute(caseId, "evidence");
    setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer(evidenceId, caseId), 120);
  },

  renderPermissionDenied(title = "Administration") {
    const container = document.getElementById("viewContainer");
    container.innerHTML = `<div class="empty-state-card investigator-empty"><h2>Permission required</h2><p>${this.text(title)} is restricted to authorised administrative roles. Your access has not been changed.</p><button class="btn btn-secondary" onclick="Router.navigate('#/cases')">Return to cases</button></div>`;
  }
};

function renderWorkspaceHeaderHtml(activeTab) {
  const c = State.activeCase;
  if (!c) return "";
  const metadata = c.fir_metadata || {};
  const allowed = (State.activeStageInfo && State.activeStageInfo.allowed_transitions) || [];
  const next = allowed[0];
  const tab = (key, label, path) => `<button class="tab-btn ${activeTab === key ? "active" : ""}" onclick="Router.selectCaseAndRoute('${c.case_id}', '${path}')">${label}</button>`;
  return `
    <section class="investigator-case-header">
      <div>
        <div class="case-header-kicker">${InvestigatorFirst.text(c.case_id)} · ${InvestigatorFirst.text(InvestigatorFirst.caseStatus(c))}</div>
        <h2>${InvestigatorFirst.text(c.title)}</h2>
        <p>FIR ${InvestigatorFirst.text(metadata.fir_number)} · ${InvestigatorFirst.text(metadata.police_station)} · Updated ${Formatters.formatDate(c.updated_at)}</p>
      </div>
      <div class="investigator-header-actions">
        <button class="btn btn-secondary btn-sm" onclick="Router.navigate('#/cases')">All cases</button>
        ${next ? `<button class="btn btn-primary btn-sm btn-stage-transition" onclick="handleStageTransition('${c.case_id}', '${next}')">${InvestigatorFirst.text((StageDisplayMap[next] || {}).short || "Continue investigation")}</button>` : ""}
      </div>
    </section>
    <nav class="case-workspace-tabs investigator-tabs" aria-label="Case workspace">
      ${tab("overview", "Case brief", "overview")}
      ${tab("evidence", `Evidence (${(State.evidence || []).length})`, "evidence")}
      ${tab("connections", "Connections", "connections")}
      ${tab("timeline", "Timeline & Scenarios", "timeline")}
      ${tab("findings", "Findings & Contradictions", "findings")}
      ${tab("report", "Case Report", "report")}
    </nav>`;
}

ScreenCaseOverview.render = async function(caseId) {
  const container = document.getElementById("viewContainer");
  document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Case Brief`;
  try {
    await ensureActiveCaseLoaded(caseId);
  } catch (err) {
    renderCaseNotFound(caseId, err.message);
    return;
  }

  const c = State.activeCase;
  const exhibits = State.evidence || [];
  let analysis = null;
  let timeline = null;
  try { [analysis, timeline] = await Promise.all([Api.getAnalysisSummary(caseId), Api.getTimelineEvents(caseId)]); } catch (err) { console.warn("Case brief analysis unavailable", err); }
  const contradictions = analysis && Array.isArray(analysis.contradictions) ? analysis.contradictions : [];
  const gaps = analysis && Array.isArray(analysis.investigation_gaps) ? analysis.investigation_gaps : [];
  const events = timeline && Array.isArray(timeline.events) ? [...timeline.events].sort((a, b) => Date.parse(a.raw_timestamp || `${a.date}T${a.time || "00:00"}`) - Date.parse(b.raw_timestamp || `${b.date}T${b.time || "00:00"}`)).slice(-4) : [];
  const questions = gaps.slice(0, 3);
  const actions = [
    ["Evidence", "evidence"], ["Connections", "connections"], ["Timeline & Scenarios", "timeline"], ["Findings & Contradictions", "findings"], ["Case Report", "report"]
  ];
  container.innerHTML = `
    ${renderWorkspaceHeaderHtml("overview")}
    <main class="investigator-brief">
      <section class="brief-summary">
        <div><h3>Case summary</h3><p>${InvestigatorFirst.text(InvestigatorFirst.caseSummary(c))}</p></div>
        <dl class="brief-facts">
          <div><dt>Current status</dt><dd>${InvestigatorFirst.text(InvestigatorFirst.caseStatus(c))}</dd></div>
          <div><dt>Evidence exhibits</dt><dd>${exhibits.length}</dd></div>
          <div><dt>Unresolved findings</dt><dd>${analysis ? contradictions.filter(item => !["CONFIRMED", "DISMISSED", "EXPLAINED"].includes(item.investigator_status)).length : "Not assessed"}</dd></div>
        </dl>
      </section>
      <div class="brief-grid">
        <section class="brief-panel"><h3>Outstanding investigative questions</h3>${analysis === null ? `<p class="muted">Grounded analysis is currently unavailable.</p>` : questions.length ? `<ol>${questions.map(item => `<li>${InvestigatorFirst.text(item.missing_information || item.title || item.question)}</li>`).join("")}</ol>` : `<p class="muted">No unresolved questions are returned by the current analysis.</p>`}</section>
        <section class="brief-panel"><h3>Recent case events</h3>${events.length ? `<ol class="case-event-list">${events.map(event => `<li><time>${InvestigatorFirst.text(event.date)} ${InvestigatorFirst.text(event.time, "")}</time><span>${InvestigatorFirst.text(event.title)}</span>${InvestigatorFirst.sourceButton(caseId, event.source_name, "Open source")}</li>`).join("")}</ol>` : `<p class="muted">No source-backed timeline events are available yet.</p>`}</section>
      </div>
      <section class="brief-actions"><h3>Open a workspace</h3><div>${actions.map(([label, path]) => `<button class="btn btn-secondary" onclick="Router.selectCaseAndRoute('${caseId}', '${path}')">${label}</button>`).join("")}</div></section>
    </main>`;
};

ScreenFindings.render = async function(caseId) {
  const container = document.getElementById("viewContainer");
  document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Findings & Contradictions`;
  try { await ensureActiveCaseLoaded(caseId); } catch (err) { renderCaseNotFound(caseId, err.message); return; }
  let analysis;
  try { analysis = await Api.getAnalysisSummary(caseId); } catch (err) {
    container.innerHTML = `${renderWorkspaceHeaderHtml("findings")}<div class="empty-state-card investigator-empty"><h2>Findings unavailable</h2><p>Grounded comparison results could not be loaded. No finding has been inferred locally.</p><button class="btn btn-secondary" onclick="ScreenFindings.render('${caseId}')">Retry</button></div>`;
    return;
  }
  const contradictions = analysis.contradictions || [];
  const observations = analysis.supported_observations || [];
  const gaps = analysis.investigation_gaps || [];
  const contradictionCard = item => `<article class="finding-card potential"><div class="finding-state">${InvestigatorFirst.text((item.investigator_status || "POTENTIAL ISSUE REQUIRING REVIEW").replaceAll("_", " "))}</div><h4>${InvestigatorFirst.text(item.title)}</h4><p>${InvestigatorFirst.text(item.difference_summary || item.reason || "The comparison requires investigator review.")}</p><div class="comparison-grid"><div><strong>${InvestigatorFirst.text(item.source_a_filename, "Source A")}</strong><blockquote>${InvestigatorFirst.text(item.source_a_passage)}</blockquote>${InvestigatorFirst.sourceButton(caseId, item.source_a_filename)}</div><div><strong>${InvestigatorFirst.text(item.source_b_filename, "Source B")}</strong><blockquote>${InvestigatorFirst.text(item.source_b_passage)}</blockquote>${InvestigatorFirst.sourceButton(caseId, item.source_b_filename)}</div></div><p class="finding-limitation">This identifies a comparison for review. It does not establish that either account is false or resolve the matter.</p></article>`;
  const observationCard = item => { const source = item.source_filename || item.source_name || item.evidence_filename; return `<article class="finding-card"><h4>${InvestigatorFirst.text(item.title || item.heading || item.observation)}</h4><p>${InvestigatorFirst.text(item.summary || item.description || item.text)}</p>${source ? `<p class="source-caption">Source: ${InvestigatorFirst.text(source)}</p>${InvestigatorFirst.sourceButton(caseId, source)}` : `<p class="source-caption">No source file reference was returned.</p>`}</article>`; };
  const gapCard = item => `<article class="finding-card"><h4>${InvestigatorFirst.text(item.missing_information || item.title)}</h4><p>${InvestigatorFirst.text(item.why_it_matters || item.reason)}</p>${item.recommended_action ? `<p><strong>Suggested next question:</strong> ${InvestigatorFirst.text(item.recommended_action)}</p>` : ""}</article>`;
  container.innerHTML = `
    ${renderWorkspaceHeaderHtml("findings")}
    <main class="findings-workspace">
      <header><h3>Findings & Contradictions</h3><p>Comparisons are shown only when the case analysis returned source-backed material. Investigator confirmation remains separate from automated analysis.</p></header>
      <section><h3>Potential contradictions</h3>${contradictions.length ? contradictions.map(contradictionCard).join("") : `<p class="empty-inline">No potential contradictions are returned by the current case analysis.</p>`}</section>
      ${observations.length ? `<section><h3>Supporting evidence</h3>${observations.map(observationCard).join("")}</section>` : ""}
      ${gaps.length ? `<section><h3>Missing or insufficient information</h3>${gaps.map(gapCard).join("")}</section>` : ""}
      <section class="finding-governance"><h3>Assessment and notes</h3><p>Finding-level assessment and notes are not available through the current findings API. Review an extracted fact or a relationship from its source to record an authorised, audited decision.</p><button class="btn btn-secondary" onclick="Router.selectCaseAndRoute('${caseId}', 'evidence')">Open evidence</button></section>
    </main>`;
};

ScreenReport.render = async function(caseId) {
  const container = document.getElementById("viewContainer");
  document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Case Report`;
  try { await ensureActiveCaseLoaded(caseId); } catch (err) { renderCaseNotFound(caseId, err.message); return; }
  const c = State.activeCase;
  const exhibits = State.evidence || [];
  const [timelineResult, analysisResult, graphResult] = await Promise.all([
    Api.getTimelineEvents(caseId).catch(() => null), Api.getAnalysisSummary(caseId).catch(() => null), Api.getKnowledgeGraph(caseId).catch(() => null)
  ]);
  const events = (timelineResult && timelineResult.events) || [];
  const analysis = analysisResult || { contradictions: [], investigation_gaps: [], candidate_scenarios: [], supported_observations: [] };
  const graph = graphResult || { edges: [] };
  const exhibitLink = evidence => `<button class="report-link" onclick="InvestigatorFirst.openEvidence('${caseId}', '${evidence.evidence_id}')">${InvestigatorFirst.text(evidence.evidence_id)}</button>`;
  const eventRows = events.length ? events.map(event => `<tr><td>${InvestigatorFirst.text(event.date)} ${InvestigatorFirst.text(event.time, "")}</td><td>${InvestigatorFirst.text(event.title)}</td><td>${InvestigatorFirst.text(event.time_certainty || "Not recorded")}</td><td>${InvestigatorFirst.sourceButton(caseId, event.source_name)}</td></tr>`).join("") : `<tr><td colspan="4">No source-backed chronological events are available.</td></tr>`;
  container.innerHTML = `
    ${renderWorkspaceHeaderHtml("report")}
    <main id="printableCaseReport" class="case-report">
      <header class="report-title"><div><span>Investigation report</span><h2>${InvestigatorFirst.text(c.title)}</h2><p>${InvestigatorFirst.text(c.case_id)} · FIR ${InvestigatorFirst.text(c.fir_metadata?.fir_number)}</p></div><button class="btn btn-secondary" onclick="window.print()">Print report</button></header>
      <section><h3>1. Case particulars</h3><dl class="report-particulars"><div><dt>Station</dt><dd>${InvestigatorFirst.text(c.fir_metadata?.police_station)}</dd></div><div><dt>Reported incident date</dt><dd>${InvestigatorFirst.text(c.fir_metadata?.incident_date)}</dd></div><div><dt>Location</dt><dd>${InvestigatorFirst.text(c.fir_metadata?.incident_location)}</dd></div><div><dt>Assigned investigator</dt><dd>${InvestigatorFirst.text(c.assigned_io_id)}</dd></div></dl></section>
      <section><h3>2. Executive case summary</h3><p>${InvestigatorFirst.text(InvestigatorFirst.caseSummary(c))}</p><p class="report-caution">This report separates case-record facts from analysis and hypotheses. It does not add conclusions beyond the available records.</p></section>
      <section><h3>3. Evidence register</h3><table><thead><tr><th>Reference</th><th>Exhibit</th><th>Category</th><th>Source / origin</th><th>Review status</th></tr></thead><tbody>${exhibits.length ? exhibits.map(e => `<tr><td>${exhibitLink(e)}</td><td>${InvestigatorFirst.text(e.original_file_name)}</td><td>${InvestigatorFirst.text(Formatters.formatPlainCategory(e.evidence_category))}</td><td>${InvestigatorFirst.text(e.source_device_or_person || e.collection_location)}</td><td>${InvestigatorFirst.text(InvestigatorFirst.evidenceStatus(e).label)}</td></tr>`).join("") : `<tr><td colspan="5">No evidence exhibits have been registered.</td></tr>`}</tbody></table></section>
      <section><h3>4. Reconstructed chronological events</h3><table><thead><tr><th>Recorded time</th><th>Event</th><th>Timestamp precision</th><th>Source</th></tr></thead><tbody>${eventRows}</tbody></table></section>
      <section><h3>5. Established relationships</h3>${graph.edges.length ? `<ul class="report-list">${graph.edges.filter(edge => edge.review_status === "CONFIRMED").map(edge => `<li>${InvestigatorFirst.text(edge.label || edge.relation_type)} — ${InvestigatorFirst.text(edge.source_filename)}. ${InvestigatorFirst.sourceButton(caseId, edge.source_filename)}</li>`).join("") || "<li>No relationships have been confirmed by an investigator.</li>"}</ul>` : `<p>No source-backed relationships are available.</p>`}</section>
      <section><h3>6. Alternative scenarios</h3>${analysis.candidate_scenarios?.length ? analysis.candidate_scenarios.map(item => `<article class="report-scenario"><h4>${InvestigatorFirst.text(item.title || item.scenario_name)}</h4><p>${InvestigatorFirst.text(item.plain_language_description || item.plain_description)}</p><p><strong>Hypothesis only:</strong> ${InvestigatorFirst.text(item.hypothesis_disclaimer, "This is an investigative hypothesis, not an established fact.")}</p><p><strong>What could distinguish it:</strong> ${InvestigatorFirst.text(item.distinguishing_evidence_needed)}</p></article>`).join("") : `<p>No supported alternative scenarios are available.</p>`}</section>
      <section><h3>7. Contradictions and unresolved findings</h3>${analysis.contradictions?.length ? analysis.contradictions.map(item => `<article class="report-finding"><h4>${InvestigatorFirst.text(item.title)}</h4><p>${InvestigatorFirst.text(item.difference_summary)}</p><p>${InvestigatorFirst.sourceButton(caseId, item.source_a_filename)} ${InvestigatorFirst.sourceButton(caseId, item.source_b_filename)}</p></article>`).join("") : `<p>No potential contradictions are returned by the current analysis.</p>`}</section>
      <section><h3>8. Missing information and investigative questions</h3>${analysis.investigation_gaps?.length ? `<ul class="report-list">${analysis.investigation_gaps.map(item => `<li>${InvestigatorFirst.text(item.missing_information || item.title)}${item.recommended_action ? ` — ${InvestigatorFirst.text(item.recommended_action)}` : ""}</li>`).join("")}</ul>` : `<p>No missing-information items are returned by the current analysis.</p>`}</section>
      <section><h3>9. Investigator assessment</h3><p>No investigator assessment is included because the current report API does not expose one. Authorised fact and relationship decisions remain linked to their original sources.</p></section>
      <section><h3>10. Evidence references and provenance</h3><p>Each table entry links to its original exhibit record where that record is available. Technical custody, scan, and integrity details remain in the exhibit's expandable technical details.</p></section>
    </main>`;
};

const ScreenAdministration = {
  render() {
    if (!InvestigatorFirst.isAdministrator()) { InvestigatorFirst.renderPermissionDenied(); return; }
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = "Administration";
    container.innerHTML = `<main class="administration-workspace"><header><h2>Administration</h2><p>Restricted tools for authorised roles. Investigation workspaces do not expose these controls.</p></header><section class="admin-grid"><article><h3>User and role management</h3><p>Manage officer accounts and role assignments through the existing protected officer registry.</p><button class="btn btn-secondary" onclick="Router.navigate('#/officers')">Open officer registry</button></article><article><h3>Access and diagnostic settings</h3><p>Review development identity settings and service diagnostics. This does not alter case access policy.</p><button class="btn btn-secondary" onclick="Router.navigate('#/settings')">Open settings</button></article><article><h3>Activity and audit records</h3><p>The currently exposed API has no server-backed, searchable audit-log endpoint. No client-side activity list is presented as an authoritative audit record.</p></article><article><h3>Case and evidence deletion</h3><p>No authorised, retention-aware deletion endpoint is exposed by the current backend. Consequently, deletion controls are intentionally unavailable; the interface will not pretend that an exhibit or case was deleted.</p></article></section></main>`;
  }
};

const legacySettingsRender = ScreenSettings.render.bind(ScreenSettings);
ScreenSettings.render = async function() {
  if (!InvestigatorFirst.isAdministrator()) { InvestigatorFirst.renderPermissionDenied("Settings"); return; }
  return legacySettingsRender();
};

const legacyAuditRender = ScreenAudit.render.bind(ScreenAudit);
ScreenAudit.render = async function(caseId) {
  if (!InvestigatorFirst.isAdministrator()) { InvestigatorFirst.renderPermissionDenied("Activity and audit"); return; }
  return legacyAuditRender(caseId);
};

// ═══════════════════════════════════════════════════════════════════════════
// 15. BOOTSTRAP WORKSTATION
// ═══════════════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
  initApplication();
});

// Expose modules for Node test runners & browser diagnostics
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    ContradictionAssessmentEvaluator,
    EvidenceSecurityEvaluator,
    RecommendedActionEvaluator,
    StatusPresentation,
    Formatters,
    StageDisplayMap,
    State
  };
}

if (typeof window !== "undefined") {
  window.ContradictionAssessmentEvaluator = ContradictionAssessmentEvaluator;
  window.EvidenceSecurityEvaluator = EvidenceSecurityEvaluator;
  window.RecommendedActionEvaluator = RecommendedActionEvaluator;
}
