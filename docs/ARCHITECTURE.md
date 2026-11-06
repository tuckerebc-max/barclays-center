# Architecture and repository strategy

Written 4 and 5 November 2026. This describes version 0.3: version 0.1 after three independent reviews of the
venue and one of its first two sibling repositories. Section 8 says what each review changed and what is still
open. The family of repositories around the venue is in `docs/FAMILY.md`.

This is the public edition. Section 2 (the map of the owner's existing tools) and section 7 (changes proposed to
the private controller) are summarised here and kept in full with the project's private documents. Their
headings stay so that section numbers used elsewhere still point somewhere.

## 1. The decision

**Barclays Center is a venue, not a controller.** The Navy Yard already has a tournament controller,
`adversarial-tournament-review` (schema `atr/1`), in a separate private repository. It freezes a contract, blinds
judges, judges both display orders, counts one vote per model family, refuses to treat a timeout as a defeat, and
can return a tied shortlist, no change, inconclusive or no eligible candidate. It is tested. Building a second one
would be the mistake the brief warns against.

What the controller leaves to whoever hosts it:

| What the controller leaves out | Where Barclays fills it |
|---|---|
| It reads text, slides and analysis outputs, and its own text checks are literal string checks. | Officials that understand a genre: a fact ledger with alternative surface forms and a proximity window, unsupported numbers (number words and scales normalised), quotation checks, and leads for dropped hedges, changed negation and swapped numbers. |
| It never runs candidate code. Reproducing a result is left to the host. | `py.exec_tests`: that host tool step. Held-back PASS_TO_PASS and FAIL_TO_PASS suites run by a trusted oracle process; the candidate in a separate jailed worker (no network, private read-only root) that can answer only with plain data; a receipt. |
| It has no lens or perspective concept, and personas of one model family never count as two families. | Lens cards with declared lanes; a blind advisory panel; factual objections become allegations. |
| It takes no human evaluators yet. | Event cards state when a human decides and what only human evidence can establish. |
| It has no genre library. | Nine event cards: two run end to end, two run their checks through plug-ins and hand the survivors to people (no model bracket), five are specifications. |
| It has not been calibrated against known-good and known-bad work with live models. | Fixtures frozen as whole directories, attack tables, a shadow bracket, reseeding and position-bias probes, and a first small set of real-model runs. |

So a bout runs in four stages, and only the third belongs to the controller:

```
event card + bout (candidates, sources, sensitivity label)
   |  manifest: every file hashed
   v
1. WEIGH-IN      officials run on every candidate         barclays/weighin.py, barclays/officials/
                 -> eligible | disqualified | incomplete   real execution; objective findings + heuristic leads
   v
2. PANEL         blind lens packets, both orders           barclays/lenses.py   (advisory, optional)
                 -> objections, allegations, per-lens preference; never decisive
   v
3. BRACKET       eligible candidates -> ATR campaign       barclays/bracket.py  (subprocess; file contract)
                 -> the controller's decision.json         adversarial-tournament-review
   v
4. VERDICT       status + flags + evidence grades          barclays/verdict.py, report.py
                 + "does a human need to decide?"          acceptance is always pending_owner
   every step appended to a hash-chained ledger over content-addressed objects      barclays/ledger.py
```

The boundary with the controller is a file contract: campaign directory in, `reports/decision.json` out. Nothing is
imported, so the two repositories version independently and Barclays records the controller's commit and file
hashes in every verdict.

## 2. What already exists

Before anything was built, the owner's existing tools and collections were inspected: what each one does, whether
its tests pass, who owns it, and how the venue relates to it. That map names private repositories, so it is kept
with the project's private documents and is not in this repository. Three facts from it shape everything here:

- A tested tournament controller already existed. The venue calls it and does not build another.
- Several one-off tournament runners already existed, each with its own way of pairing, judging both display
  orders and counting. The event cards are meant to replace those private tallies over time, with their owners.
- Checks on the owner's own websites already have an owner. The venue's browser checks are a separate plug-in
  that does not replace that work.

## 3. Who owns what

