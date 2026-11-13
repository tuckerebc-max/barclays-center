# Barclays Center

The Navy Yard's tournament venue: where the right kind of contest is run for the work at hand.

Barclays Center is **a venue, not a controller**. It does not schedule matches or count ballots. An existing
controller, `adversarial-tournament-review`, does that. It is a separate, private repository. Barclays owns what
surrounds a contest:

| Piece | What it is | Where |
|---|---|---|
| Event cards | One tournament specification per genre: what is checked on bytes, what is judged, by whom, when to abstain, when a human decides | `events/` |
| Officials | Evaluators that run on every candidate before any judge sees it. Executed code runs in its own jailed process, never in the process that scores it | `barclays/officials/` |
| Plug-in officials | Checks that need a browser or a linter live in sibling repositories and are called through a file contract. Whatever they answer is validated; a missing or broken plug-in is `unverified`, never a pass | `barclays/officials/external.py`, `docs/PLUGINS.md` |
| Lenses | Perspective cards for adversarial panels: a voice, a discipline, an audience, an opponent, a fact desk. Each has a declared lane from a closed list and no authority over facts | `lenses/`, `barclays/lenses.py` |
| The bracket bridge | Compiles a bout into a controller campaign, runs it, reads the decision | `barclays/bracket.py` |
| The verdict and ledger | One record binding exact candidate and source versions, evidence and outcome, hash-chained and sealed | `barclays/verdict.py`, `barclays/ledger.py` |
| Calibration | Fixtures frozen as whole directories; attack tables that record what is and is not caught; probes of judge noise and position bias | `fixtures/`, `barclays/calibrate.py`, `tools/freeze.py` |

Version 0.3.0. The venue itself is Python 3.11+ standard library only: no install, no network, no paid service.

It is one of six repositories. The other five plug into it: real voices as lenses, browser checks for websites
and games, static checks for code, and human gold. See `docs/FAMILY.md`.

**This repository is public. The controller and the other five repositories are private.** What that leaves you
able to run is under "What runs without the private repositories" below. The project's research comparison, the
map of the owner's existing tools and the handoff describe private repositories and are not here. The licence
is Apache 2.0 (`LICENSE`).

Four independent reviewers have attacked the venue and its plug-ins, and a fifth attacked the first two siblings.
Each broke something. What was fixed, what was cut back to a smaller claim and what is still open are in
`docs/CALIBRATION.md`. Read section 1 of that report before relying on a verdict. **No human has judged anything
here, and nothing has run on real work.**

## Run it

With the controller. If you do not have it, skip to the next section.

```bash
export BARCLAYS_ATR=/path/to/adversarial-tournament-review     # or keep it as a sibling checkout
python bc.py events                                            # the genre library
python bc.py run fixtures/editorial-clear-win --out /tmp/run1 --shadow
cat /tmp/run1/REPORT.md
python bc.py verify /tmp/run1 --expect-head <ledger_head printed by the run>   # without the head: consistent, not authenticated
python -B -m unittest discover -s tests                        # 103 tests; 6 need the siblings and skip without them
python tools/freeze.py --check && python bc.py calibrate fixtures --out /tmp/cal1
```

With the sibling repositories checked out beside this one:

```bash
python tools/plugins_table.py                                  # writes plugins.json from the siblings it finds
python bc.py --plugins plugins.json run ../barclays-officials-web/fixtures/bouts/ui-website-clear-win --out /tmp/web1
python bc.py --lenses lenses --lenses ../barclays-lenses/cards panel-export fixtures/editorial-clear-win \
    --out /tmp/panel1 --pairs faithful-plain:polished-omission \
    --panel-lenses prose-craft-skill,technical-editing,fact-checker
```

The controller needs Python 3.11 or 3.12. Barclays runs on 3.11 to 3.13 and finds a suitable interpreter for the
controller itself.

Exit codes: `0` done, whatever the verdict; `1` invalid input or I/O; `2` a deliberate refusal; `3` calibration
ran and an expectation was not met.

## What runs without the private repositories

Checked on a copy of this repository with no controller and no sibling beside it.

- The genre library and input checks: `python bc.py events`, `python bc.py validate <bout>`.
- The weigh-in on its own: `python bc.py run <bout> --out <dir> --judges none`. The built-in officials for text
  and for Python code run on every candidate, and the verdict stops at `INCONCLUSIVE` with `NO_BRACKET`.
