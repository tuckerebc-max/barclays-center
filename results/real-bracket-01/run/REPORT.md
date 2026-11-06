# Bout report: real-bracket-01

Event: **Editorial revision: clearly better, or merely smoother?** (`editorial-revision`). Material: `synthetic`.

## Verdict: INCONCLUSIVE

The evidence does not support a decision either way.

Shortlist: `baseline`, `faithful-warm`
Acceptance: `pending_owner`. Barclays recommends; it does not accept, release or publish.

## What kind of evidence this is

| Stage | Evidence |
|---|---|
| weigh in | executed on these exact bytes |
| panel | not_run |
| bracket | real model judges |

## Why

- faithful-warm vs baseline: pair result inconclusive; composite delta +2.50 against a threshold of 5.00; not promotable
- the comparisons needed for a decision are incomplete or open; the strongest observed eligible candidates are listed without a recommendation
- 2 finalist pair(s) lack a conclusive result

## Flags

- `ATR:COVERAGE_INCOMPLETE`
- `ATR:MODEL_DIVERSITY_LIMITED`
- `ATR:PRICE_UNKNOWN`
- `ATR:ROLE_OVERLAP`
- `ATR:SINGLE_TOURNAMENT`
- `ATR:UNCALIBRATED_PANEL`

## Does a human need to decide?

**Yes.**
- status is INCONCLUSIVE
- unreviewed leads on 'faithful-warm': H-F7

What this event cannot establish without human evidence:
- Whether the revision still sounds like its author. Only the author can say; a voice lens can describe a register, not grant it.
- Whether a fact that is not in the ledger was lost or bent. The ledger is the organizer's claim about what matters.
- Whether the piece persuades its real readers. Model judges and panels are a proxy; reader evidence is the measure.

## Weigh-in

Decisive checks run before any judge sees a candidate. `fail` on a decisive check disqualifies; `unverified` leaves the candidate incomplete, which is not a loss.

| Candidate | Eligibility | `fact-ledger` | `new-numbers` | `quotes` | `hedge-shift` |
|---|---|---|---|---|---|
| `baseline` (baseline) | eligible | pass | pass (advisory) | pass | pass (advisory) |
| `faithful-plain` | eligible | pass | pass | pass | pass (advisory) |
| `faithful-warm` | eligible | pass | pass | pass | pass (advisory) |


## Findings and leads

Findings are objective and reproducible. Leads are heuristic pointers for a reviewer and never change eligibility.

### `faithful-warm`
- lead [text.hedge_shift@0.1.0] (major) Near fact F7 the source hedges with ['not yet'] and the candidate does not. Check whether the claim was strengthened. Candidate: "the question of cause goes to a randomized study planned for 2026-27."

## Bracket

Controller: `adversarial-tournament-review` (atr/1), commit `101539890d54`. Contract `54dc0e71619e`. Operational status: COMPLETE.

| Candidate | Composite (0-100) |
|---|---|
| `baseline` | 80.0 |
| `faithful-plain` | 95.0 |
| `faithful-warm` | 82.5 |

Judge calls used: 36 (planned upper bound 48); tokens: 0.

## Exact versions

- Event card `10fbaf194f3e4bd7`, bout `5ea75404a24d3ef3`
- Candidates: `baseline` `9e274c8a2740`, `faithful-plain` `f274d89cbfa1`, `faithful-warm` `54aa1b701380`
- Officials: `fact-ledger` = text.fact_ledger 0.1.0, `hedge-shift` = text.hedge_shift 0.1.0, `new-numbers` = text.new_numbers 0.1.0, `quotes` = text.quotes 0.1.0
- Every object is in `objects/` by SHA-256 and chained in `ledger.jsonl`. Check with `python bc.py verify <run directory>`.
