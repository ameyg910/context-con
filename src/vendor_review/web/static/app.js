"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const state = { cfg: null, session: null, search: null, sending: false, editing: null, tab: "chat", poll: null, lastBrief: null };

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`);
  return data;
}

/* ---------------- field metadata ---------------- */

const CRITERIA = { cost: "Cost", feature_fit: "Feature fit", integration: "Integration", scale: "Scale", support: "Support", compliance: "Compliance", speed: "Speed" };
const PERIODS = { unknown: "period not stated", monthly: "per month", annual: "per year", one_time: "one-time", per_shipment: "per shipment", per_user_month: "per user / month" };
const GROUPS = [
  ["What you need", [
    ["service_category", "Service / software", "text", true],
    ["use_case", "Problem to solve", "long", true],
    ["must_haves", "Must-haves", "list", true],
    ["nice_to_haves", "Nice-to-haves", "list"],
  ]],
  ["Constraints", [
    ["budget", "Budget", "budget", true],
    ["geography", "Coverage", "list", true],
    ["scale", "Scale / volume", "text"],
    ["integrations", "Integrations", "list"],
    ["deployment", "Deployment", "text"],
    ["compliance", "Compliance", "list"],
    ["timeline", "Timeline", "text"],
    ["deal_breakers", "Deal-breakers", "list"],
  ]],
  ["Search settings", [
    ["priorities", "Compare by (in order)", "priorities"],
    ["include_vendors", "Vendors to include", "list"],
    ["exclude_vendors", "Vendors to exclude", "list"],
    ["top_k", "Vendors to evaluate", "number"],
  ]],
];

const QUICK = {
  service_category: ["Transport management system (TMS)", "Warehouse management system (WMS)", "Cold-chain carrier for pharma", "Last-mile delivery partner"],
  use_case: ["Cut freight cost on FTL lanes", "Real-time shipment visibility for clients", "Automate carrier selection and booking"],
  budget: ["₹2–4 lakh per month", "₹25 lakh one-time", "No fixed budget"],
  geography: ["Pan-India", "Maharashtra, Gujarat", "Delhi NCR", "South India"],
  scale: ["~5,000 shipments/month", "12 warehouses, 40 users", "skip"],
  integrations: ["SAP", "Oracle NetSuite", "Unicommerce", "skip"],
  priorities: ["Feature fit, cost, integration", "Cost first, then support", "skip"],
  timeline: ["Within 3 months", "Before Q1 2027", "skip"],
};

// Must-have examples follow the service category; unknown categories get none rather than
// examples from another domain.
function mustHaveExamples(category) {
  const c = category.toLowerCase();
  if (/shipping|courier|parcel|aggregator|multi-carrier/.test(c)) return ["Shopify integration, NDR management, COD remittance tracking"];
  if (/warehouse|wms/.test(c)) return ["Multi-client billing, barcode/RF scanning, wave picking"];
  if (/transport|tms|fleet|freight|truck/.test(c)) return ["Real-time GPS tracking, e-way bill integration, carrier rate comparison"];
  return [];
}

/* ---------------- boot ---------------- */

async function boot() {
  try {
    state.cfg = await api("/api/config");
  } catch (e) {
    $("#thread").innerHTML = `<div class="empty-state"><div class="big">⚠︎</div>Server unavailable: ${esc(e.message)}</div>`;
    return;
  }
  renderSystem();
  const list = await api("/api/sessions");
  renderSessions(list);
  const wanted = location.hash.slice(1);
  const pick = list.find((s) => s.id === wanted) || null;
  if (pick) await openSession(pick.id);
  else if (list.length && !wanted) await openSession(list[0].id);
  else await newSession();
}

function renderSystem() {
  const c = state.cfg;
  $("#clientName").textContent = c.client;
  $("#syntheticBanner").hidden = !c.synthetic;
  $("#systemStatus").innerHTML = `
    <div class="status-row"><span class="led ${c.model_available ? "on" : "mid"}"></span>${c.model_available ? `Model: ${esc(c.model)}` : "Model offline · guided questions"}</div>
    <div class="status-row"><span class="led ${c.v1_connected ? "on" : ""}"></span>Vendor evaluator: ${c.v1_connected ? esc(c.v1) : "not connected"}</div>
    <div class="status-row"><span class="led ${c.discovery !== "NotConnectedDiscovery" ? "on" : ""}"></span>Discovery: ${c.discovery !== "NotConnectedDiscovery" ? esc(c.discovery) : "named vendors only"}</div>`;
}

function renderSessions(list) {
  const nav = $("#sessions");
  if (!list.length) { nav.innerHTML = `<div class="session"><span class="s">No searches yet</span></div>`; return; }
  nav.innerHTML = list.map((s) => `
    <button class="session ${state.session && state.session.id === s.id ? "active" : ""}" data-id="${esc(s.id)}">
      <span class="t">${esc(s.title)}</span>
      <span class="s">${s.status ? statusLabel(s.status) : "Building brief"} · ${new Date(s.created * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</span>
    </button>`).join("");
  nav.querySelectorAll(".session[data-id]").forEach((b) => b.addEventListener("click", () => { openSession(b.dataset.id); closeDrawers(); }));
}
const statusLabel = (s) => ({ discovering: "Discovering", evaluating: "Evaluating", done: "Done", error: "Error" }[s] || s);

async function refreshSessions() { renderSessions(await api("/api/sessions")); }

async function newSession() {
  const s = await api("/api/sessions", { method: "POST" });
  setSession(s);
  refreshSessions();
  $("#input").focus();
}

async function openSession(id) {
  setSession(await api(`/api/sessions/${id}`));
  refreshSessions();
}

function setSession(s) {
  const prevBrief = state.session && state.session.id === s.id ? state.session.brief : null;
  state.session = s;
  state.editing = null;
  location.hash = s.id;
  renderThread();
  renderBrief(prevBrief);
  renderStepper();
  stopPoll();
  state.search = null;
  if (s.run_id) {
    $("#tabs").hidden = false;
    setTab("results");
    pollSearch();
  } else {
    $("#tabs").hidden = true;
    setTab("chat");
  }
}

/* ---------------- chat ---------------- */

function renderThread(typing = false) {
  const s = state.session;
  const html = s.messages.map((m) => `
    <div class="msg ${m.role}">
      <div class="avatar">${m.role === "user" ? "You" : "VS"}</div>
      <div><div class="bubble">${esc(m.text)}</div></div>
    </div>`).join("");
  $("#thread").innerHTML = html + (typing ? `<div class="msg assistant typing"><div class="avatar">VS</div><div class="bubble"><i></i><i></i><i></i></div></div>` : "");
  $("#thread").scrollTop = $("#thread").scrollHeight;
  const locked = !!s.run_id;
  $("#input").disabled = locked || state.sending;
  $("#sendBtn").disabled = locked || state.sending;
  $("#composerNote").textContent = locked
    ? "The search has started; this brief is locked. Start a new search to change requirements."
    : s.mode === "fallback" && !state.cfg.model_available
      ? "Language model offline: using guided questions. You can also edit the brief directly."
      : "Your answers build the brief on the right. Nothing is searched or spent until you press “Start vendor search”.";
  renderQuick();
}

function renderQuick() {
  const s = state.session;
  const box = $("#quickReplies");
  if (s.run_id || state.sending) { box.innerHTML = ""; return; }
  const next = (s.missing_required[0] || s.missing_recommended[0] || {}).field;
  const opts = s.messages.length <= 1 ? QUICK.service_category
    : next === "must_haves" ? mustHaveExamples(s.brief.service_category || "")
    : (QUICK[next] || []);
  box.innerHTML = opts.map((o) => `<button class="chip" type="button">${esc(o)}</button>`).join("");
  box.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => send(b.textContent)));
}

async function send(text) {
  text = text.trim();
  if (!text || state.sending) return;
  state.sending = true;
  state.session.messages.push({ role: "user", text });
  $("#input").value = "";
  autosize();
  renderThread(true);
  try {
    const prev = state.session.brief;
    const s = await api(`/api/sessions/${state.session.id}/messages`, { method: "POST", body: { text } });
    state.sending = false;
    state.session = s;
    renderThread();
    renderBrief(prev);
    renderStepper();
    refreshSessions();
  } catch (e) {
    state.sending = false;
    state.session.messages.push({ role: "assistant", text: `⚠︎ ${e.message}` });
    renderThread();
  }
  $("#input").focus();
}

function autosize() {
  const t = $("#input");
  t.style.height = "auto";
  t.style.height = Math.min(t.scrollHeight, 160) + "px";
}

/* ---------------- brief panel ---------------- */

function isEmpty(key, v) {
  if (key === "budget") return !(v.no_fixed_budget || v.min_inr != null || v.max_inr != null);
  if (key === "top_k") return false;
  return Array.isArray(v) ? v.length === 0 : !v;
}

function renderBrief(prevBrief) {
  const s = state.session;
  const b = s.brief;
  const locked = !!s.run_id;
  const pct = Math.round(s.completeness * 100);
  $("#ringFg").style.strokeDashoffset = String(97.4 * (1 - s.completeness));
  $("#ringPct").textContent = pct + "%";
  $("#briefSub").textContent = locked ? "Locked for this search run" : "Filled from the conversation · click any field to edit";

  $("#briefBody").innerHTML = GROUPS.map(([label, fields]) => `
    <div class="group-label">${label}</div>
    ${fields.map(([key, title, type, req]) => fieldHTML(key, title, type, req, b[key], locked, prevBrief && JSON.stringify(prevBrief[key]) !== JSON.stringify(b[key]))).join("")}
  `).join("");

  $("#briefBody").querySelectorAll(".field").forEach((el) => {
    const key = el.dataset.key;
    if (!locked && state.editing !== key) el.addEventListener("click", (ev) => { if (!ev.target.closest("button")) startEdit(key); });
    el.querySelectorAll("[data-remove]").forEach((btn) => btn.addEventListener("click", (ev) => { ev.stopPropagation(); removeItem(key, Number(btn.dataset.remove)); }));
  });
  if (state.editing) wireEditor(state.editing);

  const miss = s.missing_required;
  $("#missingNote").innerHTML = locked ? "Search running with this brief." : miss.length
    ? `Still needed: <b>${miss.map((m) => esc(m.label.toLowerCase())).join(", ")}</b>`
    : s.missing_recommended.length ? `Ready. Optional: ${s.missing_recommended.map((m) => esc(m.label.toLowerCase())).join(", ")}` : "Brief complete.";
  const btn = $("#startSearch");
  btn.disabled = locked || miss.length > 0;
  btn.textContent = locked ? "Search started" : "Start vendor search";
}

function fieldHTML(key, title, type, req, v, locked, changed) {
  const editing = state.editing === key;
  const empty = isEmpty(key, v);
  const badge = req ? `<span class="req ${empty ? "" : "ok"}">${empty ? "Required" : "✓"}</span>` : "";
  let body;
  if (editing) body = editorHTML(key, type, v);
  else if (type === "list") body = empty ? `<div class="field-val empty">Not stated</div>` : `<div class="tags">${v.map((x, i) => `<span class="tag">${esc(x)}${locked ? "" : `<button data-remove="${i}" aria-label="Remove">×</button>`}</span>`).join("")}</div>`;
  else if (type === "priorities") body = empty ? `<div class="field-val empty">Default weighting</div>` : `<div class="tags">${v.map((x, i) => `<span class="tag num">${i + 1}. ${esc(CRITERIA[x] || x)}</span>`).join("")}</div>`;
  else if (type === "budget") body = `<div class="field-val ${empty ? "empty" : ""}">${esc(state.session.budget_label)}</div>`;
  else body = `<div class="field-val ${empty ? "empty" : ""}">${empty ? "Not stated" : esc(v)}</div>`;
  return `<div class="field ${editing ? "editing" : ""} ${changed && !editing ? "flash" : ""}" data-key="${key}" data-type="${type}">
    <div class="field-head">${esc(title)} ${badge}</div>${body}</div>`;
}

function editorHTML(key, type, v) {
  const actions = `<div class="edit-actions"><button class="btn" data-act="cancel">Cancel</button><button class="btn primary" data-act="save">Save</button></div>`;
  if (type === "list") return `
    <div class="tags">${v.map((x, i) => `<span class="tag">${esc(x)}<button data-remove="${i}" aria-label="Remove">×</button></span>`).join("")}</div>
    <div class="edit-row"><input data-in placeholder="Add item, press Enter" maxlength="200"></div>${actions}`;
  if (type === "long") return `<textarea data-in maxlength="400">${esc(v)}</textarea>${actions}`;
  if (type === "number") return `<div class="edit-row"><input data-in type="number" min="1" max="10" value="${esc(v)}"></div>${actions}`;
  if (type === "budget") return `
    <div class="edit-row"><input data-min type="number" min="0" placeholder="Min ₹" value="${v.min_inr ?? ""}"><input data-max type="number" min="0" placeholder="Max ₹" value="${v.max_inr ?? ""}"></div>
    <div class="edit-row"><select data-period>${Object.entries(PERIODS).map(([k, l]) => `<option value="${k}" ${v.period === k ? "selected" : ""}>${l}</option>`).join("")}</select></div>
    <label class="check"><input type="checkbox" data-flex ${v.flexible ? "checked" : ""}> Flexible</label>
    <label class="check"><input type="checkbox" data-nofix ${v.no_fixed_budget ? "checked" : ""}> No fixed budget</label>${actions}`;
  if (type === "priorities") return `
    <div class="tags">${Object.entries(CRITERIA).map(([k, l]) => { const i = v.indexOf(k); return `<button class="tag ${i >= 0 ? "num" : ""}" data-crit="${k}">${i >= 0 ? i + 1 + ". " : ""}${l}</button>`; }).join("")}</div>
    <div class="missing" style="margin-top:6px">Click in order of importance; click again to remove.</div>${actions}`;
  return `<div class="edit-row"><input data-in maxlength="400" value="${esc(v)}"></div>${actions}`;
}

function startEdit(key) {
  state.editing = key;
  state.draft = JSON.parse(JSON.stringify(state.session.brief[key]));
  renderBrief();
}

function wireEditor(key) {
  const el = $(`.field[data-key="${key}"]`);
  if (!el) return;
  const type = el.dataset.type;
  const input = $("[data-in]", el);
  if (input) { input.focus(); if (input.select && type !== "list") input.select(); }
  const save = () => commitEdit(key, type, el);
  el.querySelector('[data-act="cancel"]').addEventListener("click", (e) => { e.stopPropagation(); state.editing = null; renderBrief(); });
  el.querySelector('[data-act="save"]').addEventListener("click", (e) => { e.stopPropagation(); save(); });
  if (type === "list") {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); if (input.value.trim()) { const b = clone(); b[key].push(input.value.trim()); putBrief(b, key); } else save(); }
      if (e.key === "Escape") { state.editing = null; renderBrief(); }
    });
  } else if (input && type !== "long") {
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); save(); } if (e.key === "Escape") { state.editing = null; renderBrief(); } });
  }
  if (type === "priorities") {
    el.querySelectorAll("[data-crit]").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      const k = b.dataset.crit; const arr = state.draft;
      const i = arr.indexOf(k); if (i >= 0) arr.splice(i, 1); else arr.push(k);
      $(".tags", el).innerHTML = Object.entries(CRITERIA).map(([c, l]) => { const j = arr.indexOf(c); return `<button class="tag ${j >= 0 ? "num" : ""}" data-crit="${c}">${j >= 0 ? j + 1 + ". " : ""}${l}</button>`; }).join("");
      wirePriorityButtons(el);
    }));
  }
}
function wirePriorityButtons(el) {
  el.querySelectorAll("[data-crit]").forEach((b) => b.addEventListener("click", (e) => {
    e.stopPropagation();
    const k = b.dataset.crit; const arr = state.draft;
    const i = arr.indexOf(k); if (i >= 0) arr.splice(i, 1); else arr.push(k);
    $(".tags", el).innerHTML = Object.entries(CRITERIA).map(([c, l]) => { const j = arr.indexOf(c); return `<button class="tag ${j >= 0 ? "num" : ""}" data-crit="${c}">${j >= 0 ? j + 1 + ". " : ""}${l}</button>`; }).join("");
    wirePriorityButtons(el);
  }));
}

const clone = () => JSON.parse(JSON.stringify(state.session.brief));

function commitEdit(key, type, el) {
  const b = clone();
  if (type === "list") { const v = $("[data-in]", el).value.trim(); if (v) b[key].push(v); }
  else if (type === "number") b[key] = Math.max(1, Math.min(10, parseInt($("[data-in]", el).value, 10) || 5));
  else if (type === "budget") {
    const num = (sel) => { const v = $(sel, el).value; return v === "" ? null : Number(v); };
    b.budget = { ...b.budget, min_inr: num("[data-min]"), max_inr: num("[data-max]"), period: $("[data-period]", el).value, flexible: $("[data-flex]", el).checked, no_fixed_budget: $("[data-nofix]", el).checked };
  } else if (type === "priorities") b[key] = state.draft;
  else b[key] = $("[data-in]", el).value.trim();
  state.editing = null;
  putBrief(b);
}

function removeItem(key, idx) {
  const b = clone();
  b[key].splice(idx, 1);
  putBrief(b, state.editing);
}

async function putBrief(brief, keepEditing = null) {
  try {
    const prev = state.session.brief;
    const s = await api(`/api/sessions/${state.session.id}/brief`, { method: "PUT", body: { brief } });
    state.session = s;
    state.editing = keepEditing;
    renderBrief(prev);
    renderStepper();
    renderQuick();
  } catch (e) {
    alert(e.message);
  }
}

/* ---------------- search ---------------- */

function openConfirm() {
  const b = state.session.brief;
  $("#confirmList").innerHTML = [
    `Find vendors for <b>${esc(b.service_category)}</b>${b.geography.length ? " in " + esc(b.geography.join(", ")) : ""}`,
    `Research up to <b>${b.top_k}</b> vendors against <b>${b.must_haves.length}</b> must-haves`,
    state.cfg.discovery === "CrustdataDiscovery"
      ? `Discovery: one Crustdata company search for up to <b>${b.top_k}</b> results, priced per result from your account and reserved before the call`
      : `Discovery: ${esc(state.cfg.discovery)} (no Crustdata search)`,
    `Vendor evaluation spend cap: <b>${state.cfg.search_credits} credits</b>${state.cfg.v1_connected ? "" : " (evaluator not connected, so nothing is spent)"}`,
    state.cfg.v1_connected ? "Every answer will cite its source and date, or say “cannot verify”." : "Note: the vendor evaluator is not connected in this build, so vendors will be listed without evidence.",
  ].map((x) => `<li>${x}</li>`).join("");
  $("#confirmDialog").showModal();
}

async function startSearch() {
  try {
    await api(`/api/sessions/${state.session.id}/search`, { method: "POST", body: { confirm: true } });
    await openSession(state.session.id);
  } catch (e) { alert(e.message); }
}

function stopPoll() { if (state.poll) { clearTimeout(state.poll); state.poll = null; } }

function hasEvaluations(r) {
  return Boolean(r.comparison) && Object.values(r.evaluations || {}).some(
    (e) => e.status && !["not_connected", "running"].includes(e.status));
}

async function pollSearch() {
  const id = state.session.id;
  try {
    const r = await api(`/api/sessions/${id}/search`);
    if (!state.session || state.session.id !== id) return;
    const wasRunning = state.search && state.search.run_id === r.run_id
      && !["done", "error"].includes(state.search.status);
    state.search = r;
    renderResults();
    renderStepper();
    if (r.status !== "done" && r.status !== "error") state.poll = setTimeout(pollSearch, 1200);
    else {
      refreshSessions();
      // Watched an evaluation finish: move on to the final verdict page.
      if (wasRunning && r.status === "done" && hasEvaluations(r)) {
        setTimeout(() => { location.href = `/verdict#${encodeURIComponent(id)}`; }, 1500);
      }
    }
  } catch (e) {
    state.poll = setTimeout(pollSearch, 3000);
  }
}

