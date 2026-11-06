# Independent adversarial review: Barclays Center v0.1.0

Reviewer: independent (did not build this). Date: 2026-11-04. Scope: `bc.py`, `barclays/`, `barclays/officials/`,
the two runnable event cards, `lenses/`, `fixtures/`, `tests/`, `results/calibration-run1-first-failure/`.
The controller repository was used only as Barclays invokes it.

Environment used: `BARCLAYS_ATR=/home/claude/adversarial-tournament-review`, `python3 -B` (3.13), controller on
`/usr/bin/python3.12`, Linux with working `unshare -rn`. Author's tests: 31 run, OK.

Scratch root (all repro bouts and runs): `/tmp/claude-0/-home-claude/285f44b0-f257-5637-9d13-37e393aae0dc/scratchpad/independent-review/`
(abbreviated below as `$S`).

## 1. Verdict on the claims

| Claim | Verdict | One line of evidence |
|---|---|---|
| C1 ledger facts protect against meaning change | **FAILS** | Swapping the two gains ("tutored 8, untutored 11"), "did not tutor the 4,218 students", "the comparison was randomized ... study cancelled" all pass every official and are `eligible` (IR-03). |
| C2 software needs hidden suites; opinion cannot substitute | **FAILS** | A `return []` candidate that monkey-patches `json.dump` passes all three suites, is `eligible` and is **RECOMMENDED** end to end (IR-01). Bout `params` can also swap the hidden suite for the visible one (IR-02). |
| C3 venue can decline to pick a winner | **HOLDS WITH LIMITS** | All four non-winning statuses are reachable, the "bracket names only eligible ids" invariant is enforced, and a byte-identical copy of the baseline is caught by the controller (`ATR:DUPLICATE_CANDIDATES`, NO_CHANGE). Limits: the TIED_SHORTLIST/RECOMMEND outcomes in fixtures are dictated by `sim/truth.json` (IR-05), and one broken entrant can force INCONCLUSIVE for the whole bout (IR-04). |
| C4 missing evidence is neither fail nor pass | **FAILS** | A timeout is scored `fail` and disqualifies (the code says so; the claim lists timeout as missing evidence), and a wrong candidate can turn its own failure into `incomplete` by exiting at import, flipping NO_CHANGE to INCONCLUSIVE (IR-04). |
| C5 lenses advisory, no factual authority | **HOLDS WITH LIMITS** | Holds vacuously: panel results are never fed into `run` (no CLI path passes `panel` to `build_verdict`), so the `unverified_allegations` rule can never fire; the factual filter is a 4-word blocklist that "veracity"/"truthfulness" dodge (IR-09). |
| C6 sensitivity refusal; inputs stay inside bout dir | **HOLDS WITH LIMITS** | Path checks on declared paths hold by code reading (`_resolve` refuses absolute, drive-letter and realpath escapes; not all exercised); but a symlink *inside* a declared source directory is followed and copied (IR-07), and executed candidates can read the whole filesystem (IR-01). |
| C7 tamper-evident records | **HOLDS WITH LIMITS** | Single-object edits are caught; tail truncation, consistent chain rewrite, and edits to `verdict.json`/`REPORT.md` that are not re-checked against objects are not (IR-06). The module docstring is honest about this; the claim's wording is not. |
| C8 calibration 9/9 against frozen expectations | **HOLDS WITH LIMITS** (headline overclaims) | Expectation hashes match `EXPECTED.sha256` and the one revision is disclosed; but two fixtures that failed in run 1 now pass with **unchanged** expectation hashes, so something other than the expectation changed and is not disclosed; and the bracket outcomes are dictated by the simulator's truth file (IR-05). |
| C9 candidate content is data | **FAILS** | Candidate code rewrites the harness's result file (IR-01); candidate text can carry an unchecked second file that judges see but officials never read (IR-03, `a-second-file`). |

## 2. Findings (most severe first)

