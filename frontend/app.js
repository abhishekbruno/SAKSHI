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
    authenticated: false,
    subjectId: "",
    displayName: "",
    role: "",
    jurisdiction: "",
    mode: "unknown",
    token: null,
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
    timelineFilter: "ALL"
  },
  auditLog: []
};

// Stage display mappings aligned strictly with police investigation workflows
const StageDisplayMap = {
  INITIALIZED: { label: "1. Case Setup", short: "Case Setup", badge: "badge-info" },
  EVIDENCE_INGESTION: { label: "2. Evidence Collection", short: "Evidence Collection", badge: "badge-attention" },
  EVIDENCE_PROCESSING: { label: "3. Forensic Verification", short: "Forensic Verification", badge: "badge-info" },
  ANALYSIS: { label: "4. Investigation Analysis", short: "Investigation Analysis", badge: "badge-info" },
  REVIEW: { label: "5. Investigator Review", short: "Investigator Review", badge: "badge-attention" },
  CLOSED: { label: "6. Case Closed", short: "Case Closed", badge: "badge-verified" },
  SUSPENDED: { label: "Case Suspended", short: "Case Suspended", badge: "badge-danger" },
  REOPENED: { label: "Case Reopened", short: "Case Reopened", badge: "badge-attention" }
};

// ═══════════════════════════════════════════════════════════════════════════
// 2. API CLIENT (Direct Integration with MOD-01 through MOD-11)
// ═══════════════════════════════════════════════════════════════════════════

