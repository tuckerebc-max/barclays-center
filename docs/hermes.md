# Hermes entry note

The operating contract is [AGENTS.md](../AGENTS.md). This note covers what differs for Hermes.

- Hermes drives Barclays through the command line only. Every command prints one JSON object on stdout and uses
  exit codes 0 (done), 1 (invalid input or I/O), 2 (deliberate refusal), 3 (calibration expectation not met).
  Treat 2 as "stop and ask the owner", never as "retry with fewer checks".
- A bout is a directory. Hermes prepares it (candidates, sources, `bout.json` with a sensitivity label) and calls
  `python bc.py validate <bout>` before anything else.
- Weigh-in only, no judges: `python bc.py run <bout> --out <run> --judges none`. This needs no model capacity and
  is safe to run on any lane, including lanes with no internet.
- With gateway judges: declare a controller registry as the bout source `judge_registry` (the controller ships
  a template) and run with `--judges real`. The controller calls the gateway
  itself and reads the key from the environment. Barclays never sees, logs or stores the key.
- With native judges (Claude Code or Codex subagents): the run stops with status `INCONCLUSIVE` and flag
  `WAITING_ON_JUDGES`. The work index is `<run>/bracket/native/work/INDEX.md`. After the host answers, call
  `python bc.py resume <bout> --run <run>`; repeat until it returns a verdict.
- With native judges the model writes ONLY its answer. The host wraps it:
  `python tools/native_envelope.py <packet>.prompt.json <answer file> --model <runtime model id>`. Give each
  subagent a copy of its one packet in a folder that holds nothing else, never the run directory.
- The record of a run is its ledger head (the last `hash` in `<run>/ledger.jsonl`, also printed as `ledger_head`).
  Post that value to the bout's tracking issue with the verdict; it is the external anchor the run cannot rewrite. To check a run
  later: `python bc.py verify <run> --expect-head <that value>`. Without the head, verify proves only that the
  directory is consistent with itself.
- A bout may set only what its event card lists under `bout_may_set`. Exit code 2 on a bout's `params` means the
  bout tried to change a rule; the fix is a new event card version, never a retry.
- Checks that live in sibling repositories: run `python tools/plugins_table.py` once on a lane that has the
  siblings checked out, then pass `--plugins plugins.json` before the command. A verdict with a `PLUGIN_MISSING:`
  flag means a check the event names did not run on that lane; route the bout to a lane that has the plug-in
  (the web and game checks need Chromium) instead of accepting the result.
- Website and game bouts never return a winner. Status `INCONCLUSIVE` with flag `NO_BRACKET` is the normal end:
  the report lists who was disqualified and why, and the rest go to a person.
- Real voices on a panel: `--lenses lenses --lenses ../barclays-lenses/cards` and
  `panel-export ... --panel-lenses <ids>`. `python ../barclays-lenses/lens.py roster <event>` prints a suggested
  panel. Keep a fact desk on it.
- Hermes does not accept a verdict. Acceptance is `pending_owner` in every case.
