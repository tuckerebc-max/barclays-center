# Calibration report

Barclays Center 0.3.0, 5 November 2026. Everything here ran on synthetic material. No human judged anything.
The sibling repositories are covered where they touch the venue; each also states its own limits in its README.

## 1. What you can rely on, and what you cannot

**Rely on these. They are executed checks, reproduced by tests.**

- A revision that drops a fact the organizer listed, adds a figure that is in neither the source nor the evidence,
  or invents a quotation is disqualified before any judge reads it. Polish does not change that. Shown on two
  planted defects and seven attack candidates. What still gets through is stated below.
- A code change is promoted only if it passes test suites its author could not see, run by a process the
  candidate cannot touch. A model's opinion of the code never enters that decision. Shown on two planted defects
  and ten attack candidates, including the forgery that got a `return []` candidate recommended in version 0.1.
- The venue declines to pick a winner when the evidence does not support one. All four non-winning outcomes occur
  in the fixtures, and the one bracket run with real model judges returned INCONCLUSIVE. For websites and games it
  never names a winner at all: the checks say who is out, and people decide among the rest.
- A check that lives in a sibling repository cannot pass by failing to answer. A plug-in that is missing, crashes,
  times out or returns anything out of vocabulary is `unverified`, and a decisive check in that state leaves the
  candidate incomplete. Shown with a stub plug-in misbehaving in eight ways, and with the three real plug-ins.
- A lens card cannot give a voice or a discipline authority over facts. Lanes are a closed list; only the fact
  desk holds a factual one, and what a fact desk raises is an allegation.

**Do not rely on these yet.**

- **The text checks do not catch a change of meaning that keeps the words.** "Did not tutor the 4,218 students"
  and swapping which group gained 11 points and which gained 8 both pass every decisive check. They are raised as
  leads, which send the bout to a human. That is the only protection. A fabricated statement in indirect speech
  ("Dr. Okafor also wrote that the tutoring clearly caused the gains") raises nothing at all.
- **A figure swapped under the source's own "approximately" passes, with a lead.** "Approximately $700" where the
  source says "approximately $688" is identical on the page to a faithful rounding. So are invented proportions
  in words ("about a third", "nearly double"). All three now carry a major lead, and a finalist with a major lead
  goes to a person. None is disqualified.
- **Invented counts of ten or under pass.** "Nine of them saw no gains" and "ranking 3rd in the state" are
  invented figures. Small counts are ignored because prose is full of them.
- **Nothing here measures how well model judges judge.** The calibration brackets use a simulator that is told
  what to perceive. The real-model evidence is 76 calls from one model family on easy, synthetic cases.
- **The jail is not a sandbox for hostile code.** It is a Linux namespace and a chroot on the host kernel, with no
  limit on process count. It is fit for the Navy Yard's own lanes. The browser plug-ins run a candidate's
  JavaScript inside Chromium with requests blocked; that is Chromium's sandbox, not one of ours.
- **A panel reviewer who says nothing about a factual problem, or words it as taste, is not detected.** The venue
  keeps what a reviewer raises and screens its wording with a word list. It cannot make a reviewer look.
- **A run directory proves only that it is consistent with itself**, unless its ledger head was recorded somewhere
  else and is checked with `bc verify --expect-head`. The second reviewer's 37-line script rewrote two results,
  the weigh-in, the decision, the verdict and the report, and left a consistent run that recommends the
  candidate the real run disqualified.

Version 0.1 claimed more than this. An independent reviewer broke four of its nine claims. A second
reviewer then attacked the fixes and demonstrated seven more defects, one of them critical and introduced by a
fix. A third attacked those fixes and the two paths nobody had touched: the code jail and the forged-reply
defences held; the panel path and the number rules failed. A fourth attacked the plug-in interface and the three
plug-ins. Sections 3 and 7 say what changed each time. **The fixes to the third and fourth reviews are covered
by tests the author wrote and have not themselves been independently reviewed.**

## 2. What ran

| Evidence | Size | Real or simulated | Where |
|---|---|---|---|
| Unit and regression tests, venue | 103 (6 of them need the siblings and skip without them) | real execution | `tests/` |
| Unit tests, the five siblings | 43, 61, 40, 44 and 58 (lenses, web, game, code, gold) | real execution, including Chromium, ruff and bandit | each sibling's `tests/` |
| Plug-in officials through the venue | 3 bouts (website, game, software) | real execution | `tests/test_family.py` |
| Calibration fixtures (known-good, known-bad, close call, no winner, missing evidence) | 10 bouts | weigh-in real; judges simulated | `fixtures/`, `results/calibration-run4/` |
| Reseeding and position-bias probes | 120 brackets | simulated judges | `results/calibration-run4/calibration.json` |
| Attack tables | 42 candidates | real execution | `fixtures/_attacks/` |
| Bracket with real model judges | 1 bout, 36 judge calls | real (Claude Haiku and Sonnet tiers) | `results/real-bracket-01/` |
| Panel probes with real reviewers, blind packets | 4 probes, 40 calls | real (same two models) | `results/panel-probes-v2/` |
| Panel probes voided for a blinding failure | 3 probes, 36 calls | real, void | `results/void-contaminated-probes/` |
| Independent adversarial reviews | 5: three of the venue, one of the first two siblings, one of the plug-in interface and the three plug-ins | a separate model session with no part in the build | `docs/review/` |
| Human judgment | 0 | none | none |

## 3. The record of runs, including what changed between them

A calibration result means something only if you know what moved between runs. This is all of it.

