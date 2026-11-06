"""The verdict: one record that binds the weigh-in, the panel and the bracket to exact versions.

The status vocabulary is the controller's: RECOMMEND, NO_CHANGE, TIED_SHORTLIST, INCONCLUSIVE,
NO_ELIGIBLE_CANDIDATE. Barclays adds flags and an explicit statement of which parts of the result were executed,
which were judged by real models, and which were simulated. A verdict is a recommendation. Acceptance is always
`pending_owner`.
"""
from __future__ import annotations

from . import VERDICT_SCHEMA, __version__
from .errors import BarclaysError
from .weighin import findings_and_leads


def _human_rules(event: dict, status: str, bout: dict, judges: str, bracket_ran: bool, weigh_in: dict,
                 finalists: list, panel: dict | None, gate_excluded: dict) -> list:
    because = []
    for rule in event.get("human_decides_when", []):
        if rule == "always":
            because.append("always: this event's central claims need human evidence")
        elif rule.startswith("on_status:") and status == rule.split(":", 1)[1]:
            because.append(f"status is {status}")
        elif rule == "simulated_judges" and judges == "sim" and bracket_ran:
            because.append("judging was simulated; a simulated bracket is a dry run, not evidence")
        elif rule == "open_critical_leads":
            for cid in finalists:
                _, leads = findings_and_leads(weigh_in, cid)
                hot = [item["id"] for item in leads if item["severity"] in ("major", "critical")]
                if hot:
                    because.append(f"unreviewed leads on '{cid}': {', '.join(hot[:6])}")
        elif rule == "unverified_allegations" and panel:
            # An allegation that names no candidate counts against both members of the pair it was raised on.
            open_ = [a for a in panel.get("allegations", []) if a["status"] == "unverified" and (
                a.get("candidate_id") in finalists
                or (a.get("candidate_id") is None and set(a.get("pair") or []) & set(finalists)))]
            if open_:
                loose = sum(1 for a in open_ if a.get("candidate_id") is None)
                because.append(f"{len(open_)} unverified factual allegation(s) against a finalist"
                               + (f" ({loose} name no candidate and count against the pair)" if loose else ""))
        elif rule == "model_gate_exclusion" and gate_excluded:
            because.append("a model gate inside the bracket excluded " + ", ".join(f"'{c}'" for c in sorted(gate_excluded))
                           + "; that is a judgment by models, not an executed check, and a person should confirm it")
        elif rule.startswith("sensitivity_not_in:"):
            if bout["sensitivity"] not in rule.split(":", 1)[1].split(","):
                because.append(f"material is labelled '{bout['sensitivity']}'")
    # Not a card rule and not switchable: a bout that changed a decisive check's settings, even one the card lets
    # it change, is something a person confirms (third review, R3-06: `allow` can whitelist an invented figure).
    decisive = {o["id"] for o in event.get("officials", []) if o.get("authority") == "disqualify"}
    changed = [f"{oid}.{name} = {value!r}"
               for oid, vals in sorted(((bout.get("_overrides") or {}).get("officials") or {}).items())
               if oid in decisive for name, value in sorted(vals.items())]
    if changed:
        because.append(("the bout changed settings of a decisive check: " + "; ".join(changed))[:400]
                       + ". The event card allows it; a person should confirm it was justified")
    return because