| Concern | Owner | Barclays' part |
|---|---|---|
| Scheduling, panels of model families, order reversal, ballots, the decision rule, budgets, the journal | `adversarial-tournament-review` (private) | Compiles a campaign; reads the decision; records the controller's identity. |
| Routing work to a venue, capacity, lanes | The owner's routing layer | None. A bout is an input. |
| Evidence and receipts across the owner's other tools | The owner's evidence layer | Emits its own ledger today. One receipt per verdict is planned. |
| Voices and disciplinary skills | The owner's voice and skill repositories | None. |
| What a voice may and may not assess on a panel; the pin to the exact file a card was read from | `barclays-lenses` (private) | Loads its cards; owns the closed list of lanes the cards may use. |
| Checks that need a browser, a linter or other heavy tools | `barclays-officials-web`, `barclays-officials-game`, `barclays-officials-code` (private) | Calls them through the plug-in contract; validates every answer; never imports them. |
| Human decisions on pairs, and whether a judge route agrees with them | `barclays-gold` (private) and a gold owner who is not a builder | None yet. The venue's panel and decision records are what it scores. |
| Acceptance, release, publication | The owner | Every verdict is `pending_owner`. |
| What is checked on bytes for a genre; when a human decides; calibration of the whole | **Barclays Center** | Event cards, officials, lenses, fixtures, the verdict record. |

## 4. The contracts

All JSON, all hashed. Schema ids are in `contract.json`.

- **Event card** (`barclays.event/0.1`, `events/*.json`): objective, audience, stages, `officials` (each with an
  id, an implementation name, `authority` of `disqualify` or `advise`, `applies_to` of `all` or `challengers`,
  parameters and a reason), judged `criteria` with weights, `model_gates`, `lenses`, `evidence_required`,
  `hard_disqualifiers`, `judge_qualifications`, `format` (what is passed to the controller and to the panel),
  `abstention`, `human_decides_when` (a fixed rule vocabulary), `human_evidence_boundary`, `privacy`.
  Unknown keys are rejected. Each official, and `format.bracket`, may list `bout_may_set`: the only parameters a
  bout is allowed to change, and a number only where the card gives its own value to bound it. The card owns the
  rules. A card's `status` is `runnable` (weigh-in, panel and bracket), `officials_runnable` (weigh-in and panel;
  no model bracket; survivors go to people) or `specified`.
- **Plug-in contract** (`barclays.official-request/0.1`, `barclays.official-response/0.1`, `barclays.plugins/0.1`;
  `docs/PLUGINS.md`): how an official that lives in a sibling repository is called. The venue writes a request
  file and runs the plug-in as a separate process; the plug-in writes a response file. The venue validates the
  response and turns anything missing, malformed or out of vocabulary into `unverified`. The result is the same
  `barclays.official-result/0.1` a built-in official produces. A card may name an official this venue has no
  plug-in for: it reports `unverified` and the verdict carries `PLUGIN_MISSING:<name>`.
- **Bout** (`barclays.bout/0.1`, `<bout>/bout.json`): event id, purpose, audience, a **sensitivity label**
  (`synthetic`, `public`, `internal`, `restricted`; no label, no judging), an optional baseline, candidates (id plus
  files), sources, and optional `params`. Every path must resolve inside the bout directory, and a symbolic link
  anywhere on the way to an input or inside a source directory is refused. `params` may set only what the card
  lists under `bout_may_set`; anything else is refused, a misspelled official id is an error, and each allowed
  override becomes a `BOUT_OVERRIDE:` flag in the verdict.
- **Official result** (`barclays.official-result/0.1`): official, version, kind (`deterministic` or `executable`),
  authority, status (`pass`, `fail`, `unverified`, `not_applicable`), **findings** (objective, reproducible),
  **leads** (heuristic, never decisive), metrics, a receipt, the candidate's content hash. For executed suites
  the card sets `reveal`: `traces`, `names` or `counts`. Held-back suites use `counts`, so no test name, input or
  expected value reaches a result, a report or a panel packet.
- **Lens card** (`barclays.lens/0.1`, `lenses/*.json` here and `cards/*.json` in `barclays-lenses`): kind
  (stylistic voice, disciplinary lens, audience proxy, adversarial role, fact desk), a brief, `may_assess`, the
  source it was derived from, cleared sensitivity labels. `may_assess` is drawn from a **closed list of lanes**
  (`OPINION_LANES` and `FACT_LANES` in `barclays/lenses.py`), matched exactly as written. A fact desk may list only
  factual lanes and raises allegations only; every other lens may list only opinion lanes. A word the venue does
  not know is refused, because a new word is how factual authority gets into a voice.
- **Panel record** (`barclays.panel/0.1`): per packet, the validated result; per reviewer, lens and pair, one
  reconciled preference across both display orders (or `order_sensitive`, which abstains); in-lane objections,
  out-of-lane objections, allegations (always `unverified` until checked). Marked advisory. Packet ids are
  random; which lens, pair and order a packet holds is recorded only in `panel/meta`, which reviewers never see.
  Objections are routed by allowlist: in this lens's lane, in another opinion lane, or else an allegation. An
  objection whose own words make a claim about facts or about the source is recorded as an allegation as well,
  whatever category the reviewer filed it under, and an entry that names no candidate is kept as an allegation
  against the pair. The organiser may choose who sits on a bout's panel (`--panel-lenses`); the choice is
  recorded in `panel/roster.json`, travels into the verdict, and a panel with no fact desk is flagged. A finished
  panel reaches a verdict with `bc run --panel-from <run>`, refused unless the panel read exactly the bytes the
  bout holds and the panel run still agrees with its own ledger.
