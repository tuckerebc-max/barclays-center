# Third independent review (verbatim)

Run by a separate reviewer (Opus) on a clean clone at commit `53d04d7`, on 4 November 2026, with instructions to
attack by running, not by reading: the panel path into the verdict, the code jail from inside, forged protocol
replies, the answer-size rule, the seal, the number rules and the bout overrides. The reviewer did not see the
author's conclusions. The text below is the reviewer's report, unedited. `WORK` was the reviewer's scratch
folder; the scripts it names were not kept in this repository. What was done about each finding is in
`docs/CALIBRATION.md` section 7 and in `tests/test_attacks.py` (classes `ThirdReview` and
`PanelReachesTheVerdict`).

---

# Barclays Center: independent review 3 (commit 53d04d7)

Every attack was run, not just read. WORK = `scratchpad/review3/work`. All scripts are in WORK and set
`BARCLAYS_ATR` themselves. Panel scripts use the helper `WORK/panel_try.py` (export, write results, import,
`run --judges sim --panel-from`).

| Area | Verdict | Evidence |
|---|---|---|
| A | fails | Two reviewer label/category choices remove the "unverified factual allegation" reason from the verdict (R3-01). One malformed result file aborts the whole import (R3-02). |
| B | holds | All 4 hostile candidates `disqualified`. Forged replies and order-flips had no effect. The jail exposed no host fs, `/proc` or network, and no child survived. clean-fix unaffected. |
| C1 | holds | A 1.6 MB answer was reclassified `unverified` -> `disqualified` because two competitors passed. Honest candidates stayed eligible. |
| C2 | holds with limits | SQLite views, triggers and indexes, empty dirs, chmod and mtime all pass `verify` as CONSISTENT. A symlink is caught. |
| C3 | fails | Invented "$700 per student" (source: $688) ends `eligible`. 0 of 5 faithful variants were wrongly disqualified. |
| C4 | holds with limits | `new-numbers.allow` can whitelist any plain invented number. The override is flagged. Numeric guards held. |

## Findings I ran (DEMONSTRATED)

**R3-01, major. A reviewer can suppress the "human must decide" reason for a factual allegation.**
Script: `python3 WORK/a_suppress.py`. It runs a control and an attack on `fixtures/editorial-clear-win`
(pair faithful-plain:polished-omission).
- Attack: fact-desk lists its allegation with `"candidate": "a"` (lower case). The other lenses file the
  same factual claim ("source says two sessions") under `"category": "clarity"`.
- Observed (control): `because` includes "6 unverified factual allegation(s) against a finalist";
  allegations_open = 6.
- Observed (attack): that reason is gone; allegations_open = 0; objections_in_lane = 2. All 6 results
  are still marked `valid` with no problem recorded.
- Cause, `barclays/lenses.py` `_clean_result`:
  - An entry whose `candidate` is not exactly `A`/`B` is skipped silently (lines 238, 261).
  - A category is checked only against the lens's lane, never the claim's content. `clarity` is in the
    plain-language editor's lane, so a factual claim becomes an in-lane opinion.
  - `measurement-scientist`'s `clarity` is out-of-lane, which also counts as no allegation.
- Expected: a malformed label makes the result invalid or is recorded as a problem, and the
  allegation rule cannot depend on a category the reviewer picks.
- Kind: tool defect. The panel's "authority limits" are self-declared by the reviewer.

**R3-02, major. One malformed reviewer file crashes `panel-import`.**
Script: `python3 WORK/a_crash.py`.
- Observed: `"objections": 5` raises `TypeError: 'int' object is not iterable` at `lenses.py:237`
  (`raw.get("objections") or []`). Same at line 260 for `allegations`.
- Observed: a 100,000-deep JSON array raises `RecursionError` from `read_json`. `import_panel` catches
  only `ValueError`.
- In both cases import exits rc 1, no `panel.json` is written, and `run --panel-from` refuses.
- Expected: per the docstring ("Never raises on reviewer content"), only that result becomes invalid.
- Kind: tool defect; the docstring overclaims.

**R3-03, major. An invented figure passes the whole weigh-in.**
Script: `sh WORK/c3_numbers.sh`. Bout: `WORK/numbout`, 16 one-sentence edits of `_attacks/editorial`
faithful-plain.
- `inv-700` ("approximately $700 per student") and `inv-about700` ("about 700 dollars per student")
  end `eligible` with no reasons.