def build_verdict(bout: dict, event: dict, weigh_in: dict, bracket: dict | None, shadow: dict | None,
                  panel: dict | None, judges: str, controller: dict | None, no_bracket_reason: str = "") -> dict:
    elig = weigh_in["eligibility"]
    baseline = bout.get("baseline")
    challengers = [cid for cid in elig if cid != baseline]
    eligible = [cid for cid in challengers if elig[cid]["status"] == "eligible"]
    incomplete = [cid for cid in challengers if elig[cid]["status"] == "incomplete"]
    disqualified = [cid for cid in elig if elig[cid]["status"] == "disqualified"]
    flags, reasons = [], []
    recommended, shortlist = [], []
    decision = (bracket or {}).get("decision")

    if decision is not None:
        d = decision["decision"]
        status = d["status"]
        recommended = list(d.get("recommended") or [])
        shortlist = list(d.get("shortlist") or [])
        reasons += list(d.get("reasons") or [])
        flags += [f"ATR:{f}" for f in d.get("flags") or []]
        bad = [cid for cid in recommended + shortlist if elig.get(cid, {}).get("status") != "eligible"]
        if bad:
            raise BarclaysError(f"invariant broken: the bracket named candidates that did not pass the weigh-in: {bad}")
    elif bracket is not None:
        status = "INCONCLUSIVE"
        flags.append("WAITING_ON_JUDGES")
        reasons.append("the controller exported judge work and is waiting for results")
    elif not eligible:
        if incomplete:
            status = "INCONCLUSIVE"
            flags.append("COVERAGE_INCOMPLETE")
            reasons.append("no challenger is eligible, and at least one could not be verified: "
                           + ", ".join(incomplete) + ". An unverified candidate is not a loser.")
        elif baseline and elig[baseline]["status"] == "eligible":
            status = "NO_CHANGE"
            reasons.append("no challenger passed the weigh-in; the baseline stands")
        else:
            status = "NO_ELIGIBLE_CANDIDATE"
            reasons.append("nothing passed the weigh-in" + (", including the baseline" if baseline else ""))
    else:
        status = "INCONCLUSIVE"
        flags.append("NO_BRACKET")
        reasons.append(no_bracket_reason or "eligible challengers exist but no bracket was run")

    if baseline and elig[baseline]["status"] != "eligible":
        flags.append("BASELINE_INELIGIBLE")
    if weigh_in.get("baseline_fails_target"):
        flags.append("BASELINE_FAILS_TARGET")
        if status == "NO_CHANGE":
            flags.append("TARGET_UNMET")
            reasons.append("the baseline still fails the target checks: NO_CHANGE means nothing better was shown, "
                           "not that the problem is solved")
    for cid in incomplete:
        flags.append(f"UNVERIFIED:{cid}")
    bracket_ran = decision is not None
    if judges == "sim" and bracket_ran:
        flags.append("SIMULATED_JUDGES")
    # What the bout changed about its own event card (only what the card allows; see spec.bout_overrides).
    flags += list((bout.get("_overrides") or {}).get("flags", []))
    # An official the card names and this venue has no plug-in for. It reported 'unverified'; say which.
    flags += sorted({f"PLUGIN_MISSING:{r['official']}" for r in weigh_in["results"]
                     if (r.get("receipt") or {}).get("plugin_missing")})
    if (weigh_in.get("plugin_table") or {}).get("changed_during_weigh_in"):
        flags.append("PLUGIN_TABLE_CHANGED_DURING_RUN")
    # Code that executed without the jail: the result stands, but the reader should know.
    if any((r.get("receipt") or {}).get("filesystem") == "not_isolated" for r in weigh_in["results"]):
        flags.append("EXEC_NOT_ISOLATED")
    # A candidate the weigh-in passed and a MODEL gate inside the bracket then excluded. Kept apart from weigh-in
    # disqualification on purpose: one is an executed check on bytes, the other is models' judgment.
    gate_excluded = {}
    if decision is not None:
        gate_excluded = {cid: list(why) for cid, why in (decision["decision"].get("ineligible") or {}).items()}
        flags += [f"MODEL_GATE_EXCLUDED:{cid}" for cid in sorted(gate_excluded)]

    shadow_view = None
    if shadow and shadow.get("decision"):
        sd = shadow["decision"]["decision"]
        ranking = [r["candidate_id"] for r in sd.get("ranking") or []]
        fooled = [cid for cid in (sd.get("recommended") or []) + (sd.get("shortlist") or []) if cid in disqualified]
        top = ranking[0] if ranking else None
        shadow_view = {"note": "diagnostic only: the same judges with no weigh-in and no gates; it has no authority",
                       "status": sd["status"], "recommended": sd.get("recommended") or [], "ranking": ranking,
                       "would_have_promoted_disqualified": fooled,
                       "top_ranked_was_disqualified": bool(top and top in disqualified)}
        if fooled or shadow_view["top_ranked_was_disqualified"]:
            # The prefix says whose judges these were. With simulated judges the perceptions were supplied by the
            # fixture, so this shows the venue holding against a judge that prefers polish; it is not a finding
            # about any real model.
            flags.append(("SHADOW_SIM:" if judges == "sim" else "SHADOW:")
                         + "JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE")

    panel_view = None
    if panel:
        units = [{k: u.get(k) for k in ("lens_id", "lens_kind", "reviewer_slot", "pair", "leads_mode", "outcome",
                                         "preferred", "margin")} for u in panel.get("reconciled", [])]
        fooled_panel = sorted({u["preferred"] for u in units if u["preferred"] in disqualified})
        panel_view = {"note": "advisory: a panel never changes eligibility or the bracket's decision",
                      "authority": panel.get("authority"), "packets": panel.get("packets"),
                      "valid_results": panel.get("valid_results"), "order_sensitive": panel.get("order_sensitive"),
                      "units": units, "preferred_a_disqualified_candidate": fooled_panel,
                      "allegations_open": sum(1 for a in panel.get("allegations", []) if a["status"] == "unverified"),
                      "allegations_from_non_fact_lenses": sum(1 for a in panel.get("allegations", [])
                                                              if not a.get("raised_in_lane")),
                      "allegations_unattributed": sum(1 for a in panel.get("allegations", [])
                                                      if a.get("unattributed")),
                      "allegations_filed_as_opinion": sum(1 for a in panel.get("allegations", [])
                                                          if a.get("filed_as_opinion")),
                      "results_with_notes": sum(1 for r in panel.get("records", []) if r.get("notes")),
                      "objections_in_lane": len(panel.get("objections_in_lane", [])),
                      "objections_out_of_lane": len(panel.get("objections_out_of_lane", [])),
                      "roster": panel.get("roster"),
                      "provider": panel.get("provider"), "source_run": panel.get("_source_run")}
        if fooled_panel:
            flags.append("PANEL_PREFERRED_A_DISQUALIFIED_CANDIDATE")
        roster = panel.get("roster") or {}
        if roster and roster.get("source") != "event card default":
            flags.append("PANEL_LENSES_CHOSEN_BY_ORGANISER")
        if roster and not roster.get("fact_desk_present"):
            # No lens on this panel was briefed to check facts. Any lens can still raise an allegation, but
            # nobody was asked to look.
            flags.append("PANEL_NO_FACT_DESK")

    finalists = recommended + [c for c in shortlist if c not in recommended]
    because = _human_rules(event, status, bout, judges, bracket_ran, weigh_in, finalists, panel, gate_excluded)

    return {
        "schema": VERDICT_SCHEMA,
        "barclays_version": __version__,
        "bout_id": bout["bout_id"],
        "event_id": event["event_id"],
        "status": status,
        "recommended": recommended,
        "shortlist": shortlist,
        "acceptance_state": "pending_owner",
        "reasons": reasons,
        "flags": sorted(set(flags)),
        "eligibility": elig,
        "evidence_grade": {
            "weigh_in": "executed on these exact bytes",
            "panel": ("not_run" if not panel else
                      ("real reviewers" if any(v.get("real") for v in (panel.get("provider") or {}).values())
                       else "simulated or unattributed")),
            "bracket": "not_run" if not bracket_ran else ("simulated judges (dry run)" if judges == "sim"
                                                          else "real model judges"),
        },
        "human_decision": {"required": bool(because), "because": because,
                           "boundary": event.get("human_evidence_boundary", [])},
        "shadow_bracket": shadow_view,
        "panel": panel_view,
        "model_gate_exclusions": {
            "note": "candidates that passed the weigh-in and were excluded by a model gate inside the bracket; "
                    "a judgment by models, to be confirmed by a person",
            "candidates": gate_excluded} if gate_excluded else None,
        "bracket": None if not bracket_ran else {
            "controller": controller,
            "campaign_id": decision.get("campaign_id"),
            "contract_hash": decision["decision"].get("contract_hash"),
            "operational_status": decision["decision"].get("operational_status"),
            "selected_hashes": decision["decision"].get("selected_hashes"),
            "win_matrix": (decision.get("win_matrix") or {}).get("cells"),
            "composites": decision.get("composites"),
            "usage": {k: decision.get("usage", {}).get(k) for k in ("calls_used", "tokens_used", "by_role")},
            "planned_calls_upper": ((bracket.get("plan") or {}).get("plan") or {}).get("total_calls_upper"),
            "judge_diagnostics": (decision.get("diagnostics") or {}).get("judges"),
        },
        "provenance": {
            "event_sha256": event["_sha256"],
            "bout_sha256": bout["_sha256"],
            "sensitivity": bout["sensitivity"],
            "candidates": {c["id"]: c["content_hash"] for c in bout["candidates"]},
            "sources": {k: (v["sha256"] if isinstance(v, dict) else [x["sha256"] for x in v])
                        for k, v in bout["_sources"].items()},
            "officials": sorted({(r["official_id"], r["official"], r["official_version"])
                                 for r in weigh_in["results"]}),
        },
    }