- **Verdict** (`barclays.verdict/0.1`): the controller's status vocabulary, recommended and shortlisted ids,
  flags, per-candidate eligibility with reasons, an evidence grade per stage (executed, real reviewers, simulated),
  `human_decision`, the shadow bracket when run, the attached panel when there is one, candidates a model gate
  excluded inside the bracket (kept apart from weigh-in disqualification), the controller's identity and
  contract hash, and provenance (event, bout, candidate and source hashes, official versions).
- **Ledger** (`barclays.ledger/0.1`): `ledger.jsonl`, one event per step, each carrying the hash of the previous
  event and the SHA-256 of every object it refers to; objects live once under `objects/<sha256>`. A finished
  run ends with a `seal` event over every file, directory and link in the run directory (a database by its
  schema and rows; permissions and timestamps are left out because they do not survive a copy). The seal carries
  a format number, so a run sealed by an earlier version is checked by the rules it was sealed under. `bc verify`
  reports two things: whether the
  directory is consistent with its own ledger (chain, objects, the sealed tree, eligibility re-derived from the
  recorded results), and whether it is authenticated (the head equals one recorded outside the run, given with
  `--expect-head`). Consistency catches careless edits. Only the outside head shows it is the run that happened.

## 5. The questions in the brief

**How does an organizer specify objective, audience, constraints and success criteria?** In the event card
(reusable, per genre) and the bout (this contest). The card names the checks that are decisive, the criteria that
are judged and their weights, and the threshold for "materially better". The bout names the reader and the purpose.

**How are exact candidate versions and sources identified?** By content. A candidate's identity is the hash of its
file names and bytes; ids, labels and authors are not part of it. Sources, the event card and the bout are hashed
into the manifest. Every result carries the candidate hash it was computed on, the verdict lists them all, and the
controller's own decision binds its contract hash and the selected candidates' hashes. A re-edited candidate is a
new candidate.

**How are deterministic checks, rubrics, model judges and human review combined without pretending they are
equivalent?** By stage and by authority, never by averaging. A decisive official's failure disqualifies and no
judge can outvote it. Advisory officials and the panel produce leads, objections and allegations. Model judges
decide only among candidates that passed, and only on the judged criteria. The verdict states an evidence grade per
stage, and a human rule fires on ties, inconclusive results, open leads, unverified allegations, simulated judging
and sensitive material.

**How is there room for no clear winner, uncertainty and abstention?** The status vocabulary has five values and
only one of them names a winner. A candidate that could not be verified is `incomplete`, not a loser. A judge whose
two display orders disagree abstains. A baseline that still fails the target is flagged `TARGET_UNMET`, so
"no change" is never read as "solved".

**How do we detect judges rewarding polish over substance?** Three ways. The weigh-in makes the question moot for
anything a deterministic or executable check can express. The shadow bracket reruns the same judges over every
candidate with no weigh-in and reports whether they would have promoted a disqualified one. The panel probe puts
the same pair in front of real reviewers without the reference material. What these showed is in
`CALIBRATION.md`; the short version is that the simulator was told to prefer polish, and the real reviewers, on
these fixtures, mostly did not.

**How do we evaluate agreement, position bias, repeatability, cost and latency?** `bc calibrate` reruns each bout
across seeds and with position-biased simulated judges, and reports how often the verdict holds; the controller
reports per-judge flip and abstain rates and call and token usage; officials report their own duration. What is
missing is agreement with human gold. Nothing in this repository claims it.

**How is sensitive material kept inside its boundary?** A bout without a label is refused. Each event, official,
lens and reviewer route declares the labels it is cleared for, and a mismatch is refused before anything is
written (exit code 2). Bout paths cannot leave the bout directory and symbolic links are refused. Built-in
officials run locally and send nothing. Executed candidate code runs in a jail that holds the interpreter and the
candidate's own files and nothing else. The software event still refuses `restricted` material, because a
namespace jail is not a hardened sandbox. Held-back suites reveal counts only. Honest limits are in
`CALIBRATION.md`: the run directory holds copies of the material, so a run directory inherits the bout's label,
and a hard link cannot be told from a file.

## 6. Repository strategy