**Run 1 (version 0.1, before any review): 6 of 9 fixtures met.** Kept in `results/calibration-run1-first-failure/`.
Two close-call fixtures returned RECOMMEND where a tie was expected, and `editorial-merely-smoother` returned
INCONCLUSIVE where NO_CHANGE was expected.

**Between run 1 and run 2, two things changed.**

1. *A rule.* Both runnable event cards gained `"finalists": 3`. The controller's light preset sends one leader and
   the baseline to the finals, so it cannot return a tie between two challengers; it promotes whichever led. That
   is a real defect in how the preset fits this use and it was right to fix it, but it was a change to the rules
   after seeing a result, and version 0.1's write-up did not say so. The independent review caught the omission
   (IR-05): two fixtures went from failing to passing with unchanged expectation hashes.
2. *An expectation.* `editorial-merely-smoother` now accepts NO_CHANGE or INCONCLUSIVE. The simulated judges
   perceive that candidate as better by exactly the simulator's tie margin, so they split. Both outcomes refuse
   promotion. The revision is written inside the fixture's `expected.json`.

**Run 2 (version 0.1): 9 of 9.** This is the number the review called accurate as arithmetic and misleading as a
headline.

**Between run 2 and run 3, almost everything changed**, because the review found real defects:

- `py.exec_tests` was rewritten (tests and candidate no longer share a process).
- The text officials were rewritten to 0.2 and a fifth, advisory official was added to the editorial card.
- The editorial fact ledger gained two alternative surface forms ("randomized evaluation", "not show yet that
  tutoring caused"), because faithful revisions were being disqualified for using them. This changes a fixture
  input, not an expectation.
- Both event cards changed: what a bout may override, what a held-back suite may reveal, the quotation length,
  the new human-decision rule for model-gate exclusions.
- A tenth fixture, `editorial-subtle-omission`, was added. Its expectation was written with the fixture, not
  before a first run. Treat it as a regression test, not a prediction.
- One flag was renamed in six expectations (`SHADOW_SIM:` prefix). Recorded in each `expected.json`. No expected
  outcome changed.
- Freezing now covers each whole fixture directory and every event card (`fixtures/FROZEN.json`), not just the
  expectation files. `bc calibrate` refuses inputs that differ from the freeze and records the git commit.

**Run 3 (version 0.2, commit `4636952`, working tree clean): 10 of 10 fixtures, 26 of 26 attack rows as recorded.**

**Run 3 again, after the second review's first pass (commit `48169fb`, clean): 10 of 10 fixtures, 27 of 27 attack
rows.** Between the two, the code changed in five ways (section 7), one attack candidate was added
(`slow-oracle`), and a bout may no longer set `routing` or `registry_source`. No expectation changed.

**Run 3 a third time, after the second review's demonstrated findings (commit `4a73931`, clean): 10 of 10 fixtures, 37 of 37 attack rows.**
Between these two, more inputs changed than at any earlier step, and all of it is the kind of change that could
hide a regression, so it is listed in full:

- The held-back regression suite gained one test (`test_returns_integer_pairs`). Every software fixture's inputs
  changed with it. The planted-bad `polished-shallow` now fails 1 of 8 regression tests, not 1 of 7.
- The number check changed in two directions. A percentage or an ordinal is now a different figure from the same
  digits as a count (stricter). A true rounding of a source figure is no longer a new figure (looser, by a stated
  rule: fewer significant digits and within 10 percent).
- The execution official's answer limit and its attribution changed, and the seal now covers every file.
- Ten attack candidates were added: eight editorial ones written by the second reviewer, and two type-confusion
  ones for software.
- No expectation in any `expected.json` changed.

The summary of this last rerun is what is kept in `results/calibration-run3/`; it states its own commit and
freeze hash. The published tag adds only documents, the contract file and that summary on top of commit
`4a73931`; no code, fixture, event card, lens or test differs. The full run directories (about 30 MB) are not kept in the repository; `bc calibrate` regenerates
them.

What run 3 is: a regression test, by the author, of the author's own cases, after the author changed both the code
and some inputs. It shows the officials do what the tables say and the plumbing holds. It is not a blind test.

**Run 4, after the third review and the plug-in interface (commit `3ce468a`, clean): 10 of 10 fixtures, 42 of 42
attack rows.** What changed since the last run of run 3, in full:

- The number check changed in both directions again. A figure near a source figure counts as a possible rounding
  only when the writer marked it approximate (stricter: a bare "$700" for $688 is now a new figure). A possible
  rounding and a proportion stated in words now raise major leads, where a rounding used to raise a minor one
  and a proportion raised nothing.
- Five editorial attack rows were added: `r-bare-700`, `r-about-700`, `r-swap-700`, `q-third`, `q-double`.
- The software event card gained four advisory officials that live in a sibling repository. With no plug-in
  installed, as in this run, each reports `unverified` and the verdict carries `PLUGIN_MISSING`. They are
  advisory, so no eligibility changed. The card also gained an explicit per-call time limit of 10 seconds, the
  value it already used by default.
- The website and game cards changed status from `specified` to `officials_runnable`, and the game card's input
  latency check became advisory. Neither card is part of this calibration.
- Panel routing, the seal, the override checks and the lens loader changed (section 7). None of them touches a
  fixture's expected outcome.
- No expectation in any `expected.json` changed since version 0.2.0 (`git diff v0.2.0 -- 'fixtures/*/expected.json'`
  is empty).

**Run 4 again, on the release candidate (commit `9c89aa4`, clean): 10 of 10 fixtures, 42 of 42 attack rows.**
What changed between the two runs of run 4, in full:

- The venue's side of the plug-in contract changed after the fourth review (section 7): a `pass` may not carry
  findings, the plug-in table is read once and pinned for the run, responses have size and shape limits, and the
  seal names anything at the top of a run that the venue did not write. No built-in official changed.
- The notes of the website and game event cards were rewritten for the plug-ins' second versions. Two event cards
  changed, so the freeze hash changed (`872d31ea...` to `fabd9828...`). Neither card is part of this calibration.
- `tests/test_family.py` gained assertions that the candidates the reviews produced are disqualified through the
  venue, and the stub plug-in and its tests gained the misbehaviours the fourth review used.
- No fixture, no attack row and no `expected.json` changed.

The summary of this run is what is kept in `results/calibration-run4/`; it states its own commit and freeze hash.
Version 0.3.0 adds only documents and that summary on top of commit `9c89aa4`; no code, fixture, event card, lens
or test differs. The stability table in section 5 is unchanged from run 3: the same seeds give the same counts.

## 4. What the officials catch

### Planted defects in the fixtures (real execution)

| Candidate | Defect | Outcome |
|---|---|---|
| `polished-omission` (editorial) | drops three ledger facts, adds "nearly 5,000", alters a quotation | disqualified by three officials |
| `subtle-omission` (editorial) | a tighter revision that drops one caveat and nothing else | disqualified by the fact ledger alone |
| `smoother-only` (editorial) | faithful, merely smoother | eligible; the bracket then declines to promote it |
| `polished-shallow` (software) | documented, typed, passes all 3 visible tests | fails 1 of 8 held-back regression tests and 3 of 5 target tests; disqualified |
| `overfit` (software) | special-cases the visible inputs | passes visible, fails both held-back suites; a lead flags the literals |
| empty target suite (software) | no tests to run | `unverified`, so INCONCLUSIVE: zero tests is not a pass |

### Attack tables (42 rows, all reproduced in the last run)

These are candidates built to get past the officials: the first reviewer's, six written for version 0.2, ten
that came out of the second review and five from the third. Each row records what happens, including when the
answer is "it gets through".

| Class | Editorial | Software | What it means |
|---|---|---|---|
| Caught decisively | 7 | 10 | disqualified by an executed check |
| Lead only | 6 | 0 | **passes**; a reviewer is pointed at it and a human rule fires |
| Not caught | 2 | 1 | **passes**, on the record |
| False positive remaining | 2 | 0 | a faithful revision still wrongly disqualified |
| Controls and faithful revisions handled correctly | 12 | 2 | |

The rows that matter most:

- **`a-negate` and `a-swap` (lead only).** The two meaning reversals above. Every figure and the quotation are
  intact, so no rule about bytes fires. `text.hedge_shift` raises a polarity lead and `text.number_roles` raises a
  number-order lead. Both are heuristics. A reversal phrased another way would raise nothing.
- **`y-unquoted-attrib` (not caught).** A fabricated statement attributed to the evaluator in indirect speech. No
  quotation marks, no new figure, every ledger fact present. Nothing fires, not even a lead.
- **`r-swap-700` (lead only; from the third review).** The source says "approximately $688 per student"; the
  candidate says "approximately $700 per student". The rounding rule accepted it and the candidate ended cleanly
  eligible. It is still eligible, because no rule about bytes separates it from a faithful "about $700". It now
  carries a major lead, which the event's open-leads rule turns into a required human decision. `r-bare-700`
  ("$700 for every child", no marker of approximation) is a new figure and is disqualified.
- **`q-third` and `q-double` (lead only; from the third review).** "About a third of tutored students reached the
  benchmark" and "gains were nearly double those of their peers" (the source gives 11 points against 8). Neither
  has a digit for the number check to see. Each is now a major lead. The list of proportion words is short:
  "most", "a majority" and "nearly all" raise nothing.
- **`x-ordinal` (not caught) and `y-words` (lead only, by luck).** Invented figures of ten or under.
- **`a-reverse` (caught, but only by its side effects).** It claims students were randomly assigned and the study
  was cancelled. It is disqualified because it also spells out invented figures and adds a fabricated quotation.
  Without those it would pass.
- **`y-reuse-pct` and `y-percent-word` (caught since the second review).** "About 37% of tutored students" reuses
  the 37 of "37 schools". Version 0.2 passed it, because the digits were in the source.
- **`static-bypass` (not caught).** It reaches the `os` module without tripping the source filter. The filter is
  now described as a filter. What contains this candidate is the jail.
- **`type-floats` and `type-bools` (caught, by the suite).** Right numbers, wrong types. `1.0 == 1` and
  `True == 1` in Python, so the harness cannot catch these; the held-back suite now asserts the type. A suite
  that does not say what types it wants will pass them.
- **`fp-newdate` and `f-units` (false positives remaining).** Faithful revisions that add a derived figure ("about
  114 students per school", "90 minutes in all") or a date. The rule cannot tell correct arithmetic from
  invention. A bout can list such figures under `new-numbers.allow`; that override is flagged in the verdict.
- Eight earlier false positives are fixed: British spelling, "$2,900,000", "thirty-seven", "4 218", an ellipsis
  inside a quotation, two paraphrases now in the ledger, and two roundings ("more than 4,000", "about four
  thousand two hundred").

One more defect surfaced while writing the regression tests and is fixed: a failing held-back test used to put
its name, its input and its expected value into the result and the report. A suite that prints `[[1, 3]]` into a
report is no longer held back. Held-back suites now reveal counts and digests only.

## 5. Simulated brackets: what holds when judges are noisy or biased

The simulator is given a quality for each candidate and a noise level, so it cannot tell us how models judge. It
can tell us whether the venue's decision survives a bad panel. Each bracket was rerun over five seeds, with and
without a 0.25 position bias in every simulated judge.

| Fixture | No bias: same outcome | Bias 0.25: same outcome | What moved |
|---|---|---|---|
| `editorial-clear-win` | 5 of 5 | 5 of 5 | nothing |
| `editorial-subtle-omission` | 5 of 5 | 5 of 5 | nothing |
| `software-clear-win` | 5 of 5 | 3 of 5 | two runs fell to INCONCLUSIVE |
| `editorial-close-call` | 5 of 5 | 1 of 5 | four ties fell to INCONCLUSIVE |
| `software-close-call` | 4 of 5 | 1 of 5 | three INCONCLUSIVE, and **one RECOMMEND** |
| `editorial-merely-smoother` | 3 of 5 | 3 of 5 | NO_CHANGE or INCONCLUSIVE, never a promotion |

Two things to take from this. Position bias mostly degrades a result to INCONCLUSIVE, which is the safe direction.
But one biased run of a true tie produced a RECOMMEND. With a small panel, a biased judge can manufacture a
winner. No disqualified candidate was promoted in any of the 120 runs, because the weigh-in runs first.

The **shadow bracket** (the same simulated judges, weigh-in and gates off) ranked the disqualified candidate first
in six fixtures. That is true because each fixture tells the simulator the polished candidate looks best. It
shows the weigh-in doing its job against a judge that prefers polish. Section 6 shows that real reviewers, on
these cases, were not that judge.

## 6. Real models

Claude's Haiku and Sonnet tiers, one model family, each call a fresh Claude Code subagent that saw one packet. The
run records name them `claude-haiku-4-5-20251001` and `claude-sonnet-5-5`. That is the host's statement of which
tier it asked for: the subagent runtime does not report the exact model it served, so treat the ids as the
tier, not as a verified version. The controller flags a one-family panel as `MODEL_DIVERSITY_LIMITED`, and so
should any reader.

### 6.1 One bracket: INCONCLUSIVE

`results/real-bracket-01`. The close-call editorial bout: the baseline and two faithful revisions,
`faithful-plain` and `faithful-warm`. Two judges per match instead of three, a bout override. 29 work items, 36
attempts.

| | `baseline` | `faithful-plain` | `faithful-warm` |
|---|---|---|---|
| Weigh-in | eligible | eligible | eligible |
| Judges' composite (0 to 100) | 80.0 | 95.0 | 82.5 |
| Model gate `no-new-claims` | pass | **fail** | pass |

What happened, in order:

1. The judges scored `faithful-plain` highest by a wide margin.
2. A model gate then failed it: its summary line says the program "reached a lot of students", an evaluative
   claim the source does not support. The controller excluded it.
3. Of the comparisons left, `faithful-warm` against the baseline was inconclusive (+2.5 against a threshold of 5).
4. Haiku gave the same answer in both display orders in 3 of 3 matches. **Sonnet's answer changed with the order in
   2 of 3**, and the controller counted those as abstentions.

Three lessons, none of them flattering to the fixture:

- **The "known-good" candidate had a flaw I did not plant.** I wrote `faithful-plain` and labelled it faithful. A
  model gate found a sentence the source does not support. A stricter editor would agree with the gate. The
  deterministic officials could not have caught it: it is not a number, a quotation or a ledger fact.
- **The simulator's story was wrong.** The fixture expected a tie between two faithful revisions. Real judges did
  not tie them; they ranked one far ahead, and a gate removed it.
- **Order sensitivity is real on close pairs.** It did not appear on clear ones (section 6.2).

Seven of the 36 attempts were wasted. The subagent wrote the controller's result envelope itself and left out a
field or broke the JSON, and the controller refused the file. None of those refusals says anything about
judgment. The host now writes the envelope (`tools/native_envelope.py`).

This run was made under version 0.1, so its `verdict.json` predates the seal and the "excluded by a model gate"
section; `bc verify` reports it as consistent and unsealed. Ledger head:
`eb9c508b1406d9ddf906cfebd242fc8b89469ae1b416418aec96a674f8b4260a`.

### 6.2 Four panel probes: 19 of 20 units preferred the candidate the checks passed

`results/panel-probes-v2`. A unit is one lens read by one reviewer, both display orders. All 40 results were valid
JSON. No unit changed its preference with display order.

| Probe | Pair | Shown to reviewers | Units preferring the eligible candidate | Margin (0 to 5) |
|---|---|---|---|---|
| p1 | faithful-plain vs polished-omission | no source, no tool output | 6 of 6 | 4.0 to 5.0 |
| p2 | faithful-plain vs subtle-omission | no source, no tool output | **5 of 6** | 2.5 to 4.0 |
| p3 | clean-fix vs polished-shallow | the task, no tool output | 4 of 4 | 5.0 |
| p4 | clean-fix vs polished-shallow | the task and tool output | 4 of 4 | 5.0 |

- **The one miss.** In p2 the fact-desk lens, read by Sonnet, preferred the revision that drops a caveat, in both
  orders, by a margin of 1.5. It could not see the source, so it could not know anything was missing. That is the
  failure the fact ledger exists for, observed once.
- **The polished candidates did not fool these reviewers.** In p1 every reviewer preferred the faithful revision
  without seeing the source, most likely because the polished one visibly overclaims. In p3 every reviewer found
  the bug by reading the code. So these fixtures are too easy to measure whether judges reward polish. The
  simulated shadow bracket assumed they would; on this material they did not.
- **Tool output changed nothing here.** p4 showed reviewers "1 of 7 tests in the held-back suite did not pass".
  Their preference was already at the ceiling in p3. Whether findings redirect a reviewer who would otherwise be
  wrong is untested.
- **Lenses did raise factual objections, and it cost nothing.** The reviewers filed 164 factual allegations
  across the four probes; 106 came from lenses with no brief to check facts, and 45 used a category no lens card
  lists. Every one was recorded as `unverified` and none affected eligibility or a preference count. In the
  software probes every one of the 69 allegations came from a non-fact lens: a reviewer saying "this is
  incorrect" is an allegation, and the tests are the check.

Ledger heads: p1 `ebd8dec9062fbc7a56e678b65a6123dc878056311f0b350d2ce484419e5ae3d2`,
p2 `c06d7e7f480e67f9b01cd554ce3ce993a00914299ac60ed9adc89b227111534f`,
p3 `c98b53d9f4909b84ae1190209611c0a8fed137b5a9dfd021330dd283bd58e722`,
p4 `a9d6f6405d6114ed7b42be31a07a9fa248abca6927d5b6597b860208dc80d403`.

### 6.3 Three probes voided

Version 0.1 named each packet file after the lens, both candidate ids, the display order and the reviewer. A
reviewer told to read `fact-desk--faithful-plain--polished-omission--ab--haiku--none.md` has been told the
answer. All 18 units in those probes preferred the faithful candidate, and it shows nothing. The independent
review caught it. 36 calls, about 3 million tokens, spent on a result that cannot be used. Packet ids are now
random, and each packet is staged alone in a folder of opaque files; even the run directory's name is kept away
from the reviewer.

## 7. Independent review

**First review, of version 0.1** (`docs/review/INDEPENDENT-REVIEW.md`). A separate model session with no part in
the build, asked to break nine claims. Four failed, four held with limits, one held. It got a `return []`
candidate recommended end to end, passed three meaning reversals through every text official, turned a certain
NO_CHANGE into INCONCLUSIVE by exiting at import, copied `/etc/passwd` into the judges' evidence through a
symbolic link, and edited a verdict without `verify` noticing. Each finding is now a regression test or a row in
an attack table. `docs/ARCHITECTURE.md` section 8 maps each claim to what it is now.

**Second review, of the fixes** (`docs/review/RE-REVIEW.md`). Another separate session, asked to attack what the
first review had led to. Its first pass ran one baseline, read the code and raised five suspicions; all five were
real enough to change the code. Its second pass ran attacks and **demonstrated seven findings**:

| Finding | Severity | What it showed | What was done |
|---|---|---|---|
| RR-01 | critical | The answer-size limit added after its own first pass disqualified honest candidates on any input over about 32 KB, because answers echoed their arguments. A fix had introduced a false disqualification. | Fixed. Arguments come back only when changed; the limit scales with the request; an oversize answer is `unverified` in one run and a failure only when another candidate passed the suite within the limit. Regression test with a 12,000-interval input. |
| RR-02 | major | The seal skipped every file with `.sqlite` in its name. Emptying the controller's ballots verified. | Fixed. The database is sealed by its contents; only SQLite's side files are left out. |
| RR-03 | major | A 37-line script made the disqualified candidate the recommended one and `verify` printed `ok: true`. It rewrote results in the middle of the chain, not only the tail, and re-deriving eligibility did not stop it. | Not fixable without a key or an outside anchor, so the claim is cut back. `verify` now reports `consistent` and `authenticated` separately and never prints a bare ok. The reviewer's script is kept in `tests/assets/` and a test asserts that it passes the consistency check and is caught only by the outside head. |
| RR-04 | major | Float and bool answers ended eligible. | The harness cannot fix this: the suite compares with `==`. The fixture suite now asserts integer pairs, the docstring says whose equality it is, and both candidates are in the attack table. |
| RR-05 | major | Four invented figures passed and three faithful revisions were disqualified. | Two of each fixed by stated rules (figure kind; rounding). The rest are in the attack table as not caught, lead only, or false positive remaining. |
| RR-06 | minor | A bout can still shrink the panel or accept one model family. | Kept, because a real panel has to fit the judges that exist. It is flagged in the verdict, the controller flags it too, and the docstring no longer says otherwise. |
| RR-07 | minor | `timeout_seconds: 1e300` crashed the official and made every candidate incomplete. | Fixed. A number a bout sets must be finite, positive and within a factor of ten of the card's value. |

It also confirmed closed: edits to the report and to the controller's readable decision, deleted and added files,
pipes in a source directory, and leakage from the held-back suites (it searched for every hidden test name, input
and seed and found none).

**Third review, of the fixes to the second and of two untouched paths** (`docs/review/REVIEW-3.md`). A clean
clone at commit `53d04d7`. It ran every attack.

It confirmed closed: the jail from inside (no host files, no `/proc`, no network, a read-only candidate
directory, no child that outlived the run), forged protocol replies written to every file descriptor, a
candidate that answers correctly once and wrongly on repeat, and the answer-size rule (a 1.6 MB answer was a
failure because competitors passed within the limit, and the honest candidates were untouched).

| Finding | Severity | What it showed | What was done |
|---|---|---|---|
| R3-01 | major | A reviewer could remove the reason for a person to look at a factual allegation. A fact-desk allegation labelled `a` instead of `A` was dropped in silence, and the same claim filed under `clarity` counted as an opinion. All six results were still marked valid. | An entry that names no candidate is kept as an allegation against the pair, with a note. An objection whose own words read as a claim about facts or the source is recorded as an allegation as well. The screen is a word list and can be worded around; a reviewer who stays silent cannot be detected at all. |
| R3-02 | major | One malformed result file (`"objections": 5`, or a 100,000-deep array) stopped the whole import. | One bad file marks one result invalid. |
| R3-03 | major | "Approximately $700 per student" for the source's "approximately $688" ended eligible with no reasons. | Still eligible; now with a major lead, which requires a person. A bare figure with no marker of approximation disqualifies. Rows `r-swap-700`, `r-bare-700`, `r-about-700`. |
| R3-04 | minor | Views, triggers and indexes added to the controller's database left `verify` consistent. | The database is sealed by its schema as well as its rows. |
| R3-05 | minor | An added empty directory, a world-writable ledger and a changed timestamp left `verify` consistent. | Directories and links are sealed. Permissions and timestamps are not, because they do not survive a copy; a ledger other accounts can write is a warning. |
| R3-06 | minor | A bout's `allow` list can whitelist an invented plain figure. | Still possible and flagged. A bout that changes any decisive check now requires a person. |
| read, not run | | A bout could set a per-call time limit of 0.01 s and time out every candidate. An honest answer far larger than its input would be failed as too long if a competitor passed with a short one. | The first is fixed: a bout cannot set a number the card gives no value for. The second stands: a suite whose correct answers are large needs `max_reply_bytes` raised on its card. |

Two of these (R3-02 and the directory part of R3-05) had already been changed in the working tree while the
review was running, by the author rereading the same code. They were real at the commit reviewed. The other
findings were not found by the author.

It did not reach: the number rules with an evidence document, large-input regression suites, replacing a file
with a directory, renaming database columns, and the bracket overrides.

**Review of the first two siblings** (kept in those two private repositories). Twelve findings on the first versions
of `barclays-gold` and `barclays-lenses`. The two that mattered most: the gold scorer printed "may decide alone"
for a route that answered 2 of 30 items and for 2 items repeated 15 times; and a voice lens card could carry
factual authority by spelling the lane differently ("Accuracy ", "fidelity", "evidence", "truth"), in the
registry's check and in the venue's loader alike. It also found that four briefs told non-fact lenses to judge
evidential support, that ballot file times and sizes gave away pairing and order, and that the ballot parser
would read a line of the candidate's own text as the judge's answer. Each repository's `docs/REVIEW-RESPONSE.md`
answers its findings one by one, with the test for each and what stays open. In the venue, lanes became a closed
list. The statistics held: kappa and AC1 matched the reviewer's own implementation to six decimals.

**Fourth review, of the plug-in interface and the three plug-ins** (`docs/review/REVIEW-4.md`). Clean clones of
the venue at `3ce468a` and of the web, game and code plug-ins at their first versions. It ran every attack.

It confirmed closed: a website candidate's JavaScript reached nothing (fetch, XHR, beacons, images, WebSocket and
EventSource to an outside host, to another loopback port with a listener waiting, to `file:///etc/passwd` and to
a metadata address: zero hits); candidate strings cannot forge a heading or a table row in the report; one
candidate cannot read another's request or response; a plug-in that edits the manifest, the verdict or the
report is caught by `verify`; a plug-in that hangs is cut off at its budget; the code plug-in never executed
candidate code and ignored the candidate's own lint configuration and suppression comments; a bout cannot loosen
a decisive setting on the website or game card; an officials-only event never names a winner.

| Finding | Severity | What it showed | What was done |
|---|---|---|---|
| R4-01 | major | A plug-in answer of `pass` with a critical finding attached was accepted, and the candidate stayed eligible. | A `pass` or `not_applicable` may carry leads and no findings; anything else is refused as `unverified`. |
| R4-02 | major | A plug-in rewrote the plug-in table it was listed in. Later officials ran the new entry, every candidate became eligible, the manifest still named the old table, and `verify` said consistent. | The table is read once, when the manifest is written, and that copy serves the whole run. A table file that changes during a run is flagged in the verdict. A plug-in is no longer told where the table is. |
| R4-03 | minor | A plug-in could return 30 MB of metrics and receipts, and fields of the wrong shape were turned into strings instead of refused. | Size limits on the response, on metrics, on the receipt and on each finding's evidence; text fields must be strings. |
| R4-04 | minor | A plug-in could leave a file beside the ledger and `verify` did not mention it. | A plug-in's scratch folder is now outside the run directory, and the seal names anything at the top of a run that the venue did not write; `verify` warns about it. A plug-in is trusted code and can still write where it should not. |
| R4-06 | major | Website: a page that is clean at load and breaks on the first click passed every decisive check and ended eligible. | The four decisive checks now look at each page three ways: as loaded, after a small fixed interaction (a click on the body, two tabs, a scroll), and in every state the bout's task script reaches. The reviewer's page is disqualified. Still not caught, each recorded as a test that asserts the gap: a page that breaks on the third click, on a control no journey uses, after a long delay, or only when it does not detect the automated browser or the 320 px check. |
| R4-07 | major | Game: an unwinnable maze was certified eligible because its own test hook reported a win after three ticks. | The organiser's bot script may define a referee: the game's rules, checked on every transition. With one, the lying maze fails. Without one it still passes, now with a major lead. A hook that lies consistently passes the referee, and because the harness runs in the candidate's own page a build written to deceive can replace the referee itself. The game checks find honest mistakes. They are not a defence against a hostile build. |
| R4-08 | major | Game: a permanently frozen game passed the softlock search because a counter kept changing. | The organiser's bot script may define what counts as the same situation. With it, the frozen game is a softlock finding, and so is the reviewer's untested combination (the expert bot wins, random play freezes). Without it the freeze is a major lead only, and both decisive checks pass. |

It did not reach: hangs and dialogs in a website candidate, further lying-hook variants, very long candidate
strings reaching the verdict, and the organiser's choice of panel lenses. The two plug-in lanes then covered hangs, dialogs, long strings and further lying-hook variants with tests of their own, and each plug-in's `fixtures/ATTACKS.md` records what is and is not caught. Those tests are the authors', not a reviewer's.

The lesson of the game findings is general. A check that asks the candidate about itself is only as good as the
candidate's honesty. The software official was rebuilt after the first review for exactly this reason (the
candidate no longer shares a process with its tests). The game plug-in repeated the mistake in a new place, and
its author's own tests did not see it.

What to take from the reviews together. Every one of them broke something its author believed was solid. A fix
can add a defect: RR-01 came from the fix to the reviewer's own earlier point. Self-review found two of the
third review's seven points and none of the others. And **the fixes to the third review, the sibling review and
the fourth review have not been independently attacked**: they are covered by tests the author wrote.

What no review covered: the controller's own invariants, real-model judging, anything on Windows, any attack that
would harm the host (fork bombs were reasoned about, not run), a candidate whose text tries to instruct a model
judge, and the lens cards against the people and disciplines they stand for.

## 8. Bias and uncertainty

- **Author bias.** I wrote the fixtures, the officials and the expectations. Two findings in this report exist
  only because something outside me looked: the reviewer, and a model gate that failed my own "known-good" text.
- **Position bias.** Simulated: section 5. Real: one model flipped in 2 of 3 close matches and in 0 of 20 clear
  ones. Both display orders are always run; a flip abstains.
- **Family bias.** Every real judge and reviewer was a Claude model, and the candidates were written by one too.
  The event cards ask for two model families and for the author's family to be kept off its own panel. Neither
  was possible tonight.
- **Sample size.** One real bracket. Twenty real panel units. No confidence interval is worth printing.
- **Fixture difficulty.** The planted defects are easy for a reader. Hard known-bad cases (a subtle bug that reads
  well, an omission that looks like tightening) are what would measure a judge, and there are none yet.
- **No human gold.** No judge route here has been compared with a person's decision on the same pair. Until one
  has, "the judges preferred X" is a statement about the judges. `barclays-gold` can now collect and score such
  decisions; it holds none.
- **Reviewer bias.** Every independent reviewer was a Claude model, as were the builders. They found real
  defects each time, which says the reviews were worth running, not that they were complete.
- **Lens bias.** Each lens card is one model's reading of the opening of one skill file. A card that reads well
  may still misstate the voice it stands for.

## 9. Cost and time

| Item | Measured |
|---|---|
| Editorial weigh-in, three candidates | 5 to 13 ms |
| Software weigh-in, three candidates, four officials | 0.5 to 1.1 s |
| Starting the jail | 0.04 to 0.10 s per suite |
| Whole calibration (10 fixtures, 120 probe brackets, 2 attack bouts) | about 1 min 35 s on the last run (about 3 minutes on earlier ones), no model calls |
| Venue test suite (103 tests, siblings present, browsers launched) | about 5 min 30 s |
| Website bout through the venue (four candidates, nine officials named, Chromium, each page checked in three kinds of state) | about 2 min 24 s |
| Game bout through the venue (five candidates, the card's default settings, the organiser's referee) | about 39 s |
| One real judge or reviewer call through a Claude Code subagent | 81,000 to 85,000 tokens, 9 to 37 s |
| The real bracket (36 attempts) | about 3.0 million tokens |
| The four clean probes (40 calls) | about 3.3 million tokens |
| The three void probes (36 calls) | about 3.0 million tokens |
| The second independent review (two passes) | about 320,000 tokens |
| The text-officials lane (one Sonnet builder) | about 175,000 tokens |
| The third independent review (Opus) | about 187,000 tokens |
| The review of gold and lenses (Opus) | about 150,000 tokens |
| The fourth independent review (Opus) | about 189,000 tokens |
| `barclays-gold` (Sonnet): build, then the review fixes | about 130,000, then 198,000 tokens |
| `barclays-lenses` (Sonnet): build, then the review fixes | about 140,000, then 170,000 tokens |
| `barclays-officials-code` (Sonnet) | about 135,000 tokens |
| `barclays-officials-web` (Sonnet, finishing what a Fable lane began): build, then the review fixes | about 171,000, then 289,000 tokens; the Fable lane's usage was not reported |
| `barclays-officials-game` (Sonnet): build, then the review fixes | about 180,000, then 262,000 tokens |
| A research update (Sonnet) | about 115,000 tokens |

The token figures are what the subagent harness reported, and they are almost all overhead: a packet is one to
three thousand tokens. The same call on a direct model route (a model gateway, or an API call) should cost a few
thousand tokens, so the subagent route is roughly twenty times dearer than it needs to be. It was the only route
available tonight without a credential. It is acceptable for a probe and wrong for production.

The controller records `tokens_used: 0` for native judges, so none of this is visible in a decision record. The
research agents, the catalog agent and the first review agent used earlier in the session are not itemised here;
their usage was not recorded where this report could read it. Nor is the lead session's own usage.

On the night of 4 November two build lanes stopped mid-work and the session stalled until the morning.
Everything after that ran its build lanes on Sonnet and its reviews on Opus.

## 10. Privacy

- Every fixture is synthetic. The organisation, the people and the figures do not exist. No private corpus, real
  name, credential or token is in the repository or in any packet.
- The only material that left this machine was synthetic packets sent to Claude subagents.
- A bout with no sensitivity label is refused. Each event, official, lens and reviewer route declares the labels
  it is cleared for; a mismatch is refused before anything is written. Tested.
- Bout inputs cannot leave the bout directory. Symbolic links are refused. A hard link cannot be told from a
  file, so the bout directory itself has to be under the organizer's control.
- Executed candidate code sees the interpreter and its own files, read-only, and no network. Limits in section 1.
- **A run directory holds copies of the bout's material** (in `objects/`, in packets, in the controller's
  campaign). It inherits the bout's label. Nothing encrypts it or enforces that. Do not put a run of restricted
  material anywhere the material itself may not go.
