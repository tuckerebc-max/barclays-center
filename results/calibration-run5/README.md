# Calibration run 5 (summary only)

`CALIBRATION-RESULTS.md` and `calibration.json` are the output of `python bc.py calibrate fixtures` on the commit
and freeze hash they state. That commit is the first one in this repository, so it can be checked out. The
per-fixture run directories (10 main runs, 120 probe brackets, 2 attack bouts, about 30 MB) are not kept in the
repository. Regenerate them, with the controller, with:

    python tools/freeze.py --check && python bc.py calibrate fixtures --out <a new directory>

The verdicts will match; ledger heads will not, because events carry timestamps. Judging in these runs is
simulated. Read `docs/CALIBRATION.md` before quoting any number from here.

`results/calibration-run4/` and `results/calibration-run3/` are the summaries of earlier runs, on commits in the
private development history. They are kept for the record.