**The rule.** Split a repository off only at a seam where the dependencies, the owner of the truth or the access
rule differs, and only when something real sits on the other side of the seam. Version 0.2 had one repository and
four named triggers. On 5 November, at the owner's direction, the seams that had something real behind them were
cut. Details, evidence and limits for each are in `docs/FAMILY.md`. Only this repository is public.

| Repository | The seam | What made it real |
|---|---|---|
| `barclays-center` | The core: standard library only | Two genres calibrated end to end |
| `barclays-lenses` | The owner of the truth differs: what a voice may claim belongs with the voices | Twelve of the owner's skills read and bound as lens cards, pinned by hash |
| `barclays-officials-web` | Dependencies differ: Chromium, Playwright, axe-core | Six checks that run on six fixture sites and through the venue |
| `barclays-officials-game` | Same dependency, different input (a test hook and bots) and a different human boundary (playtests) | Four checks that run on six fixture games and through the venue |
| `barclays-officials-code` | Dependencies differ: third-party linters with their own releases and licences | Five static checks; four advise on the software card |
| `barclays-gold` | The access rule differs: gold is owned by someone who is not a builder | Blind ballots and a scorer that work today on placeholders. It holds no human gold |

Each sibling is connected by a file contract, never by an import (section 4 and `docs/PLUGINS.md`), so each can be
versioned, tested and reviewed alone. `tests/test_family.py` runs the whole chain when the siblings are checked
out beside the venue and skips when they are not.

Not created, because nothing real would sit behind the seam yet:

| Future repository | Trigger | Why it would be separate |
|---|---|---|
| `barclays-officials-grounding` (MiniCheck, HHEM, LettuceDetect adapters) | A grounding model has been run and compared with human labels on the reversal attacks | Model weights, their licences and an optional GPU runtime. No weights could be downloaded or run in this session. |
| `barclays-officials-citations` (DOI and reference resolution) | The `research-synthesis` card is commissioned | It needs the network, which an offline core must not. |
| A gold directory for a real corpus | The owner names the corpus and the gold owner | It holds decisions about real work, under its owner's access. `barclays-gold` is the tool, not the place. |

Not planned: a Barclays controller, a Barclays router, a Barclays evidence store, or a website evaluator that
competes with the one the owner already has.

## 7. Changes proposed to the controller (not made)

Building the venue turned up nine changes the controller would benefit from. None was made: the controller's own
rules say builders do not edit it. They are written up for its owner and kept with the project's private
documents. Two of them shape how the venue behaves today and are visible in its code. Event cards set `finalists`
to 3, because the controller's lightest preset cannot return a tie between two challengers. And the host, not the
model, writes the envelope around a native judge's answer (`tools/native_envelope.py`).

## 8. What changed after the independent reviews

The review of version 0.1 found that four of nine claims failed. A second review then attacked the fixes and
demonstrated seven defects (`docs/review/RE-REVIEW.md`). A third attacked the fixes to the second and the two
paths nobody had touched (`docs/review/REVIEW-3.md`); two areas failed. The table says what each claim is now
and where the evidence is. "Restated" means the claim was wrong as worded and has been cut back to what the code
does. What each later review changed follows the table.

