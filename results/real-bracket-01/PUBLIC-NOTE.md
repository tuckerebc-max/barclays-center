# What is not in this copy

This is the venue's own record of the one bracket judged by real models: the bout, the manifest, the ledger, the
objects it refers to, the plan, the verdict and the report.

The controller's working directory for the run (`run/bracket/`: its campaign, its packets, the judges' answers
and its journal; 125 of its 126 files, about 1.5 MB) is not in the public repository. The packets are written by
the tournament controller, which is private, so those files are kept with the project's private history. The one
file kept is `run/bracket/reports/decision.json`, the controller's decision, because the ledger records its hash.

What that changes: `python bc.py verify results/real-bracket-01/run --expect-head <head>` still checks the ledger
chain, every object and the recorded head. It cannot show you the individual judge answers. The scores, the gate
result and the order flips reported in `docs/CALIBRATION.md` section 6.1 come from the controller's decision,
which the venue recorded in `run/verdict.json` and in the report.
