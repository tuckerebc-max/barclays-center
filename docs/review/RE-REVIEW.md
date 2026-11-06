<!-- The reviewer's report, unedited below the line. Written by a separate model session (Claude Opus) that took
no part in the build. It reviewed commit 48169fb. Paths under W are that session's scratch space and are not in
this repository; the candidates that mattered were copied into fixtures/_attacks and the forgery script into
tests/assets. What was done about each finding is in docs/CALIBRATION.md section 7. -->

---

# Re-review of Barclays Center 0.2 (commit 48169fb)

Setup for every command: `cd REPO && export BARCLAYS_ATR=/home/claude/adversarial-tournament-review`. W = `/tmp/claude-0/-home-claude/285f44b0-f257-5637-9d13-37e393aae0dc/scratchpad/rereview/work`. All candidates, bouts and scripts are under W.

| Area | Verdict | Evidence |
|---|---|---|
| 1 exec_tests | fails | The new 64 KB answer cap disqualifies the honest clean-fix on a 3,000-interval input (RR-01). Float and bool answers end `eligible` (RR-04). 8 of 10 wrong candidates were disqualified correctly. |
| 2 spec overrides / links | holds with limits | `routing` is refused, FIFOs are refused and `..` stays inside the bout. A bout can still set `allow_single_family` and `minimum_family_quorum` (RR-06). `timeout_seconds: 1e300` crashes the official for every candidate (RR-07). |
| 3 ledger audit | fails | The seal leaves out any file whose name contains `.sqlite`. Emptying the controller's ballot database, or adding `REPORT-ADDENDUM.sqlite.md`, still verifies ok (RR-02). A 37-line script makes a disqualified candidate the recommended one and verifies ok (RR-03). |
| 4 lenses / panel | not run | Not reached. |
| 5 text_fidelity | fails (against its own narrowed claim) | 4 invented figures slipped through decisively and 3 faithful revisions were disqualified (RR-05). |

## Findings

**RR-01. Critical. DEMONSTRATED. Tool defect.** The 64 KB answer cap disqualifies correct candidates.
- What I did: copied the fixture to `W/swbig` and added one test to `sources/pass_to_pass/test_regression.py`: `data = [[4*i, 4*i+1] for i in range(3000)]; assertEqual(merge_intervals(data), data)`. That list is 42,444 bytes as JSON. Ran `python3 bc.py weigh-in W/swbig --out W/swbigrun`.
- What happened: clean-fix and baseline were both `disqualified`, with the reason "the candidate's answer was longer than 65536 bytes". The cause is that the worker's reply carries the return value plus an echo of the arguments (`r`, `a`, `k`), so any input over about 32 KB breaks an honest candidate.
- What should have happened: pass. At worst `unverified`, because an answer too large for the harness is a harness limit, not a candidate failure.

