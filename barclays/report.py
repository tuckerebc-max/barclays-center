"""The human-readable bout report. Built only from recorded results; nothing here is computed from prose."""
from __future__ import annotations

from .weighin import findings_and_leads

MEANING = {
    "RECOMMEND": "One candidate passed every decisive check and won the bracket. The owner decides.",
    "NO_CHANGE": "Nothing was shown to be better than the baseline.",
    "TIED_SHORTLIST": "No clear winner: the leading candidates tie or form a cycle. The owner chooses.",
    "INCONCLUSIVE": "The evidence does not support a decision either way.",
    "NO_ELIGIBLE_CANDIDATE": "Nothing passed the decisive checks. Repair needs are listed below.",
}


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_report(bout: dict, event: dict, weigh_in: dict, verdict: dict) -> str:
    v = verdict
    out = [f"# Bout report: {bout['bout_id']}", "",
           f"Event: **{event['title']}** (`{event['event_id']}`). Material: `{bout['sensitivity']}`.", "",
           f"## Verdict: {v['status']}", ""]
    if event.get("status") == "officials_runnable":
        # This kind of event stops at people on purpose. Say who is still standing, and that it is not a ranking.
        elig = v["eligibility"]
        standing = [c for c, e in elig.items() if e["status"] == "eligible"]
        out_ = [c for c, e in elig.items() if e["status"] == "disqualified"]
        unknown = [c for c, e in elig.items() if e["status"] == "incomplete"]
        out += ["This event has no model judging. The checks say who is out; a person decides among the rest.", "",
                "- Still standing after the checks: " + (", ".join(f"`{c}`" for c in standing) or "nobody") + ".",
                "- Removed by a decisive check: " + (", ".join(f"`{c}`" for c in out_) or "nobody") + "."]
        if unknown:
            out.append("- Not established (a decisive check could not run): "
                       + ", ".join(f"`{c}`" for c in unknown) + ". That is not a loss.")
        out += ["", "Still standing is not a ranking and not a recommendation. Passing these checks does not show "
                    "the work is good for the people it is for.", ""]
    else:
        out += [MEANING[v["status"]], ""]
    if v["recommended"]:
        out.append("Recommended: " + ", ".join(
            f"`{c}` (content `{v['eligibility'][c]['content_hash'][:12]}`)" for c in v["recommended"]))
    if v["shortlist"]:
        out.append("Shortlist: " + ", ".join(f"`{c}`" for c in v["shortlist"]))
    out += ["Acceptance: `pending_owner`. Barclays recommends; it does not accept, release or publish.", ""]

    out += ["## What kind of evidence this is", "",
            "| Stage | Evidence |", "|---|---|"]
    for stage, grade in v["evidence_grade"].items():
        out.append(f"| {stage.replace('_', ' ')} | {grade} |")
    out.append("")

    if v["reasons"]:
        out += ["## Why", ""] + [f"- {r}" for r in v["reasons"]] + [""]
    if v["flags"]:
        out += ["## Flags", ""] + [f"- `{f}`" for f in v["flags"]] + [""]

    hd = v["human_decision"]
    out += ["## Does a human need to decide?", ""]
    if hd["required"]:
        out += ["**Yes.**"] + [f"- {b}" for b in hd["because"]]
    else:
        out += ["No rule on this event card requires it. The owner still accepts or rejects."]
    if hd["boundary"]:
        out += ["", "What this event cannot establish without human evidence:"] + [f"- {b}" for b in hd["boundary"]]
    out.append("")

    officials = []
    for r in weigh_in["results"]:
        if r["official_id"] not in officials:
            officials.append(r["official_id"])
    out += ["## Weigh-in", "",
            "Decisive checks run before any judge sees a candidate. `fail` on a decisive check disqualifies; "
            "`unverified` leaves the candidate incomplete, which is not a loss.", "",
            "| Candidate | Eligibility | " + " | ".join(f"`{o}`" for o in officials) + " |",
            "|---|---|" + "---|" * len(officials)]
    for cand in bout["candidates"]:
        cid = cand["id"]
        cells = []
        for oid in officials:
            res = next((r for r in weigh_in["results"] if r["candidate_id"] == cid and r["official_id"] == oid), None)
            if res is None:
                cells.append("—")
            else:
                decisive = res["authority"] == "disqualify" and (res["applies_to"] == "all" or not res["is_baseline"])
                cells.append(res["status"] + ("" if decisive else " (advisory)"))
        name = f"`{cid}`" + (" (baseline)" if cid == bout.get("baseline") else "")
        out.append(f"| {name} | {v['eligibility'][cid]['status']} | " + " | ".join(cells) + " |")
    out.append("")
    for cand in bout["candidates"]:
        e = v["eligibility"][cand["id"]]
        if e["reasons"]:
            out.append(f"`{cand['id']}` is {e['status']}:")
            out += [f"- {_cell(r)}" for r in e["reasons"]]
    out.append("")

    out += ["## Findings and leads", "",
            "Findings are objective and reproducible. Leads are heuristic pointers for a reviewer and never change "
            "eligibility.", ""]
    for cand in bout["candidates"]:
        findings, leads = findings_and_leads(weigh_in, cand["id"])
        if not findings and not leads:
            continue
        out.append(f"### `{cand['id']}`")
        out += [f"- finding [{f['tool']}] ({f['severity']}) {_cell(f['claim'])}" for f in findings]
        out += [f"- lead [{item['tool']}] ({item['severity']}) {_cell(item['note'])}" for item in leads]
        out.append("")

    b = v["bracket"]
    if b:
        out += ["## Bracket", "",
                f"Controller: `{b['controller']['name']}` ({b['controller']['schema']}), commit "
                f"`{(b['controller']['commit'] or 'unknown')[:12]}`. Contract `{(b['contract_hash'] or '')[:12]}`. "
                f"Operational status: {b['operational_status']}.", ""]
        if b["composites"]:
            out += ["| Candidate | Composite (0-100) |", "|---|---|"]
            out += [f"| `{cid}` | {score if score is not None else '—'} |" for cid, score in b["composites"].items()]
            out.append("")
        usage = b["usage"] or {}
        out.append(f"Judge calls used: {usage.get('calls_used')} (planned upper bound {b['planned_calls_upper']}); "
                   f"tokens: {usage.get('tokens_used')}.")
        out.append("")
    gx = v.get("model_gate_exclusions")
    if gx:
        out += ["## Excluded by a model gate (a judgment, not a check)", "",
                "These candidates passed every executed check in the weigh-in. Inside the bracket, model judges "
                "ruled that they break a gate on the event card, and the controller removed them. That ruling is "
                "models' reading of the text. A person should confirm it before treating the candidate as "
                "defective.", ""]
        for cid, why in gx["candidates"].items():
            out.append(f"`{cid}`:")
            out += [f"- {_cell(w)}" for w in why]
        out.append("")
    pv = v.get("panel")
    if pv:
        out += ["## Perspective panel (advisory, no authority)", "",
                f"{pv['valid_results']} valid result(s) from {pv['packets']} packet(s); "
                f"{pv['order_sensitive']} reviewer unit(s) changed their preference with display order and were "
                "counted as abstaining.", ""]
        roster = pv.get("roster") or {}
        if roster:
            out += [f"Who sat on the panel ({roster.get('source')}): "
                    + ", ".join(f"`{x['lens_id']}` ({str(x['kind']).replace('_', ' ')})"
                                for x in roster.get("lenses", [])) + ". "
                    + ("" if roster.get("fact_desk_present") else
                       "**No lens on this panel was briefed to check facts.** ")
                    + "A lens is a way of reading; none of them decides what is true.", ""]
        out += [
                "| Lens | Kind | Reviewer | Pair | Tool output shown | Outcome | Preferred | Margin (0-5) |",
                "|---|---|---|---|---|---|---|---|"]
        for u in pv["units"]:
            out.append(f"| `{u['lens_id']}` | {str(u['lens_kind']).replace('_', ' ')} | {u['reviewer_slot']} | "
                       f"{' vs '.join(u['pair'])} | {u['leads_mode']} | {u['outcome']} | "
                       f"{u['preferred'] or '—'} | {u.get('margin') if u.get('margin') is not None else '—'} |")
        out += ["",
                f"- Objections inside a lens's own lane: {pv['objections_in_lane']}; outside it (read, not "
                f"counted): {pv['objections_out_of_lane']}.",
                f"- Factual allegations still unverified: {pv['allegations_open']}, of which "
                f"{pv['allegations_from_non_fact_lenses']} came from lenses with no brief to check facts. An "
                "allegation counts for nothing until an official or a person confirms it.",
                f"- Of those, {pv.get('allegations_filed_as_opinion', 0)} were filed by the reviewer as opinions and "
                f"read as claims about facts or the source, and {pv.get('allegations_unattributed', 0)} named no "
                "candidate and count against the pair. Reviewer results that needed a note: "
                f"{pv.get('results_with_notes', 0)}.",
                "- A panel preferred a candidate the weigh-in disqualified: "
                + (", ".join(f"`{c}`" for c in pv["preferred_a_disqualified_candidate"]) or "no") + ".", ""]
    sb = v["shadow_bracket"]
    if sb:
        out += ["## Shadow bracket (diagnostic, no authority)", "",
                "The same judges over every candidate with the weigh-in and gates switched off. It shows what "
                "judging alone would have done. When the judges are simulated, their perceptions were supplied by "
                "the fixture: this then shows the venue holding against a judge that prefers polish, and says "
                "nothing about what a real model would prefer.", "",
                f"- Status: {sb['status']}; recommended: {sb['recommended'] or 'none'}; ranking: "
                f"{', '.join(sb['ranking']) or 'n/a'}",
                f"- Top-ranked candidate was one the weigh-in disqualified: "
                f"{'YES' if sb['top_ranked_was_disqualified'] else 'no'}", ""]

    p = v["provenance"]
    out += ["## Exact versions", "",
            f"- Event card `{p['event_sha256'][:16]}`, bout `{p['bout_sha256'][:16]}`",
            "- Candidates: " + ", ".join(f"`{cid}` `{h[:12]}`" for cid, h in p["candidates"].items()),
            "- Officials: " + ", ".join(f"`{oid}` = {name} {ver}" for oid, name, ver in p["officials"]),
            "- Every object is in `objects/` by SHA-256 and chained in `ledger.jsonl`. Check with "
            "`python bc.py verify <run directory>`.", ""]
    return "\n".join(out)