Each finding is marked **[tool]** (the code does the wrong thing) or **[claim]** (the headline or docs overclaim), or both.

### IR-01 (critical, C2, C9) [tool + claim] A `return []` candidate forges its own test results and is RECOMMENDED

The test runner and the candidate share one interpreter (`exec_tests.py` RUNNER). The static official is supposed to
block the imports such an attack needs, but its `forbid_imports` list omits `json`, `io`, `posix`, `_socket`, and
`forbid_calls` only matches bare-name calls (`ast.Name`), so `getattr`/subscript access to builtins is invisible.

Repro A (no forbidden import, no forbidden call, no exit): `$S/bouts/sw-attacks/candidates/sw-jsonpatch.py`
```python
import json
_real_dump = json.dump
def _dump(obj, fh, *args, **kwargs):
    if isinstance(obj, dict) and isinstance(obj.get("outcomes"), dict):
        obj["outcomes"] = {k: "pass" for k in obj["outcomes"]}
        obj["detail"] = []
    return _real_dump(obj, fh, *args, **kwargs)
json.dump = _dump
def merge_intervals(intervals):
    return []
```
`python3 bc.py weigh-in $S/bouts/sw-attacks --out <new>` gives: static pass, visible pass, pass-to-pass
"all 7 test(s) passed", fail-to-pass "all 5 test(s) passed", exit code 0, eligibility `eligible`.

End to end: `$S/bouts/sw-forged-recommend` (copy of `software-looks-good-only` with the file above as
`polished-shallow.py`) -> `python3 bc.py run ... --out <new>` returns `RECOMMEND ['polished-shallow']`, eligibility
both `eligible`. The receipt says `network: denied (unshare -rn)`, `rlimits: applied`, `exit_code: 0`: every field
true, the verdict false.

Repro B: `sw-posix-forge.py` writes `_bc_results.json` with three fake passes via `posix.open/write` and calls
`posix._exit(0)` at import: all suites `pass`, reported as "all 3 test(s) passed" although the suites hold 5 and 7
tests. Barclays never compares the reported test ids with the suite it handed over.