function renderStepper() {
  const s = state.session;
  const r = state.search;
  let active = "brief";
  const done = new Set();
  if (s.run_id) {
    done.add("brief");
    active = "discover";
    if (r && r.candidates) { done.add("discover"); active = "evaluate"; }
    if (r && r.status === "done") { done.add("evaluate"); done.add("compare"); active = null; }
  }
  document.querySelectorAll("#stepper li").forEach((li) => {
    li.classList.toggle("done", done.has(li.dataset.step));
    li.classList.toggle("active", li.dataset.step === active);
  });
}

const VERDICT = { supported: ["✓", "Supported"], partially_supported: ["◐", "Partially supported"], contradicted: ["✕", "Contradicted"], cannot_verify: ["?", "Cannot verify"] };

function renderResults() {
  const r = state.search;
  const view = $("#resultsView");
  if (!r || r.status === "not_started") { view.innerHTML = ""; return; }
  const cands = r.candidates || [];
  const evals = r.evaluations || {};
  const finished = cands.filter((c) => evals[c.key] && evals[c.key].status !== "running").length;
  const parts = [];

  // recommendation
  if (r.status === "error") {
    parts.push(`<div class="card rec none"><div class="rec-icon">!</div><div><h2>Search stopped</h2><div class="sub">${esc(r.error)}</div></div></div>`);
  } else if (r.comparison) {
    const c = r.comparison;
    parts.push(`<div class="card rec ${c.recommended_key ? "good" : "none"}">
      <div class="rec-icon">${c.recommended_key ? "★" : "?"}</div>
      <div><h2>${esc(c.recommendation)}</h2>${c.rationale.length ? `<ul>${c.rationale.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}</div></div>`);
  } else {
    const phase = r.candidates ? `Evaluating vendors · ${finished}/${cands.length}` : "Discovering relevant vendors…";
    parts.push(`<div class="card"><h3>${phase}</h3><div class="sub">Each vendor is researched against your brief. Completed work is saved, so a restart resumes here.</div>
      <div class="bar" style="margin-top:10px"><i style="width:${cands.length ? (100 * finished) / cands.length : 8}%"></i></div></div>`);
  }

  // vendor progress cards
  if (r.candidates) {
    if (!cands.length) {
      parts.push(`<div class="card empty-state"><div class="big">∅</div>No candidate vendors found.${state.cfg.discovery === "NotConnectedDiscovery" ? "<br>Discovery isn't connected yet: only vendors named in “Vendors to include” are evaluated." : ""}</div>`);
    } else {
      const score = {};
      (r.comparison?.ranking || []).forEach((x) => (score[x.candidate_key] = x));
      parts.push(`<div class="card"><h3>Vendors</h3><div class="sub">${(() => { const f = cands[0]?.discovery_fit; return f && f.pool_size ? `Best ${cands.length} of ${f.pool_size} companies retrieved (${esc(f.filters)}), reranked by discovery fit.` : `Top ${cands.length} in Crustdata relevance order.`; })()} Discovery fit is a shortlist heuristic from indexed descriptions, size and age, not evidence that a company meets your requirements.</div><div class="progress-list">${cands.map((c) => {
        const e = evals[c.key]; const st = e ? e.status : "queued"; const sc = score[c.key];
        const facts = [c.headquarters, c.employee_count_range && c.employee_count_range + " employees", c.year_founded && "founded " + c.year_founded].filter(Boolean).join(" · ");
        const fit = c.discovery_fit && c.discovery_fit.parts ? `<div class="sub fit">Discovery fit <b>${Math.round(c.discovery_fit.score * 100)}%</b> · brief match ${Math.round(c.discovery_fit.parts.brief_match * 100)}% · size ${Math.round(c.discovery_fit.parts.scale * 100)}% · maturity ${Math.round(c.discovery_fit.parts.maturity * 100)}% · region ${c.discovery_fit.parts.region ? "yes" : "no"} · provider rank #${c.rank}</div>` : "";
        return `<div class="vcard"><div class="name">${esc(c.name)}</div>${fit}<div class="dom">${esc(c.domain || "")}${facts ? " · " + esc(facts) : ""}</div>
          ${c.why_relevant ? `<div class="sub desc">${esc(c.why_relevant.length > 280 ? c.why_relevant.slice(0, 280) + "…" : c.why_relevant)}</div>` : ""}
          ${c.discovery_source ? `<div class="sub src">Source: ${esc(c.discovery_source)}</div>` : ""}
          <span class="pill ${st}">${st === "running" ? '<span class="spin"></span>' : ""}${esc(st.replace("_", " "))}</span>
          ${sc && st !== "not_connected" ? `<div class="sub">${sc.must_have_supported}/${sc.must_have_total} critical supported · ${sc.credits.toFixed(1)} credits</div>` : ""}
          ${e?.result?.notes ? `<div class="sub">${esc(e.result.notes)}</div>` : ""}</div>`;
      }).join("")}</div></div>`);
    }
  }

  // matrix
  const qs = r.spec.questions;
  const evaluated = cands.filter((c) => evals[c.key]?.result?.answers?.length);
  if (evaluated.length) {
    const ranking = r.comparison?.ranking || [];
    const order = ranking.length ? ranking.map((x) => evaluated.find((c) => c.key === x.candidate_key)).filter(Boolean) : evaluated;
    const best = r.comparison?.recommended_key;
    parts.push(`<div class="card"><h3>Requirement matrix</h3><div class="sub">Click a cell for the evidence behind it.</div>
      <div class="legend">${Object.entries(VERDICT).map(([k, [i, l]]) => `<span><span class="v ${k}">${i}</span>${l}</span>`).join("")}</div>
      <div class="matrix-wrap"><table class="matrix"><thead><tr><th>Requirement</th>${order.map((c) => `<th class="${c.key === best ? "best" : ""}">${c.key === best ? "★ " : ""}${esc(c.name)}</th>`).join("")}</tr></thead>
      <tbody>${qs.map((q) => `<tr><td><div class="kind">${esc(q.kind.replace("_", " "))}</div>${esc(q.text)}</td>${order.map((c) => {
        const a = evals[c.key].result.answers.find((x) => x.question_id === q.id);
        const v = a ? a.verdict : "none";
        return `<td><button class="v ${v}" data-c="${c.key}" data-q="${q.id}" title="${a ? VERDICT[v][1] : "Not answered"}">${a ? VERDICT[v][0] : "–"}</button></td>`;
      }).join("")}</tr>`).join("")}</tbody>
      <tfoot><tr><td>Score</td>${order.map((c) => { const s = ranking.find((x) => x.candidate_key === c.key); return `<td>${s ? Math.round(s.score * 100) + "%" : "–"}</td>`; }).join("")}</tr></tfoot></table></div></div>`);
  }

  // vendor questions
  if (r.comparison && Object.values(r.comparison.vendor_questions).some((x) => x.length)) {
    parts.push(`<div class="card vq"><h3>Questions to send each vendor</h3><div class="sub">Unresolved requirements become questions — nothing is sent automatically.</div>
      ${cands.filter((c) => r.comparison.vendor_questions[c.key]?.length).map((c) => `<h4>${esc(c.name)}</h4><ul class="qlist">${r.comparison.vendor_questions[c.key].map((q) => `<li>${esc(q)}</li>`).join("")}</ul>`).join("")}</div>`);
  }

  parts.push(`<div class="card"><h3>Search spec</h3><div class="sub">Derived only from the approved brief</div><dl class="kv">
    <dt>Run</dt><dd>${esc(r.run_id)}</dd><dt>Category</dt><dd>${esc(r.spec.category)}</dd>
    <dt>Semantic query</dt><dd>${esc(r.spec.semantic_query || r.spec.queries.join(" | "))}</dd><dt>Mode</dt><dd>${esc(r.spec.search_mode || "")}</dd><dt>Requirements</dt><dd>${qs.length}</dd><dt>Top k</dt><dd>${r.spec.top_k}</dd></dl></div>`);

  if (r.status === "done" && hasEvaluations(r)) {
    parts.splice(1, 0, `<div class="card verdict-cta"><h3>Final verdict is ready</h3><div class="sub">Verdict, scorecard, evidence and recommended next steps on one page.</div><a class="btn primary" href="/verdict#${encodeURIComponent(state.session.id)}">Open final verdict →</a></div>`);
  }
  const pendingEval = state.cfg.v1_connected && (r.status === "done" || r.status === "error")
    && cands.some((c) => (evals[c.key]?.status || "not_connected") === "not_connected");
  if (pendingEval) {
    parts.splice(1, 0, `<div class="card"><h3>Evaluate this shortlist</h3><div class="sub">Runs the V1 evidence review on each listed vendor in parallel, using your saved brief. Discovery is not repeated. Spend is capped per vendor at ${(state.cfg.search_credits / Math.max(1, cands.length)).toFixed(2)} credits (${state.cfg.search_credits} total).</div><button class="btn primary" id="evaluateShortlist">Evaluate ${cands.length} vendors with V1</button></div>`);
  }
  view.innerHTML = parts.join("");
  view.querySelectorAll(".v[data-c]").forEach((b) => b.addEventListener("click", () => showEvidence(b.dataset.c, b.dataset.q)));
  const ev = view.querySelector("#evaluateShortlist");
  if (ev) ev.addEventListener("click", async () => {
    if (!confirm(`Approve spending up to ${state.cfg.search_credits} Crustdata credits to evaluate ${cands.length} vendors?`)) return;
    ev.disabled = true; ev.textContent = "Starting…";
    try {
      await api(`/api/sessions/${state.session.id}/search/evaluate`, { method: "POST", body: { confirm: true } });
      pollSearch();
    } catch (e) { ev.disabled = false; ev.textContent = "Evaluate with V1"; alert(e.message || e); }
  });
}

function showEvidence(ckey, qid) {
  const r = state.search;
  const c = r.candidates.find((x) => x.key === ckey);
  const q = r.spec.questions.find((x) => x.id === qid);
  const a = r.evaluations[ckey].result.answers.find((x) => x.question_id === qid);
  const v = a ? a.verdict : "none";
  $("#drawerBody").innerHTML = `
    <div class="sub">${esc(c.name)}</div><h3>${esc(q.text)}</h3>
    <span class="pill ${v === "supported" ? "completed" : v === "contradicted" ? "failed" : v === "partially_supported" ? "partial" : "queued"}">${a ? VERDICT[v][1] : "Not answered"}</span>
    ${a ? `<p>${esc(a.summary)}</p>` : ""}
    ${a && a.evidence.length ? a.evidence.map((e) => `<div class="ev"><blockquote>${esc(e.passage_or_field)}</blockquote>
      <div class="src">${e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.url)}</a>` : esc(e.artifact_id)}<br>
      ${e.publisher ? esc(e.publisher) + " · " : ""}Source date: ${esc(e.source_date || "unknown")} · Retrieved: ${esc(e.retrieved_at || "unknown")}</div></div>`).join("") : `<div class="ev"><div class="src">No source settles this.</div></div>`}
    ${a && a.missing ? `<p class="sub"><b>Missing:</b> ${esc(a.missing)}</p>` : ""}`;
  $("#drawer").hidden = false;
}

/* ---------------- layout ---------------- */

function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $("#chatView").hidden = tab !== "chat";
  $("#resultsView").hidden = tab !== "results";
}

function closeDrawers() { $("#app").classList.remove("show-side", "show-brief"); }

document.addEventListener("DOMContentLoaded", () => {
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); send($("#input").value); });
  $("#input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send($("#input").value); } });
  $("#input").addEventListener("input", autosize);
  $("#newSession").addEventListener("click", () => { newSession(); closeDrawers(); });
  $("#startSearch").addEventListener("click", openConfirm);
  $("#confirmDialog").addEventListener("close", () => { if ($("#confirmDialog").returnValue === "ok") startSearch(); });
  $("#tabs").addEventListener("click", (e) => { const b = e.target.closest("button[data-tab]"); if (b) setTab(b.dataset.tab); });
  $("#drawerClose").addEventListener("click", () => ($("#drawer").hidden = true));
  $("#drawer").addEventListener("click", (e) => { if (e.target.id === "drawer") $("#drawer").hidden = true; });
  $("#toggleSidebar").addEventListener("click", () => $("#app").classList.toggle("show-side"));
  $("#toggleBrief").addEventListener("click", () => $("#app").classList.toggle("show-brief"));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { $("#drawer").hidden = true; closeDrawers(); } });
  boot();
});
