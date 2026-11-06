"""Barclays Center: the Navy Yard's tournament venue.

A venue, not a controller. Barclays Center owns the things around a contest:

  event cards   purpose-specific tournament specifications (one per genre)
  officials     deterministic and executable evaluators that run before any judge sees a candidate
  lenses        perspective cards for adversarial panels, with explicit authority limits
  the ledger    exact candidate and source versions, evidence and verdicts, hash-chained
  calibration   known-good, known-bad, close-call and no-winner fixtures with frozen expectations

Pairwise judging, panels of model families, order reversal, scheduling and the decision rule stay in the
existing controller, adversarial-tournament-review (atr/1). Barclays compiles a bout into an ATR campaign,
runs it as a subprocess and binds the decision into one verdict record.

Python 3.11+ standard library only.
"""

__version__ = "0.3.0"

EVENT_SCHEMA = "barclays.event/0.1"
BOUT_SCHEMA = "barclays.bout/0.1"
LENS_SCHEMA = "barclays.lens/0.1"
RESULT_SCHEMA = "barclays.official-result/0.1"
PANEL_SCHEMA = "barclays.panel/0.1"
VERDICT_SCHEMA = "barclays.verdict/0.1"
LEDGER_SCHEMA = "barclays.ledger/0.1"

# Sensitivity labels, least to most restricted. A component may handle a bout only if the bout's label is in the
# component's allowed set. Unknown labels are refused.
SENSITIVITY = ("synthetic", "public", "internal", "restricted")

# The decision vocabulary is the controller's (atr/1). Barclays does not invent a second one.
STATUSES = ("RECOMMEND", "NO_CHANGE", "TIED_SHORTLIST", "INCONCLUSIVE", "NO_ELIGIBLE_CANDIDATE")