- Candidate output is recorded by hash and size, not content. Held-back suites reveal counts only.
- Not tested: a reviewer route that leaks. The clearance check is a declaration by whoever configures the route.
- **Lens cards come from private skill files.** Twelve of the owner's skill files were staged into
  the build session, read by one Sonnet lane, and described in each card in that lane's own words. A test finds no
  run of 12 words shared between a card and its source; the reviewer found none longer than 4. The cards and
  their registry are private. The skill files are in no repository here.
- A plug-in runs with the venue's environment minus every variable whose name looks like a credential, and each
  plug-in entry declares the labels it is cleared for. That is a declaration too.
- The game plug-in serves the candidate from a loopback port while it runs, which another account on the same
  machine could read. Do not run restricted material through it.

## 11. The role of human review

Every verdict is `pending_owner`. Barclays recommends; it never accepts, releases or publishes.

A verdict says "a human must decide" when its event card's rules fire: a tie or an inconclusive result, an open
major lead on a finalist, an unverified factual allegation against a finalist, a model gate that excluded a
candidate, simulated judging, or material above public. In the fixtures that is most verdicts, and that is
correct for a venue whose judges have never been compared with a person.

What no check in this repository can establish, and no amount of model judging will:

- whether a revision still sounds like its author;
- whether a fact that was not in the ledger was lost;
- whether readers are persuaded, whether a site works for the people who use it, whether a game is fun.