- The panel: `panel-export` and `panel-import`, with the fourteen generic lens cards in `lenses/`.
- `python bc.py verify` on the saved runs under `results/`, and `python tools/freeze.py --check`.
- The tests: 103, of which 74 run. 23 skip because they need the controller and 6 because they need a sibling.

A bracket and `bc calibrate` need the controller. Without it they refuse with exit code 2 and say what was not
found. The website, game and static code checks live in the sibling repositories. A card that names one reports
it as `unverified`, and the verdict carries `PLUGIN_MISSING`.

## What a verdict can be

`RECOMMEND`, `NO_CHANGE`, `TIED_SHORTLIST`, `INCONCLUSIVE`, `NO_ELIGIBLE_CANDIDATE`. This is the controller's
vocabulary, kept as is. Only one of the five names a winner. Every verdict is `pending_owner`: Barclays recommends
and never accepts, releases or publishes.

## What is runnable

| Event | Status | Decisive checks | Then |
|---|---|---|---|
| `editorial-revision` | runnable | a ledger fact is absent, a figure is unsupported, a quotation is not verbatim. Not caught decisively: a sentence that keeps every figure and reverses its meaning, a fabricated statement in indirect speech, an invented count of ten or under, a figure swapped under the source's own "approximately" | judged: clarity, argument, voice, economy |
| `software-change` | runnable (Python functions over plain data) | held-back PASS_TO_PASS and FAIL_TO_PASS suites run by a separate oracle process; a source filter for imports. Advisory through a plug-in: committed credentials, lint, security scan, complexity | judged: maintainability, generality, economy |
| `ui-website` | officials runnable through `barclays-officials-web`; no bracket | pages load clean, links resolve, no overflow at 320 px, structural HTML, axe-core | people. The verdict never names a winner |
| `game-build` | officials runnable through `barclays-officials-game`; no bracket | the game boots, a bot finishes level 1, random play finds no softlock | people. The verdict never names a winner |
| `research-synthesis`, `policy-document`, `factual-extraction`, `instructional-material`, `manuscript-production` | specified | named in each card, not built | see `docs/GENRE-CATALOG.md` |

## What is real and what is simulated

Read this before quoting any result.

- **Weigh-in results are real.** Officials ran on the exact bytes recorded in the ledger. The attack tables under
  `fixtures/_attacks/` record 42 hostile or tricky candidates: 17 caught decisively, 6 raised only as leads, 3 not
  caught, 2 faithful revisions still wrongly disqualified, 14 controls and faithful revisions handled correctly.
- **The plug-in checks are real and their fixtures are synthetic.** A browser really loaded the fixture sites and
  games; ruff and bandit really ran. The sites, games and code were written by the same lanes that built the
  checks. Passing them does not show a site works for people or a game is fun.
- **The calibration brackets are simulated.** Each fixture tells the controller's simulator what to perceive. A
  matching verdict shows that the venue turns those perceptions into the right decision and holds when judges are
  noisy or position-biased. It says nothing about how real models judge, and "10 of 10" is a regression test of
  the author's own cases.
- **One bracket and four panel probes used real model reviewers** (Claude Haiku and Sonnet, one model family) on
  synthetic material: 76 calls. The bracket returned INCONCLUSIVE. Three earlier probes are void because their
  packet file names named the candidates. No panel has yet been run with the real voice lenses.
- **No human has judged anything here.** No judge route has been scored against human gold; `barclays-gold` holds
  none. Nothing here shows that a revision still sounds like its author, that a site works for people or that a
  game is fun.

## Read next

- `docs/FAMILY.md`: the six repositories, how they connect, what each has and has not shown.
- `docs/ARCHITECTURE.md`: the boundaries, the contracts, the repository strategy.
- `docs/GENRE-CATALOG.md`: nine genres, their formats, officials, lenses and human-evidence boundaries.
- `docs/PLUGINS.md`: the contract for officials that live in sibling repositories.
- `docs/CALIBRATION.md`: what was measured, what broke, what was fixed, what remains unproven.
- `docs/review/`: the independent reviews, verbatim.
- `docs/ROADMAP.md`: what to build next.
- `AGENTS.md`: the operating contract for any agent working in this repository.

All fixture material is synthetic. The organisation, people and figures in it do not exist.
