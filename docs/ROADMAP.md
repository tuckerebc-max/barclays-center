# Roadmap

Ordered by what stands between this family of repositories and a verdict someone can act on. Each item says what
it is, why it is where it is, and what "done" means. The research behind the tool choices is a private
document; the leads it produced are named in each item. The repositories themselves are described in `FAMILY.md`.

## Where things stand (version 0.3, 5 November 2026)

- Two genres run end to end: editorial revision and software change.
- Two more run their checks through plug-ins and then stop for people, by design: websites and games. They have
  no model bracket.
- Five genres are specifications.
- The venue has had three independent reviews. Its first two siblings have had one. The plug-in interface and the
  three plug-ins have had one (see `CALIBRATION.md` section 7 for what each found).
- **No human has judged anything. No judge route has been compared with a person. Nothing has run on real work.**

Read `CALIBRATION.md` section 1 before planning from this list.

## First: before any verdict is used for a real decision

**1. Human gold for one genre.** Start with editorial revision.
Twenty to thirty real pairs from material the owner is authorized to use, each decided blind by a person who is not a
builder: which is better, or neither. `barclays-gold` now does the mechanics: it exports blind ballots in both
orders, imports the filled forms, and scores any judge route against the result (agreement, chance-corrected
agreement, flip rate, abstention).
*Why first:* without it, every bracket result is a statement about the judges. *Done when:* each route has a
measured agreement on at least 30 covered items and the event card names a threshold below which that route is
advisory.
*Needs from the owner:* the corpus, and a gold owner. The gold itself goes in a private gold directory under separate
access, never in a builder's working tree.

**2. A direct judge route with two model families.**
Run a real bracket through the controller's model-gateway provider, with the author's family kept off its own
panel.
*Why:* every real judge so far was one family, reached through subagents at about 82,000 tokens a call. A direct
call should cost a few thousand. *Done when:* `editorial-close-call` runs under `--judges real` with two families
and the decision records usage. *Needs:* a gateway credential in the environment. Barclays never reads it.

**3. Hard known-bad fixtures.**
The planted defects here are easy for a reader, so they cannot measure whether a judge rewards polish. Add: a
meaning reversal that reads well, an omission that looks like tightening, a bug that passes the visible tests and
reads clean, an overclaim in a confident voice, and a candidate whose text tries to instruct the judge. Leads for
the last one: PyRIT and garak.
*Done when:* real reviewers disagree on them often enough that there is something to measure, and each has a row
in an attack table.

**4. A check for changed meaning in text.**
The decisive text checks compare surface forms. The gap is a sentence that keeps the words and reverses the
claim. Build a grounding official as a plug-in: split the candidate into claims, test each against the source for
support. Leads: MiniCheck-FT5 (MIT) and HHEM-2.1-Open (Apache-2.0) for support scoring, LettuceDetect (MIT) for
span-level flags, the Claimify approach for splitting. Avoid Bespoke-MiniCheck-7B and Lynx for production
(non-commercial licences).
*Authority:* advisory until it is calibrated on the reversal attacks and on human labels; only then decide whether
it may disqualify. *Where:* a new sibling, `barclays-officials-grounding`, through the plug-in contract. It was
not created in this session because no model weights could be downloaded or run here; an empty repository would
have been a name without a need.

**5. A real sandbox for executed code.**
Replace the namespace-and-chroot jail with bubblewrap or nsjail (or a disposable container), with a process-count
limit and a kill-on-exit guarantee that the candidate cannot undo. The microVM options (Firecracker, Kata) are the
next rung if restricted material ever has to be cleared. Decide the Windows story: require WSL2, and refuse rather
than run unjailed. The browser plug-ins run candidate JavaScript inside Chromium's own sandbox only; put them in
the same jail.
*Done when:* the fork-bomb and detach cases are in the attack table as caught, and the software card can be
cleared for untrusted authors.

**6. Another independent review** after items 2 to 5, with real attacks on each.

## Second: widen the venue

