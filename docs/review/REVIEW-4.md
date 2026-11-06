# Fourth independent review: the plug-in interface and the three plug-ins (verbatim)

Run by a separate reviewer (Opus) on 5 November 2026 against clean clones of `barclays-center` at `3ce468a`,
`barclays-officials-web` at `ae95a5b`, `barclays-officials-game` at `2f6e678` and `barclays-officials-code` at
`ac4abf7`, with instructions to break their claims by running attacks. The text below is the reviewer's report,
unedited. Its scripts lived in a scratch folder (`review4/work`) and were not kept. What was done about each
finding is in `docs/CALIBRATION.md` section 7 here and in `docs/REVIEW-RESPONSE.md` of each plug-in repository.

---

# Review 4: Barclays Center plug-in interface + web/game/code plug-ins

Independent adversarial review. Attacks were RUN, not read. Everything lives under `review4/work`.

## Summary table

| Area | Verdict | One line |
|---|---|---|
| A (venue wrapper `external.py`) | holds with limits | Response-shape, size and run-dir-write checks are incomplete; a `pass` with a critical finding stays eligible, and the plug-in table is re-read per official so a plug-in can swap it mid-run. Tamper of manifest/verdict/REPORT is caught by `bc verify`. |
| B-web | holds with limits | Network blocking and reach are solid; injection into REPORT.md is escaped. But interaction-gated breakage passes every decisive official. |
| B-game | fails | A lying hook makes an unwinnable game `eligible`; `softlock_search` passes a permanently frozen game masked by a changing counter. Both decisive game officials are defeated by candidate-controlled hooks. |
| C (code) | holds | Suppression (`# noqa`/`# nosec`) and candidate config ignored; no candidate code executed; honest companion not harmed by a hostile sibling. |
| D (venue pieces) | holds | A bout cannot loosen a decisive param (`bout_may_set: nothing`); `officials_runnable` is always INCONCLUSIVE/NO_BRACKET for every `--judges` value; a missing plug-in is loud (PLUGIN_MISSING). |

## Findings I ran

**R4-01 (major, missing check) — a `pass` carrying a critical finding is accepted and the candidate stays eligible.**
Script `work/A/evil.py` mode `pass_with_critical`.
`EVIL_MODE=pass_with_critical python3 bc.py --events work/A/events --plugins work/A/plugins-evil.json weigh-in work/A/bout --out work/A/run-pwc`
Observed: all candidates `eligible`; the critical finding is stored in the result object. Expected: a `pass` whose findings contain critical/major items is incoherent and should be refused as `unverified`. `external.py` enforces "a `fail` needs a finding" but never the converse.

