# Void: three panel probes whose packets were not blind

These three probes ran with real reviewers (Claude Haiku and Sonnet) under Barclays 0.1. They are **void as
evidence** and are kept only as a record of the mistake.

What went wrong: version 0.1 named each packet file after the lens, the two candidate ids, the display order and the
reviewer, for example `fact-desk--faithful-plain--polished-omission--ab--haiku--none.md`. A reviewer told to read
that file could see from its name which pair it held, including the words "faithful" and "omission". The independent
review caught it (IR-09). All 18 reviewer units in these probes preferred the faithful candidate; with the file name
saying which one that was, the result shows nothing.

What is here: the imported `panel.json` of each probe (every reviewer's validated result, objections and
allegations). The fourth probe (`...-noref-tools`) was exported and never run.

What replaced them: `results/panel-probes-v2/`, run under 0.2 with random packet ids, each packet staged alone in a
folder that holds nothing but opaque packet files. See `docs/CALIBRATION.md`.
