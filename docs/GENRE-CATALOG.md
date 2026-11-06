# Barclays Center genre catalog

One universal rubric is the wrong tool. A clause-level policy rewrite, a game build and a table of extracted values fail in different ways, and a single "which is better?" question hides which ones can be settled by looking at bytes and which cannot. An event card fixes, for one genre, what is checked on bytes, what is judged, by whom, and what only a human can decide. This catalog describes the nine cards in `events/`. Two are runnable end to end. Two are `officials_runnable`: their checks run through plug-ins in sibling repositories (`docs/PLUGINS.md`), there is no model bracket, and the survivors go to people. Five are specified: designed and validated against the schema, but their officials are not built, so they cannot run.

Tool names and licences come from the research notes (A: text evaluators, B: software, UI and games, C: tournaments and judge reliability). Anything the notes could not verify is marked UNVERIFIED. Archived status of upstream repositories was not checkable and is UNVERIFIED for all of them.

## 1. Summary

| Genre | Status | Format | Decisive checks (officials) | Judged criteria | Lenses | Human evidence needed |
|---|---|---|---|---|---|---|
| editorial-revision | runnable | bracket, both orders, baseline | fact ledger, new numbers, quotes | clarity, argument, voice, economy | plain-language-editor, measurement-scientist, fact-desk | the author; real readers |
| software-change | runnable | bracket on survivors | static, pass-to-pass, fail-to-pass; advisory through a plug-in: committed credentials, lint, security scan, complexity | maintainability, generality, economy | maintainer, adversarial-tester | maintainers' merge decision |
| research-synthesis | specified | gauntlet then finals | cite.resolves, cite.quote_verbatim, cite.number_grounded | weighting, calibration, conflicts, coverage, clarity | fact-desk, research-methodologist, measurement-scientist, plain-language-editor | expert; support of claims by passages |
| ui-website | officials runnable (plug-in); no bracket | gauntlet, advisory panel, people | load, structural HTML, links, axe-core, 320px reflow | none ranked by models in this version | accessibility-auditor, first-time-visitor, plain-language-editor | real users: task success, SUS |
| game-build | officials runnable (plug-in); no bracket | gauntlet, panel, human play | boot, bot completes level 1, softlock (input latency advises) | none ranked | game-designer, novice-player, adversarial-tester | play sessions with miniPXI |
| policy-document | specified | champion-challenger | cross-references, numbering, defined terms, required provisions, frozen text | implementability, clarity, proportionality, intent | policy-counsel, district-administrator, plain-language-editor | counsel; policy owner |
| factual-extraction | specified | scored against gold | schema, locator, identifiers, gold agreement | none | none | gold labels; owner |
| instructional-material | specified | gauntlet then finals | objectives, answer key, reading band, accessibility basics | explanation, alignment, scaffolding, feedback, relevance | classroom-teacher, learning-scientist, measurement-scientist, plain-language-editor, fact-desk | teachers and learners |
| manuscript-production | specified | checklist, no winner | citations match, numbering, style sheet, callouts, permissions | none | none | editor; rights holders |

## 2. The genres

### 2.1 editorial-revision (runnable)

**Objective.** Promote a revision only if it keeps every fact the source carries, adds nothing the source cannot support, and is materially better for the stated audience. Smoother is not better.
**Inputs.** One or more text files (every file is checked); sources are the draft and a fact ledger, with optional evidence.
**Format.** Bracket under the controller (light profile, three judges per match, at most 400 model calls) plus an advisory panel, both display orders. A baseline makes it champion-challenger in effect.
**Officials (built).** `text.fact_ledger`, `text.new_numbers` (challengers; integers up to 10 ignored; number words and scales normalised) and `text.quotes` (three words or more; single or double marks) disqualify. `text.hedge_shift` (dropped hedges, changed negation) and `text.number_roles` (numbers in a different order) advise.
**Judged.** Clarity 0.35, argument 0.25, voice 0.2, economy 0.2, with a no-new-claims gate.
**Lenses.** Plain-language-editor (clarity, voice, economy), measurement-scientist (argument, inference), fact-desk (the only lens that may raise factual objections, as allegations).
**Disqualified when.** A ledger fact is absent in every surface form the ledger lists, a number is in neither source nor evidence, or a quotation is not verbatim. **Not disqualified:** a sentence that keeps every figure and reverses its meaning. That is raised as a lead, which sends the bout to a human, and by the model gate.
**Judges.** Two or more model families, author family excluded, blind. No route has been calibrated against human gold.
**Abstains.** Tie or cycle, no challenger clears the 5-point improvement threshold, lost quorum, or an unverified challenger.
**Human decides.** Ties, inconclusive results, open critical leads, unverified allegations, a candidate excluded by a model gate, simulated judges, and any label beyond synthetic or public.
**Cannot establish.** Whether the revision still sounds like its author, whether an unledgered fact was lost, or whether real readers are persuaded.