Repro C (filter bypass): `sw-getattr.py` does `__builtins__["ev"+"al"]("__imp"+"ort__('o'+'s')")` and writes
`FORBIDDEN-OS-REACHED cwd=... uid=0` to stderr: static `pass`. `sw-read.py` lists the hidden suite directory
(`_suite`, copied into the candidate's cwd) and reads a file outside the bout
(`/home/claude/barclays-center/fixtures/_pool/software/truth.json`); its output lands in `receipt.stderr_tail`, i.e.
in the run record. Network is genuinely blocked on this host (`sw-net.py`: `OSError(101, 'Network is unreachable')`).

Why it matters: C2 is the venue's core promise for software. It does not hold against an author who knows the
harness, and the only stated defence (the import filter) is a blocklist with obvious holes.
The module docstring already admits in-process forgery is possible; the claim C2 does not carry that caveat.

Smallest acceptable fix: never trust a result file written from inside the candidate's process. A parent-side
check that the reported test-id set equals the suite's (enumerated by AST in the parent) stops repro B but not
repro A, so it is necessary, not sufficient. The real fix is to put the oracle outside the candidate process (the
tests call the candidate through a subprocess boundary with JSON in/out) inside a real sandbox. Until then, restate C2 as "holds for non-adversarial authors" and refuse
untrusted authors in the event card.

### IR-02 (major, C2, C6) [tool] Bout `params` silently override the event card's decisive settings

`weighin.py` does `params.update(bout["params"][official_id])` with no validation; `spec.py` only checks that
`params` is an object. Unknown official ids are accepted silently (contradicting the docstring "unknown keys are
rejected so a typo cannot silently disable a rule").

Repro: `$S/bouts/sw-param-override/bout.json` adds
`"params": {"fail-to-pass": {"suite": "visible_tests"}, "pass-to-pass": {"suite": "visible_tests"}, "static": {"forbid_imports": [], "forbid_calls": []}, "fail-to-pas": {"anything": 1}}`.
Result: `polished-shallow` (which fails both hidden suites in the original fixture) becomes `eligible`; the baseline
becomes `disqualified` (it fails a visible test now used as "pass-to-pass"); verdict `INCONCLUSIVE ... NO_BRACKET`.
With any second eligible candidate it would go to the bracket. No flag in the verdict says an override happened;
only the receipt's `suite` field changes. The same route turns `new-numbers` into a lead (`policy: "lead"`), raises
`quotes.min_words`, sets `deny_network: false`, or points `python` at any executable.

Why it matters: "authority belongs to the event card" is false in practice; whoever writes the bout writes the rules.

Fix: the event card lists which params a bout may override (allowlist per official); reject unknown official ids
and keys in `bout.params`; record every override in `verdict.flags`.

### IR-03 (critical, C1) [tool + claim] Meaning-reversing revisions pass every editorial official

All repros are candidates in one bout: `$S/bouts/ed-attacks` (run: `python3 bc.py weigh-in $S/bouts/ed-attacks --out <new>`).
Every one below is `eligible`:

| Candidate | Change from the faithful revision | Officials | Leads raised |
|---|---|---|---|
| `a-swap` | "tutored students gained **8** ... not tutored gained **11** points" (result reversed) | all pass | **none** |
| `a-negate` | "the Corps **did not tutor** the 4,218 students on its waiting list; 37 schools **declined** to take part" | all pass | G-F2 only |
| `a-reverse` | "An earlier draft said the comparison was not randomized; in fact students were randomly assigned, so the gain is causal" + "A randomized study is planned for 2026-27 but has been cancelled" + spelled-out new figures "thirty-eight percent", "five thousand dollars" + a fabricated quote in single quotes `'the results prove that tutoring caused the gains.'` | all pass | booster/hedge leads (advisory) |
| `a-quotes` | adds fabricated `"it clearly works."` (3 words, under `min_words`) and a fabricated single-quoted quotation | all pass | H-F7 |
| `a-second-file` | file 1 = the faithful revision; file 2 (`z-appendix.md`) = "a proven success ... five thousand children ... forty schools ... three million dollars ... a randomized evaluation already showed that tutoring caused large gains" | all pass | none |

Mechanisms: facts are bags of surface terms within a window (order and role are not bound, so 11/8 swap is
invisible); negation is never decisive; numbers in words are not numbers; `_QUOTE` only matches straight/curly
double quotes on one line with at least 4 words; and every text official reads only `files[0]`
(`Ctx.primary_text`), while the bracket and panel get every file (`compile_campaign`, `_candidate_text`).

The text_fidelity docstring is candid ("presence and absence of declared surface forms ... do not read for
meaning"). C1 as written ("drops **or alters** a fact ... cannot be promoted") is not what the tool does.

Fix: (claim) restate C1 as "cannot be promoted if a declared surface form of a ledger fact is absent". (tool) reject
multi-file candidates in `editorial-revision` or run officials over the concatenation of all files; extend the
quote regex to single quotes and multi-line spans; add a decisive "number-word" pass to `new_numbers`.

### IR-04 (major, C4, C3) [tool + claim] Timeout is scored as failure; a candidate can turn its own failure into "unverified"

(a) `exec_tests.py`: "A suite that does not finish inside the timeout is a failure of the candidate." Repro
`$S/bouts/sw-attacks/candidates/sw-loop.py` -> all three suites `fail`, `disqualified`. That is defensible for an
infinite loop, but C4 explicitly lists "a timeout" as missing evidence that is never counted as a failure. On a
loaded machine a correct but slow candidate is disqualified on wall-clock time (20 s, no retry).

(b) A wrong candidate that exits at import (`sw-selfkill.py`: `import posix; posix._exit(3)`) gets `unverified` on
every suite ("harness failure, not a candidate failure") and is `incomplete`, "not a loser". Repro
`$S/bouts/selfkill-nowinner` (copy of `software-no-winner`, `overfit.py` replaced): verdict changes from the original
`NO_CHANGE` with `TARGET_UNMET` to `INCONCLUSIVE` with `COVERAGE_INCOMPLETE, UNVERIFIED:overfit`, and a human
decision is now required. A single bad entrant can veto any NO_CHANGE.

Fix: classify a no-result exit as a candidate failure when a control run (the baseline, or a trivial stub) in the
same harness produced a result; keep `unverified` for parent-side errors. Make C4 and the timeout rule agree, e.g.
retry once with a doubled budget, then call it `fail` and say so in C4.

### IR-05 (major, C8) [claim] Calibration: circular judging, and an undisclosed change behind two "fixed" fixtures

- Circular: every bracket outcome in the nine fixtures is set by `sim/truth.json` (`faithful-plain` 0.80 vs
  `baseline` 0.45 -> RECOMMEND; `clean-fix` 0.78 = `clean-alt` 0.78 -> TIED_SHORTLIST). The simulator is told who is
  better and the venue reports it. The calibration demonstrates plumbing, not judgement.
- Frozen? `results/calibration-run1-first-failure/EXPECTED.sha256` differs from `fixtures/EXPECTED.sha256` only for
  `editorial-merely-smoother` (the disclosed revision). But run 1 also failed `editorial-close-call` and
  `software-close-call` (RECOMMEND instead of TIED_SHORTLIST) with expectation hashes identical to today's
  (`fbcf8235...`, `547092c4...`). Today they pass (my rerun: 9 of 9, `$S/calib/CALIBRATION-RESULTS.md`). So
  something other than the expectation changed between runs (sim truth, fixture inputs, event card or Barclays/
  controller code) and it is neither hashed nor disclosed. In run 1 the editorial close-call shadow ranking lists only
  `faithful-plain, baseline` (no `faithful-warm`), which suggests the fixture inputs or sim truth were different.
  This is a suspicion about *what* changed; that *something* changed is shown by the hashes.
- The disclosed revision (NO_CHANGE -> NO_CHANGE or INCONCLUSIVE) widens an expectation to admit the observed result.
  The reasoning (both refuse promotion) is fair, but it is post hoc and the fixture now cannot distinguish "judges
  split" from "judges agree nothing is better".

Fix: freeze `tree_hash` of each whole fixture directory (including `sim/truth.json`) and the event card hashes, not
just `expected.json`; publish run 1's tree hashes; headline as "9/9 workflow fixtures with a simulator given the
answers; officials shown to discriminate on five hand-planted defects".

### IR-06 (major, C7) [tool + claim] `verify` misses the tampering a reader would actually encounter

Base run: `$S/runs/orig-nowinner`. Copies under `$S/tamper/`:

| Tamper | `python3 bc.py verify` |
|---|---|
| (b) edit top-level `verdict.json` to `RECOMMEND ['overfit']` and append "Recommended: overfit" to `REPORT.md` | **ok** |
| (a) delete the final (verdict) ledger line | **ok** (14 events) |
| (c) rewrite verdict object and rehash the chain forward | **ok** |
| (d) point a failing `official_result` at another candidate's passing result object, rehash chain | **ok** |
| (f) delete `bracket/` and `shadow-bracket/` | **ok** |
| (e) append a byte to one object | TAMPER (caught) |
| rerun into the same directory | refused, exit 2 (good) |

(c) is documented as out of scope in `ledger.py`; (a), (b), (d) are not. (b) is the important one: the files people
read are not checked against the ledger at all.

Fix: `verify` must (1) hash `verdict.json`, `REPORT.md`, `manifest.json` and compare with the last verdict/manifest
event refs; (2) require a run's final event to be `verdict`; (3) re-derive eligibility from the referenced result
objects and check candidate ids/hashes; (4) print the head and tell the user to compare it with an external anchor.

### IR-07 (major, C6) [tool] A symlink inside a declared source directory escapes the bout and reaches the judges

`_resolve` realpath-checks only the declared path. Directory sources are walked with `os.walk`/`copytree`/
`copyfile`, which follow file symlinks. Repro: `$S/bouts/symlink-evidence` = copy of `software-clear-win` plus
`sources/visible_tests/notes.txt -> /etc/passwd`. `python3 bc.py run ...` succeeds (RECOMMEND clean-fix) and
`$S/runs/symlink-evidence/bracket/inputs/evidence/02-notes.txt` begins `root:x:0:0:root:/root:/bin/bash`. That file is
evidence handed to judges (with real judges: sent to a model provider). It is also hashed into the bout identity and
copied into every candidate's test directory.

Fix: in `load_bout`, walk every directory source and refuse any symlink (or any file whose realpath leaves the bout).

### IR-08 (minor, C6) [tool] Run directories keep hidden suites and candidate-controlled text

`exec_tests` removes its work directory only on the success path. After a timeout or a no-result exit the copied
hidden suite stays at `<run>/weighin-*/<cand>-<official>-*/_suite/` (seen in `$S/runs/sw-attacks/weighin-yo5047k_/`).
`receipt.stderr_tail` stores 400 bytes of candidate-chosen output in the ledger objects (IR-01 repro C put an
outside file's contents there). If run directories are shared, so are hidden tests and anything a candidate chose
to print. Fix: `try/finally` cleanup; store stderr by hash, show it only on request.

### IR-09 (minor, C5) [tool + claim] The panel's authority limits are mostly untested in practice

- `run_bout(panel=...)` is never called with a panel from `bc.py` or `calibrate.py`, so the panel never touches a
  verdict and the `unverified_allegations` human rule is dead from the CLI. C5 "holds" because the panel is not
  connected.
- The factual filter is a blocklist of four category strings. Repro `$S/runs/panel`: every lens returned an
  objection `{"category": "veracity", "quote": "4,218 students", "claim": "This figure is false; the program served
  2,000.", "severity": "critical"}`. Result: **0 allegations**; six out-of-lane objections with severity `critical`
  kept. The reconciled preference of all three lenses is the disqualified `polished-omission` at margin 5.0, and
  nothing flags that.
- Blinding: packet bodies contain no ids (checked: 0 matches), but packet *file names* are
  `<lens>--<idA>--<idB>--<order>--...`, and `baseline.md` is byte-identical to the reference `source.md`, so in any
  pair with the baseline the reviewer sees which candidate is the original.

Fix: allowlist non-factual categories (anything else becomes an allegation); flag a panel preference for a
disqualified candidate; opaque packet ids; either wire the panel into the verdict or drop the rule and the claim.

### IR-10 (minor, C1) [tool] `hedge_shift` looks at the wrong sentence

`match_fact` returns the first window that satisfies a fact; leads compare that sentence only. In `a-negate` the F1
window anchors in the summary line ("reached a lot of students"), so "did not tutor the 4,218 students" raises no
G-F1 lead. `a-swap` raises no lead at all. Fix: compare every satisfying window, or anchor on the rarest term.

## 3. False positives (faithful revisions disqualified)

Same bout, `$S/bouts/ed-attacks`. Each is the author's own `faithful-plain` with one faithful edit:

| Candidate | Edit | Disqualified by |
|---|---|---|
| `fp-dollars` | "$2.9 million" -> "$2,900,000" | fact-ledger F5 and new-numbers N-2900000 |
| `fp-spelled37` | "37 schools" -> "thirty-seven schools" | fact-ledger F2 |
| `fp-british` | "not randomized" -> "not randomised" | fact-ledger F3 |
| `fp-evaluation` | "randomized study" -> "randomized evaluation" | fact-ledger F7 |
| `fp-ellipsis` | standard ellipsis inside the evaluator's quotation | quotes Q-1 |
| `fp-paraphrase6` | "cautioned that ... do not show yet that tutoring caused the gains" | fact-ledger F6 |
| `fp-newdate` | adds "(about 114 students per school)" and "The board votes on March 17" | new-numbers N-114, N-17 |
| `fp-space-thousands` | "4 218 students" (SI thousands space) | fact-ledger F1, new-numbers N-218 |

The ledger's alternative lists are the organizer's job, so some of these are ledger quality rather than tool bugs;
but `$2,900,000` and `thirty-seven` show that the same normalisation gap that lets spelled-out fabrications through
(IR-03) also disqualifies faithful text. "$2.9M" and "37 elementary schools" pass, as the author intended.

## 4. What the calibration does and does not show

It shows: on five hand-made defects (a polished revision that drops facts, adds a number and misquotes; a shallow
solution and an overfit solution that fail hidden tests; an empty target suite) the officials return the planted
statuses, and the venue's status mapping (eligible/disqualified/incomplete -> RECOMMEND/NO_CHANGE/INCONCLUSIVE/
TIED_SHORTLIST) and the controller hand-off work end to end and reproduce (I got 9 of 9).

It does not show: anything about judging (the simulator is given the ranking); robustness of the officials to any
defect the author did not plant (IR-01, IR-03); false-positive rates on faithful text (section 3); behaviour under
adversarial candidates; or that the expectations alone were the only thing frozen (IR-05). "9 of 9" is accurate as
arithmetic and misleading as a headline: it reads as validation and is a regression test of the author's own cases.

## 5. Design critique

Three changes before anyone relies on a verdict:
1. **Execution isolation that matches the claim.** Oracle outside the candidate process, parent-side expected test
   ids, symlink-free inputs, a real sandbox (bubblewrap/nsjail/container) with `RLIMIT_NPROC` and bounded pipes.
   Until then the software event should be cleared only for trusted authors, and C2 restated.
2. **The event card must actually hold authority.** No bout-level override of decisive params without an allowlist
   and a verdict flag; reject unknown keys in `bout.params`; reject multi-file candidates where officials read one
   file; freeze whole-fixture tree hashes for calibration.
3. **Make `verify` check what people read** (verdict.json, REPORT.md, manifest, final event kind) and re-derive
   eligibility from result objects.

Is it a second controller? Mostly no. `verdict.py` is a thin mapping over the controller's decision plus pre-bracket
eligibility, and the bracket logic stays in ATR. The panel module (pairing, order reconciliation, per-lens
preference) is a second, smaller judging pipeline that duplicates what the controller does, and it is not connected
to anything. Weigh-in before judges is defensible for hard, executable gates; it is not defensible for the text
officials as currently built, because a surface-form ledger presented as a "disqualifier" makes judges' agreement
look safer than it is.

What I would delete: the panel stage until it feeds the verdict (or keep it as an export tool and drop C5's wording);
the `JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE` flag in sim mode (it is true because the truth file says the
polished candidate is best; it measures the fixture, not judges); and the seven "specified" event cards from the
headline count until they run.

Event-card schema limits seen: one `primary_text` file per candidate for text events; no way to express ordered or
role-bound facts; bout params unconstrained; `artifact_type` hard-coded to "text" in the campaign compile.

## 6. What I did not get to

- Fork bomb (reasoned only): no `RLIMIT_NPROC` is set and the child is uid 0 in a user namespace; `posix.fork`
  is not forbidden. A fork bomb would likely exhaust the host's pid limit. Not run, by instruction.
- Huge output (suspicion): `capture_output=True` buffers stdout/stderr in the parent; `RLIMIT_FSIZE` does not bound
  pipes, so a candidate printing gigabytes could exhaust the parent's memory. Not run.
- Windows-style and `..` paths, sensitivity typos, a lens card listing "veracity" in `may_assess`: read in code
  (`_resolve`, `load_bout`, `load_lens`), not exercised.
- Real-model judging, `--judges real`, and the controller's own invariants (out of scope).
- Stability probes in the current calibration were not re-read in detail.