| Claim as first made | Review | Now | Evidence |
|---|---|---|---|
| C1 The fact ledger protects against meaning change | fails | **Restated, twice.** A dropped ledger fact, an invented figure (a percentage or ordinal counts as its own figure; counts of ten or under are ignored) and an invented quotation are caught on bytes. A sentence that keeps every surface form and reverses its meaning is not; negation and swapped numbers are raised as leads; a fabricated statement in indirect speech raises nothing. | `fixtures/_attacks/editorial/ATTACKS.json`: 6 caught decisively, 3 lead only, 2 not caught, 2 false positives remaining |
| C2 Software needs held-back suites; opinion cannot substitute | fails | **Fixed.** The oracle is a separate process; forged results, a rigged `__eq__`, exiting, hanging and an oversize answer all fail; a bout cannot repoint a suite. Equality is the suite's: types must be asserted by the suite. | `fixtures/_attacks/software/ATTACKS.json`: 10 caught decisively, 1 not caught (the static filter, contained by the jail) |
| C3 The venue can decline to pick a winner | holds with limits | Holds. All four non-winning statuses are reached in fixtures, and the first real bracket returned INCONCLUSIVE. | `results/calibration-run4`, `results/real-bracket-01` |
| C4 Missing evidence is neither fail nor pass | fails | **Fixed and reworded.** A harness failure is `unverified`. A candidate that exits or twice fails to answer in time has failed. | `tests/test_attacks.py` |
| C5 Lenses are advisory and have no factual authority | holds vacuously, then failed in the third review | **Fixed twice, and bounded.** A panel reaches the verdict and changes nothing but flags and reasons. Lanes are a closed list, so a card cannot claim factual authority under another spelling. A mislabelled entry is kept, and an objection that reads as a factual claim is also an allegation. Not closed: a reviewer who stays silent, or words a factual claim as taste. | `tests/test_attacks.py` (`PanelReachesTheVerdict`), `results/panel-probes-v2` |
| C6 Sensitivity refusal; inputs stay inside the bout | holds with limits | **Tightened.** Symbolic links refused; executed code jailed; held-back suites reveal counts. | `tests/test_attacks.py` |
| C7 Tamper-evident records | holds with limits | **Tightened and cut back.** Every file, directory and link in a finished run is under the seal (the controller's database by its schema and rows). Permissions and timestamps are not. That catches careless edits only: a short script produces a fully consistent forgery. `verify` reports `consistent` and `authenticated` separately; only the head recorded outside the run authenticates. | `tests/test_attacks.py`, `tests/assets/forge_consistent_run.py` |
| C8 Calibration against frozen expectations | headline overclaims | **Restated.** A regression test of the author's own cases with simulated judges, plus a small set of real-model runs. Whole fixtures and event cards are frozen. | `docs/CALIBRATION.md` |
| C9 Candidate content is data | fails | **Fixed for execution and for multi-file candidates.** Not tested: a candidate whose text tries to instruct a model judge. | `docs/CALIBRATION.md` section on what remains unproven |

The reviewer also asked whether the panel is a second, smaller judging pipeline. It still is one: it pairs, swaps
orders and reconciles. It is kept because the controller has no lens concept, it is advisory by construction, and
it now feeds the verdict. Folding it into the controller's challenge loop is one of those proposals and roadmap work.

### The third review

It ran every attack. The code jail from inside, forged protocol replies and the answer-size rule held. What
failed or held only with limits:

| Finding | What it showed | Now |
|---|---|---|
| R3-01 (major) | A reviewer could make a factual allegation disappear. A lower-case label was dropped in silence, and a factual claim filed under an opinion category counted as an opinion, so the reason for a person to look was gone. | An entry that names no candidate is kept as an allegation against the pair. An objection whose words read as a claim about facts or the source is an allegation as well. The screen is a word list: a reviewer who stays silent, or words the claim as taste, is not detected. |
| R3-02 (major) | One malformed result file stopped the whole import. | One bad file marks one result invalid. |
| R3-03 (major) | "Approximately $700" for the source's "approximately $688" ended cleanly eligible. | Still eligible, because on the page it is identical to a faithful rounding. It now carries a major lead, so the open-leads rule requires a person. A bare figure with no marker of approximation is a new figure and disqualifies. |
| R3-04, R3-05 (minor) | The seal ignored database schema objects, added directories, permissions and timestamps. | Schema, directories and links are sealed. Permissions and timestamps are not; a ledger other accounts can write is a warning. |
| R3-06 (minor) | A bout's `allow` list can whitelist an invented figure. | Still possible and flagged. A bout that changes any decisive check now requires a person. |
| Read, not run | A bout could set a per-call time limit of 0.01 s and time out every candidate. | A bout cannot set a number the card gives no value for; the card's value bounds it to a factor of ten. |
| From its tally | Proportions in words ("a third", "one in three", "double") passed the number check unseen. | Each one the source does not state in the same terms is a major lead. Never a finding: "a third" can restate 33 percent. |

### The fourth review: the plug-in interface and the three plug-ins

`docs/review/REVIEW-4.md`. Website candidates could not reach the network, the code plug-in never ran candidate
code, and a bout could not loosen a decisive setting. Four findings were against the venue's wrapper and are
fixed here: a `pass` with a critical finding was accepted; a plug-in could rewrite the plug-in table in mid-run;
responses had no size or shape limits; a plug-in could leave a file in the run unremarked. Three were against the
plug-ins: a website that breaks on the first click passed, and both decisive game checks could be defeated by the
candidate's own test hook. What each plug-in did about its findings is in its `docs/REVIEW-RESPONSE.md`, and
`docs/CALIBRATION.md` section 7 has the table.

### The review of the first two siblings

A fifth review attacked `barclays-gold` and `barclays-lenses`. It is kept in those two private repositories, and
each one's `docs/REVIEW-RESPONSE.md` answers its own findings. One finding changed the venue: a voice card could carry
factual authority by spelling the lane differently ("Accuracy ", "fidelity", "evidence", "truth"), because the
check was a short list of forbidden words. Lanes are now a closed list in the venue and in the registry, kept
equal by a test.