### 2.2 software-change (runnable)

**Objective.** Promote a code change only if it passes tests the author could not see, breaks nothing that worked, and is the better change to maintain.
**Inputs.** One or more Python files whose contract is module-level functions over plain data; sources are the task, the visible tests, and the held-back pass-to-pass and fail-to-pass suites (SWE-bench vocabulary).
**Format.** The same bracket and panel as above, on candidates that already passed execution.
**Officials (built).** `py.exec_tests` on pass-to-pass (all candidates) and fail-to-pass (challengers) disqualify: the suite runs in a trusted process, the candidate in a separate jailed one, and the held-back suites reveal counts only. `py.static` (a source filter for imports and calls, special-case detection) also disqualifies, but it can be evaded and is not what protects the harness. The visible suite is advisory.
**Officials (plug-in, advisory).** `code.secrets`, `code.lint` (ruff), `code.security` (bandit) and `code.complexity` from `barclays-officials-code`. They never execute the candidate. They produce a few objective findings (a key-shaped credential, an undefined name) and many leads for a reviewer, and they travel to the panel as tool output. A clean lint or security scan does not show code is correct, safe or maintainable. Without the plug-in they report `unverified` and the verdict says `PLUGIN_MISSING`.
**Judged.** Maintainability 0.4, generality 0.35, economy 0.25.
**Lenses.** Maintainer; adversarial-tester, whose proposed failing inputs are allegations until run.
**Disqualified when.** It does not parse, uses a forbidden import, fails either held-back suite, will not import, exits, or twice fails to answer in time.
**Judges.** Rank maintainability only; they do not rule on correctness.
**Abstains.** Several passers tie, every challenger fails (NO_CHANGE), or a suite could not run or needs something the official cannot carry across a process boundary (INCONCLUSIVE).
**Human decides.** As above, minus the allegation rule.
**Cannot establish.** Behaviour the hidden suites do not exercise, whether maintainers would merge, or end-to-end behaviour. Privacy excludes restricted material until a real sandbox such as [bubblewrap](https://github.com/containers/bubblewrap) replaces the namespace-and-chroot jail.

### 2.3 research-synthesis (specified)

**Objective.** Promote a synthesis only if every citation resolves in the source pack, every quotation is verbatim in its cited source and every cited figure is there, then choose the one that weighs evidence best.
**Inputs.** A Markdown file; a hashed source pack, a requirements ledger, optional known conflicts.
**Format.** Gauntlet then finals, pairwise in both orders. Checks first because they can eliminate everyone.
**Officials (planned).** Decisive: `cite.resolves`, `cite.quote_verbatim` (wraps rapidfuzz, MIT), `cite.number_grounded`. Advisory: `cite.coverage`, `cite.conflict_acknowledged`, `cite.grounding_score` wrapping [MiniCheck](https://github.com/Liyan06/MiniCheck) (code Apache-2.0, Flan-T5-Large weights MIT) and [HHEM-2.1-Open](https://huggingface.co/vectara/hallucination_evaluation_model) (Apache-2.0). Both are leads until calibrated. [Independent work](https://arxiv.org/html/2501.14883v2) found true-positive and true-negative rates diverging by more than 20 points on 7 of 14 datasets, so the two are reported separately.
**Judged.** Evidence weighting 0.25, calibration of confidence 0.25, conflict handling 0.2, coverage balance 0.15, clarity 0.15.
**Lenses.** Fact-desk, research-methodologist, measurement-scientist, plain-language-editor.
**Evidence and judges.** The pack, ledger and candidates hashed; each disqualification names the citation, source and locator; grounding leads record the model revision and threshold. Two or more families, author family excluded, blind; none calibrated.
**Abstains.** Nobody passes, tie or cycle, a decisive official cannot run.
**Human decides.** The usual set.
**Cannot establish.** That a cited passage supports its claim, that the pack is the right one, or that unlisted conflicts do not exist.

### 2.4 ui-website (officials runnable through a plug-in; no bracket)

**Objective.** Promote a site only if it loads cleanly and passes agreed integrity and accessibility checks, then choose the better site for the stated visitor and tasks.
**Inputs.** A flat static build; brief, task scripts, viewports.
**Format.** Gauntlet, then an advisory panel, then people. The card was designed with judged finals; this version has no model bracket for it, because the controller has no adapter for rendered pages and no judge has been calibrated against visitors.
**Officials (built, in `barclays-officials-web`).** Decisive: no console errors, uncaught exceptions or failed local requests at three viewports (`web.load_console`); internal links and anchors resolve (`web.links`; external links are listed, never fetched); no horizontal overflow at 320px (`web.no_hscroll`); a built-in structural HTML check for a missing doctype, title or `lang`, duplicate ids and images with no `alt` (`web.html_valid`; it is not the Nu Html Checker); [axe-core](https://github.com/dequelabs/axe-core) violations at the agreed impact (`web.axe`; `unverified` when axe-core is not installed, never a pass). Advisory: scripted task journeys (`web.task_success`, in the journey format the owner's existing website evaluator uses). The candidate's pages are served to the browser by a request handler with the network blocked.
**Officials (still planned).** A full validator ([Nu Html Checker](https://github.com/validator/validator) or [html-validate](https://github.com/html-validate/html-validate), both MIT) and a link checker with external verification ([lychee](https://github.com/lycheeverse/lychee)). Advisory: Lighthouse (Apache-2.0, median of runs), IBM Equal Access (Apache-2.0), task-script success, and a screenshot-checklist model (protocol from [ArtifactsBench](https://arxiv.org/html/2507.04952v2), 94.4% ranking consistency with WebDev Arena, whose method is UNVERIFIED).
**Judged.** Navigation clarity 0.3, visual hierarchy 0.25, content clarity 0.25, consistency 0.2.
**Lenses.** Accessibility-auditor, first-time-visitor, plain-language-editor.
**Evidence and judges.** Tool and browser versions, viewport and page state for every run, the raw axe report including incomplete items, and the screenshots shown. Judges see normalised captures of survivors and rank design only; none calibrated against visitors.
**Human decides.** Always.
**Cannot establish.** Automated checks find only a fraction of WCAG problems: [Deque](https://www.deque.com/automated-accessibility-coverage-report/) reports 57.38% of issue instances by volume (vendor data) and about 20 to 30% of success criteria testable; the [UK GDS test](https://accessibility.blog.gov.uk/2017/02/24/what-we-found-when-we-tested-tools-on-the-worlds-least-accessible-webpage/) found 17% to 41% per tool, 71% combined, 29% missed by all. No automated check or simulated user shows a site works for people; that needs real-user task success and SUS (SUS validity UNVERIFIED in the notes). UXAgent ([paper](https://arxiv.org/pdf/2504.09407)) did not compare agents with real users.

### 2.5 game-build (officials runnable through a plug-in; no bracket)

**Objective.** Narrow builds to those that boot, respond in time, can be finished by a bot and show no softlock. Never rule on fun.
**Inputs.** A browser build exposing a test API; design brief, test contract, bot script.
**Format.** Gauntlet, advisory panel, human play sessions. No bracket: the only thing left to rank survivors on is fun, which no judge reads from a trace and no proxy predicts. The criteria weights already sum to 1 should a bracket ever be validated.
**Officials (built, in `barclays-officials-game`).** Decisive, on games that expose the plug-in's test hook (`window.__barclays`): boot with no console errors and a canvas that draws (`game.boot`), the organiser's bot completes level 1 on every seed (`game.bot_completes_level`), no softlock in seeded random play, each reproduced by seed (`game.softlock_search`). Advisory: completion rate and steps by bot skill and level (`game.difficulty_curve`). A game without the hook gets the boot check only; the rest report `unverified`. A candidate can lie through its own hook; the only guard is a lead for an implausibly fast win.
**Officials (still planned).** Input response time (it advises; headless timing on a shared host is not perceived latency), bot win rates, first-player advantage, frame time. Bots would sit behind [Gymnasium](https://github.com/Farama-Foundation/Gymnasium) (MIT). Ludii is excluded (CC BY-NC-ND 4.0).
**Lenses.** Game-designer, novice-player, adversarial-tester.
**Evidence and judges.** Seeds, input traces, raw latencies and win rates with game counts; every softlock reproduced by seed. Panel reviewers propose objections and test ideas, never rankings.
**Abstains.** More than one survivor is TIED_SHORTLIST by design.
**Human decides.** Always.
**Cannot establish.** No automated proxy has been validated as predicting human-reported fun; the closest [study](https://arxiv.org/html/2407.11396v1) measured perceived balance on 71 respondents with mixed results. Fun claims need play sessions with a validated instrument such as the [miniPXI](https://arxiv.org/html/2407.19516v1), whose test-retest reliabilities ran from .365 to .704. PXI construct validity is UNVERIFIED in the notes.

### 2.6 policy-document (specified)

**Objective.** Promote a revision over the adopted version only if it is consistent, complete against a requirements ledger, leaves frozen provisions unchanged and is clearly better to implement.
**Inputs.** Full revised text; the adopted version as baseline, ledger, frozen list, optional rationale.
**Format.** Champion-challenger in both orders, because the production question is "better than today's text".
**Officials (planned).** Decisive: `policy.xref_resolves`, `policy.numbering_consistent` (markdownlint, MIT, plus custom), `policy.defined_terms` (Vale, MIT), `policy.required_provisions`, `policy.frozen_unchanged`. Advisory: `policy.plain_language` ([textstat](https://github.com/textstat/textstat), Vale, alex, all MIT) and `policy.obligation_delta`, a custom modal-verb diff giving leads for counsel.
**Judged.** Implementability 0.3, clarity 0.3, proportionality 0.2, fit to intent 0.2.
**Lenses.** Policy-counsel, district-administrator, plain-language-editor.
**Evidence and judges.** Adopted version, ledger and frozen list hashed; the obligation-delta listing provision by provision for counsel. Judges rank implementability and clarity, not legal effect.
**Abstains.** No challenger clears the threshold (NO_CHANGE), or the adopted version fails an official and is not a valid comparator.
**Human decides.** Any RECOMMEND, plus ties, inconclusive results and non-public material.
**Cannot establish.** Legal effect, which is for counsel, or stakeholder acceptance, which is for the policy owner and affected parties.

### 2.7 factual-extraction (specified)

**Objective.** Choose among extractions (CV and publication metadata, table values) on schema validity, traceability and exact agreement with held-out gold.
**Inputs.** JSON records with source locators; documents, schema, gold subset.
**Format.** Scored against gold. No bracket, no panel. Extracted values have a determinable answer; judges without source access favour fluency, and non-reasoning judges sit near chance on checkable correctness (JudgeBench: GPT-4o 56.57% against 50%).
**Officials (planned).** Decisive: `extract.schema_valid` (jsonschema or pydantic, MIT), `extract.locator_traceable` (rapidfuzz), `extract.no_fabricated_ids`, `extract.gold_agreement` (placeholder: 0.95 exact, at least 50 gold items). Advisory: identifier lookups through bibtex-updater ([HALLMARK](https://github.com/rpatrik96/hallmark); 0.820 detection at 0.051 false positives, co-designed so an upper bound) and candidate disagreement.
**Lenses and judges.** None: no model reads the candidates. The gold subset needs at least two independent annotators with reported chance-corrected agreement. Thresholds are fixed before scoring, with intervals.
**Abstains.** Overlapping intervals, too small a gold set, nobody meets the threshold.
**Human decides.** Ties, inconclusive results, non-public material.
**Cannot establish.** Correctness outside the gold subset; gold is also human and noisy, so its annotator agreement is reported.

### 2.8 instructional-material (specified)

**Objective.** Promote material only if each stated objective is addressed, machine-checkable keys are right, reading level is in band and accessibility basics hold; then choose on pedagogy.
**Inputs.** Lesson files with objective tags; objectives, reading band, curriculum reference.
**Format.** Gauntlet then finals; the panel stands in for a teacher.
**Officials (planned).** Decisive: `edu.objectives_covered`, `edu.answer_key` (custom recomputation, never running candidate code), `edu.reading_level` (textstat, a descriptive statistic only), `edu.accessibility_basics` (html-validate, axe-core, markdownlint). Advisory: language leads (alex).
**Judged.** Explanation quality 0.3, task alignment 0.25, scaffolding 0.25, feedback 0.1, relevance 0.1.
**Lenses.** Classroom-teacher, learning-scientist, measurement-scientist, plain-language-editor, fact-desk.
**Evidence and judges.** Each answer key item recomputed or marked not applicable, never passed by default. Judges rank pedagogy among survivors; none calibrated against teachers.
**Abstains.** Nobody passes, ties, or too little was machine-checkable.
**Human decides.** Always.
**Cannot establish.** Learning effect, which needs evidence from learners (pre and post items, a comparison group, delayed retention) and from teachers who use it. Item quality needs response data.

### 2.9 manuscript-production (specified)

**Objective.** Report whether a chapter or volume is ready for production. No winner, no ranking.
**Inputs.** Manuscript and bibliography files; style sheet, figure and table inventory, permissions ledger.
**Format.** Checklist gauntlet; each version gets its own report.
**Officials (planned).** Blocking: `ms.citations_match_refs` (pybtex or bibtexparser, MIT), `ms.xref_numbering` (markdownlint), `ms.style_sheet` (Vale), `ms.figure_table_callouts`, `ms.permissions_complete`. Advisory: `ms.references_resolve` (bibtex-updater; a single-source miss is a prompt for a person, since a DOI-only check detected 21.8% of fakes and LLM lookups had a 0.478 false-positive rate), links (lychee), language leads (LanguageTool as a local server, LGPL-2.1).
**Lenses and judges.** None: no model judges the manuscript. A copyeditor or production editor works the blockers and leads.
**Abstains.** It never names a winner. A check that cannot run is unverified, never a pass.
**Human decides.** Always.
**Cannot establish.** That the manuscript is good, that a reference supports its claim, or that permissions are legally sufficient.

## 3. Formats and when to use them

Counts assume each pairing is judged in both orders; they are derived arithmetic. Scheduling, ranking and decisions are done by the existing controller (adversarial-tournament-review, `atr/1`), not by Barclays Center. The Swiss, elimination and Delphi cells rest on standard practice; no source was opened for them (UNVERIFIED).

| Format | Cost for N candidates | Main pathology |
|---|---|---|
| Pairwise, both orders | 2 calls per pair | Order flips are common: GPT-4 stayed consistent in only 65.0% of MT-Bench pairs ([Zheng 2023](https://arxiv.org/abs/2306.05685)). |
| Round robin | N(N-1) calls | Quadratic. Judge non-transitivity of 3.98 to 22.9% of triplets ([Xu 2025](https://arxiv.org/abs/2502.14074)). |
| Swiss | about N/2 pairs per round, log2 N rounds | Early noise misseeds later rounds; needs a rating model. |
| Elimination | N-1 matches | One noisy verdict removes a strong candidate; never abstains. |
| Champion-challenger | N matches against the incumbent | Depends on the incumbent: 20% of models kept rank across 20 fixed baselines (Xu 2025). |
| Gauntlet then finals | checks nearly free; finals on survivors only | The disqualifier set must be frozen first or it drifts ([Shankar 2024](https://arxiv.org/abs/2404.12272)). |
| Panel | N times J jurors | Pointwise scores compress and are easily moved by universal phrases ([Raina 2024](https://arxiv.org/abs/2402.14016)). |
| Debate or challenge-rebuttal | rounds times agents times candidates | Majority voting explains most gains ([Choi 2025](https://arxiv.org/abs/2508.17536)). |
| Checklist, no winner | one pass per item | Ranks nothing, by design. |

## 4. Lenses are not authorities

A lens is a way of reading, not a source of truth. The rules:

1. **A lens card declares its limits.** It names a kind, a brief, what it `may_assess`, the sensitivity labels it is cleared for, and in `notes` what it cannot establish. `may_assess` is drawn from a closed list of lanes. Only a `fact_desk` lens may list a factual lane, and it may list nothing else; a word the venue does not know is refused. An opinion lane covers the reasoning as the draft presents it. Whether a statement is true, complete or what the source says is the fact desk's, and comes out as an allegation. Role prompts add diversity of critique, not competence: adding personas did not improve accuracy across 162 personas and nine models ([Zheng 2023](https://arxiv.org/abs/2311.10054)).
2. **Factual objections are allegations until verified.** An official or a second checker confirms them. Judges follow persuasive wrong advice about as often as right advice ([Kenton 2024](https://arxiv.org/abs/2407.04622), [Khan 2024](https://arxiv.org/abs/2402.06782)), and fake references fooled GPT-4 in 69% of attacks ([Chen 2024](https://arxiv.org/abs/2402.10669)).
3. **Every objection quotes its passage.** A quote not found in the candidate is marked unresolved. This is a design rule from note C with no direct experiment behind it.
4. **Both display orders, one preference.** A reviewer whose orders disagree abstains. Position bias is strongest on near-equal pairs ([Shi 2024](https://arxiv.org/abs/2406.07791)), and GPT-4's consistency under swap was 65.0% ([Zheng 2023](https://arxiv.org/abs/2306.05685)).
5. **A model playing an audience is not that audience.** Simulated users are unreliable proxies; success varied by up to 9 points with the model playing the user ([Lost in Simulation](https://arxiv.org/abs/2601.17087v1)), and UXAgent did not compare agents with real humans.
6. **Reviewers do not see each other's votes.** Eleven of fifteen models followed a fake majority ([Koo 2023](https://arxiv.org/abs/2309.17012)). Candidate text is untrusted data, since optimised injections succeeded 90.8% to 98.9% of the time ([JudgeDeceiver](https://arxiv.org/abs/2403.17710)).

The panel is advisory. It never disqualifies and never picks a winner.

**Real voices.** The sibling repository `barclays-lenses` binds twelve of the owner's voice and review skills as lens cards (three scholar-modelled editorial voices, two writers' workshops, the fact checker, anti-slop and prose craft, technical editing, citation and editorial integrity, a debate skill), each pinned to the file it was read from. An organiser seats them on a bout's panel with `--lenses <registry>/cards --panel-lenses a,b,c`; the choice is recorded in the verdict, and a panel with no fact desk is flagged. A voice card describes documented editorial standards. It does not speak as a person, and it decides nothing about facts.

## 5. Where these genres come from

Each genre maps to work the owner already runs as tournaments. That mapping names internal projects, so it is
kept with the project's private documents.

## 6. Adding a genre

1. Write the event card. State the objective, the decisive checks, the judged criteria, and what only a human can decide. Mark it `specified`.
2. Name or build the officials. Each decisive official wraps a named tool with a licence you have read, and returns findings (reproducible) separately from leads (heuristic).
3. Write the lens cards the panel needs. Each gets a brief, a `may_assess` list and a note on what it cannot establish.
4. Build fixtures with frozen expectations: a known-good candidate, a known-bad one, a close call, and a case with no winner.
5. Run calibration. Judges and thresholds must be scored against human gold on the genre with a chance-corrected statistic before they decide anything.
6. Only then mark the card `runnable`. A genre whose checks exist and whose judging cannot yet be trusted is `officials_runnable`: the checks decide who is out, and people decide among the rest.
