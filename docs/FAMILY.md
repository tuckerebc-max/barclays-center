# The Barclays Center family

Six repositories. One is the venue. Five plug into it. Each was split off at a seam where the dependencies, the
owner of the truth, or the access rule is different. Nothing was split for tidiness.

This repository, the venue, is public. The five siblings are private and are meant to stay private: several
hold material derived from the owner's private skill files or are meant to hold decisions about private work.
They are described here so that the venue's plug-in points make sense. The contracts they use are public
(`docs/PLUGINS.md`, and the lens card format in `docs/ARCHITECTURE.md` section 4), so anyone can write an
official or a lens registry of their own for the same venue.

## 1. The six

| Repository | What it is for | Why it is its own repository | Needs |
|---|---|---|---|
| `barclays-center` | The venue: event cards, the weigh-in, built-in checks for text and Python, the lens panel, the bridge to the tournament controller, the ledger, the verdict, fixtures and calibration | The core that everything else plugs into | Python 3.11+ standard library; the controller for a bracket |
| `barclays-lenses` | Lens cards bound to the owner's real voice and review skills, each pinned to the file it was read from; suggested panels per genre | What a voice may claim belongs with the voices and changes on their schedule. The venue must not carry voice content. | Python standard library |
| `barclays-officials-web` | Browser checks for the `ui-website` event | Needs Chromium and Playwright, and optionally axe-core. None of that may enter a standard-library core. | Python Playwright, Chromium; axe-core optional |
| `barclays-officials-game` | Bot-driven checks for the `game-build` event | The same browser dependency, a different input (a per-game test hook, organiser-supplied bots) and a different human-evidence boundary (playtests) | Python Playwright, Chromium |
| `barclays-officials-code` | Static checks for the `software-change` event: committed credentials, lint, security scan, complexity | Third-party linters with their own releases and licences (ruff MIT, bandit Apache-2.0) | ruff and bandit optional |
| `barclays-gold` | Blind ballots for people, and a scorer that measures any judge route against their decisions | Gold must be owned by someone who is not a builder, may carry a sensitivity label, and must never be visible to a run before that run is scored | Python standard library |

The family works with tools it does not own:

| Tool | Relation |
|---|---|
| `adversarial-tournament-review` (private) | The tournament controller. The venue compiles a campaign for it and reads its decision. Nothing in the family edits it. Changes proposed to it are kept with the project's private documents. |
| The owner's voice and review skill repositories | Sources of lens cards. Read, never written. |
| The owner's other tools: a website evaluator, an evidence layer, a router, atlases of outside tools | Read, or adopted by convention (exit codes, refusals, hashes not content). Never written. No integration yet. |

## 2. How they connect

```
        voice and review skills (the owner's, private)
                    |  read once, pinned by hash
                    v
            barclays-lenses  --- cards/*.json, lanes.json, rosters.json
                    |  bc --lenses <cards dir> --panel-lenses a,b,c
                    v
 bout + event card ---> barclays-center ---- campaign dir ----> adversarial-tournament-review
                         |     ^     |  <--- decision.json ----        (the controller)
       request.json      |     |     |
       (docs/PLUGINS.md) v     |     +--> run directory: manifest.json, panel/panel.json, verdict.json, ledger
                    response.json                         |
                         |                                |  gold.py score --panel / --route
  barclays-officials-web / -game / -code                  v
  (separate processes; never imported)              barclays-gold  <--- blind ballots filled in by people
```

Four contracts hold the family together. Each is a file format, so each repository can be versioned and tested
alone.

1. **Plug-in officials** (`docs/PLUGINS.md`). The venue writes a request file and runs the plug-in as a separate
   process. The plug-in writes a response file. The venue validates it: anything missing, malformed or out of
   vocabulary becomes `unverified`, never `pass`. A card may name an official the venue has no plug-in for; it
   reports `unverified` and the verdict says `PLUGIN_MISSING`.
2. **Lens cards and lanes** (`barclays.lens/0.1`). A card names what a lens may assess, from a closed list of
   lanes that the venue and the registry both carry and a test keeps equal. Only a fact desk may hold a factual
   lane. The registry's cards load in the venue's own loader.
3. **Run records** (`manifest.json`, `panel/panel.json`, `verdict.json`). `barclays-gold` reads a venue panel and
   binds each decision to candidate bytes through the run's manifest. It needs nothing else from the venue.
4. **The controller's campaign and decision** (`atr/1`). Unchanged from version 0.2.

## 3. Each repository: what it has shown and what it has not