**7. Lenses: from bound to trusted.** Twelve voice and review skills are bound as lens cards in `barclays-lenses`,
pinned to the file each was read from. Not done: nobody who owns a voice has approved its "may not claim" line; the
cards were written from the opening of each skill file, not the whole of it; twelve more skills are known by name
only; no lens has been compared with the person or discipline it stands for.
*Done when:* each card's limit line is approved by its owner, the named-only skills are bound or dropped, and one
real panel has run with these voices on authorized material.

**8. `research-synthesis` runnable.** Officials: every citation resolves to a source in the bout; each quoted or
numeric claim is supported by the cited source (the text officials, pointed at the cited passage); coverage of the
sources the brief required. Resolving a DOI needs the network, so that part is a plug-in that reports `unverified`
when offline (leads: habanero, pyalex, crossrefapi). The fact desk's allegations go to the grounding official from
item 4.

**9. `ui-website`: from checks to evidence.** The checks run through `barclays-officials-web`. Next: a full
validator (Nu Html Checker or html-validate) in place of the built-in structural check, a pinned axe-core policy,
Lighthouse, and a decision with the operator of the owner's existing website evaluator about whether its evidence
should feed this event. None of that shows the site works for people. The card names the evidence that would: task
completion by real users. *Done when:* one bout carries that evidence beside the checks.

**10. `game-build`: from bots to players.** The checks run through `barclays-officials-game` on games that expose
its test hook. Every one of them is a bot proxy. *Done when:* one real game has gone through the checks and a
playtest that follows `barclays-officials-game/docs/HUMAN-PLAYTEST.md`, reported separately.

**11. Deeper software checks.** Static leads now come from `barclays-officials-code` (ruff, bandit, complexity,
committed credentials). Still to build: the same oracle-and-worker split for JavaScript and TypeScript;
property-based tests (Hypothesis) and mutation score (mutmut) as advisory officials; coverage of the changed lines
(diff-cover); gitleaks; object and class contracts across the process boundary.

**12. Move the owner's existing one-off tournament runners onto the venue**, one event card each, with their
owners and not silently.

## Third: integration and the controller

**13. Send the proposed changes to the controller's owner.** `ARCHITECTURE.md` section 7 says where they are
kept.

**14. Evidence layer.** Emit one receipt per sealed verdict (status, ledger head, hashes) to the owner's evidence
layer, so that verdicts waiting on the owner are visible there and bouts can be routed to the venue.

**15. Heads recorded automatically.** On seal, post the ledger head to the bout's tracking issue. Later, sign the
seal (in-toto or DSSE). Until then `bc verify` without `--expect-head` proves consistency, not authenticity. The
same applies to the plug-in table: it is recorded by hash, not signed.

**16. More formats.** Round robin with a rating model for more than four candidates (leads: py-irt, many-facet
rater models). An iterative challenge, where authors revise against findings while the held-back suite stays held
back. Events with no single winner: a portfolio, or a ranking with a stated cut. The event card has the slot; the
controller needs the support.

**17. Human ballots in the controller**, as a family of their own, so a human decision is recorded in the same
decision record it settles. Until then `barclays-gold` collects human decisions beside the controller, not in it.

**18. Finish reading the owner's collections that were found late.** The detail is in the private documents.

## Not planned

A second tournament controller. A router. An evidence store for the fleet. A general agent framework. A website
evaluator that competes with the one the owner already has.

## Decisions that are the owner's

1. Which corpus is authorized for human gold, and who owns the gold.
2. Who approves each lens card's "may not claim" line, and which of the named-only voices to bind next.
3. Whether the venue should take website evidence from the evaluator the owner already has. That is a
   conversation with its operator.
4. Whether to send the proposed changes to the controller's owner now.
5. Whether the software event may run on a Windows host without WSL2 at all. The recommendation is no.
6. Which model route judges should use, given what the subagent route costs (`CALIBRATION.md` section 9).
7. Done on 11 November: this repository carries the Apache 2.0 licence.
