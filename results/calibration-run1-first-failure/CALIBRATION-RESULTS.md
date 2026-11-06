# Calibration results

6 of 9 fixtures met their frozen expectation.

Judging in these runs is SIMULATED. The weigh-in columns are real executions on synthetic files.

| Fixture | Kind | Expected | Got | Recommended / shortlist | Met | Shadow: judges alone ranked first | Judge calls |
|---|---|---|---|---|---|---|---|
| `editorial-clear-win` | known-good beats a polished known-bad | RECOMMEND | RECOMMEND | faithful-plain | yes | `polished-omission` (disqualified at weigh-in) | 14 |
| `editorial-close-call` | close call: two faithful revisions the judges cannot separate | TIED_SHORTLIST | RECOMMEND | faithful-plain | NO | `faithful-plain` | 29 |
| `editorial-merely-smoother` | no candidate deserves promotion (faithful, but only smoother) | NO_CHANGE | INCONCLUSIVE | baseline, smoother-only | NO | `baseline` | 14 |
| `editorial-polish-only` | no candidate deserves promotion (the only challenger drops facts) | NO_CHANGE | NO_CHANGE | — | yes | `polished-omission` (disqualified at weigh-in) | — |
| `software-clear-win` | known-good beats a polished candidate that fails hidden tests | RECOMMEND | RECOMMEND | clean-fix | yes | `polished-shallow` (disqualified at weigh-in) | 12 |
| `software-close-call` | close call: two correct changes the judges cannot separate | TIED_SHORTLIST | RECOMMEND | clean-alt | NO | `clean-alt` | 26 |
| `software-looks-good-only` | no candidate deserves promotion (looks good, fails in use) | NO_CHANGE | NO_CHANGE | — | yes | `polished-shallow` (disqualified at weigh-in) | — |
| `software-no-winner` | no candidate deserves promotion (every challenger fails hidden tests) | NO_CHANGE | NO_CHANGE | — | yes | `polished-shallow` (disqualified at weigh-in) | — |
| `software-unverified-target` | missing evidence: the target suite has no tests, so a correct change cannot be verified | INCONCLUSIVE | INCONCLUSIVE | — | yes | `clean-fix` | — |

## Stability under reseeding and position-biased judges

Each bout that reached a bracket was rerun with new seeds, with and without position bias in every simulated judge. 'Same' counts runs whose status and recommendation matched the main run.

| Fixture | Position bias | Runs | Same as main | Statuses seen |
|---|---|---|---|---|
| `editorial-clear-win` | 0.0 | 5 | 5 | RECOMMEND |
| `editorial-clear-win` | 0.25 | 5 | 5 | RECOMMEND |
| `editorial-close-call` | 0.0 | 5 | 5 | RECOMMEND |
| `editorial-close-call` | 0.25 | 5 | 5 | RECOMMEND |
| `editorial-merely-smoother` | 0.0 | 5 | 3 | INCONCLUSIVE, NO_CHANGE |
| `editorial-merely-smoother` | 0.25 | 5 | 3 | INCONCLUSIVE, NO_CHANGE |
| `software-clear-win` | 0.0 | 5 | 5 | RECOMMEND |
| `software-clear-win` | 0.25 | 5 | 3 | INCONCLUSIVE, RECOMMEND |
| `software-close-call` | 0.0 | 5 | 5 | RECOMMEND |
| `software-close-call` | 0.25 | 5 | 4 | RECOMMEND |

## Mismatches

### `editorial-close-call`
- status: expected TIED_SHORTLIST, got RECOMMEND
- recommended: expected [], got ['faithful-plain']
- shortlist lacks ['faithful-plain', 'faithful-warm'] (got [])
### `editorial-merely-smoother`
- status: expected NO_CHANGE, got INCONCLUSIVE
### `software-close-call`
- status: expected TIED_SHORTLIST, got RECOMMEND
- recommended: expected [], got ['clean-alt']
- shortlist lacks ['clean-fix', 'clean-alt'] (got [])
