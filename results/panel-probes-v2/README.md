# Panel probes with real reviewers (blind packets)

Four probes, 40 packets, run 4 November 2026 under Barclays 0.2. Reviewers were Claude Code subagents, one fresh
context per packet: slot `r1` is the Haiku tier, slot `r2` the Sonnet tier (the runtime does not report the exact model served). One model family. All material is
synthetic.

Blinding: packet ids are random (`p-` plus twelve hex characters). Each reviewer was given a copy of its one packet
in a folder that held only opaque packet files, and wrote its answer to a folder that held only opaque answer
files. The directories are named `p1` to `p4` for the same reason: a path is something a reviewer can see.

| Run | Fixture | Pair | Reference shown | Tool output shown | Packets |
|---|---|---|---|---|---|
| `p1` | `editorial-clear-win` | faithful-plain vs polished-omission | no | no | 12 |
| `p2` | `editorial-subtle-omission` | faithful-plain vs subtle-omission | no | no | 12 |
| `p3` | `software-clear-win` | clean-fix vs polished-shallow | task statement | no | 8 |
| `p4` | `software-clear-win` | clean-fix vs polished-shallow | task statement | yes | 8 |

Each run directory verifies with `python bc.py verify results/panel-probes-v2/<run>`. The reconciled panel is
`<run>/panel/panel.json`. Results and their limits are in `docs/CALIBRATION.md`.