- Cause: `rounding_of` accepts 700 as a rounding of 688 (1 vs 3 significant digits, within 10%), so it
  becomes a lead only. $688 is not a must-keep fact, so fact-ledger passes.
- Expected: a figure the source does not contain should not leave the candidate cleanly eligible; at
  least a human-decides reason.
- Full C3 tally, invention attempts (11):
  - Ended eligible: 2, the two above.
  - Passed new-numbers but were disqualified only by fact-ledger: 7. "40 schools" (37), "$3 million"
    ($2.9M), "10 points" (11; ignored as ≤10), "a third", "one in three", "double", "half".
  - Disqualified by new-numbers itself: 2. "38 percent", "37 in 100" (on the 100).
- Faithful variants: 0 of 5 wrongly disqualified ("$2.9m", "2.9M dollars", "between 8 and 11",
  "2025 to 2026", "about 4,218").
- Kind: tool defect, plus an overclaim ("rounding is not a new figure").

**R3-04, minor. The seal does not cover SQLite schema objects.**
Script: `sh WORK/c2_seal.sh`.
- Observed: `CREATE VIEW`, `CREATE TRIGGER` and `CREATE INDEX` on `bracket/atr.sqlite` of a finished
  `--judges sim --shadow` run all give `verify` = "CONSISTENT, NOT AUTHENTICATED".
- Cause: `ledger.py:118 sqlite_content_hash` hashes only rows of `type='table'`. A trigger is logic
  that runs if the database is written again.
- Expected: a schema change breaks the seal.

**R3-05, minor. The seal does not cover directories, permissions or timestamps.**
Same script.
- Observed: an empty `objects/EMPTY_DIR`, `chmod 0777 ledger.jsonl` and `touch -d 2000-01-01
  manifest.json` all stay CONSISTENT.
- Cause: `run_tree` walks files and hashes contents only.
- A symlink added after the run is reported NOT CONSISTENT (closed).

**R3-06, minor. The `allow` override can whitelist an invented number.**
Script: `sh WORK/c4_allow.sh`.
- Observed: `params.new-numbers.allow: [100, 38]` turns `inv-37in100` new-numbers to pass. `inv-38pct`
  still fails: its value is `38%`, so the figure-kind rule resists.
- The card permits the override and flags it `BOUT_OVERRIDE`.
- Expected: either the card restricts it, or the verdict treats the flag as needing a human.

## Suspicions (read, not run)
- `call_timeout_seconds` has no card default, so the factor-of-ten bound does not apply; any value
  0 < v ≤ 86400 is accepted. A bout could set 0.01 s and push every candidate to time out
  (`spec.py bout_overrides`). Not run.
- An honest function whose correct answer is much larger than its input (more than 64 KB beyond twice
  the request) would be failed as `ANSWER-TOO-LONG` if any competitor passed with a short answer.
  Not run: merge_intervals cannot expand its input.

## Confirmed closed
- **B.** Script `sh WORK/b_jail.sh`, bout `WORK/swbout`.
  - `forge.py` wrote fake replies to fds 0–20 and answered wrongly: `disqualified`. The writes land on
    the worker's own pipes.
  - `flip.py` (correct first call, wrong on repeat): `disqualified`.
  - `recon.py` returned, through the visible-suite trace: jail root only (`bin cand etc jailbin lib
    lib64 sbin tmp usr`), `/proc` absent, candidate dir read-only, suite absent, socket OSError. Its
    root write went to throwaway tmpfs.
  - `spawner.py`: no child process or marker survived.
- **C1.** `sh WORK/c1_bloat.sh`: oversize answers reclassified to `disqualified` on all 3 suites;
  baseline and clean-fix eligible.
- **A, rest.**
  - Factual categories (any casing or padding), unknown words and look-alikes, and everything fact-desk
    raises all become allegations.
  - Panel preferences never changed eligibility or the bracket.
  - Reviewer `reasons`/`quote`/`claim` never appear in REPORT.md (checked with a heading/table-pipe
    payload), so markdown injection is not possible.
  - Two packets compared: they differ only in lens and random DATA ids. Nothing marks baseline,
    faithful or polished apart from the text itself.

## Not run
- Long-string and nested-object categories beyond `str()` coercion; candidate labels like `"A "`.
- C3 with an evidence document.
- C1 with large-input pass_to_pass tests.
- C2: replacing a file with a directory; renaming SQLite columns.
- C4: bracket overrides (`allow_single_family`, `minimum_family_quorum`).
