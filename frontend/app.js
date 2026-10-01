const API_BASE = "http://127.0.0.1:8000/api/v1";

// ─── MOD-02: Authentication State ────────────────────────────────────
// In development mode, uses X-Investigator-Id headers.
// In OIDC mode, would use Bearer tokens from the IdP.
let authState = {
  mode: "development",
  token: null,
  investigator: null,
  headers: {
    "Content-Type": "application/json",
    "X-Investigator-Id": "IO-7842-SHARMA",
    "X-Investigator-Role": "INVESTIGATING_OFFICER",
    "X-Investigator-Jurisdiction": "JUR-DEL-04"
  }
};

let activeCaseId = null;

document.addEventListener("DOMContentLoaded", async () => {
  // ─── MOD-02: Check auth status and authenticate ──────────────────
  await checkAuthStatus();
  await authenticateInvestigator();

  loadCases();

  document.getElementById("createCaseForm").addEventListener("submit", handleCreateCase);
  document.getElementById("refreshBtn").addEventListener("click", loadCases);
  document.getElementById("viewContractBtn").addEventListener("click", viewPhase2Contract);
  document.getElementById("closeContractBtn").addEventListener("click", () => {
    document.getElementById("contractBox").classList.add("hidden");
  });

  // MOD-02: Login form handler
  const loginForm = document.getElementById("devLoginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", handleDevLogin);
  }
});


// ═══════════════════════════════════════════════════════════════════════
// MOD-02: Authentication Functions
// ═══════════════════════════════════════════════════════════════════════

async function checkAuthStatus() {
  try {
    const res = await fetch(`${API_BASE}/auth/status`);
    if (res.ok) {
      const data = await res.json();
      authState.mode = data.auth_mode;

      const modeIndicator = document.getElementById("authModeIndicator");
      if (modeIndicator) {
        if (data.development_mode) {
          modeIndicator.textContent = "DEV AUTH";
          modeIndicator.className = "auth-mode-badge dev";
        } else {
          modeIndicator.textContent = "OIDC";
          modeIndicator.className = "auth-mode-badge oidc";
        }
      }

      // Show/hide dev login based on mode
      const devLoginSection = document.getElementById("devLoginSection");
      if (devLoginSection) {
        devLoginSection.classList.toggle("hidden", !data.development_mode);
      }
    }
  } catch (err) {
    console.warn("Auth status check failed — backend may be offline.");
  }
}

async function authenticateInvestigator() {
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: authState.headers
    });

    if (res.ok) {
      authState.investigator = await res.json();
      updateAuthDisplay(authState.investigator);
    } else {
      updateAuthDisplay(null);
    }
  } catch (err) {
    console.warn("Authentication check failed — backend may be offline.");
    updateAuthDisplay(null);
  }
}

function updateAuthDisplay(investigator) {
  const userIdEl = document.getElementById("currentUserDisplay");
  const roleEl = document.querySelector(".user-role");
  const statusEl = document.querySelector(".status-indicator");
  const authMethodEl = document.getElementById("authMethodDisplay");

  if (investigator) {
    if (userIdEl) userIdEl.textContent = investigator.investigator_id || investigator.subject_id;
    if (roleEl) roleEl.textContent = investigator.role || "UNKNOWN";
    if (statusEl) {
      statusEl.textContent = "AUTHENTICATED";
      statusEl.className = "status-indicator authenticated";
    }
    if (authMethodEl) {
      authMethodEl.textContent = investigator.authentication_method === "development"
        ? "⚠️ DEVELOPMENT ONLY"
        : "🔒 OIDC";
      authMethodEl.className = investigator.authentication_method === "development"
        ? "auth-method dev-warning"
        : "auth-method oidc-secured";
    }
  } else {
    if (userIdEl) userIdEl.textContent = "NOT AUTHENTICATED";
    if (statusEl) {
      statusEl.textContent = "DISCONNECTED";
      statusEl.className = "status-indicator disconnected";
    }
  }
}

