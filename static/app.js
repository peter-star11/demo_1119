const state = { dashboard: null, records: [], events: [], toastTimer: null };
const $ = (selector, root = document) => root.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function titleCase(value) {
  return String(value || "").replaceAll("_", " ").toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatTime(value) {
  return value
    ? new Date(value).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
    : "—";
}

function formatAmount(value) {
  return typeof value === "number"
    ? new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value)
    : value || "—";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

function showToast(message, isError = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.add("hidden"), 4000);
}

async function refreshData() {
  const [dashboard, records, events] = await Promise.all([
    api("/api/dashboard"),
    api("/api/records"),
    api("/api/events"),
  ]);
  state.dashboard = dashboard;
  state.records = records;
  state.events = events;
  render();
}

function renderSummary() {
  const stats = [
    ["Total records", state.dashboard.total],
    ["Waiting", state.dashboard.new],
    ["Auto processed", state.dashboard.auto_processed],
    ["Needs review", state.dashboard.needs_review],
  ];
  $("#summary").innerHTML = stats.map(([label, value]) => `
    <div class="summary-card"><span>${label}</span><strong>${value}</strong></div>
  `).join("");
}

function statusBadge(status) {
  const css = String(status || "").toLowerCase().replaceAll("_", "-");
  return `<span class="status status-${escapeHtml(css)}">${escapeHtml(titleCase(status))}</span>`;
}

function confidenceText(value) {
  return value === null || value === undefined ? "Not scored" : `${Math.round(value * 100)}%`;
}

function renderRecords() {
  $("#record-count").textContent = `${state.records.length} total`;
  $("#empty-records").classList.toggle("hidden", state.records.length > 0);
  $("#records-list").innerHTML = state.records.map((record) => {
    const data = record.data || {};
    const needsReview = record.status === "NEEDS_REVIEW";
    const info = needsReview
      ? `<small class="reason">${escapeHtml(record.reason || "Manual review required.")}</small>`
      : `<small>${escapeHtml(data.location || "Location not provided")}</small>`;
    const action = needsReview
      ? `<div class="review-actions">
          <button class="button button-approve" data-review="approve" data-id="${escapeHtml(record.id)}">Approve</button>
          <button class="button button-reject" data-review="reject" data-id="${escapeHtml(record.id)}">Reject</button>
        </div>`
      : `<button class="text-button" data-open-record="${escapeHtml(record.id)}">Details</button>`;

    return `<tr>
      <td><button class="record-link" data-open-record="${escapeHtml(record.id)}"><strong>${escapeHtml(data.name || "Unnamed record")}</strong><small>${escapeHtml(record.id)}</small></button>${info}</td>
      <td>${escapeHtml(data.category || "—")}</td>
      <td>${confidenceText(record.confidence)}</td>
      <td>${statusBadge(record.status)}</td>
      <td>${action}</td>
    </tr>`;
  }).join("");
}

function renderActivity() {
  const events = state.events.slice(0, 6);
  $("#empty-activity").classList.toggle("hidden", events.length > 0);
  $("#activity-list").innerHTML = events.map((event) => `
    <li>
      <span class="activity-dot"></span>
      <span class="activity-text"><strong>${escapeHtml(titleCase(event.action))}</strong>
        <button class="text-button" data-open-record="${escapeHtml(event.record_id)}">${escapeHtml(event.record_id)}</button>
        <small>${escapeHtml(event.result)}</small>
      </span>
      <time>${formatTime(event.created_at)}</time>
    </li>
  `).join("");
}

function render() {
  renderSummary();
  renderRecords();
  renderActivity();
  const button = $("#run-processing");
  button.disabled = state.dashboard.new === 0;
  button.textContent = state.dashboard.new
    ? `Process ${state.dashboard.new} new record${state.dashboard.new === 1 ? "" : "s"}`
    : "No new records";
}

