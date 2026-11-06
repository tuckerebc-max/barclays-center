# Calibration run 3 (summary only)

`CALIBRATION-RESULTS.md` and `calibration.json` are the output of `python bc.py calibrate fixtures` on the commit
and freeze hash they state. The per-fixture run directories (10 main runs, 120 probe brackets, 2 attack bouts,
about 30 MB) are not kept in the repository. Regenerate them with:

    python tools/freeze.py --check && python bc.py calibrate fixtures --out <a new directory>

The verdicts will match; ledger heads will not, because events carry timestamps. Judging in these runs is
simulated. Read `docs/CALIBRATION.md` before quoting any number from here.