The event cards for websites and games say this in their own text: automated checks and agent play-throughs are
proxies, and the cards name the human evidence that would count (task completion by real users, playtest
sessions). Those two events now run their checks and stop there: the verdict is always INCONCLUSIVE with no
recommended candidate and a human decision required. None of the human evidence has been collected.

## 12. What remains unproven

1. Agreement of any judge route with human decisions, in any genre.
2. Whether real judges reward polish over substance on hard cases. The easy cases here did not show it.
3. Whether tool findings change a reviewer who would otherwise be wrong.
4. Behaviour of real judges from a second model family, and with the author's family excluded.
5. A candidate whose text tries to instruct a model judge. Packets fence candidate text as data; no injection
   test was run with real reviewers.
6. The jail against a hostile author: process-count limits, kernel exposure, a candidate that detaches itself.
   And one known way to dodge a failure: a wrong candidate with no competitor that passes the suite can answer
   over the size limit and end `unverified` instead of `fail`. It cannot end `pass`, and the reason is printed.
7. Anything on Windows or macOS. The jail needs Linux user namespaces; elsewhere the worker runs unjailed and the
   verdict is flagged `EXEC_NOT_ISOLATED`. That path has unit coverage for its logic and has never been run on
   another system.
8. The execution official beyond Python functions over plain data. Classes, callbacks and other languages are
   reported `unverified`.