**R4-02 (major, tool defect) — the plug-in table is re-read per official; a plug-in can rewrite it mid-run, and the manifest keeps the stale table while `bc verify` still says CONSISTENT.**
`work/A/evil.py` mode `rewrite_table` (rewrites the file named by `BARCLAYS_PLUGINS`, which `child_env()` leaves in the plug-in's environment), card `work/A/events2`, table `work/A/plugins-swap.json`.
Control (`EVIL_MODE=pass ... weigh-in`): all three `disqualified` (strict.check fails on the word "the"). Attack: `EVIL_MODE=rewrite_table python3 bc.py --events work/A/events2 --plugins work/A/plugins-swap.json run work/A/bout --out work/A/run-swap --judges none` -> all three `eligible`; strict.check result receipts show argv `evil.py` and version 6.6 while manifest.json still records `stub_plugin.py` and the pre-attack table sha. `bc verify` = CONSISTENT. Expected: pin the table by content at manifest time, and keep `BARCLAYS_PLUGINS` out of the child environment.

**R4-03 (minor, missing check) — response size/shape unbounded in metrics/receipt/evidence.**
`work/A/evil.py` mode `huge` (20MB metrics + 5MB receipt + 5MB evidence) accepted as `pass`; run dir 86MB (`work/A/run-huge`). Mode `nested_fields` (dict `id`/`claim`/`summary`, list `official_version`) accepted and stringified (`"{'forged': 'obj'}"`) rather than refused. Only `_MAX_ITEMS` and 120/240/300/600-char truncation of id/locator/summary/claim exist; `metrics`, `receipt`, `evidence` are copied verbatim into the ledger objects.

**R4-04 (minor, missing check) — a plug-in may write stray files into the run directory during weigh-in and `bc verify` still says CONSISTENT.**
`work/A/evil.py` mode `scribble_run` leaves `PLANTED.txt` beside the ledger (`work/A/run-scribble`); verify = CONSISTENT, file unreported. The plug-in workdir is `run/weighin-*/ext-*`, i.e. under the run directory. (Rewrites of the sealed files manifest.json/verdict.json/REPORT.md ARE caught — see Confirmed closed.)

**R4-05 (confirmed closed, B-web reach) — candidate JS cannot reach the network or loopback.**
`work/web/bout/candidates/attacker`: fetch/XHR/sendBeacon/img/script-tag/link-prefetch/WebSocket/EventSource to `127.0.0.1:18777`, `example.com`, `file:///etc/passwd`, `169.254.169.254`. A `python3 -m http.server` on 127.0.0.1:18777 logged ZERO hits (`work/web/listen.log`). Attacker `disqualified` (console errors), honest `clean` stayed `eligible` — no collateral. Network blocking holds.

**R4-06 (major, missing check) — interaction-gated breakage passes every decisive web official: ended ELIGIBLE.**
`work/web/bout/candidates/evader` (final): clean at load, but on first `click`/`pointerdown` adds a 2000px overflow div, a broken internal link, and a missing-alt image.
`python3 bc.py --events events --plugins work/plugins.json run work/web/bout --out work/web/run-ev3 --judges none` -> evader = `eligible`, reasons []. `web.no_hscroll`/`web.links`/`web.axe` never interact; `web.task_success` (the only official that clicks) is `advise`. Post-load mutations within `settle_ms` ARE caught (`work/web/run-ev`), so the hole is specifically interaction- or long-timer-gated defects. README admits it; decisive coverage still has the gap. Caught-by: none of the decisive officials.

**R4-07 (major, lying hook) — an unwinnable-by-human game is certified ELIGIBLE.**
`work/game/bout/candidates/lying.html` (as in `work/game/run3`): the maze exit is walled off (no person and no BFS bot can reach it) but `step()` sets `won=true` at tick>=3 regardless of action.
`python3 bc.py --events events --plugins work/plugins.json run work/game/bout --out work/game/run3 --judges none` -> lying = `eligible`, reasons []. Passes `game.boot` (non-blank canvas), `game.bot_completes_level` (won after 3 steps >= `min_plausible_steps` 2, so even the weak implausible-fast lead never fires), `game.softlock_search`. Both decisive game officials defeated. Ended eligible.

**R4-08 (major, missing check) — `game.softlock_search` passes a permanently frozen game.**
`work/game/run4` candidate: player never moves, never wins/loses, but a `progress` field increments every `step()`. `ignore_state_keys` is only `["tick","clock"]`, so the harness `key()` sees state change every step and never counts a frozen state. Softlock result: `pass — no softlock in 200 seeded random run(s)`, `softlocks_found: 0`, all 200 outcomes `max_steps`. Any monotonic field not named tick/clock blinds the detector. Ended: not flagged by softlock (the candidate was DQ'd only because `bot_completes` caught the never-winning game; a game the expert bot can win but random play softlocks would pass both).

## Confirmed closed (attacks that failed)
- `symlink_out` (`work/A/evil.py`): response_path replaced by a symlink to /etc/hostname -> `unverified` ("wrote no readable response"); candidate `incomplete`, not pass.
- `deep` (deep-nested metrics that break json read) -> plug-in exits non-zero -> `unverified`/`incomplete`; `deep_ok` (900-deep, readable) accepted but see R4-03.
- `late_child` / `edit_manifest` (`work/A/run-late3`, `work/A/run-manifest`): a detached grandchild rewrites REPORT.md/verdict.json or the plug-in edits manifest.json -> `bc verify` = NOT CONSISTENT, naming each altered sealed file. Tamper of sealed files is caught (but only against the in-run ledger; without `--expect-head` a whole-directory rewrite is not — stated by the tool itself).
- Timeout-bypass via pipe-holding grandchild (`work/A/hold.py`, 5s budget): wrapper returns `unverified` ("did not answer within 5 s") at the budget; the orphan cannot change the already-recorded result.
- B-web injection into REPORT.md: `report.py _cell()` escapes `|` and newlines and findings render as list items, so a candidate string cannot forge a heading or a table row.
- Stale-response reuse across candidates: `external.external()` makes a fresh `tempfile.mkdtemp` workdir per call with request/response inside it; no previous candidate's request or response is reachable.
- C (code): `# noqa`/`# nosec` ignored (ruff `--isolated --ignore-noqa`, bandit `--ignore-nosec --ini empty`), candidate pyproject.toml/ruff.toml/setup.cfg/.bandit not read; the AKIA key and 9 lint findings surfaced despite them (`work/code/run2`). No candidate code executed — sitecustomize.py/conftest.py/__init__.py/.pth staged, marker file never written (`work/code/run3`, MARK2 absent). Honest companion stayed `eligible` next to the hostile candidate.
- D: bout cannot loosen a decisive param — `params:{loads-clean:{max_console_errors:99}}` REFUSED ("a bout may set: nothing"); `officials_runnable` is INCONCLUSIVE/NO_BRACKET for `--judges none|sim`; missing advise plug-ins raise PLUGIN_MISSING flags.

## Suspicions I read but did not run
- A combined game that the expert bot CAN win but random play softlocks, with the frozen state hidden under a non-tick/clock counter (R4-08 mechanism), would pass BOTH decisive game officials — not just one. Only each half was demonstrated.
- `--expect-head` is the only defence against a consistent whole-directory rewrite; a run whose head is not recorded outside it (Linear/commit) can be rebuilt wholesale and will verify CONSISTENT (tool states this as a warning).
- A `.pth`/`sitecustomize.py` would execute only if copy_dir were on a future interpreter's path; not reachable through the current tool invocations, but worth a guard if the code plugin ever imports anything from the copy.

## Not reached
- B-web.3 denial/hang (infinite loop, alert()/beforeunload, never-fires-load, huge DOM, download trigger) — not run; the web officials retry-then-timeout design (`load()` double-timeout) suggests `unverified`, unconfirmed.
- B-game.4 variants: reset-ignores-seed, state()-differs-each-call, detects-webdriver/random-bot — not run.
- B-web/game.5 10,000-char and HTML-in-title reaching verdict.json untruncated — only the REPORT.md path was checked.
- `--panel-lenses`/duplicate-lens-id shadowing (D) — not run.
