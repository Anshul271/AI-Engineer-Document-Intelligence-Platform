const API_BASE = "/api";

const form = document.getElementById("upload-form");
const statusEl = document.getElementById("upload-status");
const processBtn = document.getElementById("process-btn");
const dashboardBody = document.getElementById("dashboard-body");
const refreshBtn = document.getElementById("refresh-btn");

const modal = document.getElementById("result-modal");
const closeModalBtn = document.getElementById("close-modal");
const tabReadable = document.getElementById("tab-readable");
const tabRaw = document.getElementById("tab-raw");

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const target = btn.dataset.tab;
    tabReadable.classList.toggle("hidden", target !== "readable");
    tabRaw.classList.toggle("hidden", target !== "raw");
  });
});

closeModalBtn.addEventListener("click", () => modal.classList.add("hidden"));
modal.addEventListener("click", (e) => { if (e.target === modal) modal.classList.add("hidden"); });

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const docType = document.getElementById("doc-type").value;
  const fileInput = document.getElementById("file-input");
  if (!fileInput.files.length) return;

  const fd = new FormData();
  fd.append("document_type", docType);
  fd.append("file", fileInput.files[0]);

  processBtn.disabled = true;
  statusEl.className = "";
  statusEl.textContent = "Processing… this can take up to a minute for scanned documents.";

  try {
    const res = await fetch(`${API_BASE}/documents/process`, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) {
      statusEl.className = "status-err";
      statusEl.textContent = `Error: ${data.detail || data.error || "Processing failed."}`;
    } else if (data.status === "SUCCESS") {
      statusEl.className = "status-ok";
      statusEl.textContent = `✔ Processed "${data.document_name}" successfully.`;
      renderResult(data);
    } else {
      statusEl.className = "status-err";
      statusEl.textContent = `${data.status}: ${data.error || "See details."}`;
    }
    loadDashboard();
  } catch (err) {
    statusEl.className = "status-err";
    statusEl.textContent = `Network error: ${err.message}`;
  } finally {
    processBtn.disabled = false;
  }
});

refreshBtn.addEventListener("click", loadDashboard);

async function loadDashboard() {
  try {
    const res = await fetch(`${API_BASE}/documents`);
    const rows = await res.json();
    dashboardBody.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(r.document_name)}</td>
        <td>${escapeHtml(r.document_type)}</td>
        <td><span class="badge badge-${r.status}">${r.status}</span></td>
        <td>${new Date(r.created_at).toLocaleString()}</td>
        <td><span class="view-link" data-name="${encodeURIComponent(r.document_name)}">View</span></td>`;
      dashboardBody.appendChild(tr);
    });
    document.querySelectorAll(".view-link").forEach((el) => {
      el.addEventListener("click", () => openDocument(decodeURIComponent(el.dataset.name)));
    });
  } catch (err) {
    console.error("Failed to load dashboard", err);
  }
}

async function openDocument(name) {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(name)}`);
  const data = await res.json();
  renderResult(data, true);
}

function renderResult(data, fromDashboard = false) {
  tabRaw.textContent = JSON.stringify(data, null, 2);

  const fields = fromDashboard ? (data.extracted_data?.fields || {}) : (data.extracted_data || {});
  const tables = fromDashboard ? (data.extracted_data?.tables || []) : (data.tables || []);
  const validations = data.financial_validations || [];

  let html = `<h3>${escapeHtml(data.document_name)} <span class="badge badge-${data.status}">${data.status}</span></h3>`;

  html += `<div class="section-title">Extracted Fields</div><div class="field-grid">`;
  const fieldEntries = Object.entries(fields || {});
  if (fieldEntries.length === 0) html += `<div class="field-item missing"><div class="fvalue">No fields extracted.</div></div>`;
  for (const [name, info] of fieldEntries) {
    const value = info && typeof info === "object" ? info.value : info;
    const page = info && typeof info === "object" ? info.page : null;
    const src = info && typeof info === "object" ? info.source_text : null;
    const missing = value === null || value === undefined || value === "";
    html += `<div class="field-item ${missing ? "missing" : ""}">
      <div class="fname">${escapeHtml(name)}</div>
      <div class="fvalue">${missing ? "⚠ Missing" : escapeHtml(String(value))}</div>
      ${src ? `<div class="fevidence">p.${page ?? "?"} — "${escapeHtml(src)}"</div>` : ""}
    </div>`;
  }
  html += `</div>`;

  if (tables.length) {
    html += `<div class="section-title">Tables / Line Items</div>`;
    tables.forEach((t) => {
      const rows = t.rows || [];
      if (!rows.length) return;
      const cols = Object.keys(rows[0]);
      html += `<div style="font-size:12px;color:#5f6368;margin-bottom:4px;">${escapeHtml(t.table_name || "Table")}</div>`;
      html += `<table class="mini"><thead><tr>${cols.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead><tbody>`;
      rows.forEach((r) => {
        html += `<tr>${cols.map((c) => `<td>${escapeHtml(String(r[c] ?? ""))}</td>`).join("")}</tr>`;
      });
      html += `</tbody></table>`;
    });
  }

  html += `<div class="section-title">Financial Validations</div>`;
  if (!validations.length) html += `<p style="font-size:13px;color:#5f6368;">No applicable validations.</p>`;
  validations.forEach((v) => {
    html += `<div class="val-row">
      <div>
        <strong>${escapeHtml(v.check_name)}</strong><br/>
        <span style="color:#5f6368;">${escapeHtml(v.formula)}</span><br/>
        <span style="color:#5f6368;">calculated=${v.calculated_value ?? "—"} reported=${v.reported_value ?? "—"} variance=${v.variance ?? "—"}</span>
      </div>
      <div class="val-status val-${v.status}">${v.status}</div>
    </div>`;
  });

  tabReadable.innerHTML = html;
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
  document.querySelector('.tab-btn[data-tab="readable"]').classList.add("active");
  tabReadable.classList.remove("hidden");
  tabRaw.classList.add("hidden");
  modal.classList.remove("hidden");
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

loadDashboard();
