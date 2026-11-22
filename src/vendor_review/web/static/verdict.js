/* Final verdict page: renders /api/sessions/{id}/verdict. All text is escaped. */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");
const ICON = { recommend: "✓", leading_candidate: "!", no_evidence: "?", pending: "…" };

function evidence(item, cls) {
  const url = safeUrl(item.url);
  return `<div class="ev ${cls}"><div class="req">${esc(item.requirement)}</div>
    ${item.quote ? `<blockquote>“${esc(item.quote)}”</blockquote>` : ""}
    ${url ? `<a href="${esc(url)}" target="_blank" rel="noreferrer noopener">${esc(url)}</a>` : ""}
    ${cls === "part" && item.missing ? `<div class="note">Open: ${esc(item.missing)}</div>` : ""}
    ${item.retrieved_at ? `<div class="note">Retrieved ${esc(item.retrieved_at.slice(0, 10))}</div>` : ""}</div>`;
}

function render(v) {
  document.title = `Final verdict · ${v.brief.service || "Vendor search"}`;
  document.getElementById("subtitle").textContent =
    [v.brief.service, v.brief.budget, v.brief.timeline].filter(Boolean).join(" · ");
  const parts = [];
  parts.push(`<section class="hero ${esc(v.verdict)}"><div class="icon">${ICON[v.verdict] || "?"}</div><div>
    <h1>${esc(v.headline)}</h1><p>${esc(v.detail)}</p>
    <div class="facts">
      <span class="chip">${v.vendors.length} vendors evaluated</span>
      <span class="chip">${v.brief.must_haves.length} must-haves</span>
      <span class="chip">${esc(v.total_credits)} Crustdata credits for evaluation</span>
      <span class="chip">Independently verified: No</span>
    </div></div></section>`);

  parts.push(`<div class="section-title">Scorecard</div><div class="scoreboard">${v.vendors.map((x, i) => {
    const pct = x.critical_total ? Math.round((100 * x.critical_supported) / x.critical_total) : 0;
    const facts = [x.headquarters, x.size && `${x.size} employees`, x.founded && `founded ${x.founded}`].filter(Boolean).join(" · ");
    return `<div class="vendor ${x.key === v.leader_key ? "leader" : ""}">
      <div class="rank">${x.key === v.leader_key ? (v.verdict === "recommend" ? "Recommended" : "Leading candidate") : `#${i + 1}`}</div>
      <div class="name">${esc(x.name)}</div>
      <div class="meta">${esc(x.domain)}${facts ? " · " + esc(facts) : ""}</div>
      <div class="meter" title="${pct}% of critical requirements supported"><span style="width:${pct}%"></span></div>
      <div class="meta"><b>${x.critical_supported}/${x.critical_total}</b> critical requirements supported</div>
      <div class="counts">
        <span class="count ok">${x.supported.length} supported</span>
        <span class="count part">${x.partial.length} partial</span>
        <span class="count unk">${x.unverified.length} unverified</span>
        ${x.disqualified_by.length ? `<span class="count bad">contradicted</span>` : ""}
      </div></div>`;
  }).join("")}</div>`);

  parts.push(`<div class="section-title">Recommended next steps</div><div class="recs">${v.recommendations.map((r) =>
    `<div class="rec"><div class="t">${esc(r.title)}</div><div class="d">${esc(r.detail)}</div></div>`).join("")}</div>`);

  parts.push(`<div class="section-title">Evidence by vendor</div>${v.vendors.map((x) => `
    <details class="vdetail" ${x.key === v.leader_key ? "open" : ""}><summary><span>${esc(x.name)}</span>
      <span class="counts"><span class="count ok">${x.supported.length}</span><span class="count part">${x.partial.length}</span><span class="count unk">${x.unverified.length}</span></span></summary>
      <div class="vbody">
        ${x.supported.map((e) => evidence(e, "")).join("") || `<div class="unv">No requirement fully supported by published evidence.</div>`}
        ${x.partial.map((e) => evidence(e, "part")).join("")}
        ${x.unverified.length ? `<div class="unv"><b>Not verified from public sources:</b> ${x.unverified.map(esc).join("; ")}</div>` : ""}
      </div></details>`).join("")}`);

  parts.push(`<div class="section-title">How to read this</div><ul class="caveats">${v.caveats.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>`);
  document.getElementById("verdict").innerHTML = parts.join("");
}

async function load() {
  const sid = location.hash.slice(1) || new URLSearchParams(location.search).get("s");
  const back = document.getElementById("back");
  if (sid) back.href = `/#${encodeURIComponent(sid)}`;
  document.getElementById("print").addEventListener("click", () => {
    document.querySelectorAll("details.vdetail").forEach((d) => (d.open = true));
    window.print();
  });
  if (!sid) {
    document.getElementById("verdict").innerHTML = `<div class="card">No search selected.</div>`;
    return;
  }
  const res = await fetch(`/api/sessions/${encodeURIComponent(sid)}/verdict`);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    document.getElementById("verdict").innerHTML = `<div class="card"><h3>Verdict not ready</h3><div class="sub">${esc(data.detail || "The evaluation has not finished yet.")}</div></div>`;
    return;
  }
  render(data);
}
load();
