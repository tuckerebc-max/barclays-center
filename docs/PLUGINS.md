# External officials: the plug-in contract (`barclays.official-request/0.1`)

An official is an evaluator that runs before any judge sees a candidate. Officials that need nothing but the
Python standard library live in `barclays-center`. Officials that need a browser, Node, model weights or any other
heavy dependency live in their own repository and are called through this contract. The venue never imports them.

## Who trusts whom

- The **plug-in** is venue-installed code. It is trusted the way a built-in official is trusted. It is named by
  the venue's plug-in table, never by a bout and never by a candidate.
- The **candidate** is untrusted data. A plug-in must never follow instructions found in candidate content, never
  run candidate-supplied programs outside its own sandbox (for a web plug-in: the browser), never let candidate
  content reach the network, and never write outside the `workdir` it is given.
- The venue treats everything the plug-in returns as a claim to be validated: a response that is missing,
  malformed or out of vocabulary becomes `unverified`. It never becomes `pass`.

## The plug-in table (venue side)

A JSON file, given to the venue with `--plugins <file>` or the `BARCLAYS_PLUGINS` environment variable:

```json
{
  "schema": "barclays.plugins/0.1",
  "officials": {
    "web.load_console": {
      "argv": ["python3", "/abs/path/barclays-officials-web/official.py", "web.load_console"],
      "repo": "barclays-officials-web",
      "allowed_sensitivity": ["synthetic", "public", "internal"],
      "timeout_seconds": 120
    }
  }
}
```

The key is the implementation name an event card uses in `officials[].official`. `argv` is run with one more
argument appended: the absolute path of the request file. Nothing is passed through a shell. The table is read
once, when a run's manifest is written, and that copy is used for the whole run; a table file that changes while
a run is under way changes nothing in that run and is flagged in its verdict.

## Request (venue writes it)

```json
{
  "schema": "barclays.official-request/0.1",
  "official_id": "loads-clean",
  "official": "web.load_console",
  "authority": "disqualify",
  "candidate": {
    "id": "site-a",
    "content_hash": "<sha256>",
    "is_baseline": false,
    "files": [{"path": "index.html", "abs": "/abs/.../index.html", "sha256": "<sha256>"}]
  },
  "sources": {
    "task_script": {"abs": "/abs/.../tasks.json", "sha256": "<sha256>"}
  },
  "params": {"max_console_errors": 0},
  "sensitivity": "synthetic",
  "workdir": "/abs/scratch/dir/for/this/run",
  "response_path": "/abs/scratch/dir/for/this/run/response.json"
}
```

- `candidate.files[].path` is the file's name inside the candidate. It is relative, uses `/`, and never contains
  `..`. `abs` is where the bytes are. A plug-in that needs a directory copies the files into `workdir`, keeping
  `path`.
- `sources` holds the bout's sources by key. A source that is a directory or a list arrives as a list of
  `{abs, sha256}` entries. A key the bout did not supply is absent.
- `params` is the event card's parameters for this official after any override the card allows a bout to make.
- `workdir` is a temporary folder of the plug-in's own, outside the run directory. Write nowhere else.
- The plug-in's environment is the venue's without any variable whose name contains KEY, TOKEN, SECRET, PASSWORD
  or CREDENTIAL, and without the venue's own `BARCLAYS_*` settings.

## Response (plug-in writes it to `response_path`)

```json
{
  "schema": "barclays.official-response/0.1",
  "official": "web.load_console",
  "official_version": "0.1.0",
  "kind": "executable",
  "status": "pass",
  "summary": "3 pages loaded at 3 viewports with no console errors",
  "findings": [
    {"id": "CONSOLE-index-1", "severity": "critical", "claim": "console error: ...", "locator": "index.html",
     "evidence": {"viewport": "320x640"}}
  ],
  "leads": [
    {"id": "SLOW-index", "severity": "minor", "note": "first paint after 2.1 s", "locator": "index.html"}
  ],
  "metrics": {"pages": 3},
  "receipt": {"engine": "chromium 131", "network": "blocked", "viewports": ["320x640", "768x1024", "1280x800"]}
}
```