async function openRecord(id) {
  try {
    const record = await api(`/api/records/${encodeURIComponent(id)}`);
    const data = record.data || {};
    const fields = [
      ["Name", data.name],
      ["Category", data.category],
      ["Amount", formatAmount(data.amount)],
      ["Location", data.location],
      ["Record status", data.status],
      ["Date", data.date],
    ];
    const rules = (record.rules || []).map((rule) => {
      const label = typeof rule === "string" ? titleCase(rule) : rule.label;
      const detail = typeof rule === "string" ? "" : rule.detail;
      const flagged = typeof rule === "object" && rule.result === "flagged";
      return `<li class="${flagged ? "flagged" : ""}"><span>${flagged ? "!" : "✓"}</span><div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(detail)}</small></div></li>`;
    }).join("");
    const timeline = (record.events || []).map((event) => `
      <li><span class="timeline-dot"></span><div><strong>${escapeHtml(titleCase(event.action))}</strong>
        <small>${escapeHtml(event.result)} · ${formatTime(event.created_at)}</small>
        ${event.details ? `<small>${escapeHtml(event.details)}</small>` : ""}
      </div></li>
    `).join("");

    $("#modal-content").innerHTML = `
      <header class="modal-header">
        <div><small>${escapeHtml(record.id)} · ${statusBadge(record.status)}</small><h2 id="modal-title">${escapeHtml(data.name || "Record details")}</h2></div>
        <button class="close-button" aria-label="Close details">×</button>
      </header>
      <div class="modal-body">
        <h3>Record information</h3>
        <dl class="field-list">${fields.map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value || "—")}</dd></div>`).join("")}</dl>
        <h3>Automated result · ${confidenceText(record.confidence)}</h3>
        <p class="decision">${escapeHtml(record.reason || "This record is waiting to be processed.")}</p>
        ${rules ? `<h3>Rules</h3><ul class="rule-list">${rules}</ul>` : ""}
        <h3>History</h3>
        <ol class="timeline">${timeline || "<li>No activity yet.</li>"}</ol>
      </div>
    `;
    $("#modal-backdrop").classList.remove("hidden");
    $(".close-button").addEventListener("click", closeModal);
  } catch (error) {
    showToast(error.message, true);
  }
}

function closeModal() {
  $("#modal-backdrop").classList.add("hidden");
}

async function runProcessing() {
  const button = $("#run-processing");
  button.disabled = true;
  $("#processing-note").classList.remove("hidden");
  try {
    const result = await api("/api/process", { method: "POST" });
    await refreshData();
    showToast(result.count
      ? `${result.count} record${result.count === 1 ? "" : "s"} processed. Review any flagged items.`
      : "There were no new records to process.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    $("#processing-note").classList.add("hidden");
    button.disabled = state.dashboard?.new === 0;
  }
}

async function reviewRecord(id, decision) {
  try {
    await api(`/api/records/${encodeURIComponent(id)}/review`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    });
    await refreshData();
    showToast(`Record ${id} ${decision === "approve" ? "approved" : "rejected"}.`);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function resetDemo() {
  if (!window.confirm("Restore the original sample records?")) return;
  try {
    await api("/api/demo/reset", { method: "POST" });
    await refreshData();
    showToast("Demo reset. You can run processing again.");
  } catch (error) {
    showToast(error.message, true);
  }
}

document.addEventListener("click", (event) => {
  const review = event.target.closest("[data-review]");
  if (review) {
    reviewRecord(review.dataset.id, review.dataset.review);
    return;
  }
  const record = event.target.closest("[data-open-record]");
  if (record) openRecord(record.dataset.openRecord);
});

$("#run-processing").addEventListener("click", runProcessing);
$("#reset-demo").addEventListener("click", resetDemo);
$("#modal-backdrop").addEventListener("click", (event) => {
  if (event.target === $("#modal-backdrop")) closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeModal();
});

refreshData().catch((error) => showToast(`Could not load records: ${error.message}`, true));