**RR-02. Major. DEMONSTRATED. Tool defect and documentation overclaim.** The seal skips every file whose name contains `.sqlite`.
- What I did: `ledger.run_tree` drops any file where `".sqlite" in name`. On a fresh run `W/L0` (`bc.py run fixtures/software-clear-win --judges sim --shadow`) I made two copies:
  - `W/T-sql`: deleted every row of all 10 tables in `bracket/atr.sqlite` (the controller's ballots, attempts, results and records).
  - `W/T-name`: added the file `REPORT-ADDENDUM.sqlite.md` containing "The owner accepted polished-shallow."
- What happened: `python3 bc.py verify` reported `ok: true` with no problems for both.
- What should have happened: verify fails. The docstring's stated reason for the exclusion ("journal files ... a reader changes merely by opening") covers `-journal` and `-wal` files, not the database itself and not arbitrary names. Note: the README and docstring claim the seal covers "every file a reader might open".

**RR-03. Major. DEMONSTRATED. The concession is worse than stated.** A tail rewrite recommends a disqualified candidate.
- What I did: wrote `W/scripts/tail_rewrite.py` (37 lines) and ran it on the copy `W/T-tail`. It changes polished-shallow's two failing official results to pass, sets weigh_in eligibility, `decision.recommended` and `verdict.recommended`, and edits the REPORT.md line. It writes the new objects and working files, rechains every event and rebuilds the seal using REPO's own `run_tree`.
- What happened: `verify W/T-tail` reported `ok: true`, and `verdict.json` says RECOMMEND `['polished-shallow']`. With `--expect-head e936a30f…` (the original head), verify failed: "this is not the run that was recorded".
- The difference from what is conceded: the ledger docstring concedes rewriting "the last few events (decision, verdict, seal)". Recommending the disqualified candidate also required rewriting mid-chain official results (events 10 and 13) and the weigh-in. Re-deriving eligibility does not stop it, because the result objects it re-derives from are just as rewritable. The only real control is `--expect-head`, and `verify` without it should not print `ok: true` as its headline.

**RR-04. Major. DEMONSTRATED. Tool limit and documentation overclaim.** Type confusion ends `eligible`.
- What I did: added two candidates to `W/sw`.
  - `W/sw/candidates/w-floats.py` returns `[[1.0, 6.0], …]`.
  - `W/sw/candidates/w-bools.py` returns `True` in place of a start of `1`.
  - Ran `python3 bc.py weigh-in W/sw --out W/swrun`.
- What happened: both `eligible` on every suite. The task requires integer pairs, but unittest compares with `==`, and `1.0 == 1` and `True == 1`.
- What should have happened: the docstring says "the oracle rebuilds builtin values and compares those", which suggests type fidelity. Either the oracle should compare types, or the docstring should state that equality is Python `==`.
- The other 8 wrong candidates were disqualified as expected:
  - w-empty, w-nan, w-special, w-tuples: wrong answers.
  - w-mutate: in-place sort, caught by the sync.
  - w-stateful: wrong after 40 calls.
  - w-stall: 4.5 s per call.
  - w-big: 6,000-interval answer, caught by the cap.
- Argument-mutation rewriting of expected values: not exploitable against this suite. Every expected value is a literal, a `deepcopy` taken before the call, or computed from data the candidate never receives.

**RR-05. Major. DEMONSTRATED. Documentation overclaim.** Invented figures slip through and faithful revisions are disqualified. The claim tested is "an invented figure ... caught decisively". Bout: `W/ed` (a copy of `fixtures/_attacks/editorial` with 26 new candidates), run with `python3 bc.py weigh-in W/ed --out W/edrun2`. Each candidate is faithful-plain with one sentence added or changed.

Slipped through, ended `eligible` (4). Each reuses a number already in the source or writes the figure in words:
- x-ordinal: "at 37 schools, ranking 3rd in the state."
- y-reuse-pct: "About 37% of tutored students reached grade level."
- y-words: "nine of them saw no gains at all."
- y-percent-word: "roughly eleven percent of the district."
- Also eligible: y-unquoted-attrib, "Dr. Okafor also wrote that the tutoring clearly caused the gains." This is within the conceded meaning-reversal class.

Caught correctly (12): x-percent (37.5%), x-range (11 to 13), x-date, x-comment (an HTML comment), x-table, x-zwsp-num (a zero-width space inside 4,218), x-homoglyph-quote, x-quote-fake-curly, x-dollars-words, y-single-quote, y-code-span, y-link.

Wrongly disqualified (3), each for "new-numbers":
- f-roundword: "4,218 students (about four thousand two hundred)"
- f-about-4000: "more than 4,000 students (4,218)"
- f-units: "three sessions a week of 30 minutes each, or 90 minutes in all"

Faithful and correctly eligible (6): f-reorder, f-quote-caps (capital T, period moved outside the quotation mark), f-half-hour, f-per-student, f-thirtyseven-word, f-difference.

**RR-06. Minor. DEMONSTRATED. Documentation overclaim.** A bout can still choose its judge mix.
- What I did: `bc.py validate` on a bout copy with `params.bracket = {"allow_single_family": true, "minimum_family_quorum": 1}`.
- What happened: accepted. The card says `minimum_model_families: 2`, and `bout_overrides` says decisive settings belong to the card. The override does appear as a flag.

**RR-07. Minor. DEMONSTRATED. Tool defect.** Override values are typed but not range-checked.
- What I did: set `pass-to-pass.timeout_seconds: 1e300` in a bout copy, then ran weigh-in.
- What happened: both candidates ended `incomplete` with "official crashed: OverflowError". A bout can turn any contest INCONCLUSIVE. The value `call_timeout_seconds: 0.0005` was accepted, and the candidates still passed.

## Confirmed closed (re-tested)

- 0.1 symbolic-link escape: links are refused. Not re-attacked, but the FIFO probe of the same check was refused.
- RR-01 from the earlier pass (decision.md, deleted files, added files, REPORT.md edits): all four tamperings now fail verify.
- RR-05 from the earlier pass: a FIFO in a source directory is refused at validate.
- Hidden suites with `reveal: counts`: grepping `W/swrun` and `W/L0` (objects and REPORT.md, controller folders excluded) for every pass_to_pass and fail_to_pass test name, the hidden seed and the hidden-only inputs found nothing. The only traces found belong to the visible suite.
- RR-04 from the earlier pass, partly: `bracket.routing` is refused, and a bool `timeout_seconds` is refused.

## Not run

- Probing what the jail exposes from inside the worker (filesystem, /proc, network, leftover processes) and the non-jail fallback path. I did not do this in this pass.
- Protocol-level forgery by a worker sending hand-crafted replies.
- The panel path (`--panel-from`) and packet anonymity (area 4).
- Hard links: accepted as conceded (`W/hl` validated with a hard-linked outside file).
- RR-03 from the earlier pass (proxy path order): read in the diff only, not attacked.