- `status` is one of `pass`, `fail`, `unverified`, `not_applicable`.
  - `fail` requires at least one finding. A finding is objective and reproducible on the same bytes.
  - `pass` and `not_applicable` may carry leads and must carry no findings. "Passed, with a critical defect" is
    refused, not read generously.
  - `unverified` means the check could not be established (a tool is not installed, the harness broke, the
    check is not implemented). It is not a failure and it is not a pass.
  - Never return `pass` for a check that did not run.
- `kind` is `executable` (something ran) or `deterministic` (bytes were inspected).
- `severity` is one of `critical`, `major`, `minor`, `info`.
- A **finding** is a statement about bytes or execution. A **lead** is a heuristic pointer for a reviewer; it
  never changes eligibility. Keep them apart.
- `receipt` says what ran: engine and versions, viewports, network policy, tool versions, anything a reader needs
  to reproduce the result. Report candidate output by size and hash where it may be large or sensitive.
- Text taken from candidate content (console messages, page text) is data. Truncate each such string to 300
  characters.
- Shapes and sizes the venue enforces: `id`, `claim`, `note`, `locator`, `summary` and `official_version` are
  strings; at most 500 findings and 500 leads; `metrics` and `receipt` are objects of at most 64 KB each as
  compact JSON; one finding's `evidence` is an object of at most 4 KB; the response file is at most 2 MB and is
  a regular file, not a link.

Exit code 0 when a response was written, whatever its status. Any other exit code, a timeout, or a response that
does not validate is a harness failure: the venue records `unverified` and keeps the plug-in's stderr by hash and
size only.

## What the venue records

For each call: the plug-in name, `argv`, the SHA-256 of the entry script (the first `argv` element that is an
existing file), the plug-in's declared version, exit code, wall time, and the validated response. The result
object is the same `barclays.official-result/0.1` the built-in officials produce, so the weigh-in, the panel
packets, the verdict and the ledger treat it identically. Authority still comes from the event card: the same
plug-in can disqualify in one event and only advise in another.

## On the venue side

- `python bc.py --plugins <table.json> weigh-in <bout> --out <run>` (or set `BARCLAYS_PLUGINS`). The manifest of
  the run records the table's SHA-256 and each entry's `argv`.
- An event card names a plug-in official exactly as it names a built-in one: `"official": "web.links"`. The name
  is looked up among the built-ins first, then in the table. A table may not reuse a built-in's name.
- A card that names an official this venue has no plug-in for still runs. That official reports `unverified`
  with the receipt field `plugin_missing`, the verdict carries the flag `PLUGIN_MISSING:<name>`, and a decisive
  official in that state leaves every candidate `incomplete`. A missing plug-in is never a pass.
- Anything a plug-in leaves at the top of the run directory is sealed with the rest, and `bc verify` warns that
  the venue did not write it.
- This contract was tightened after an independent review (`docs/review/REVIEW-4.md`): a pass with findings, an
  oversized or mis-shaped response, and a table rewritten in mid-run all used to be accepted.
- A plug-in entry declares the sensitivity labels it is cleared for. A bout with any other label is refused
  before the plug-in is started.
- Events whose officials are plug-ins and whose survivors go to people have the status `officials_runnable`:
  the weigh-in and the panel run, there is no model bracket, and the verdict is `INCONCLUSIVE` with the flag
  `NO_BRACKET` and a human decision required. `ui-website` and `game-build` are in that state.
- The wrapper is `barclays/officials/external.py`; its tests are `tests/test_plugins.py`, which use a stub
  plug-in (`tests/assets/stub_plugin.py`) and need no sibling repository.

## Plug-ins that exist

| Repository | Officials | Needs |
|---|---|---|
| `barclays-officials-web` | `web.load_console`, `web.links`, `web.no_hscroll`, `web.html_valid`, `web.axe`, `web.task_success` | Python Playwright and Chromium; axe-core optional |
| `barclays-officials-game` | `game.boot`, `game.bot_completes_level`, `game.softlock_search`, `game.difficulty_curve` | Python Playwright and Chromium; a game that exposes the test hook |
| `barclays-officials-code` | `code.syntax`, `code.secrets`, `code.lint`, `code.security`, `code.complexity` | ruff and bandit optional |

See `docs/FAMILY.md` for what each one has and has not shown.