9. The five specified event cards. They are specifications. Nothing in them has run. The website and game
   events have run only on synthetic fixtures written by the same lanes that built their checks.
10. The model-gateway judge path. The controller supports it; Barclays compiles the campaign; it was not exercised
    because no credential was used tonight.
11. Integration with the owner's evidence layer and routing. Barclays keeps its own ledger.
12. The lens cards against the people and disciplines they stand for, and a real panel seated with them.
13. `barclays-gold` on a single human decision.
14. The plug-ins on a real site, a real game or a real code base.
15. The fixes to the third review, the sibling review and the fourth review, beyond the author's own tests.

## 13. Reproduce it

```bash
export BARCLAYS_ATR=/path/to/adversarial-tournament-review
python -B -m unittest discover -s tests                 # 103 tests; 6 need the siblings beside the venue
python tools/freeze.py --check                          # inputs are what was frozen
python bc.py calibrate fixtures --out /tmp/cal          # 10 fixtures, 120 probes, 42 attack rows; no model calls
python tools/plugins_table.py && python -B -m unittest tests.test_family -v     # the whole chain, with the siblings
python bc.py verify results/real-bracket-01/run --expect-head eb9c508b1406d9ddf906cfebd242fc8b89469ae1b416418aec96a674f8b4260a
python bc.py verify results/panel-probes-v2/p2 --expect-head c06d7e7f480e67f9b01cd554ce3ce993a00914299ac60ed9adc89b227111534f
```

The real-model runs cannot be reproduced bit for bit; models are not deterministic. For the panel probes, the
packets, answers and decisions are in the run directories. For the bracket, the venue's own record is here
(manifest, ledger, objects, verdict, report); the controller's working directory, which holds its packets and the
judges' answers, is kept privately (`results/real-bracket-01/PUBLIC-NOTE.md`).