Test counts are from the lead's own rerun of each suite on 5 November 2026, on Linux with Python 3.13.

### barclays-center (0.3.0)

Runs two genres end to end (editorial revision, software change) and two more through plug-ins up to the point
where people take over (websites, games). Details are in `README.md` and `CALIBRATION.md`. Three independent
reviews; each broke something and each finding is a test or a row in an attack table.

Not shown: that any model judge agrees with a person; anything on real work; anything on Windows or macOS.

### barclays-lenses (0.2.0)

Twelve lens cards: three editorial voices modelled on scholars' published writing, two writers' workshops
(policy, scholarly), the fact checker (the only fact desk), anti-slop and prose craft, technical editing,
reference and citation integrity, scholarly editorial integrity, and a debate skill as an adversarial role. Twelve more skills are listed by name with no card, because their files
were not read. `lens.py` validates cards, checks pins against the source files, records a re-pin, and prints a
suggested panel per genre. 43 tests.

How the venue uses it:

```bash
python bc.py --lenses lenses --lenses ../barclays-lenses/cards \
    panel-export <bout> --out <run> --pairs a:b \
    --panel-lenses prose-craft-skill,technical-editing,fact-checker
```

The roster is recorded in the run and in the verdict. A panel with no fact desk is flagged.

Not shown: that any card matches the judgment of the person or discipline it is derived from. Each card is one
reading, on one day, of the opening 3,000 to 4,500 characters of a skill file. Nobody who owns a voice has
approved its "may not claim" line. The source repositories' commits could not be read from here; the pin is the
file's hash. One independent review (it found that a voice card could carry factual authority through a synonym;
lanes are now a closed list). No panel with these lenses has been run with real reviewers.

### barclays-officials-web (0.2.0)

Six officials: pages load with no console errors or failed local requests at three viewports; internal links and
anchors resolve; no horizontal overflow at 320 px; a built-in structural HTML check (it is not a full validator);
axe-core violations at the agreed impact, `unverified` when axe-core is not installed; scripted task journeys as
advice. Candidate pages are served to Chromium by a request handler at a made-up origin with the network blocked.
The decisive checks look at each page as loaded, after a small fixed interaction, and in each state the bout's
task script reaches. 61 tests, which launch Chromium. axe-core 4.10.2 ran in them.

Through the venue: the fixture bout ends with `clean` eligible and `polished-but-broken` and `interaction-gated`
disqualified, status `INCONCLUSIVE`, no bracket, a human decision required.

Shown by an independent reviewer: a candidate's JavaScript reached nothing outside its own files (an outside
host, another loopback port with a listener waiting, a local file, a metadata address).

Not shown: that a site that passes works for a person. A page that breaks on the third click, on a control no
journey uses, after a long delay, or only when it does not detect the automated browser, passes; each is a test
that asserts the gap (`fixtures/ATTACKS.md`). Network blocking is request blocking inside Chromium, not an
operating-system sandbox. Nothing has been compared with the website evaluator the owner already has. Three officials the card names are not
built and say so.

### barclays-officials-game (0.2.0)

Four officials on games that expose a small test hook (`window.__barclays`): the game boots and draws; the
organiser's bot finishes level 1 on every seed; seeded random play cannot reach a situation that never changes
again (each softlock is reported with its seed so it can be replayed); and, as advice, completion rate and steps
by bot skill and level. The organiser's bot script can also carry a referee (the game's rules, checked on every
transition) and a definition of "the same situation". 40 tests, which launch Chromium.

Through the venue: the fixture bout ends with `fair` eligible and four games disqualified: one that can seal the
player in, one whose hook reports a win in a maze with no way out, one frozen behind a rising counter, and the
baseline, whose instant wins the referee rejects.

Not shown: that any game is fun, fair, balanced or well paced. Every check is a bot proxy, and the receipts say
so. **Everything a game's hook says is the candidate's own claim.** An independent reviewer defeated both
decisive checks through the hook. The referee and the situation function answer the two attacks it ran; without
them a passing result carries only a major lead. A hook that lies consistently still passes, and the harness,
the bots and the referee all run in the candidate's own page, so a build written to deceive can replace them.
These checks find honest mistakes; they are not a defence against a hostile build. The candidate is served from
a loopback HTTP port for the length of the run, which other local accounts could read; the web plug-in's
no-socket approach is stricter and the two should converge. `docs/HUMAN-PLAYTEST.md` says what a playtest must
record before anyone may call a game fun.

