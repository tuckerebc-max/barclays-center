# Claude instructions

See [AGENTS.md](AGENTS.md); it is the single source of repository instructions.

Claude-specific notes:

- In a Claude Code session, real reviewers and judges are fresh subagents, one per packet (Agent tool, model per the
  registry alias). Never give a subagent the index, the meta directory, another packet or your own view of the
  candidates.
- **Stage every packet outside the run directory.** Copy `<run>/panel/packets/<id>.md` into a folder that holds
  only opaque packet files, have the subagent write `<id>.json` into a second such folder, then copy the answers
  to `<run>/panel/results/` and run `python bc.py panel-import <bout> --run <run> --provider <file>`. A path is
  something a reviewer can see: name nothing after a candidate, a lens or a condition. Three probes were voided
  tonight because version 0.1 put candidate ids in packet file names.
- Bracket packets are the controller's: `<run>/bracket/native/work/INDEX.md`. The subagent writes ONLY the JSON
  object the packet's Output section asks for; you wrap it with
  `python tools/native_envelope.py <packet>.prompt.json <answer file> --model <runtime model id>`, then run
  `python bc.py resume <bout> --run <run>` until it returns a verdict. Do not let the model write the envelope:
  7 of 36 attempts in the first real bracket were refused for a missing envelope field.
- A subagent call costs about 82,000 tokens however small the packet, almost all of it harness overhead. A real
  bracket of three candidates took 36 calls. Use a direct model route for anything larger than a probe.
- A Claude-only panel is one model family. The controller flags it `MODEL_DIVERSITY_LIMITED`. Say so in any report.
