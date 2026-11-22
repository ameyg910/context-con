"""Escaped, standalone HTML dossier with immutable local snapshots and a JSON companion."""

import html
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from vendor_review.intake import readiness
from vendor_review.research import sources

STATUS_LABELS = {
    "vendor_documented": "Documented by the vendor",
    "partially_supported": "Partly supported — gaps remain",
    "conflicting_vendor_docs": "Vendor documents disagree — review needed",
    "cannot_verify": "Cannot verify from the available evidence",
}


def details(label, content):
    return f"<details><summary>{esc(label)}</summary>{content}</details>"


def esc(value):
    return html.escape(str(value), quote=True)


def link(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return esc(url)
    return f'<a href="{esc(url)}" rel="noreferrer noopener">{esc(url)}</a>'


def render_report(state, thread, budget, operations):
    brief = state.get("brief", {})
    intake = readiness(brief)
    findings = {f["requirement_id"]: f for f in state.get("findings", [])}
    pages = sources(state.get("messages", []))
    rows = []
    for requirement in brief.get("requirements", []):
        finding = findings.get(requirement["id"], {})
        evidence = []
        for citation in finding.get("citations", []):
            page = pages.get((citation["artifact_id"], citation["url"]), {})
            retrieved = page.get("retrieved_at_unix")
            date = (
                datetime.fromtimestamp(retrieved, timezone.utc).isoformat()
                if retrieved
                else "unknown"
            )
            evidence.append(
                f"<blockquote>{esc(citation['quote'])}</blockquote>{link(citation['url'])}"
                + details(
                    "Retrieval details",
                    f"<p>Artifact {esc(citation['artifact_id'])} · retrieved {esc(date)}<br>"
                    f"Publication/event date: unknown unless established in passage. "
                    f"Quality: {esc(', '.join(page.get('quality', [])))}</p>",
                )
            )
        steps = finding.get("verification_steps") or [
            "Fetch relevant product/developer documentation and inspect exact support for this requirement.",
            "Request a scoped demonstration or reproducible pilot with explicit pass/fail criteria.",
            "Later: seek customer-owned corroboration and relevant professional artifacts.",
        ]
        rows.append(
            "<tr>"
            + "".join(
                f"<td>{cell}</td>"
                for cell in (
                    f"<strong>{esc(requirement['id'])} · {esc(requirement['text'])}</strong>"
                    + details(
                        "Original buyer wording", f"<p>{esc(requirement['buyer_quote'])}</p>"
                    ),
                    f"{esc({'must': 'Required', 'should': 'Preferred', 'question': 'Research question', 'unspecified': 'Needs clarification'}.get(requirement['priority'], requirement['priority']))}<p>What would count as passing: {esc(requirement.get('acceptance_criterion') or 'Needs clarification')}</p>",
                    esc(finding.get("claim", "This question has not been researched yet.")),
                    f'<span class="status">{esc(STATUS_LABELS.get(finding.get("status", "cannot_verify"), "Needs review"))}</span>'
                    "<p>Independently verified: <strong>No</strong></p>",
                    details(f"Read {len(evidence)} supporting passage(s)", "".join(evidence))
                    if evidence
                    else "No supporting page passage recorded yet. Search snippets alone cannot verify this claim.",
                    esc(
                        finding.get(
                            "limitations",
                            "Research not completed; absence of evidence is not evidence of failure.",
                        )
                    ),
                    "<ol>"
                    + "".join(f"<li>{esc(step)}</li>" for step in steps[:2])
                    + "</ol>"
                    + (
                        details(
                            "More verification steps",
                            "<ol start='3'>"
                            + "".join(f"<li>{esc(step)}</li>" for step in steps[2:])
                            + "</ol>",
                        )
                        if len(steps) > 2
                        else ""
                    ),
                )
            )
            + "</tr>"
        )
    if not rows:
        rows = [
            '<tr><td colspan="7">Intake incomplete: no buyer requirements recorded yet.</td></tr>'
        ]
    questions = "".join(f"<li>{esc(q)}</li>" for q in intake["questions"])
    constraints = "".join(
        f"<dt>{esc(key)}</dt><dd>{esc(value)}</dd>"
        for key, value in brief.get("constraints", {}).items()
    )
    source_rows = "".join(
        f"<tr><td>{link(p.get('url') or 'unknown')}</td><td>{esc(p['artifact_id'])}</td>"
        f"<td>{esc(p.get('title'))}</td><td>{esc(p.get('content_sha256'))}</td></tr>"
        for p in pages.values()
    )
    operation_rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{esc(op.get(key))}</td>"
            for key in ("kind", "name", "status", "reserved", "actual", "tokens")
        )
        + "</tr>"
        for op in operations
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{esc(brief.get("vendor") or "Buyer intake")} — preliminary evidence review</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;margin:0;color:#182536;background:#f4f7fa}}main{{max-width:1600px;margin:auto;padding:32px}}h1{{font-size:30px}}h2{{margin-top:32px}}.notice{{background:#fff3cf;padding:18px;border-left:5px solid #b47a00}}.summary{{display:flex;gap:20px;flex-wrap:wrap}}.card{{background:white;padding:20px;border-radius:12px;flex:1}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{border:1px solid #d5dee8;padding:14px;text-align:left;vertical-align:top;min-width:130px;overflow-wrap:anywhere}}th{{background:#183348;color:white}}blockquote{{margin:8px 0;padding-left:12px;border-left:3px solid #7297b7}}p{{margin:8px 0}}.status{{font-weight:700;color:#31516e}}details{{margin:12px 0}}summary{{cursor:pointer;font-weight:600;color:#31516e}}details[open]{{padding-bottom:12px}}dt{{font-weight:700}}dd{{margin-bottom:10px}}@media print{{main{{padding:0}}body{{background:white}}th{{color:black;background:#eee}}.scroll{{overflow:visible}}table{{font-size:10px}}td,th{{min-width:0;padding:6px}}}}</style></head><body><main>
<h1>{esc(brief.get("vendor") or "Buyer intake")} · preliminary vendor evidence review</h1>
<p>Thread {esc(thread)} · generated {datetime.now(timezone.utc).isoformat()} · {esc(brief.get("domain", ""))}</p>
<div class="notice">Vendor-document review only. Customer corroboration and professional research are pending.
Documented claims do not establish independent verification, production outcomes, security certification or supplier approval.</div>
<div class="summary"><section class="card"><h2>Buyer purpose</h2><p>{esc(brief.get("use_case") or "Needs clarification")}</p>
<p>Intake completeness: <strong>{intake["completeness_score"]}/100</strong>. {esc(intake["score_meaning"])}</p>
<p>Requirement specificity: <strong>{intake["specificity_score"]}/100</strong> (declared priority and acceptance criteria; not a vendor rating).</p>
<p>Assessment: {"partial" if len(findings) < len(brief.get("requirements", [])) or not intake["ready"] else "preliminary vendor review recorded"}.
Coverage: {len(findings)} of {len(brief.get("requirements", []))} requirements have recorded findings.</p></section>
<section class="card"><h2>Constraints and open questions</h2><dl>{constraints}</dl><ul>{questions}</ul></section></div>
<h2>What we found</h2><p>Read the finding, evidence status and next steps first. Expand any source to see the exact passage. Ask in chat about a requirement ID for a source-backed explanation; questions beyond the saved evidence need further research.</p><div class="scroll"><table><thead><tr>
<th>Your requirement</th><th>Priority and pass condition</th><th>Finding</th><th>How well is it supported?</th>
<th>Supporting sources</th><th>What remains uncertain?</th><th>Steps to verify</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<details><summary>Explore all studied sources</summary><p>Identical content hashes indicate repeated content, not independent corroboration. Source relevance and semantic support still require review.</p>
<div class="scroll"><table><tr><th>URL</th><th>Artifact</th><th>Title</th><th>Content hash</th></tr>{source_rows}</table></div>
</details><details><summary>Research activity and cost details</summary><pre>{esc(json.dumps(budget, indent=2))}</pre>
<p>Credits in operation rows use millionths of a Crustdata credit. Model monetary prices and errors are in the JSON companion/CLI ledger; unknown charges retain reservations.</p>
<div class="scroll"><table><tr><th>Kind</th><th>Operation</th><th>Status</th><th>Reserved units</th><th>Observed units</th><th>Model tokens</th></tr>{operation_rows}</table></div>
</details></main></body></html>"""


def write_report(state, ledger, thread, settings):
    directory = settings.data_dir.parent / "reports" / thread
    directory.mkdir(parents=True, exist_ok=True)
    budget, operations = ledger.summary(thread), ledger.recent(thread, limit=10000)
    snapshot = settings.redact(
        {
            "brief": state.get("brief", {}),
            "findings": state.get("findings", []),
            "intake": readiness(state.get("brief")),
            "budget": budget,
            "operations": operations,
            "sources": list(sources(state.get("messages", [])).values()),
            "deferred_branches": ["Customer corroboration", "Professional research"],
        }
    )
    stem = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    content = settings.redact(render_report(state, thread, budget, operations))
    path = directory / (stem + ".html")
    path.write_text(content, encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    temporary = directory / "latest.tmp"
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(directory / "latest.html")
    return path.resolve()