### barclays-officials-code (0.1.1)

Five officials that never execute the candidate: files parse; no key-shaped credential is committed (the match
is reported by pattern, line and hash, never echoed); ruff findings (undefined names are objective, the rest are
leads); bandit issues as leads; function size and branching as leads. A candidate cannot switch rules off with
its own configuration files or suppression comments. 44 tests; ruff 0.16.9 and bandit 1.9.4 ran in
them.

Through the venue: the software card names four of them as advisory. They add columns to the report and leads to
the panel's tool output, and they change no eligibility. Without the plug-in they are `unverified` and flagged.

Shown by an independent reviewer: no candidate code ran (start-up files planted among the candidate's files were
inert), candidate configuration and suppression comments were ignored, and a hostile candidate did not harm an
honest one beside it.

Not shown: that clean lint or a quiet security scan means code is correct, safe or maintainable. A credential
built through a tuple and a join is not caught, and the fixture records that.

### barclays-gold (0.2.0)

Exports blind ballots for a person (two orders per pair, opaque ids, equal file times, padded sizes), imports the
filled forms (only from a marked form block; a pair judged differently in the two orders becomes "no clear
winner"), freezes gold append-only, and scores a judge route against it: coverage, raw agreement with a seeded
bootstrap interval, Cohen's kappa, Gwet's AC1, flip rate, abstention, a confusion table. A route "may decide
alone" only on at least 30 covered human items, bound to the same bytes, with a cited run record. 58 tests.

Not shown: anything about any judge. **There is no human gold.** Every example is a synthetic placeholder, and
the tool prints a banner that such numbers are not agreement with any person. "May decide alone" rests on two
declarations the tool cannot verify: that the forms were filled in by a person, and that the route used real
models. The thresholds are a starting proposal, not a standard. One independent review (it got "may decide
alone" from a route that answered 2 of 30 items; fixed).

## 4. What was not created, and what would justify it

| Repository | Trigger | Why not now |
|---|---|---|
| `barclays-officials-grounding`: does each claim in a candidate have support in the source (MiniCheck, HHEM, LettuceDetect adapters) | A grounding model has been run and compared with human labels on the reversal attacks | This is the most valuable missing check: a sentence that keeps its words and reverses its meaning still passes every decisive text check. It needs model weights, which could not be downloaded or run in this session. A repository with no model in it would be a name. |
| `barclays-officials-citations`: do citations and DOIs resolve | The `research-synthesis` card is commissioned | Needs the network; cannot be part of an offline core. |
| A website evaluator for the owner's own sites | Never, unless the operator of the existing one declines | That evaluator already exists. |
| A second controller, a router, an evidence store | Never | They exist already. |

## 5. Put them side by side

```bash
mkdir barclays && cd barclays
git clone <each of the six>          # and adversarial-tournament-review beside them, or set BARCLAYS_ATR
cd barclays-center
python tools/plugins_table.py        # writes plugins.json from the siblings it finds; prints what it found
python -B -m unittest discover -s tests          # the venue alone; sibling tests skip when a sibling is absent
python -B -m unittest tests.test_family -v       # the whole chain, with real browsers and linters

python bc.py --plugins plugins.json run ../barclays-officials-web/fixtures/bouts/ui-website-clear-win --out /tmp/web1
python bc.py --plugins plugins.json run ../barclays-officials-game/fixtures/bouts/game-build-clear-win --out /tmp/game1
python bc.py --plugins plugins.json run fixtures/software-clear-win --out /tmp/sw1 --shadow
```

`tools/plugins_table.py` runs each sibling's `official.py list`. Run it only for repositories you installed. The
table is recorded in every run's manifest by hash; it is not signed.

## 6. Review status

| Repository | Independent reviews | Where |
|---|---|---|
| `barclays-center` | Three of the venue, one of the plug-in interface | `docs/review/`, `CALIBRATION.md` section 7 |
| `barclays-gold`, `barclays-lenses` | One, on their first versions; fixes checked by tests, not re-reviewed | each of those private repositories' `docs/review/` and `docs/REVIEW-RESPONSE.md` |
| `barclays-officials-web`, `-game`, `-code` | One, on their first versions; the web and game fixes are checked by tests, not re-reviewed | `docs/review/REVIEW-4.md` here and in each plug-in; each plug-in's `docs/REVIEW-RESPONSE.md` and `fixtures/ATTACKS.md` |

Every review so far has broken something its authors believed was solid. Treat the absence of a later review as
the absence of evidence, not as a clean bill.