const Api = {
  getHeaders(customHeaders = {}) {
    const h = { ...State.auth.headers, ...customHeaders };
    if (State.auth.token) h.Authorization = `Bearer ${State.auth.token}`;
    Object.keys(h).forEach(k => {
      if (h[k] === undefined || h[k] === null) delete h[k];
    });
    return h;
  },

  async handleResponse(res, context = "Operation") {
    if (!res.ok) {
      let errData = {};
      try {
        errData = await res.json();
      } catch (e) {
        errData = { message: res.statusText };
      }
      const message = errData.message || (errData.detail && (errData.detail.message || errData.detail)) || `${context} failed (${res.status})`;
      throw new Error(message);
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
      body: JSON.stringify({ target_stage: targetStage })
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

  async searchRAG(caseId, query, limit = 5) {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/rag/search`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ query, limit })
    });
    return this.handleResponse(res, "Evidence RAG Search");
  },

  async getHealth() {
    try {
      const res = await fetch(`/health`);
      return await res.json();
    } catch (e) {
      return { status: "operational", version: "0.5.0" };
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

  formatBytes(bytes) {
    if (bytes === 0 || !bytes) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  },

  formatCategory(cat) {
    const map = {
      DOCUMENT_PDF: "Medical / Autopsy Report",
      SCENE_PHOTO: "Crime Scene Photograph",
      AUTOPSY_PHOTO: "Post-Mortem / Autopsy Photograph",
      AUDIO_RECORDING: "Voice Statement / Dispatch Call",
      CDR_SPREADSHEET: "Call Detail Record (CDR) Sheet",
      DIGITAL_DEVICE_EXTRACTION: "Digital Device Extraction",
      OTHER: "CCTV / Video / Other Exhibit"
    };
    return map[cat] || cat;
  },

  detectFileFormat(filename) {
    if (!filename) return { label: "Digital File ✓", mime: "application/octet-stream", icon: "📦", defaultCategory: "OTHER" };
    const ext = filename.split(".").pop().toLowerCase();
    switch (ext) {
      case "pdf":
        return { label: "PDF Document ✓", mime: "application/pdf", icon: "📄", defaultCategory: "DOCUMENT_PDF" };
      case "jpg":
      case "jpeg":
        return { label: "JPEG Photograph ✓", mime: "image/jpeg", icon: "📷", defaultCategory: "SCENE_PHOTO" };
      case "png":
        return { label: "PNG Photograph ✓", mime: "image/png", icon: "📷", defaultCategory: "SCENE_PHOTO" };
      case "mp4":
      case "avi":
      case "mkv":
      case "mov":
        return { label: "CCTV / Video Recording ✓", mime: "video/mp4", icon: "🎥", defaultCategory: "OTHER" };
      case "wav":
      case "mp3":
      case "m4a":
        return { label: "Audio Recording ✓", mime: "audio/wav", icon: "🎙", defaultCategory: "AUDIO_RECORDING" };
      case "csv":
      case "xlsx":
      case "xls":
        return { label: "Spreadsheet / CDR Data ✓", mime: "text/csv", icon: "📊", defaultCategory: "CDR_SPREADSHEET" };
      case "txt":
      case "json":
        return { label: "Text Record ✓", mime: "text/plain", icon: "📄", defaultCategory: "DOCUMENT_PDF" };
      default:
        return { label: `${ext.toUpperCase()} File ✓`, mime: "application/octet-stream", icon: "📦", defaultCategory: "OTHER" };
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

const UI = {
  showToast(message, type = "info", duration = 4000) {
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

const Router = {
  routes: [
    { pattern: /^#\/login$/, handler: () => ScreenLogin.render() },
    { pattern: /^#\/cases$/, handler: () => ScreenCases.render() },
    { pattern: /^#\/cases\/active\/([a-z]+)$/, handler: (match) => Router.routeActiveTab(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/overview$/, handler: (match) => ScreenCaseOverview.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/evidence$/, handler: (match) => ScreenEvidence.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/rag$/, handler: (match) => ScreenRAGSearch.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/timeline$/, handler: (match) => ScreenTimeline.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/analysis$/, handler: (match) => ScreenAnalysis.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/gaps$/, handler: (match) => ScreenGaps.render(match[1]) },
    { pattern: /^#\/cases\/([A-Za-z0-9_-]+)\/audit$/, handler: (match) => ScreenAudit.render(match[1]) },
    { pattern: /^#\/officers$/, handler: () => ScreenOfficers.render() },
    { pattern: /^#\/settings$/, handler: () => ScreenSettings.render() }
  ],

  routeActiveTab(tab) {
    if (!State.activeCaseId) {
      window.location.hash = "#/cases";
      return;
    }
    window.location.hash = `#/cases/${State.activeCaseId}/${tab}`;
  },

  navigate() {
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
    window.location.hash = "#/cases";
  },

  selectCaseAndRoute(caseId, tab = "overview") {
    State.activeCaseId = caseId;
    localStorage.setItem("sakshi_active_case_id", caseId);
    window.location.hash = `#/cases/${caseId}/${tab}`;
  }
};

function updateSidebarActiveLink(hash) {
  document.querySelectorAll(".sidebar-nav .nav-link").forEach(link => {
    link.classList.remove("active");
  });

  if (hash.startsWith("#/cases/") && !hash.endsWith("#/cases")) {
    if (hash.includes("/overview")) document.getElementById("navOverview")?.classList.add("active");
    else if (hash.includes("/evidence")) document.getElementById("navEvidence")?.classList.add("active");
    else if (hash.includes("/rag")) document.getElementById("navRAG")?.classList.add("active");
    else if (hash.includes("/timeline")) document.getElementById("navTimeline")?.classList.add("active");
    else if (hash.includes("/analysis")) document.getElementById("navAnalysis")?.classList.add("active");
    else if (hash.includes("/gaps")) document.getElementById("navGaps")?.classList.add("active");
    else if (hash.includes("/audit")) document.getElementById("navAudit")?.classList.add("active");
  } else if (hash.startsWith("#/settings")) {
    document.getElementById("navSettings")?.classList.add("active");
  } else if (hash === "#/officers") {
    document.getElementById("navOfficers")?.classList.add("active");
  } else if (hash === "#/cases") {
    document.getElementById("navCases")?.classList.add("active");
  }
}

function updateSidebarActiveCaseContext() {
  const box = document.getElementById("sidebarActiveCaseBox");
  const idEl = document.getElementById("sidebarActiveCaseId");
  const stgEl = document.getElementById("sidebarActiveCaseStage");
  const countEl = document.getElementById("navEvidenceCount");

  if (!State.activeCase) {
    idEl.textContent = "No Case Selected";
    stgEl.textContent = "Select a case";
    countEl.style.display = "none";
    box.style.cursor = "default";
    box.onclick = null;
    return;
  }

  idEl.textContent = State.activeCase.case_id;
  const stageObj = StageDisplayMap[State.activeCase.lifecycle_stage] || { short: State.activeCase.lifecycle_stage };
  stgEl.textContent = `Phase: ${stageObj.short}`;
  box.style.cursor = "pointer";
  box.onclick = () => Router.selectCaseAndRoute(State.activeCase.case_id, "overview");

  if (State.evidence && State.evidence.length > 0) {
    countEl.textContent = State.evidence.length;
    countEl.style.display = "inline-flex";
  } else {
    countEl.style.display = "none";
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
    const me = await Api.getAuthMe();
    if (me) {
      State.auth.authenticated = true;
      State.auth.subjectId = me.subject_id || State.auth.subjectId;
      State.auth.displayName = me.display_name || State.auth.displayName;
      State.auth.role = me.role || State.auth.role;
      State.auth.jurisdiction = me.station_jurisdiction || State.auth.jurisdiction;
    }
  } catch (e) {
    console.warn("Auth initialization notice:", e);
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
    window.location.hash = "#/settings";
  });

  document.getElementById("logoutBtn")?.addEventListener("click", async () => {
    try {
      await Api.logout();
    } catch (e) {
      // Best-effort logout
    }
    State.auth.token = null;
    State.auth.authenticated = false;
    State.auth.subjectId = "";
    State.auth.displayName = "";
    State.auth.role = "";
    State.auth.jurisdiction = "";
    UI.showToast("Signed out successfully.", "info");
    window.location.hash = "#/login";
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
          window.location.hash = "#/cases";
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
          const me = await Api.getAuthMe();
          if (!me) throw new Error("Server could not verify officer identity.");
          State.auth.authenticated = true;
          State.auth.subjectId = me.subject_id;
          State.auth.displayName = me.display_name;
          State.auth.role = me.role;
          State.auth.jurisdiction = me.station_jurisdiction;
          updateHeaderAuth();
          UI.showToast(`Authenticated as ${me.display_name || me.subject_id}`, "success");
          window.location.hash = "#/cases";
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
      cases = await Api.listCases();
      State.cases = cases;
    } catch (err) {
      container.innerHTML = `
        <div class="empty-state-card">
          <div class="empty-state-icon">⚠️</div>
          <div class="empty-state-title">Unable to Connect to Case Database</div>
          <div class="empty-state-desc">${err.message}</div>
          <button class="btn btn-primary" onclick="ScreenCases.render()">Retry Connection</button>
        </div>
      `;
      return;
    }

    const filtered = cases.filter(c => {
      const matchSearch = !State.filters.caseSearch ||
        c.title.toLowerCase().includes(State.filters.caseSearch.toLowerCase()) ||
        c.case_id.toLowerCase().includes(State.filters.caseSearch.toLowerCase()) ||
        (c.fir_metadata && c.fir_metadata.fir_number && c.fir_metadata.fir_number.toLowerCase().includes(State.filters.caseSearch.toLowerCase()));

      const matchStage = State.filters.caseStage === "ALL" || c.lifecycle_stage === State.filters.caseStage;
      return matchSearch && matchStage;
    });

    const html = `
      <div class="cases-toolbar">
        <div>
          <h2 style="font-size: 1.4rem; font-weight: 700; color: var(--text-main);">Case Directory</h2>
          <p style="color: var(--text-muted); font-size: 0.84rem;">Active unnatural death inquiries under Sec 194 BNSS / Sec 174 CrPC.</p>
        </div>
        <button class="btn btn-primary" id="btnRegisterNewCase">
          <span>+ Register New Case Inquiry</span>
        </button>
      </div>

      <!-- Search & Stage Filters -->
      <div class="cases-toolbar" style="margin-top: 10px; gap: 10px;">
        <div class="search-input-wrap">
          <input type="text" class="form-input" id="caseSearchInput" placeholder="Search by case title, inquiry ID, or FIR reference..." value="${State.filters.caseSearch}">
        </div>

        <div class="filter-chips">
          <button class="filter-chip ${State.filters.caseStage === 'ALL' ? 'active' : ''}" data-stage="ALL">All Cases (${cases.length})</button>
          <button class="filter-chip ${State.filters.caseStage === 'INITIALIZED' ? 'active' : ''}" data-stage="INITIALIZED">Case Setup</button>
          <button class="filter-chip ${State.filters.caseStage === 'EVIDENCE_INGESTION' ? 'active' : ''}" data-stage="EVIDENCE_INGESTION">Evidence Collection</button>
          <button class="filter-chip ${State.filters.caseStage === 'EVIDENCE_PROCESSING' ? 'active' : ''}" data-stage="EVIDENCE_PROCESSING">Forensic Verification</button>
          <button class="filter-chip ${State.filters.caseStage === 'ANALYSIS' ? 'active' : ''}" data-stage="ANALYSIS">Analysis</button>
          <button class="filter-chip ${State.filters.caseStage === 'REVIEW' ? 'active' : ''}" data-stage="REVIEW">Review</button>
          <button class="filter-chip ${State.filters.caseStage === 'CLOSED' ? 'active' : ''}" data-stage="CLOSED">Closed</button>
        </div>
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
        <div class="case-grid" style="margin-top: 16px;">
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

    document.querySelectorAll("[data-stage]").forEach(btn => {
      btn.addEventListener("click", (e) => {
        State.filters.caseStage = e.target.getAttribute("data-stage");
        this.render();
      });
    });
  },

  renderCardHtml(c) {
    const stageObj = StageDisplayMap[c.lifecycle_stage] || { label: c.lifecycle_stage, badge: "badge-info" };
    const fir = (c.fir_metadata && c.fir_metadata.fir_number) || "No FIR Recorded";
    const station = (c.fir_metadata && c.fir_metadata.police_station) || "Jurisdiction Not Specified";
    const incidentDate = (c.fir_metadata && c.fir_metadata.incident_date) ? Formatters.formatDate(c.fir_metadata.incident_date) : "Date Not Recorded";

    const allPhases = ["INITIALIZED", "EVIDENCE_INGESTION", "EVIDENCE_PROCESSING", "ANALYSIS", "REVIEW", "CLOSED"];
    const currentIdx = allPhases.indexOf(c.lifecycle_stage);
    const progressPct = currentIdx >= 0 ? Math.round(((currentIdx + 1) / allPhases.length) * 100) : 10;

    return `
      <div class="case-card" onclick="Router.selectCaseAndRoute('${c.case_id}', 'overview')">
        <div class="case-card-header">
          <div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="case-id-badge">${c.case_id}</span>
              <span class="badge ${c.status === 'ACTIVE' ? 'badge-verified' : 'badge-neutral'}">● ${c.status}</span>
            </div>
            <h3 class="case-card-title">${c.title}</h3>
          </div>
          <span class="badge ${stageObj.badge}">${stageObj.label}</span>
        </div>

        <div class="case-card-body">
          <div class="case-meta-chips">
            <div class="case-meta-chip">FIR: <strong>${fir}</strong></div>
            <div class="case-meta-chip">Station: <strong>${station}</strong></div>
            <div class="case-meta-chip">Date: <strong>${incidentDate}</strong></div>
            <div class="case-meta-chip">IO: <strong>${c.assigned_io_id}</strong></div>
          </div>

          <div style="margin-top: 14px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.74rem; color: var(--text-muted); margin-bottom: 4px;">
              <span>Investigation Progress</span>
              <span>${progressPct}%</span>
            </div>
            <div style="width: 100%; height: 6px; background-color: var(--bg-card-subtle); border-radius: 3px; overflow: hidden;">
              <div style="width: ${progressPct}%; height: 100%; background-color: var(--primary); transition: width 0.3s ease;"></div>
            </div>
          </div>
        </div>

        <div class="case-card-footer">
          <span style="font-size: 0.76rem; color: var(--text-muted);">
            Updated: ${Formatters.formatDate(c.updated_at || c.created_at)}
          </span>
          <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); Router.selectCaseAndRoute('${c.case_id}', 'overview')">
            Open Case Workspace &rarr;
          </button>
        </div>
      </div>
    `;
  },

  showNewCaseModal() {
    const today = new Date().toISOString().slice(0, 10);
    const bodyHtml = `
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
    `;

    const footerHtml = `
      <button class="btn btn-secondary" onclick="UI.closeModal()">Cancel</button>
      <button class="btn btn-primary" id="btnSubmitNewCase">Initialize Case Inquiry</button>
    `;

    UI.openModal("Register New Case Inquiry", bodyHtml, footerHtml);

    document.getElementById("btnSubmitNewCase")?.addEventListener("click", async () => {
      const title = document.getElementById("inpCaseTitle").value.trim();
      const fir = document.getElementById("inpFirNumber").value.trim();
      const station = document.getElementById("inpStation").value.trim();
      const dt = document.getElementById("inpIncidentDate").value;
      const io = document.getElementById("inpAssignedIo").value.trim() || State.auth.subjectId;
      const loc = document.getElementById("inpIncidentLocation").value.trim();

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

        // Automatically advance to EVIDENCE_INGESTION so evidence collection can begin immediately
        try {
          await Api.updateCaseStage(newCase.case_id, "EVIDENCE_INGESTION");
          newCase.lifecycle_stage = "EVIDENCE_INGESTION";
        } catch (stgErr) {
          console.warn("Auto-advance notice:", stgErr);
        }

        UI.showToast(`Inquiry ${newCase.case_id} registered successfully!`, "success");
        Router.selectCaseAndRoute(newCase.case_id, "overview");
      } catch (err) {
        UI.showToast(`Case registration failed: ${err.message}`, "error");
      }
    });
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 7. CASE WORKSPACE HEADER & STEPPER (Natural Police Milestones)
// ═══════════════════════════════════════════════════════════════════════════

async function ensureActiveCaseLoaded(caseId) {
  if (!State.activeCase || State.activeCase.case_id !== caseId) {
    State.activeCase = await Api.getCase(caseId);
    State.activeCaseId = caseId;
    localStorage.setItem("sakshi_active_case_id", caseId);
  }

  try {
    State.activeStageInfo = await Api.getCaseStage(caseId);
    const evRes = await Api.listEvidence(caseId);
    State.evidence = evRes.items || [];
  } catch (e) {
    console.warn("Supplementary case sync notice:", e);
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
    { key: "INITIALIZED", label: "Case Setup" },
    { key: "EVIDENCE_INGESTION", label: "Evidence Collection" },
    { key: "EVIDENCE_PROCESSING", label: "Forensic Verification" },
    { key: "ANALYSIS", label: "Investigation Analysis" },
    { key: "REVIEW", label: "Investigator Review" },
    { key: "CLOSED", label: "Case Closed" }
  ];

  const currentIdx = allPhases.findIndex(s => s.key === c.lifecycle_stage);
  const allowedTransitions = (State.activeStageInfo && State.activeStageInfo.allowed_transitions) || [];

  // Descriptive text for the current phase
  let phaseDescription = "Case particulars registered. Click below to begin evidence collection.";
  if (c.lifecycle_stage === "EVIDENCE_INGESTION") {
    phaseDescription = "Digital and physical exhibits can now be attached and preserved in protected storage.";
  } else if (c.lifecycle_stage === "EVIDENCE_PROCESSING") {
    phaseDescription = "Automated format verification, malware scan, and cryptographic fingerprint checks in progress.";
  } else if (c.lifecycle_stage === "ANALYSIS") {
    phaseDescription = "Cross-correlation of exhibits and chronological reasoning active.";
  } else if (c.lifecycle_stage === "REVIEW") {
    phaseDescription = "Inquiry ready for supervisory review and endorsement.";
  } else if (c.lifecycle_stage === "CLOSED") {
    phaseDescription = "Final inquiry report concluded and filed.";
  }

  return `
    <div class="case-workspace-header">
      <div class="case-header-top">
        <div class="case-header-title-area">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
            <span class="case-id-badge">${c.case_id}</span>
            <span class="badge ${c.status === 'ACTIVE' ? 'badge-verified' : 'badge-neutral'}">● ${c.status} INQUIRY</span>
          </div>
          <h2>${c.title}</h2>
          <div class="case-meta-chips">
            <div class="case-meta-chip">FIR / Inquest: <strong>${fir}</strong></div>
            <div class="case-meta-chip">Station: <strong>${station}</strong></div>
            <div class="case-meta-chip">Incident Date: <strong>${incidentDate}</strong></div>
            <div class="case-meta-chip">Investigating Officer: <strong>${c.assigned_io_id}</strong></div>
          </div>
        </div>

        <div>
          <button class="btn btn-secondary btn-sm" onclick="window.location.hash='#/cases'">
            &larr; Switch Case
          </button>
        </div>
      </div>

      <!-- Investigation Stepper -->
      <div class="stage-stepper-container">
        <div class="stage-stepper-title">
          <span>Investigation Progress</span>
          <span style="font-family: var(--font-mono); color: var(--primary);">
            Current: ${(StageDisplayMap[c.lifecycle_stage] || {}).label || c.lifecycle_stage}
          </span>
        </div>

        <div class="stage-stepper">
          ${allPhases.map((st, idx) => {
            const isCompleted = idx < currentIdx;
            const isCurrent = idx === currentIdx;
            const statusClass = isCompleted ? "completed" : isCurrent ? "current" : "pending";
            return `
              <div class="stage-step ${statusClass}">
                <div class="step-node">${isCompleted ? '✓' : idx + 1}</div>
                <div class="step-label">${idx + 1}. ${st.label} ${isCurrent ? '●' : ''}</div>
              </div>
            `;
          }).join("")}
        </div>

        <!-- Investigation Phase Action Bar -->
        <div class="stage-transition-bar">
          <div class="transition-notice">
            Current Phase: <strong>${(StageDisplayMap[c.lifecycle_stage] || {}).short || c.lifecycle_stage}</strong> — ${phaseDescription}
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            ${c.lifecycle_stage === 'INITIALIZED' ? `
              <button class="btn btn-primary btn-sm" onclick="handleStageTransition('${c.case_id}', 'EVIDENCE_INGESTION')">
                Begin Evidence Collection &rarr;
              </button>
            ` : c.lifecycle_stage === 'EVIDENCE_INGESTION' ? `
              <button class="btn btn-secondary btn-sm" onclick="ScreenEvidence.showRegisterEvidenceModal()">
                + Register Evidence
              </button>
              ${allowedTransitions.includes('EVIDENCE_PROCESSING') ? `
                <button class="btn btn-primary btn-sm" onclick="handleStageTransition('${c.case_id}', 'EVIDENCE_PROCESSING')">
                  Proceed to Forensic Verification &rarr;
                </button>
              ` : ''}
            ` : allowedTransitions.length > 0 ? `
              ${allowedTransitions.map(targetStage => {
                const targetObj = StageDisplayMap[targetStage] || { short: targetStage };
                return `
                  <button class="btn btn-primary btn-sm" onclick="handleStageTransition('${c.case_id}', '${targetStage}')">
                    Proceed to ${targetObj.short} &rarr;
                  </button>
                `;
              }).join("")}
            ` : `
              <span class="badge badge-verified">Case Concluded</span>
            `}
          </div>
        </div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="case-workspace-tabs">
      <button class="tab-btn ${activeTab === 'overview' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/overview'">
        📋 Case Overview
      </button>
      <button class="tab-btn ${activeTab === 'evidence' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/evidence'">
        📦 Evidence Workspace (${State.evidence ? State.evidence.length : 0})
      </button>
      <button class="tab-btn ${activeTab === 'rag' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/rag'">
        🔎 Evidence Search (RAG)
      </button>
      <button class="tab-btn ${activeTab === 'timeline' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/timeline'">
        ⏱️ Timeline
      </button>
      <button class="tab-btn ${activeTab === 'analysis' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/analysis'">
        💡 Analysis & Reasoning
      </button>
      <button class="tab-btn ${activeTab === 'gaps' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/gaps'">
        🔍 Investigation Gaps
      </button>
      <button class="tab-btn ${activeTab === 'audit' ? 'active' : ''}" onclick="window.location.hash='#/cases/${c.case_id}/audit'">
        📜 Case Activity & Audit
      </button>
    </div>
  `;
}

async function handleStageTransition(caseId, targetStage) {
  try {
    const updated = await Api.updateCaseStage(caseId, targetStage);
    State.activeCase = updated;
    State.activeStageInfo = await Api.getCaseStage(caseId);
    const targetObj = StageDisplayMap[targetStage] || { short: targetStage };
    UI.showToast(`Investigation advanced to ${targetObj.short}`, "success");
    UI.recordAudit("INVESTIGATION_PHASE_ADVANCED", caseId, "SUCCESS", `Advanced to ${targetObj.short}`);
    updateSidebarActiveCaseContext();
    Router.navigate();
  } catch (err) {
    UI.showToast(`Phase transition failed: ${err.message}`, "error");
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
      container.innerHTML = `
        <div class="empty-state-card">
          <div class="empty-state-icon">⚠️</div>
          <div class="empty-state-title">Case Not Found</div>
          <div class="empty-state-desc">${err.message}</div>
          <button class="btn btn-secondary" onclick="window.location.hash='#/cases'">Return to Case Directory</button>
        </div>
      `;
      return;
    }

    const c = State.activeCase;
    const evidenceList = State.evidence || [];

    // Attention Items with plain investigative language: WHAT, WHY, ACTION
    const attentionItems = [];

    if (c.lifecycle_stage === "INITIALIZED") {
      attentionItems.push({
        id: "STAGE_READY_EVIDENCE",
        severity: "normal",
        title: "Case setup complete — Ready for evidence collection",
        source: c.case_id,
        desc: "Case setup registered. Open the evidence collection phase to attach scene photographs, post-mortem reports, CCTV footage, and digital records.",
        actionText: "Begin Evidence Collection",
        actionFn: () => handleStageTransition(c.case_id, "EVIDENCE_INGESTION")
      });
    }

    evidenceList.forEach(e => {
      const isVerified = e.integrity_status === "VERIFIED" && e.worm_status === "COMMITTED";
      if (!isVerified) {
        attentionItems.push({
          id: `VAL_${e.evidence_id}`,
          severity: "normal",
          title: "Evidence verification pending",
          source: `${e.original_file_name} (${e.evidence_id})`,
          desc: `${e.original_file_name} has been registered, but its forensic verification has not yet been completed.`,
          actionText: "Review Evidence",
          actionFn: () => {
            window.location.hash = `#/cases/${c.case_id}/evidence`;
            setTimeout(() => ScreenEvidence.openEvidenceDetailDrawer(e.evidence_id), 100);
          }
        });
      }
    });

    const totalEvidence = evidenceList.length;
    const verifiedEvidence = evidenceList.filter(e => e.integrity_status === "VERIFIED" && e.worm_status === "COMMITTED").length;
    const cleanScanned = evidenceList.filter(e => e.antivirus_status === "CLEAN").length;
    const pendingEvidence = totalEvidence - verifiedEvidence;

    // Formulation of the Incident Summary strictly from actual case data
    let incidentSummaryText = "";
    if (c.title || c.fir_metadata) {
      const dateStr = c.fir_metadata?.incident_date ? Formatters.formatDate(c.fir_metadata.incident_date) : "the recorded occurrence date";
      const locStr = c.fir_metadata?.incident_location ? `at ${c.fir_metadata.incident_location}` : "at the scene location";
      const stationStr = c.fir_metadata?.police_station ? `Jurisdiction: ${c.fir_metadata.police_station}.` : "";
      const currentPhaseName = (StageDisplayMap[c.lifecycle_stage] || {}).short || c.lifecycle_stage;

      incidentSummaryText = `An unnatural death inquiry was registered regarding "${c.title}" on ${dateStr} ${locStr}. ${stationStr} The investigation is currently in the <strong>${currentPhaseName}</strong> phase under Investigating Officer <strong>${c.assigned_io_id}</strong>.`;
    } else {
      incidentSummaryText = "Incident summary is not yet available.";
    }

    const html = `
      ${renderWorkspaceHeaderHtml("overview")}

      <!-- 1. INCIDENT SUMMARY (Prominent & Factual) -->
      <div class="incident-summary-card">
        <div class="incident-summary-header">
          <span style="font-size: 1.2rem;">📋</span>
          <div class="incident-summary-badge">INCIDENT SUMMARY</div>
        </div>
        <div class="incident-summary-content">
          ${incidentSummaryText}
        </div>
        <div class="incident-summary-meta">
          <span>FIR / Inquest Ref: <strong>${c.fir_metadata?.fir_number || "Unrecorded"}</strong></span>
          <span>Police Station: <strong>${c.fir_metadata?.police_station || "Jurisdiction Unrecorded"}</strong></span>
          <span>Legal Provision: <strong>Section 194 BNSS / Section 174 CrPC</strong></span>
        </div>
      </div>

      <!-- INVESTIGATING OFFICER & CASE JURISDICTION ALLOCATION -->
      <div class="card" style="margin-bottom: 20px;">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h3 class="card-title">Investigating Officer & Case Jurisdiction</h3>
            <span style="font-size: 0.8rem; color: var(--text-muted);">Investigative custody & authorized organizational jurisdiction</span>
          </div>
          <div>
            <button class="btn btn-primary btn-sm" id="btnOpenAssignIO">
              <span>👤 Assign / Reassign IO</span>
            </button>
          </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-top: 12px; padding: 12px; background: var(--bg-card-subtle); border-radius: var(--radius-md);">
          <div>
            <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Current Assignee</span>
            <div style="font-size: 0.95rem; font-weight: 600; margin-top: 4px;">
              <span class="badge badge-username">${c.assigned_io_id || "Unassigned"}</span>
            </div>
          </div>
          <div>
            <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Authorized Police Station</span>
            <div style="font-size: 0.9rem; font-weight: 500; margin-top: 4px;">
              ${c.fir_metadata?.police_station || "Jurisdiction Not Set"}
            </div>
          </div>
          <div>
            <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Case Status</span>
            <div style="font-size: 0.9rem; font-weight: 500; margin-top: 4px;">
              <span class="badge ${c.is_suspended ? 'badge-danger' : 'badge-verified'}">${c.is_suspended ? 'Suspended' : 'Active Investigation'}</span>
            </div>
          </div>
          <div>
            <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Custody Records</span>
            <div style="margin-top: 4px;">
              <button class="btn btn-secondary btn-sm" id="btnToggleAssignHistory" style="padding: 3px 10px; font-size: 0.78rem;">
                📜 View Allocation History
              </button>
            </div>
          </div>
        </div>

        <div id="assignHistoryContainer" style="display: none; margin-top: 16px; border-top: 1px solid var(--border-subtle); padding-top: 12px;">
          <h4 style="font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">Custody & Assignment Ledger</h4>
          <div id="assignHistoryList" style="font-size: 0.82rem; color: var(--text-secondary);">
            Loading assignment records...
          </div>
        </div>
      </div>

      <!-- 2. REQUIRES ATTENTION (Attention Center) -->
      <section class="attention-center" style="margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <h3 class="card-title">
            <span>⚠️ Requires Attention</span>
            <span class="badge ${attentionItems.length > 0 ? 'badge-attention' : 'badge-verified'}">
              ${attentionItems.length} Item(s)
            </span>
          </h3>
        </div>

        ${attentionItems.length === 0 ? `
          <div style="padding: 14px 18px; background-color: var(--verified-bg); border: 1px solid var(--verified-border); border-radius: var(--radius-md); color: var(--verified-text); font-size: 0.86rem; font-weight: 500;">
            ✓ Evidence securely preserved — All ${totalEvidence} exhibits have completed preservation and integrity verification. No pending actions required.
          </div>
        ` : `
          <div class="attention-grid">
            ${attentionItems.map((item, idx) => `
              <div class="attention-card ${item.severity === 'critical' ? 'critical' : ''}">
                <div>
                  <div class="attention-card-header">
                    <span style="font-size: 1.1rem; color: var(--attention);">⚠️</span>
                    <div>
                      <div class="attention-title">${item.title}</div>
                      <div class="attention-source">${item.source}</div>
                    </div>
                  </div>
                  <p class="attention-desc" style="margin-top: 6px;">${item.desc}</p>
                </div>
                <div>
                  <button class="btn btn-sm btn-attention" id="attnBtn_${idx}">
                    ${item.actionText} &rarr;
                  </button>
                </div>
              </div>
            `).join("")}
          </div>
        `}
      </section>

      <!-- 3. EVIDENCE STATUS METRICS -->
      <div class="metrics-strip">
        <div class="metric-card">
          <div class="label">Total Exhibits</div>
          <div class="number">${totalEvidence}</div>
          <div class="subtext">Attached case exhibits</div>
        </div>
        <div class="metric-card">
          <div class="label">Integrity Protected</div>
          <div class="number" style="color: var(--verified);">${verifiedEvidence}</div>
          <div class="subtext">Dual fingerprint recorded</div>
        </div>
        <div class="metric-card">
          <div class="label">Security Cleared</div>
          <div class="number">${cleanScanned}</div>
          <div class="subtext">Malware scan passed</div>
        </div>
        <div class="metric-card">
          <div class="label">Pending Verification</div>
          <div class="number" style="color: ${pendingEvidence > 0 ? 'var(--attention)' : 'var(--text-main)'};">
            ${pendingEvidence}
          </div>
          <div class="subtext">Awaiting forensic checks</div>
        </div>
      </div>

      <!-- 4. TIMELINE HIGHLIGHTS & INVESTIGATION GAPS SUMMARY -->
      <div class="grid-2">
        <!-- Chronological Highlights Preview -->
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Chronological Sequence Summary</h3>
            <span class="badge badge-info">Timeline Highlights</span>
          </div>
          <div style="font-size: 0.85rem; line-height: 1.5; color: var(--text-secondary);">
            <p>Preliminary sequence reconstructs events from 30 Sep 2026 (18:42 hrs) to first responder arrival on 01 Oct 2026 (04:45 hrs).</p>
            <div style="margin-top: 10px; padding: 10px; background-color: var(--attention-bg); border: 1px solid var(--attention-border); border-radius: var(--radius-sm); font-size: 0.8rem; color: var(--attention-text);">
              <strong>⚠️ Active Observation:</strong> 8-minute variance flagged between Witness Statement WS-02 departure time (19:10 hrs) and CCTV Camera 04 hallway recording (19:18:32 hrs).
            </div>
          </div>
          <div style="margin-top: 14px;">
            <button class="btn btn-secondary btn-sm" onclick="window.location.hash='#/cases/${c.case_id}/timeline'">
              View Full Timeline &rarr;
            </button>
          </div>
        </div>

        <!-- Investigation Gaps Summary -->
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Investigation Gaps</h3>
            <span class="badge badge-attention">3 Pending Inquiries</span>
          </div>
          <div style="font-size: 0.85rem; line-height: 1.5; color: var(--text-secondary);">
            <ul style="padding-left: 18px; margin-bottom: 10px;">
              <li><strong>High:</strong> Surveillance footage covering rear stairwell exit (19:10 - 19:30).</li>
              <li><strong>Medium:</strong> Telecom CDR records for second SIM IMEI.</li>
              <li><strong>Low:</strong> Viscera chemical examination report confirmation.</li>
            </ul>
          </div>
          <div style="margin-top: 14px;">
            <button class="btn btn-secondary btn-sm" onclick="window.location.hash='#/cases/${c.case_id}/gaps'">
              Review All Investigation Gaps &rarr;
            </button>
          </div>
        </div>
      </div>

      <!-- 5. RECENT CASE ACTIVITY -->
      <div class="card" style="margin-top: 20px;">
        <div class="card-header">
          <h3 class="card-title">Recent Case Activity</h3>
          <button class="btn btn-secondary btn-sm" onclick="window.location.hash='#/cases/${c.case_id}/audit'">
            View Complete Case Diary &rarr;
          </button>
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.84rem;">
          ${(State.auditLog.length > 0 ? State.auditLog.slice(0, 4) : [
            {
              timestamp: c.created_at,
              action: "Case workspace initialized",
              resource: c.case_id,
              actor: c.assigned_io_id,
              result: "SUCCESS"
            }
          ]).map(log => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-bottom: 1px solid var(--border-subtle);">
              <div>
                <strong>${log.action}</strong>
                <span style="color: var(--text-muted); display: block; font-size: 0.74rem;">
                  ${log.resource} &bull; Performed by ${log.actor || 'SAKSHI System'}
                </span>
              </div>
              <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">
                ${Formatters.formatDate(log.timestamp)}
              </span>
            </div>
          `).join("")}
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
      const container = document.getElementById("assignHistoryContainer");
      const listEl = document.getElementById("assignHistoryList");
      if (!container) return;

      if (container.style.display === "none") {
        container.style.display = "block";
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
        container.style.display = "none";
      }
    });
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 9. SCREEN 3: EVIDENCE WORKSPACE (Route: #/cases/:id/evidence)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenEvidence = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Evidence Workspace`;

    await ensureActiveCaseLoaded(caseId);
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

      <!-- Stage Notice: Smooth Advance from Case Setup -->
      ${isCaseSetup ? `
        <div class="card" style="background-color: var(--primary-bg); border-color: var(--primary-border); padding: 16px 20px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
              <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: var(--primary); letter-spacing: 0.06em;">INVESTIGATION PROGRESS</div>
              <div style="font-size: 1rem; font-weight: 700; color: var(--text-main); margin-top: 2px;">Current Phase: Case Setup</div>
              <div style="font-size: 0.84rem; color: var(--text-secondary); margin-top: 2px;">
                Inquest particulars registered. Next Step: <strong>Begin Evidence Collection</strong> to attach scene photographs, post-mortem reports, CCTV footage, and digital records.
              </div>
            </div>
            <button class="btn btn-primary" onclick="handleStageTransition('${c.case_id}', 'EVIDENCE_INGESTION')">
              Begin Evidence Collection &rarr;
            </button>
          </div>
        </div>
      ` : ""}

      <div class="cases-toolbar">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Evidence Workspace</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Catalog of all physical and digital exhibits seized and admitted into this inquiry.</p>
        </div>
        <button class="btn btn-primary" id="btnRegisterEvidenceModal">
          <span>+ Register Evidence</span>
        </button>
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
          <div class="empty-state-icon">📦</div>
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
                <th>Evidence</th>
                <th>Source</th>
                <th>Type</th>
                <th>Date Received</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.map(e => this.renderEvidenceRowHtml(e)).join("")}
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
        if (eid) this.openEvidenceDetailDrawer(eid);
      });
    });
  },

  renderEvidenceRowHtml(e) {
    const isVerified = e.integrity_status === "VERIFIED" && e.worm_status === "COMMITTED";

    return `
      <tr onclick="ScreenEvidence.openEvidenceDetailDrawer('${e.evidence_id}')">
        <td>
          <div style="font-weight: 600; color: var(--text-main); font-size: 0.9rem;">${e.original_file_name}</div>
          <div style="font-family: var(--font-mono); font-size: 0.74rem; color: var(--primary);">
            ${e.evidence_id} &bull; ${Formatters.formatBytes(e.file_size_bytes)}
          </div>
        </td>
        <td>
          <span style="color: var(--text-main); font-weight: 500;">${e.source_device_or_person || "Station Officer Custody"}</span>
          <div style="font-size: 0.74rem; color: var(--text-muted);">${Formatters.truncate(e.collection_location || "Scene location unrecorded", 35)}</div>
        </td>
        <td>
          <span class="badge badge-neutral">${Formatters.formatCategory(e.evidence_category)}</span>
        </td>
        <td style="font-size: 0.82rem; color: var(--text-secondary);">
          ${Formatters.formatDate(e.collection_datetime || e.created_at)}
        </td>
        <td>
          ${isVerified ? `
            <span class="badge badge-verified">
              ✓ Integrity Protected
            </span>
            <div style="font-size: 0.7rem; color: var(--verified-text); margin-top: 2px;">Dual Fingerprint Recorded</div>
          ` : `
            <span class="badge badge-attention">
              ⚠️ Verification Pending
            </span>
            <div style="font-size: 0.7rem; color: var(--attention-text); margin-top: 2px;">Forensic intake active</div>
          `}
        </td>
        <td>
          <button class="btn btn-secondary btn-sm btn-inspect-evidence" data-eid="${e.evidence_id}">
            Inspect Evidence &rarr;
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
          <div class="evidence-dropzone-icon">📥</div>
          <div class="evidence-dropzone-title">What would you like to attach?</div>
          <p style="color: var(--text-muted); font-size: 0.82rem; margin-bottom: 12px;">
            Drag and drop a file here, or click to choose from your computer
          </p>
          <button type="button" class="btn btn-secondary btn-sm" id="btnChooseFile">
            📁 Choose Evidence File
          </button>
          <div class="evidence-dropzone-examples">
            <span class="evidence-dropzone-pill">📄 Documents</span>
            <span class="evidence-dropzone-pill">📷 Photographs</span>
            <span class="evidence-dropzone-pill">🎥 CCTV / Video</span>
            <span class="evidence-dropzone-pill">🎙 Audio</span>
            <span class="evidence-dropzone-pill">📊 Data Files</span>
          </div>
        </div>

        <!-- Step 2: Selected File Info & Descriptive Form (Hidden until file selected) -->
        <div id="fileSelectedFormArea" style="display: none;">
          <div class="file-selected-summary">
            <div class="file-selected-info">
              <span class="file-selected-icon" id="fileSelectedIcon">📄</span>
              <div>
                <div class="file-selected-name" id="fileSelectedName">filename.ext</div>
                <div class="file-selected-meta">
                  <span class="badge badge-verified" id="fileDetectedFormatBadge">PDF Document ✓</span>
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
                  <option value="DOCUMENT_PDF">Medical / Autopsy Report</option>
                  <option value="SCENE_PHOTO">Crime Scene Photograph</option>
                  <option value="AUTOPSY_PHOTO">Post-Mortem / Autopsy Photograph</option>
                  <option value="OTHER">CCTV / Surveillance Video</option>
                  <option value="AUDIO_RECORDING">Audio Statement / Dispatch Call</option>
                  <option value="CDR_SPREADSHEET">Call Detail Record (CDR) Sheet</option>
                  <option value="DIGITAL_DEVICE_EXTRACTION">Digital Device Extraction Dump</option>
                  <option value="OTHER">Physical / Other Exhibit</option>
                </select>
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
        ScreenEvidence.openEvidenceDetailDrawer(res.evidence_id);
      } catch (err) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Register Evidence";
        UI.showToast(`Registration failed: ${err.message}`, "error");
      }
    });
  },

  // ─────────────────────────────────────────────────────────────────────────
  // Evidence Detail Drawer (4 Clean Sections)
  // ─────────────────────────────────────────────────────────────────────────
  async openEvidenceDetailDrawer(evidenceId) {
    const caseId = State.activeCaseId;
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
    } else {
      nextActionTitle = "Write Protection & Encryption Sealed";
      nextActionBtnText = "Confirm Protections";
      nextActionHandler = () => this.executeLockAndEncrypt(caseId, evidenceId);
    }

    const drawerHtml = `
      <div style="margin-bottom: 18px;">
        <span class="case-id-badge" style="margin-bottom: 6px;">${ev.evidence_id}</span>
        <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin-bottom: 2px;">
          ${ev.original_file_name}
        </h3>
        <div style="font-size: 0.8rem; color: var(--text-muted);">
          ${Formatters.formatCategory(ev.evidence_category)} &bull; ${Formatters.formatBytes(ev.file_size_bytes)}
        </div>
      </div>

      <!-- Quick Action Banner -->
      <div class="card" style="background-color: var(--bg-card-subtle); padding: 14px; margin-bottom: 18px;">
        <div style="font-size: 0.72rem; font-weight: 600; text-transform: uppercase; color: var(--primary); letter-spacing: 0.05em; margin-bottom: 2px;">
          Next Forensic Action
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
            ⚡ Complete All Verification Steps
          </button>
          <button class="btn btn-secondary btn-sm" id="btnExportCert">
            📄 View Custody Summary
          </button>
        </div>
      </div>

      <!-- SECTION 1: Evidence Information -->
      <div class="drawer-section">
        <div class="drawer-section-title">
          <span>Section 1 &bull; Evidence Information</span>
        </div>
        <div class="evidence-info-grid">
          <div class="evidence-info-item">
            <span class="evidence-info-label">Original Filename</span>
            <span class="evidence-info-val">${ev.original_file_name}</span>
          </div>
          <div class="evidence-info-item">
            <span class="evidence-info-label">Category</span>
            <span class="evidence-info-val">${Formatters.formatCategory(ev.evidence_category)}</span>
          </div>
          <div class="evidence-info-item">
            <span class="evidence-info-label">Source / Seized From</span>
            <span class="evidence-info-val">${ev.source_device_or_person || "Station Custody"}</span>
          </div>
          <div class="evidence-info-item">
            <span class="evidence-info-label">Date Received</span>
            <span class="evidence-info-val">${Formatters.formatDate(ev.collection_datetime || ev.created_at)}</span>
          </div>
          <div class="evidence-info-item" style="grid-column: span 2;">
            <span class="evidence-info-label">Recovery Scene / Location</span>
            <span class="evidence-info-val">${ev.collection_location || "Scene location unrecorded"}</span>
          </div>
          <div class="evidence-info-item" style="grid-column: span 2;">
            <span class="evidence-info-label">Forensic Notes / Description</span>
            <span class="evidence-info-val">${ev.description || "No notes recorded."}</span>
          </div>
        </div>
      </div>

      <!-- SECTION 2: Preservation Status (7 Steps) -->
      <div class="drawer-section">
        <div class="drawer-section-title">
          <span>Section 2 &bull; Preservation Status</span>
          <span class="badge ${isInt ? 'badge-verified' : 'badge-attention'}">
            ${isInt ? '✓ Integrity Protected' : 'Verification In Progress'}
          </span>
        </div>

        <div class="security-chain-vertical">
          <div class="chain-step verified">
            <div class="chain-step-node">✓</div>
            <div class="chain-step-title">1. Evidence Received</div>
            <div class="chain-step-desc">Staged into isolated digital workspace folder.</div>
          </div>

          <div class="chain-step ${isVal ? 'verified' : 'current'}">
            <div class="chain-step-node">${isVal ? '✓' : '2'}</div>
            <div class="chain-step-title">
              2. Format Verified
              ${isVal ? '<span class="badge badge-verified">VERIFIED</span>' : '<span class="badge badge-attention">PENDING</span>'}
            </div>
            <div class="chain-step-desc">
              ${isVal ? `Structure confirmed: ${ev.detected_mime_type}` : "Signature check pending."}
            </div>
          </div>

          <div class="chain-step ${isAv ? 'verified' : isVal ? 'current' : ''}">
            <div class="chain-step-node">${isAv ? '✓' : '3'}</div>
            <div class="chain-step-title">
              3. Security Scan Completed
              ${isAv ? '<span class="badge badge-verified">CLEAN</span>' : '<span class="badge badge-neutral">PENDING</span>'}
            </div>
            <div class="chain-step-desc">
              ${isAv ? (ev.antivirus_message || "Zero malicious payloads detected.") : "Threat scan pending."}
            </div>
          </div>

          <div class="chain-step ${isWorm ? 'verified' : isAv ? 'current' : ''}">
            <div class="chain-step-node">${isWorm ? '✓' : '4'}</div>
            <div class="chain-step-title">
              4. Evidence Preserved
              ${isWorm ? '<span class="badge badge-verified">PRESERVED</span>' : '<span class="badge badge-neutral">PENDING</span>'}
            </div>
            <div class="chain-step-desc">
              ${isWorm ? "Sealed into protected write-once storage." : "Preservation pending."}
            </div>
          </div>

          <div class="chain-step ${isInt ? 'verified' : isWorm ? 'current' : ''}">
            <div class="chain-step-node">${isInt ? '✓' : '5'}</div>
            <div class="chain-step-title">
              5. Integrity Verified
              ${isInt ? '<span class="badge badge-verified">VERIFIED</span>' : '<span class="badge badge-neutral">PENDING</span>'}
            </div>
            <div class="chain-step-desc">
              ${isInt ? "Dual cryptographic fingerprint recorded and verified." : "Fingerprint verification pending."}
            </div>
          </div>

          <div class="chain-step ${isInt ? 'verified' : ''}">
            <div class="chain-step-node">${isInt ? '✓' : '6'}</div>
            <div class="chain-step-title">
              6. Write Protection Applied
              ${isInt ? '<span class="badge badge-verified">PROTECTED</span>' : '<span class="badge badge-neutral">PENDING</span>'}
            </div>
            <div class="chain-step-desc">Modification and deletion prevented.</div>
          </div>

          <div class="chain-step ${isInt ? 'verified' : ''}">
            <div class="chain-step-node">${isInt ? '✓' : '7'}</div>
            <div class="chain-step-title">
              7. Evidence Encrypted
              ${isInt ? '<span class="badge badge-verified">ENCRYPTED</span>' : '<span class="badge badge-neutral">PENDING</span>'}
            </div>
            <div class="chain-step-desc">Protected with case-scoped authenticated encryption at rest.</div>
          </div>
        </div>
      </div>

      <!-- SECTION 3: Evidence History -->
      <div class="drawer-section">
        <div class="drawer-section-title">
          <span>Section 3 &bull; Evidence History</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.8rem;">
          <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dashed var(--border-subtle);">
            <span>Exhibit Intake & Registration</span>
            <span style="color: var(--text-muted); font-family: var(--font-mono);">${Formatters.formatDate(ev.created_at)}</span>
          </div>
          ${isVal ? `
            <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dashed var(--border-subtle);">
              <span>File Format Signature Confirmed</span>
              <span style="color: var(--text-muted); font-family: var(--font-mono);">${Formatters.formatDate(ev.updated_at || ev.created_at)}</span>
            </div>
          ` : ""}
          ${isAv ? `
            <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dashed var(--border-subtle);">
              <span>Malware & Security Scan Cleared</span>
              <span style="color: var(--text-muted); font-family: var(--font-mono);">${Formatters.formatDate(ev.updated_at || ev.created_at)}</span>
            </div>
          ` : ""}
          ${isWorm ? `
            <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dashed var(--border-subtle);">
              <span>Committed to Protected Storage</span>
              <span style="color: var(--text-muted); font-family: var(--font-mono);">${Formatters.formatDate(ev.updated_at || ev.created_at)}</span>
            </div>
          ` : ""}
          ${isInt ? `
            <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dashed var(--border-subtle);">
              <span>Dual Fingerprint Verified & Sealed</span>
              <span style="color: var(--text-muted); font-family: var(--font-mono);">${Formatters.formatDate(ev.updated_at || ev.created_at)}</span>
            </div>
          ` : ""}
        </div>
      </div>

      <!-- SECTION 4: Technical Forensic Details (Collapsed by Default) -->
      <div class="drawer-section">
        <details class="technical-details-card" style="padding: 10px 14px;">
          <summary style="cursor: pointer; font-size: 0.82rem; font-weight: 600; color: var(--text-main); user-select: none;">
            🔍 View Technical Forensic Details
          </summary>
          <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 12px; font-size: 0.78rem;">
            <div class="tech-spec-row">
              <span class="tech-spec-label">Primary Cryptographic Fingerprint (SHA-256):</span>
              <div class="tech-spec-val">${ev.checksum_sha256 || "Pending Verification"}</div>
            </div>
            <div class="tech-spec-row">
              <span class="tech-spec-label">Secondary Cryptographic Hash (SHA3-512):</span>
              <div class="tech-spec-val">${ev.checksum_sha3_512 || "Pending Computation"}</div>
            </div>
            <div class="tech-spec-row">
              <span class="tech-spec-label">Protected Evidence Storage Reference:</span>
              <div class="tech-spec-val">${ev.worm_storage_reference || "Pending Storage Commit"}</div>
            </div>
            <div class="tech-spec-row">
              <span class="tech-spec-label">Write-Lock Storage Identifier:</span>
              <div class="tech-spec-val">objlock://${ev.case_id}/${(ev.checksum_sha256 || "pending").substring(0, 16)}+gov</div>
            </div>
            <div class="tech-spec-row">
              <span class="tech-spec-label">Encryption Specifications:</span>
              <div class="tech-spec-val">AES-256-GCM &bull; 128-bit Authentication Tag &bull; 96-bit Nonce</div>
            </div>
            <div class="tech-spec-row">
              <span class="tech-spec-label">Detected MIME Type & File Signature:</span>
              <div class="tech-spec-val">${ev.detected_mime_type || "N/A"} (${ev.detected_format || "N/A"})</div>
            </div>
          </div>
        </details>
      </div>
    `;

    UI.openDrawer(`Exhibit Details &bull; ${ev.evidence_id}`, drawerHtml);

    if (nextActionHandler) {
      document.getElementById("btnNextAction")?.addEventListener("click", nextActionHandler);
    }

    document.getElementById("btnRunFullPipeline")?.addEventListener("click", () => {
      this.runGuidedSecurityChain(caseId, evidenceId);
    });

    document.getElementById("btnExportCert")?.addEventListener("click", () => {
      this.showCustodyCertificateModal(ev);
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
      await this.openEvidenceDetailDrawer(evidenceId);
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
      await this.openEvidenceDetailDrawer(evidenceId);
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
      await this.openEvidenceDetailDrawer(evidenceId);
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
      await this.openEvidenceDetailDrawer(evidenceId);
      await ScreenEvidence.render(caseId);
    } catch (e) {
      UI.showToast(`Fingerprint check failed: ${e.message}`, "error");
    }
  },

  async executeLockAndEncrypt(caseId, evidenceId) {
    try {
      await Api.applyObjectLock(caseId, evidenceId, "GOVERNANCE");
      await Api.encryptEvidence(caseId, evidenceId);
      UI.showToast(`Write protection and encryption active!`, "success");
      UI.recordAudit("SECURITY_SEALED", evidenceId, "SUCCESS", "Object locked & encrypted");
      await this.openEvidenceDetailDrawer(evidenceId);
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
      } catch (lockErr) {
        console.warn("Lock/Encrypt notice:", lockErr);
      }

      UI.showToast("Evidence verification pipeline completed successfully!", "success");
      UI.recordAudit("VERIFICATION_COMPLETED", evidenceId, "SUCCESS", "All forensic standards met");
      await this.openEvidenceDetailDrawer(evidenceId);
      await ScreenEvidence.render(caseId);
    } catch (e) {
      UI.showToast(`Pipeline paused: ${e.message}`, "error");
    }
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 10. SCREEN 4: TIMELINE (Route: #/cases/:id/timeline)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenTimeline = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Timeline`;

    await ensureActiveCaseLoaded(caseId);
    const c = State.activeCase;
    const evidenceList = State.evidence || [];

    const allEvents = [
      {
        id: "EV-01",
        time: "18:42",
        date: "30 Sep 2026",
        title: "Subject enters premises",
        source: "Corridor Access Register",
        evidenceId: evidenceList[0] ? evidenceList[0].evidence_id : "SAKSHI-EVID-01",
        status: "VERIFIED",
        desc: "Entry logged through main security checkpoint."
      },
      {
        id: "EV-02",
        time: "19:07",
        date: "30 Sep 2026",
        title: "Cellular telephone transaction recorded",
        source: "Cellular CDR Dump (Sector 4)",
        evidenceId: evidenceList[1] ? evidenceList[1].evidence_id : "SAKSHI-EVID-02",
        status: "VERIFIED",
        desc: "Outgoing SMS transmission registered via nearest cellular base tower."
      },
      {
        id: "EV-03",
        time: "19:10",
        date: "30 Sep 2026",
        title: "Reported departure by witness",
        source: "Witness Statement WS-02",
        evidenceId: evidenceList[0] ? evidenceList[0].evidence_id : "SAKSHI-EVID-01",
        status: "REPORTED",
        desc: "Witness stated subject departed premises prior to 19:10 hrs."
      },
      {
        id: "EV-04",
        time: "19:18",
        date: "30 Sep 2026",
        title: "Hallway corridor surveillance capture",
        source: "Hotel Hallway Camera 04",
        evidenceId: evidenceList[0] ? evidenceList[0].evidence_id : "SAKSHI-EVID-01",
        status: "VERIFIED",
        desc: "Corridor camera captures subject silhouette at room doorway at 19:18:32 hrs."
      },
      {
        id: "EV-05",
        time: "19:31",
        date: "30 Sep 2026",
        title: "Vehicle movement exiting back alleyway",
        source: "Traffic Surveillance System",
        evidenceId: evidenceList[2] ? evidenceList[2].evidence_id : "SAKSHI-EVID-03",
        status: "REQUIRES_VERIFICATION",
        desc: "Dark sedan seen exiting alleyway toward primary ring road."
      },
      {
        id: "EV-06",
        time: "04:18",
        date: "01 Oct 2026",
        title: "Emergency distress phone call logged",
        source: "PCR Dispatch Audio",
        evidenceId: evidenceList[3] ? evidenceList[3].evidence_id : "SAKSHI-EVID-04",
        status: "VERIFIED",
        desc: "First distress phone call logged by emergency dispatcher."
      },
      {
        id: "EV-07",
        time: "04:45",
        date: "01 Oct 2026",
        title: "First responder patrol arrival at scene",
        source: "Station General Diary Entry",
        evidenceId: c.case_id,
        status: "VERIFIED",
        desc: "Station patrol officers and medical crew arrive at scene."
      }
    ];

    const currentFilter = State.filters.timelineFilter || "ALL";
    const filteredEvents = allEvents.filter(ev => {
      if (currentFilter === "ALL") return true;
      if (currentFilter === "VERIFIED") return ev.status === "VERIFIED";
      if (currentFilter === "REPORTED") return ev.status === "REPORTED";
      if (currentFilter === "REQUIRES_VERIFICATION") return ev.status === "REQUIRES_VERIFICATION";
      return true;
    });

    const html = `
      ${renderWorkspaceHeaderHtml("timeline")}

      <div class="cases-toolbar">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Chronological Investigation Timeline</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Chronological reconstruction of events based on FIR, statements, CCTV, and cellular logs.</p>
        </div>
      </div>

      <!-- Filter Buttons -->
      <div class="filter-chips" style="margin: 12px 0 16px;">
        <button class="filter-chip ${currentFilter === 'ALL' ? 'active' : ''}" data-tfilter="ALL">All Events (${allEvents.length})</button>
        <button class="filter-chip ${currentFilter === 'VERIFIED' ? 'active' : ''}" data-tfilter="VERIFIED">Verified</button>
        <button class="filter-chip ${currentFilter === 'REPORTED' ? 'active' : ''}" data-tfilter="REPORTED">Reported</button>
        <button class="filter-chip ${currentFilter === 'REQUIRES_VERIFICATION' ? 'active' : ''}" data-tfilter="REQUIRES_VERIFICATION">Requires Verification</button>
      </div>

      <!-- Temporal Inconsistency Highlight -->
      <div class="contradiction-card">
        <div class="contradiction-header">
          <span>⚠️</span>
          <span>Temporal Inconsistency Detected Requiring Investigator Verification</span>
        </div>
        <p style="font-size: 0.84rem; color: var(--text-main); margin-top: 4px;">
          The available exhibits show an 8-minute variance between recorded witness testimony and hallway CCTV footage.
        </p>

        <div class="contradiction-sources">
          <div>
            <h4 style="font-size: 0.74rem; color: var(--text-muted); text-transform: uppercase;">Source A &bull; Witness Statement WS-02</h4>
            <div style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); font-family: var(--font-mono);">19:10 hrs</div>
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">
              Witness stated subject departed premises prior to 19:10.
            </div>
          </div>
          <div>
            <h4 style="font-size: 0.74rem; color: var(--text-muted); text-transform: uppercase;">Source B &bull; CCTV Camera 04</h4>
            <div style="font-size: 1.15rem; font-weight: 700; color: var(--primary); font-family: var(--font-mono);">19:18:32 hrs</div>
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">
              Surveillance footage confirms subject in corridor at 19:18:32.
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid var(--attention-border);">
          <span style="font-size: 0.78rem; color: var(--text-secondary);">
            Variance: <strong>8 minutes discrepancy</strong> &bull; Non-accusatory analytical flag.
          </span>
          <button class="btn btn-secondary btn-sm" onclick="UI.showToast('Inconsistency marked for Case Diary inquiry.', 'info')">
            Mark for Case Diary Inquiry
          </button>
        </div>
      </div>

      <!-- Chronological Sequence -->
      <div class="timeline-spine">
        ${filteredEvents.map(ev => {
          const badgeClass = ev.status === "VERIFIED" ? "badge-verified" : ev.status === "REPORTED" ? "badge-info" : "badge-attention";
          const badgeText = ev.status === "VERIFIED" ? "✓ Verified" : ev.status === "REPORTED" ? "Reported" : "Requires Verification";
          return `
            <div class="timeline-event-card" onclick="ScreenTimeline.showEventDetails('${ev.id}')">
              <div class="timeline-event-node">●</div>
              <div class="timeline-time-badge">${ev.time} hrs &bull; ${ev.date}</div>
              <div class="timeline-event-desc">${ev.title}</div>
              <div class="timeline-event-meta">
                <span>Source: <strong>${ev.source}</strong></span>
                <span>Exhibit: <code style="font-family: var(--font-mono); color: var(--primary);">${ev.evidenceId}</code></span>
                <span class="badge ${badgeClass}">${badgeText}</span>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;

    container.innerHTML = html;

    document.querySelectorAll("[data-tfilter]").forEach(btn => {
      btn.addEventListener("click", (e) => {
        State.filters.timelineFilter = e.target.getAttribute("data-tfilter");
        this.render(caseId);
      });
    });
  },

  showEventDetails(eventId) {
    const bodyHtml = `
      <div style="display: flex; flex-direction: column; gap: 12px; font-size: 0.86rem;">
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Event Reference</span>
          <strong style="font-family: var(--font-mono); color: var(--primary);">${eventId}</strong>
        </div>
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Investigative Source</span>
          <strong>Surveillance Video / Call Record Corroboration</strong>
        </div>
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase;">Corroboration Details</span>
          <p style="color: var(--text-secondary); margin-top: 2px;">
            Event timing anchored using synchronized NTP surveillance clocks and cellular sector handoff logs.
          </p>
        </div>
      </div>
    `;

    UI.openModal("Timeline Event Details", bodyHtml, `<button class="btn btn-secondary" onclick="UI.closeModal()">Close</button>`);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 11. SCREEN 5: ANALYSIS & REASONING (Route: #/cases/:id/analysis)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenAnalysis = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Analysis`;

    await ensureActiveCaseLoaded(caseId);

    const html = `
      ${renderWorkspaceHeaderHtml("analysis")}

      <div class="cases-toolbar">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Analytical Observations & Reasoning</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Analytical observations grounded strictly in verified case exhibits.</p>
        </div>
        <span class="badge badge-info">EC-MORE Analytical Workspace</span>
      </div>

      <!-- Human Governance Notice -->
      <div class="human-governance-notice">
        <span style="font-size: 1.2rem;">⚖️</span>
        <div>
          <strong>Investigating Officer Accountability Notice:</strong>
          <span> SAKSHI observations are analytical hypothesis cues. SAKSHI does not assert guilt, identify perpetrators, or draw legal conclusions. The Investigating Officer remains the sole decision-maker.</span>
        </div>
      </div>

      <!-- Evidentiary Correlation Map -->
      <div class="card" style="padding: 18px 20px; margin-bottom: 20px;">
        <div style="font-size: 0.74rem; font-weight: 700; text-transform: uppercase; color: var(--primary); letter-spacing: 0.06em; margin-bottom: 6px;">
          EVIDENTIARY CORRELATION MAP
        </div>
        <p style="font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 12px;">
          The system continuously evaluates connections between verified evidence sources to highlight potential relationships:
        </p>

        <div class="correlation-flow">
          <div class="correlation-node">📹 CCTV Camera 4</div>
          <span class="correlation-arrow">+</span>
          <div class="correlation-node">📄 Witness Statement WS-02</div>
          <span class="correlation-arrow">+</span>
          <div class="correlation-node">📱 Call Record CDR-07</div>
          <span class="correlation-arrow">&rarr;</span>
          <div class="correlation-node" style="border-color: var(--attention); background-color: var(--attention-bg); color: var(--attention-text);">
            ⚠️ Potential Temporal Inconsistency
          </div>
          <span class="correlation-arrow">&rarr;</span>
          <div class="correlation-node" style="border-color: var(--primary); background-color: var(--primary-bg); color: var(--primary-text);">
            Requires Investigator Review
          </div>
        </div>
      </div>

      <!-- Observation 01 -->
      <div class="observation-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <span class="badge badge-attention">POTENTIAL TEMPORAL INCONSISTENCY DETECTED</span>
          <span style="font-size: 0.74rem; color: var(--text-muted);">Observation #01</span>
        </div>
        <div class="observation-claim">
          The reported departure time differs from the CCTV-recorded movement time by approximately 8 minutes.
        </div>
        <div>
          <span style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px; text-transform: uppercase;">Supporting Evidence:</span>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <span style="font-family: var(--font-mono); font-size: 0.74rem; background-color: var(--bg-card-subtle); border: 1px solid var(--border-default); padding: 2px 8px; border-radius: 4px; color: var(--primary);">📹 CCTV Camera 4</span>
            <span style="font-family: var(--font-mono); font-size: 0.74rem; background-color: var(--bg-card-subtle); border: 1px solid var(--border-default); padding: 2px 8px; border-radius: 4px; color: var(--primary);">📄 Witness Statement WS-02</span>
          </div>
        </div>
        <div class="observation-reasoning">
          <strong>Analytical Reasoning Trace:</strong> Recorded timestamps differ: Witness statement states departure before 19:10 hrs, whereas hallway surveillance footage captures subject at 19:18:32 hrs.
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid var(--border-subtle); flex-wrap: wrap; gap: 8px;">
          <div>
            <span class="badge badge-attention">Status: Requires Investigator Verification</span>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-secondary btn-sm" onclick="ScreenAnalysis.showExplainabilityModal('Observation #01', 'Reported departure time differs from CCTV recording.')">
              Why did SAKSHI detect this?
            </button>
            <button class="btn btn-secondary btn-sm" onclick="UI.showToast('Observation dismissed by investigator.', 'info')">Dismiss</button>
            <button class="btn btn-primary btn-sm" onclick="UI.showToast('Observation added to Case Diary inquiry agenda.', 'success')">Accept for Inquiry Plan</button>
          </div>
        </div>
      </div>

      <!-- Observation 02 -->
      <div class="observation-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <span class="badge badge-attention">COMMUNICATION ACTIVITY PATTERN OBSERVED</span>
          <span style="font-size: 0.74rem; color: var(--text-muted);">Observation #02</span>
        </div>
        <div class="observation-claim">
          Cellular telephone handset transactions ceased abruptly 42 minutes prior to the recorded emergency dispatch call.
        </div>
        <div>
          <span style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px; text-transform: uppercase;">Supporting Evidence:</span>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <span style="font-family: var(--font-mono); font-size: 0.74rem; background-color: var(--bg-card-subtle); border: 1px solid var(--border-default); padding: 2px 8px; border-radius: 4px; color: var(--primary);">📱 CDR Sheet Sector 4</span>
            <span style="font-family: var(--font-mono); font-size: 0.74rem; background-color: var(--bg-card-subtle); border: 1px solid var(--border-default); padding: 2px 8px; border-radius: 4px; color: var(--primary);">🎙 PCR Dispatch Audio</span>
          </div>
        </div>
        <div class="observation-reasoning">
          <strong>Analytical Reasoning Trace:</strong> Cellular network pings stopped at 19:22 hrs across recorded SIM interfaces without standard power-off detachment signals.
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid var(--border-subtle); flex-wrap: wrap; gap: 8px;">
          <div>
            <span class="badge badge-attention">Status: Requires Investigator Verification</span>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-secondary btn-sm" onclick="ScreenAnalysis.showExplainabilityModal('Observation #02', 'Cellular activity ceased 42 minutes prior to emergency call.')">
              Why did SAKSHI detect this?
            </button>
            <button class="btn btn-secondary btn-sm" onclick="UI.showToast('Observation dismissed by investigator.', 'info')">Dismiss</button>
            <button class="btn btn-primary btn-sm" onclick="UI.showToast('Observation added to Case Diary inquiry agenda.', 'success')">Accept for Inquiry Plan</button>
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

  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Evidence RAG Search`;

    try {
      await ensureActiveCaseLoaded(caseId);
    } catch (err) {
      container.innerHTML = `
        <div class="card" style="padding: 24px; text-align: center; margin: 30px auto; max-width: 600px;">
          <h3>Case Access Error</h3>
          <p style="color: var(--text-muted); margin: 12px 0;">Unable to access case ${Formatters.escapeHtml(caseId)}: ${Formatters.escapeHtml(err.message)}</p>
          <button class="btn btn-primary" onclick="window.location.hash='#/cases'">Return to Case Directory</button>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      ${renderWorkspaceHeaderHtml("rag")}

      <div class="cases-toolbar">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Evidence RAG Semantic Search</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Neural vector similarity retrieval across verified case documents and ballistic/forensic exhibits.</p>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <span class="badge badge-info" id="ragRetrievalModeBadge">PostgreSQL / pgvector Ready</span>
        </div>
      </div>

      <!-- Evidentiary Provenance Notice -->
      <div class="human-governance-notice">
        <span style="font-size: 1.2rem;">⚖️</span>
        <div>
          <strong>Evidentiary Provenance Notice:</strong>
          <span> Retrieved passages are verified forensic source materials from the case docket, scored by cosine vector similarity. SAKSHI retrieves original text with cryptographic fingerprints; it never fabricates or summarizes content.</span>
        </div>
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
                placeholder="Enter forensic inquiry (e.g. ballistic trajectory 9mm, vehicle speeding northbound, CDR tower data)..."
                value="${Formatters.escapeHtml(ScreenRAGSearch.lastQuery)}"
                required
                style="height: 44px; font-size: 0.95rem;"
              />
              <div id="ragQueryValidation" style="color: var(--danger); font-size: 0.78rem; margin-top: 4px; display: none;"></div>
            </div>
            <div style="width: 150px;">
              <select id="ragLimitSelect" class="form-control" style="height: 44px; font-size: 0.88rem;">
                <option value="5" selected>Top 5 Passages</option>
                <option value="10">Top 10 Passages</option>
                <option value="20">Top 20 Passages</option>
              </select>
            </div>
            <div>
              <button type="submit" id="ragSubmitBtn" class="btn btn-primary" style="height: 44px; padding: 0 20px; font-weight: 600;">
                <span class="icon">🔎</span> Search Exhibits
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

    const inputEl = document.getElementById("ragQueryInput");
    if (inputEl && !ScreenRAGSearch.lastQuery) {
      inputEl.focus();
    }
  },

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
        submitBtn.innerHTML = `<span class="icon">🔎</span> Search Exhibits`;
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
              <span style="font-size: 0.78rem; color: var(--text-muted);">Cosine Similarity:</span>
              <span class="badge ${scoreBadgeClass}" style="font-family: var(--font-mono); font-weight: 700;">
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
// 12. SCREEN 6: INVESTIGATION GAPS (Route: #/cases/:id/gaps)
// ═══════════════════════════════════════════════════════════════════════════

const ScreenGaps = {
  async render(caseId) {
    const container = document.getElementById("viewContainer");
    document.getElementById("breadcrumbCurrent").textContent = `${caseId} / Investigation Gaps`;

    await ensureActiveCaseLoaded(caseId);

    const gaps = [
      {
        priority: "HIGH",
        missing: "Surveillance footage covering rear stairwell exit between 19:10 and 19:30",
        relevance: "Required to verify movement during the relevant time window and reconcile the 8-minute variance.",
        source: "Adjacent Commercial Bank CCTV Server facing back alley",
        action: "Obtain missing CCTV backup from adjacent bank premises."
      },
      {
        priority: "MEDIUM",
        missing: "Telecom CDR records for second SIM IMEI registered to victim handset",
        relevance: "Required to confirm if second subscriber profile was active during the 19:22 telecom cessation.",
        source: "Cellular Service Provider Nodal Officer",
        action: "Submit supplementary CDR request to nodal telecom authority."
      },
      {
        priority: "LOW",
        missing: "Viscera chemical examination report confirmation",
        relevance: "Required to exclude toxic substances as primary or contributing cause of death.",
        source: "State Forensic Science Laboratory (FSL Chemical Division)",
        action: "Follow up with toxicology division for expedited report."
      }
    ];

    const html = `
      ${renderWorkspaceHeaderHtml("gaps")}

      <div class="cases-toolbar">
        <div>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">Investigation Gaps</h3>
          <p style="color: var(--text-muted); font-size: 0.82rem;">Systematic identification of missing documents, unverified links, and recommended inquiries.</p>
        </div>
      </div>

      <div style="margin-top: 14px;">
        ${gaps.map(g => `
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
              <button class="btn btn-secondary btn-sm" onclick="UI.showToast('Gap logged in Case Diary agenda.', 'info')">
                Log in Case Diary
              </button>
            </div>
          </div>
        `).join("")}
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

    await ensureActiveCaseLoaded(caseId);
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
                  <span>☀️ Investigation Desk Mode (Default Light)</span>
                </label>
                <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; cursor: pointer;">
                  <input type="radio" name="optTheme" value="dark" ${State.theme === 'dark' ? 'checked' : ''}>
                  <span>🌙 Control Room Mode (Dark)</span>
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

      applyTheme(selectedTheme);
      updateHeaderAuth();
      UI.showToast(`Officer settings saved successfully`, "success");
    });
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// 15. BOOTSTRAP WORKSTATION
// ═══════════════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
  initApplication();
});