async function handleDevLogin(e) {
  e.preventDefault();
  const subjectId = document.getElementById("devSubjectId").value.trim();
  const role = document.getElementById("devRole").value;
  const jurisdiction = document.getElementById("devJurisdiction").value.trim();

  if (!subjectId) return;

  // Update auth headers for development mode
  authState.headers = {
    "Content-Type": "application/json",
    "X-Investigator-Id": subjectId,
    "X-Investigator-Role": role,
    "X-Investigator-Jurisdiction": jurisdiction || undefined
  };

  // Clean up undefined headers
  Object.keys(authState.headers).forEach(key => {
    if (authState.headers[key] === undefined) delete authState.headers[key];
  });

  await authenticateInvestigator();
  loadCases();

  showBanner(`Development identity set: ${subjectId}`, "success");
}


// ═══════════════════════════════════════════════════════════════════════
// MOD-01: Case Management Functions (preserved from original)
// ═══════════════════════════════════════════════════════════════════════

async function handleCreateCase(e) {
  e.preventDefault();
  const banner = document.getElementById("statusBanner");
  banner.className = "banner hidden";

  const payload = {
    title: document.getElementById("caseTitle").value.trim(),
    fir_metadata: {
      fir_number: document.getElementById("firNumber").value.trim(),
      police_station: document.getElementById("policeStation").value.trim(),
      incident_date: document.getElementById("incidentDate").value ? new Date(document.getElementById("incidentDate").value).toISOString() : null,
      incident_location: document.getElementById("incidentLocation").value.trim() || null
    },
    assigned_io_id: document.getElementById("assignedIO").value.trim() || null
  };

  try {
    const res = await fetch(`${API_BASE}/cases`, {
      method: "POST",
      headers: authState.headers,
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok) {
      const errorMsg = data.message || (data.detail && data.detail.message) || "Case creation failed";
      showBanner(errorMsg, "error");
      return;
    }

    // Success
    activeCaseId = data.case_id;
    showBanner(`Case ${data.case_id} established successfully!`, "success");

    // Populate output card
    document.getElementById("outCaseId").textContent = data.case_id;
    document.getElementById("outWorkspaceId").textContent = data.case_workspace.workspace_id;
    document.getElementById("outAssignedIO").textContent = data.assigned_io_id;
    document.getElementById("outStage").textContent = data.lifecycle_stage;
    document.getElementById("outputCard").classList.remove("hidden");

    // Refresh table
    loadCases();

  } catch (err) {
    showBanner(`Network or connection error: Ensure backend is running on ${API_BASE}`, "error");
  }
}

async function loadCases() {
  const tbody = document.getElementById("casesTableBody");
  try {
    const res = await fetch(`${API_BASE}/cases`, {
      headers: authState.headers
    });
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Unable to load cases (${res.status})</td></tr>`;
      return;
    }
    const data = await res.json();
    if (!data.cases || data.cases.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No cases initiated yet. Use the form to establish one.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.cases.map(c => `
      <tr>
        <td><strong style="color: #00f0ff; font-family: monospace;">${c.case_id}</strong></td>
        <td>${c.fir_metadata.fir_number || "-"}</td>
        <td>${c.title}</td>
        <td>${c.assigned_io_id}</td>
        <td><span class="stage-tag">${c.lifecycle_stage}</span></td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Backend service offline or unreachable.</td></tr>`;
  }
}

async function viewPhase2Contract() {
  if (!activeCaseId) return;
  const contractBox = document.getElementById("contractBox");
  const contractCode = document.getElementById("contractCode");

  try {
    const res = await fetch(`${API_BASE}/cases/${activeCaseId}/phase2-contract`, {
      headers: authState.headers
    });
    const data = await res.json();
    contractCode.textContent = JSON.stringify(data, null, 2);
    contractBox.classList.remove("hidden");
  } catch (err) {
    alert("Failed to load Phase 2 contract.");
  }
}

function showBanner(message, type) {
  const banner = document.getElementById("statusBanner");
  banner.textContent = message;
  banner.className = `banner ${type}`;
}
