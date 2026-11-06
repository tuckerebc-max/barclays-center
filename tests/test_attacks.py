"""Regression tests for what the independent review broke (docs/review/INDEPENDENT-REVIEW.md).

Each test names the finding it answers. Where a weakness remains, the test says so by asserting the weak behaviour
(for example: a run cut back to an earlier state verifies unless the head was recorded outside it).

    python -B -m unittest tests.test_attacks -v
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from barclays.bracket import find_atr, find_python  # noqa: E402
from barclays.canon import canonical, read_json, sha256_bytes, write_json  # noqa: E402
from barclays.errors import BarclaysError, Refusal  # noqa: E402
from barclays.ledger import GENESIS, audit  # noqa: E402
from barclays.lenses import export_panel, import_panel, load_lenses  # noqa: E402
from barclays.runner import _load, open_run, run_bout, write_manifest  # noqa: E402
from barclays.weighin import run_weigh_in  # noqa: E402

EVENTS = os.path.join(ROOT, "events")
LENSES = os.path.join(ROOT, "lenses")
FIX = os.path.join(ROOT, "fixtures")


def have_controller():
    try:
        return find_atr(None), find_python(None)
    except Refusal as exc:
        return None, str(exc)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bc-attack-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def copy_fixture(self, name, as_name=None):
        dst = os.path.join(self.tmp, as_name or name.replace("/", "-"))
        shutil.copytree(os.path.join(FIX, name), dst)
        return dst

    def weigh(self, bout_dir):
        bout, event = _load(bout_dir, EVENTS)
        out = os.path.join(self.tmp, "run-" + os.path.basename(bout_dir) + str(len(os.listdir(self.tmp))))
        ledger = open_run(out)
        write_manifest(bout, event, ledger, out)
        return bout, event, run_weigh_in(bout, event, out, ledger), out, ledger

    @staticmethod
    def result(wi, cid, oid):
        return next(r for r in wi["results"] if r["candidate_id"] == cid and r["official_id"] == oid)


class ExecutionAttacks(Base):
    """IR-01, IR-04, IR-08: a candidate cannot forge, dodge or outlast its own tests."""

    def test_every_attack_ends_as_the_table_says(self):
        rows = read_json(os.path.join(FIX, "_attacks", "software", "ATTACKS.json"))
        _, _, wi, out, _ = self.weigh(self.copy_fixture("_attacks/software"))
        jailed = self.result(wi, "clean-fix", "pass-to-pass")["receipt"]["filesystem"].startswith("isolated")
        for row in rows:
            cid = row["candidate"]
            if cid == "probe-escape" and not jailed:
                continue    # with no jail this candidate is expected to pass; the receipt and verdict flag say so
            with self.subTest(candidate=cid):
                self.assertEqual(wi["eligibility"][cid]["status"], row["eligibility"])
                for oid, status in row["expected"].items():
                    self.assertEqual(self.result(wi, cid, oid)["status"], status, f"{cid} {oid}")
        # The forged outcomes never arrive: every forger's hidden suites report real failures.
        for cid in ("forge-json-patch", "forge-result-file", "forge-stdout", "always-equal"):
            self.assertTrue(self.result(wi, cid, "fail-to-pass")["receipt"]["result_authenticated"])
        # Leaving before the tests is a failure of the candidate, not a harness failure that buys a second look.
        self.assertEqual(wi["eligibility"]["exit-at-import"]["status"], "disqualified")
        hang = self.result(wi, "hang", "fail-to-pass")
        self.assertEqual(hang["receipt"]["attempts"], 2)
        self.assertTrue(hang["receipt"]["timed_out"])
        self.assertEqual(hang["findings"][0]["id"], "TIMEOUT")
        # Nothing from the hidden suites, and no scratch directory, is left behind in the run.
        left = [n for n in os.listdir(out) if n not in ("ledger.jsonl", "manifest.json", "objects")]
        self.assertEqual(left, [])
        # Held-back suites stay held back: no test name, input or expected value reaches the run's records.
        for res in wi["results"]:
            if res["official_id"] in ("pass-to-pass", "fail-to-pass"):
                text = json.dumps(res)
                for leak in ("brute_force", "test_touching", "test_unsorted", "test_input_not_modified", "[[1, 3]]",
                             "test_target", "test_regression"):
                    self.assertNotIn(leak, text, f"hidden suite text leaked into {res['candidate_id']}'s result")

    def test_without_a_jail_forgeries_still_fail_and_the_verdict_says_so(self):
        """The fallback for hosts with no user namespaces (Windows, macOS, locked-down Linux). The oracle is still
        a separate process, so forged results still fail. What is lost is containment: the candidate that passes
        only if it can see outside its jail now passes, and the verdict must carry EXEC_NOT_ISOLATED."""
        from barclays.officials import exec_tests
        saved = (exec_tests._jail_mode, exec_tests._netns_available)
        exec_tests._jail_mode = lambda python: ""
        exec_tests._netns_available = lambda: False
        try:
            d = self.copy_fixture("_attacks/software")
            verdict = run_bout(d, os.path.join(self.tmp, "nojail"), EVENTS, judges="none")
        finally:
            exec_tests._jail_mode, exec_tests._netns_available = saved
        wi = verdict["_weigh_in"]
        self.assertEqual(self.result(wi, "clean-fix", "fail-to-pass")["receipt"]["filesystem"], "not_isolated")
        self.assertIn("EXEC_NOT_ISOLATED", verdict["flags"])
        for cid in ("forge-json-patch", "forge-stdout", "always-equal", "exit-at-import", "hang", "slow-oracle"):
            self.assertEqual(wi["eligibility"][cid]["status"], "disqualified", cid)
        self.assertEqual(wi["eligibility"]["clean-fix"]["status"], "eligible")
        self.assertEqual(wi["eligibility"]["probe-escape"]["status"], "eligible")      # the jail was the defence

    def test_a_large_input_does_not_break_an_honest_candidate(self):
        """RR-01: the answer limit once counted the arguments echoed back, so an honest candidate failed on any
        input over about 32 KB. Arguments now come back only when changed, and the limit scales with the request."""
        d = self.copy_fixture("software-clear-win")
        with open(os.path.join(d, "sources", "pass_to_pass", "test_scale.py"), "w", encoding="utf-8") as fh:
            fh.write("import unittest\n\nfrom solution import merge_intervals\n\n\nclass Scale(unittest.TestCase):\n"
                     "    def test_many_disjoint(self):\n        data = [[4 * i, 4 * i + 1] for i in range(12000)]\n"
                     "        self.assertEqual(merge_intervals(data), data)\n")
        _, _, wi, _, _ = self.weigh(d)
        for cid in ("baseline", "clean-fix"):
            res = self.result(wi, cid, "pass-to-pass")
            self.assertEqual(res["status"], "pass", res["summary"])

    def test_what_crosses_the_process_boundary(self):
        """Constants, exceptions, in-place mutation and container types survive; a non-data value equals nothing."""
        d = self.copy_fixture("software-clear-win")
        with open(os.path.join(d, "candidates", "clean-fix.py"), "w", encoding="utf-8") as fh:
            fh.write("LIMIT = 3\n\n\ndef boom(x):\n    raise ValueError('bad ' + str(x))\n\n\n"
                     "def mutate(xs):\n    xs.append(1)\n\n\ndef shapes():\n    return (1, {'a': {2, 3}}, b'x', 1.5)\n\n\n"
                     "def stream():\n    return (i for i in range(3))\n")
        suite = os.path.join(d, "sources", "pass_to_pass")
        shutil.rmtree(suite)
        os.mkdir(suite)
        with open(os.path.join(suite, "test_boundary.py"), "w", encoding="utf-8") as fh:
            fh.write("import unittest\n\nimport solution\n\n\nclass Boundary(unittest.TestCase):\n"
                     "    def test_constant(self):\n        self.assertEqual(solution.LIMIT, 3)\n\n"
                     "    def test_exception_type_survives(self):\n"
                     "        with self.assertRaises(ValueError):\n            solution.boom(1)\n\n"
                     "    def test_mutation_is_visible(self):\n        xs = [0]\n        solution.mutate(xs)\n"
                     "        self.assertEqual(xs, [0, 1])\n\n"
                     "    def test_container_types_survive(self):\n"
                     "        self.assertEqual(solution.shapes(), (1, {'a': {2, 3}}, b'x', 1.5))\n\n"
                     "    def test_a_non_data_value_equals_nothing(self):\n"
                     "        self.assertNotEqual(solution.stream(), solution.stream())\n")
        _, _, wi, _, _ = self.weigh(d)
        res = self.result(wi, "clean-fix", "pass-to-pass")
        self.assertEqual(res["status"], "pass", res["summary"])
        self.assertEqual(res["metrics"]["tests_run"], 5)

    def test_a_suite_that_needs_candidate_classes_is_unverified_not_failed(self):
        d = self.copy_fixture("software-clear-win")
        with open(os.path.join(d, "candidates", "clean-fix.py"), "w", encoding="utf-8") as fh:
            fh.write("class Merger:\n    def run(self, xs):\n        return xs\n")
        suite = os.path.join(d, "sources", "pass_to_pass")
        shutil.rmtree(suite)
        os.mkdir(suite)
        with open(os.path.join(suite, "test_cls.py"), "w", encoding="utf-8") as fh:
            fh.write("import unittest\n\nfrom solution import Merger\n\n\nclass T(unittest.TestCase):\n"
                     "    def test_it(self):\n        self.assertEqual(Merger().run([1]), [1])\n")
        _, _, wi, _, _ = self.weigh(d)
        res = self.result(wi, "clean-fix", "pass-to-pass")
        self.assertEqual(res["status"], "unverified")
        self.assertIn("class", res["summary"])
        self.assertEqual(res["findings"], [])        # a limit of the official is not a finding against the candidate


class TimeoutsAreAttributedAcrossCandidates(unittest.TestCase):
    """RR-02: a candidate must not be able to buy 'unverified' by making the suite's own work slow."""

    @staticmethod
    def res(cid, status, **receipt):
        return {"official_id": "fail-to-pass", "candidate_id": cid, "status": status, "summary": "", "findings": [],
                "metrics": {"seconds": 0.2}, "receipt": dict({"suite": "fail_to_pass"}, **receipt)}

    def test_a_timeout_nobody_else_had_is_a_failure(self):
        from barclays.weighin import attribute_timeouts
        rows = [self.res("clean", "pass", result_authenticated=True, timed_out=False),
                self.res("slow", "unverified", unattributed_timeout=True),
                self.res("empty-suite", "unverified")]
        attribute_timeouts(rows)
        self.assertEqual([r["status"] for r in rows], ["pass", "fail", "unverified"])
        self.assertEqual(rows[1]["findings"][0]["id"], "TIMEOUT-RELATIVE")
        self.assertIn("unverified -> fail", rows[1]["receipt"]["reclassified"])

    def test_an_oversize_answer_fails_only_if_someone_passed_within_the_limit(self):
        from barclays.weighin import attribute_limits
        rows = [self.res("clean", "pass", result_authenticated=True, timed_out=False),
                self.res("huge", "unverified", unattributed_limit=True)]
        rows[1]["summary"] = "an answer of 9 bytes exceeded the 3 bytes allowed. Either x"
        attribute_limits(rows)
        self.assertEqual(rows[1]["status"], "fail")
        self.assertEqual(rows[1]["findings"][0]["id"], "ANSWER-TOO-LONG")

    def test_the_known_gap_an_oversize_answer_with_no_passer_stays_unverified(self):
        """A wrong candidate whose only competitor fails the suite (the baseline on the target suite) can end
        'unverified' by answering over the limit. A wrong short answer says nothing about how long a right one
        is, so this is not called a failure. It cannot end 'pass', and the verdict prints the reason."""
        from barclays.weighin import attribute_limits
        rows = [self.res("baseline", "fail", result_authenticated=True, timed_out=False),
                self.res("huge", "unverified", unattributed_limit=True)]
        attribute_limits(rows)
        self.assertEqual(rows[1]["status"], "unverified")

    def test_a_suite_too_slow_for_everyone_stays_unverified(self):
        from barclays.weighin import attribute_timeouts
        rows = [self.res("a", "unverified", unattributed_timeout=True),
                self.res("b", "unverified", unattributed_timeout=True)]
        attribute_timeouts(rows)
        self.assertEqual([r["status"] for r in rows], ["unverified", "unverified"])


class BoutCannotRewriteItsEvent(Base):
    """IR-02, IR-07: a bout cannot change decisive settings or reach outside itself."""

    def test_a_bout_cannot_point_the_hidden_suite_at_the_visible_one(self):
        d = self.copy_fixture("software-looks-good-only")
        bout = read_json(os.path.join(d, "bout.json"))
        bout["params"] = {"fail-to-pass": {"suite": "visible_tests"}, "pass-to-pass": {"suite": "visible_tests"}}
        write_json(os.path.join(d, "bout.json"), bout)
        with self.assertRaises(Refusal):
            _load(d, EVENTS)
        bout["params"] = {"static": {"forbid_imports": [], "forbid_calls": []}}
        write_json(os.path.join(d, "bout.json"), bout)
        with self.assertRaises(Refusal):
            _load(d, EVENTS)

    def test_a_misspelled_official_id_is_an_error_not_a_silent_no_op(self):
        d = self.copy_fixture("software-looks-good-only")
        bout = read_json(os.path.join(d, "bout.json"))
        bout["params"] = {"fail-to-pas": {"timeout_seconds": 5}}
        write_json(os.path.join(d, "bout.json"), bout)
        with self.assertRaises(BarclaysError):
            _load(d, EVENTS)

    def test_an_override_of_the_wrong_kind_is_an_error(self):
        d = self.copy_fixture("software-looks-good-only")
        bout = read_json(os.path.join(d, "bout.json"))
        for bad in ("soon", -1, 0, 1e300, 0.5, 2000, {"a": 1}, True):
            bout["params"] = {"fail-to-pass": {"timeout_seconds": bad}}
            write_json(os.path.join(d, "bout.json"), bout)
            with self.assertRaises(BarclaysError):
                _load(d, EVENTS)
        bout["params"] = {"bracket": {"routing": {"judge": "x"}}}      # who judges is the card's to say
        write_json(os.path.join(d, "bout.json"), bout)
        with self.assertRaises(Refusal):
            _load(d, EVENTS)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs named pipes")
    def test_a_pipe_in_a_source_directory_is_refused_not_read(self):
        d = self.copy_fixture("software-clear-win")
        os.mkfifo(os.path.join(d, "sources", "visible_tests", "feed"))
        with self.assertRaises(Refusal):
            _load(d, EVENTS)

    def test_an_allowed_override_is_flagged_in_the_verdict(self):
        d = self.copy_fixture("software-looks-good-only")
        bout = read_json(os.path.join(d, "bout.json"))
        bout["params"] = {"fail-to-pass": {"timeout_seconds": 15}}
        write_json(os.path.join(d, "bout.json"), bout)
        verdict = run_bout(d, os.path.join(self.tmp, "out"), EVENTS, judges="none")
        self.assertIn("BOUT_OVERRIDE:fail-to-pass.timeout_seconds", verdict["flags"])

    @unittest.skipIf(os.name == "nt", "symbolic links need privileges on Windows")
    def test_a_symlink_inside_a_source_directory_is_refused(self):
        d = self.copy_fixture("software-clear-win")
        outside = os.path.join(self.tmp, "outside-secret.txt")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write("not part of the bout\n")
        os.symlink(outside, os.path.join(d, "sources", "visible_tests", "notes.txt"))
        with self.assertRaises(Refusal):
            _load(d, EVENTS)

    @unittest.skipIf(os.name == "nt", "symbolic links need privileges on Windows")
    def test_a_symlinked_candidate_or_directory_is_refused(self):
        d = self.copy_fixture("software-clear-win")
        real = os.path.join(d, "candidates", "clean-fix.py")
        moved = os.path.join(self.tmp, "clean-fix.py")
        shutil.move(real, moved)
        os.symlink(moved, real)
        with self.assertRaises(Refusal):
            _load(d, EVENTS)
        d2 = self.copy_fixture("software-clear-win", "second")
        shutil.move(os.path.join(d2, "sources"), os.path.join(d2, "real-sources"))
        os.symlink(os.path.join(d2, "real-sources"), os.path.join(d2, "sources"))
        with self.assertRaises(Refusal):
            _load(d2, EVENTS)


def rewrite_chain(run_dir, mutate):
    """What a forger with write access does: change events, then recompute every hash so the chain is whole."""
    path = os.path.join(run_dir, "ledger.jsonl")
    with open(path, encoding="utf-8") as fh:
        events = [json.loads(line) for line in fh if line.strip()]
    events = mutate(events) or events
    prev = GENESIS
    for i, event in enumerate(events, 1):
        event.pop("hash", None)
        event["seq"], event["prev"] = i, prev
        event["hash"] = sha256_bytes(canonical(event))
        prev = event["hash"]
    with open(path, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")


def put(run_dir, obj):
    data = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sha = sha256_bytes(data)
    with open(os.path.join(run_dir, "objects", sha), "wb") as fh:
        fh.write(data)
    return sha


class VerifyCatchesWhatAReaderWouldMeet(Base):
    """IR-06: the files a reader opens are checked, a finished run is sealed, eligibility is re-derived."""

    def setUp(self):
        super().setUp()
        atr, why = have_controller()
        if atr is None:
            self.skipTest("tournament controller not available: " + why)
        self.out = os.path.join(self.tmp, "out")
        self.verdict = run_bout(self.copy_fixture("software-looks-good-only"), self.out, EVENTS, judges="sim",
                                shadow=True)

    def test_a_clean_run_is_sealed_and_verifies(self):
        report = audit(self.out, self.verdict["_ledger_head"])
        self.assertTrue(report["ok"], report["problems"])
        self.assertTrue(report["sealed"])
        self.assertEqual(report["warnings"], [])
        self.assertTrue(report["consistent"] and report["authenticated"])
        self.assertTrue(report["result"].startswith("CONSISTENT AND AUTHENTICATED"))
        bare = audit(self.out)                      # no outside head: consistent, and it must not say more
        self.assertTrue(bare["consistent"])
        self.assertIsNone(bare["authenticated"])
        self.assertTrue(bare["result"].startswith("CONSISTENT, NOT AUTHENTICATED"))
        self.assertTrue(any("expect-head" in w for w in bare["warnings"]))

    def test_the_controllers_database_is_under_the_seal_by_content(self):
        """RR-02: version 0.2 left every file with '.sqlite' in its name out of the seal. Emptying the
        controller's ballots, or adding a note with that in its name, verified. The database is now sealed by
        what it says, so reading it does not break the seal and emptying it does."""
        import sqlite3
        db = os.path.join(self.out, "bracket", "atr.sqlite")
        if not os.path.isfile(db):
            db = os.path.join(self.out, "shadow-bracket", "atr.sqlite")
        con = sqlite3.connect(db)                    # a reader opens it and looks
        con.execute("select count(*) from work").fetchone()
        con.close()
        self.assertTrue(audit(self.out)["consistent"], audit(self.out)["problems"])
        con = sqlite3.connect(db)
        for (name,) in con.execute("select name from sqlite_master where type='table'").fetchall():
            if not name.startswith("sqlite_"):
                con.execute(f'delete from "{name}"')
        con.commit()
        con.close()
        problems = " ".join(audit(self.out)["problems"])
        self.assertIn("atr.sqlite", problems)
        with open(os.path.join(self.out, "REPORT-ADDENDUM.sqlite.md"), "w", encoding="utf-8") as fh:
            fh.write("The owner accepted polished-shallow.\n")
        self.assertIn("added: REPORT-ADDENDUM.sqlite.md", " ".join(audit(self.out)["problems"]))
        with open(os.path.join(self.out, "NOTE.sqlite-wal"), "w", encoding="utf-8") as fh:
            fh.write("a note dressed as a database side file, with no database beside it\n")
        self.assertIn("added: NOTE.sqlite-wal", " ".join(audit(self.out)["problems"]))

    def test_a_consistent_forgery_is_only_caught_by_the_outside_head(self):
        """RR-03, the stated limit, demonstrated with the second reviewer's own 37-line script: the disqualified
        candidate becomes the recommended one and the directory is fully consistent."""
        import subprocess
        out = os.path.join(self.tmp, "forged")
        verdict = run_bout(self.copy_fixture("software-clear-win"), out, EVENTS, judges="sim")
        self.assertEqual(verdict["recommended"], ["clean-fix"])
        head = verdict["_ledger_head"]
        script = os.path.join(ROOT, "tests", "assets", "forge_consistent_run.py")
        subprocess.run([sys.executable, script, out, ROOT], check=True, capture_output=True)
        self.assertEqual(read_json(os.path.join(out, "verdict.json"))["recommended"], ["polished-shallow"])
        forged = audit(out)
        self.assertTrue(forged["consistent"], forged["problems"])        # it gets past every internal check
        self.assertIsNone(forged["authenticated"])                       # and verify does not claim it is genuine
        caught = audit(out, head)
        self.assertFalse(caught["authenticated"])
        self.assertTrue(caught["result"].startswith("NOT AUTHENTICATED"))

    def test_an_edited_verdict_or_report_is_caught(self):
        path = os.path.join(self.out, "verdict.json")
        doc = read_json(path)
        doc["status"], doc["recommended"] = "RECOMMEND", ["polished-shallow"]
        write_json(path, doc)
        problems = audit(self.out)["problems"]
        self.assertTrue(any("verdict.json" in p for p in problems), problems)
        with open(os.path.join(self.out, "REPORT.md"), "a", encoding="utf-8") as fh:
            fh.write("\nRecommended: polished-shallow\n")
        self.assertTrue(any("REPORT.md" in p for p in audit(self.out)["problems"]))

    def test_a_deleted_shadow_bracket_is_caught(self):
        shutil.rmtree(os.path.join(self.out, "shadow-bracket"))
        problems = audit(self.out)["problems"]
        self.assertTrue(any("shadow-bracket" in p and "missing" in p for p in problems), problems)

    def test_any_file_a_reader_might_open_is_under_the_seal(self):
        """RR-01: the controller's readable decision, the inputs the judges saw and the plan are files a reader
        opens. The seal now covers every file in the run, not three of them."""
        for rel in ("shadow-bracket/reports/decision.md", "bracket-plan.json"):
            path = os.path.join(self.out, rel)
            if os.path.isfile(path):
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write("\nedited\n")
                problems = audit(self.out)["problems"]
                self.assertTrue(any("not what was sealed" in p and rel in p for p in problems), (rel, problems))
        inputs = os.path.join(self.out, "shadow-bracket", "inputs", "candidates")
        victim = os.path.join(inputs, sorted(os.listdir(inputs))[0], "solution.py")
        with open(victim, "a", encoding="utf-8") as fh:
            fh.write("\n# edited after the run\n")
        with open(os.path.join(self.out, "NOTES-added-later.md"), "w", encoding="utf-8") as fh:
            fh.write("x\n")
        text = " ".join(audit(self.out)["problems"])
        self.assertIn("changed: shadow-bracket/inputs/candidates", text)
        self.assertIn("added: NOTES-added-later.md", text)

    def test_added_folders_links_and_database_objects_are_under_the_seal(self):
        import sqlite3
        os.mkdir(os.path.join(self.out, "ACCEPTED-BY-OWNER"))
        self.assertIn("added: ACCEPTED-BY-OWNER/", " ".join(audit(self.out)["problems"]))
        os.rmdir(os.path.join(self.out, "ACCEPTED-BY-OWNER"))
        self.assertTrue(audit(self.out)["consistent"])
        if hasattr(os, "symlink") and os.name != "nt":
            os.symlink("/etc", os.path.join(self.out, "evidence"))
            self.assertIn("added: evidence/", " ".join(audit(self.out)["problems"]))
            os.remove(os.path.join(self.out, "evidence"))
        db = os.path.join(self.out, "shadow-bracket", "atr.sqlite")
        con = sqlite3.connect(db)
        con.execute("create view owner_accepted as select 'polished-shallow' as winner")
        con.commit()
        con.close()
        self.assertIn("atr.sqlite", " ".join(audit(self.out)["problems"]))

    def test_cutting_the_tail_off_is_caught_while_the_files_remain(self):
        rewrite_chain(self.out, lambda events: [e for e in events if e["kind"] not in ("verdict", "seal")])
        problems = audit(self.out)["problems"]
        self.assertTrue(any("records no verdict" in p for p in problems), problems)

    def test_a_flipped_result_is_caught_by_rederiving_eligibility(self):
        def flip(events):
            new_shas = {}
            for event in events:
                if event["kind"] == "official_result" and event["summary"]["candidate_id"] == "polished-shallow" \
                        and event["summary"]["status"] == "fail":
                    res = read_json(os.path.join(self.out, "objects", event["refs"]["result"]))
                    res["status"], res["summary"], res["findings"] = "pass", "all tests passed", []
                    new = put(self.out, res)
                    new_shas[event["refs"]["result"]] = new
                    event["refs"]["result"], event["summary"]["status"] = new, "pass"
            for event in events:
                if event["kind"] == "weigh_in":     # the forger updates the list of results but forgets the rest
                    doc = read_json(os.path.join(self.out, "objects", event["refs"]["weigh_in"]))
                    doc["result_objects"] = [new_shas.get(s, s) for s in doc["result_objects"]]
                    event["refs"]["weigh_in"] = put(self.out, doc)
        rewrite_chain(self.out, flip)
        problems = audit(self.out)["problems"]
        self.assertTrue(any("is not what the official results imply" in p for p in problems), problems)

    def test_a_run_cut_back_to_an_earlier_honest_state_needs_the_outside_head(self):
        """The stated limit. With every later file removed, the directory is a valid weigh-in-only run. Only the
        head recorded outside the run shows that it is not the run that was recorded."""
        head = self.verdict["_ledger_head"]

        def cut(events):
            keep = []
            for event in events:
                keep.append(event)
                if event["kind"] == "weigh_in":
                    break
            return keep
        rewrite_chain(self.out, cut)
        for name in ("verdict.json", "REPORT.md", "bracket-plan.json"):
            if os.path.exists(os.path.join(self.out, name)):
                os.remove(os.path.join(self.out, name))
        for name in ("bracket", "shadow-bracket"):
            shutil.rmtree(os.path.join(self.out, name), ignore_errors=True)
        self.assertTrue(audit(self.out)["ok"])                       # undetectable from inside
        report = audit(self.out, head)
        self.assertFalse(report["ok"])
        self.assertTrue(any("not the expected" in p for p in report["problems"]))


class PanelReachesTheVerdict(Base):
    """IR-09: packet names are opaque, and what a panel raised travels into the verdict without authority."""

    def setUp(self):
        super().setUp()
        atr, why = have_controller()
        if atr is None:
            self.skipTest("tournament controller not available: " + why)

    def test_a_panel_that_prefers_the_disqualified_candidate_is_flagged_and_changes_nothing(self):
        d = self.copy_fixture("editorial-clear-win")
        bout, event, wi, prun, ledger = self.weigh(d)
        lenses = load_lenses(LENSES)
        export_panel(prun, bout, event, wi, lenses, [("faithful-plain", "polished-omission")], ["r1"], "none",
                     ["synthetic"], ledger)
        mdir = os.path.join(prun, "panel", "meta")
        for name in os.listdir(mdir):
            meta = read_json(os.path.join(mdir, name))
            polished = "A" if meta["labels"]["A"] == "polished-omission" else "B"
            other = "B" if polished == "A" else "A"
            write_json(os.path.join(prun, "panel", "results", name), {
                "preference": polished, "margin": 4, "reasons": "reads better", "objections": [],
                "allegations": [{"candidate": other, "quote": "4,218 students", "claim": "this figure is wrong"}]})
        import_panel(prun, bout, lenses, ledger, {"r1": {"model": "scripted test reviewer", "real": False}})

        out = os.path.join(self.tmp, "out")
        verdict = run_bout(d, out, EVENTS, judges="sim", panel_from=prun)
        self.assertEqual(verdict["status"], "RECOMMEND")
        self.assertEqual(verdict["recommended"], ["faithful-plain"])                 # the panel changed nothing
        self.assertIn("PANEL_PREFERRED_A_DISQUALIFIED_CANDIDATE", verdict["flags"])
        self.assertEqual(verdict["panel"]["preferred_a_disqualified_candidate"], ["polished-omission"])
        self.assertEqual(verdict["evidence_grade"]["panel"], "simulated or unattributed")
        self.assertTrue(any("unverified factual allegation" in b for b in verdict["human_decision"]["because"]))
        with open(os.path.join(out, "REPORT.md"), encoding="utf-8") as fh:
            self.assertIn("Perspective panel (advisory, no authority)", fh.read())
        self.assertTrue(audit(out, verdict["_ledger_head"])["ok"])

    def test_a_malformed_reviewer_result_is_recorded_not_crashed_on(self):
        d = self.copy_fixture("editorial-clear-win")
        bout, event, wi, prun, ledger = self.weigh(d)
        lenses = load_lenses(LENSES)
        ids = export_panel(prun, bout, event, wi, lenses, [("faithful-plain", "polished-omission")], ["r1"], "none",
                           ["synthetic"], ledger)
        rdir = os.path.join(prun, "panel", "results")
        shapes = [{"preference": "A", "margin": 3, "objections": 5, "allegations": "none"},
                  {"preference": "B", "margin": 2, "objections": {"candidate": "A"}, "allegations": [[], 7, None]},
                  {"preference": "A", "margin": 1, "reasons": {"x": [1]},
                   "objections": [{"candidate": "C", "category": ["clarity"], "quote": {"q": 1}, "claim": 9,
                                   "severity": ["critical"]},
                                  {"candidate": "A", "category": "  CLARITY \n", "quote": 12, "claim": None,
                                   "severity": "catastrophic"}]}]
        for pid, shape in zip(ids, shapes):
            write_json(os.path.join(rdir, pid + ".json"), shape)
        with open(os.path.join(rdir, ids[3] + ".json"), "w", encoding="utf-8") as fh:
            fh.write("[" * 100000)                                     # nested far too deeply to parse
        with open(os.path.join(rdir, ids[4] + ".json"), "w", encoding="utf-8") as fh:
            fh.write("not json at all")
        panel = import_panel(prun, bout, lenses, ledger, None)          # must not raise
        by_id = {r["packet_id"]: r for r in panel["records"]}
        self.assertTrue(all(by_id[pid]["valid"] for pid in ids[:3]))
        self.assertFalse(by_id[ids[3]]["valid"])
        self.assertFalse(by_id[ids[4]]["valid"])
        self.assertTrue(by_id[ids[5]].get("missing"))
        # The entry labelled "C" names no candidate. It is kept as an allegation against the pair, not dropped.
        kept = [a for pid in ids[:3] for a in by_id[pid]["allegations"]]
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0]["unattributed"])
        self.assertIsNone(kept[0]["candidate_id"])
        self.assertTrue(any("not a list" in n for n in by_id[ids[0]]["notes"]))

    def test_a_reviewer_cannot_file_a_factual_claim_out_of_sight(self):
        """Third review, R3-01: a lower-case label was dropped in silence, and a factual claim filed under an
        opinion category stopped counting as an allegation, so the reason for a human to look disappeared."""
        d = self.copy_fixture("editorial-clear-win")
        bout, event, wi, prun, ledger = self.weigh(d)
        lenses = load_lenses(LENSES)
        export_panel(prun, bout, event, wi, lenses, [("faithful-plain", "polished-omission")], ["r1"], "none",
                     ["synthetic"], ledger)
        mdir = os.path.join(prun, "panel", "meta")
        quote = "4,218 students"
        for name in os.listdir(mdir):
            meta = read_json(os.path.join(mdir, name))
            faithful = "A" if meta["labels"]["A"] == "faithful-plain" else "B"
            body = {"preference": faithful, "margin": 3, "reasons": "x", "objections": [], "allegations": []}
            if lenses[meta["lens_id"]]["kind"] == "fact_desk":
                body["allegations"] = [{"candidate": " " + faithful.lower() + " ", "quote": quote,
                                        "claim": "invented figure"},
                                       {"candidate": "the second one", "quote": quote, "claim": "also wrong"}]
            else:
                body["objections"] = [{"candidate": faithful, "category": "clarity", "quote": quote,
                                       "claim": "Factual error: the source says two sessions.",
                                       "severity": "critical"},
                                      {"candidate": faithful, "category": "clarity", "quote": quote,
                                       "claim": "This sentence is long and hard to follow."}]
            write_json(os.path.join(prun, "panel", "results", name), body)
        panel = import_panel(prun, bout, lenses, ledger, {"r1": {"model": "scripted test reviewer", "real": False}})
        labelled = [a for a in panel["allegations"] if a["category"] == "allegation" and a["candidate_id"]]
        unattributed = [a for a in panel["allegations"] if a.get("unattributed")]
        screened = [a for a in panel["allegations"] if a.get("filed_as_opinion")]
        self.assertTrue(labelled and all(a["candidate_id"] == "faithful-plain" for a in labelled))
        self.assertTrue(unattributed and all(a["pair"] == unattributed[0]["pair"] for a in unattributed))
        self.assertTrue(screened and all(a["category"] == "clarity" for a in screened))
        # The plain style objection is still only an opinion; the factual one is both.
        in_lane = panel["objections_in_lane"]
        self.assertTrue(any(o.get("also_allegation") for o in in_lane + panel["objections_out_of_lane"]))
        self.assertFalse(any("hard to follow" in a["claim"] for a in panel["allegations"]))

        verdict = run_bout(d, os.path.join(self.tmp, "out"), EVENTS, judges="sim", panel_from=prun)
        because = " | ".join(verdict["human_decision"]["because"])
        self.assertIn("unverified factual allegation", because)
        self.assertIn("name no candidate", because)
        self.assertGreater(verdict["panel"]["allegations_filed_as_opinion"], 0)
        self.assertGreater(verdict["panel"]["allegations_unattributed"], 0)
        self.assertEqual(verdict["recommended"], ["faithful-plain"])          # still advisory: nothing moved

    def test_a_voice_card_cannot_carry_factual_authority_under_another_spelling(self):
        # Family review, RF-09: exact membership in a short list of forbidden words let "Accuracy ", "fidelity",
        # "evidence" and "truth" through. Lanes are now a closed vocabulary, matched exactly as written.
        from barclays.lenses import FACT_LANES, OPINION_LANES, load_lens
        base = read_json(os.path.join(LENSES, "plain-language-editor.json"))
        tried = ["Accuracy ", "ACCURACY", " accuracy", "Factual", "Source_Support", "source-support", "truth",
                 "factual_accuracy", "fidelity", "evidence", "citation_support", "completeness", "accuracy",
                 "", 7, None, ["voice"]]
        for lane in tried:
            with self.subTest(lane=lane):
                card = dict(base, may_assess=["voice", lane])
                path = os.path.join(self.tmp, "card.json")
                write_json(path, card)
                with self.assertRaises(BarclaysError):
                    load_lens(path)
        fact = read_json(os.path.join(LENSES, "fact-desk.json"))
        path = os.path.join(self.tmp, "fact.json")
        write_json(path, dict(fact, may_assess=["accuracy", "voice"]))     # a fact desk has no opinions
        with self.assertRaises(BarclaysError):
            load_lens(path)
        self.assertFalse(OPINION_LANES & FACT_LANES)
        for card in load_lenses(LENSES).values():                          # every shipped card still loads
            lanes = set(card["may_assess"])
            self.assertTrue(lanes <= (FACT_LANES if card["kind"] == "fact_desk" else OPINION_LANES), card["lens_id"])

    def test_a_fidelity_claim_filed_as_voice_is_also_an_allegation(self):
        from barclays.lenses import reads_as_factual
        self.assertTrue(reads_as_factual("Candidate A softens the evaluator's caution about causation."))
        self.assertTrue(reads_as_factual("It loses the caveat about selection."))
        self.assertTrue(reads_as_factual("The draft no longer says the study was not randomized."))
        self.assertFalse(reads_as_factual("The second paragraph could soften its tone."))
        self.assertFalse(reads_as_factual("An alternative order would read better."))

    def test_a_panel_edited_after_import_is_refused(self):
        d = self.copy_fixture("editorial-clear-win")
        bout, event, wi, prun, ledger = self.weigh(d)
        lenses = load_lenses(LENSES)
        export_panel(prun, bout, event, wi, lenses, [("faithful-plain", "polished-omission")], ["r1"], "none",
                     ["synthetic"], ledger)
        import_panel(prun, bout, lenses, ledger, None)
        path = os.path.join(prun, "panel", "panel.json")
        doc = read_json(path)
        doc["valid_results"] = 6                       # someone tidies the panel after the fact
        write_json(path, doc)
        with self.assertRaises(Refusal):
            run_bout(d, os.path.join(self.tmp, "out"), EVENTS, judges="sim", panel_from=prun)

    def test_a_panel_that_read_other_bytes_is_refused(self):
        d = self.copy_fixture("editorial-clear-win")
        bout, event, wi, prun, ledger = self.weigh(d)
        lenses = load_lenses(LENSES)
        export_panel(prun, bout, event, wi, lenses, [("faithful-plain", "polished-omission")], ["r1"], "none",
                     ["synthetic"], ledger)
        import_panel(prun, bout, lenses, ledger, None)
        with open(os.path.join(d, "candidates", "faithful-plain.md"), "a", encoding="utf-8") as fh:
            fh.write("\nOne more sentence.\n")
        with self.assertRaises(Refusal):
            run_bout(d, os.path.join(self.tmp, "out"), EVENTS, judges="sim", panel_from=prun)


class ThirdReview(Base):
    """docs/review/REVIEW-3.md: what the third independent review broke, and what was done about each finding."""

    def test_a_figure_swapped_under_the_sources_own_about_sends_the_verdict_to_a_person(self):
        # R3-03. "approximately $700" for "approximately $688" is identical on the page to a faithful rounding. It
        # is not disqualified; its lead is major, so the event's open-leads rule fires for a finalist carrying it.
        from barclays.verdict import _human_rules
        from barclays.weighin import findings_and_leads
        bout, event, wi, _, _ = self.weigh(self.copy_fixture("_attacks/editorial"))
        for cid, lead_id in (("r-swap-700", "R-700"), ("r-about-700", "R-700"), ("q-third", "Q-1in3"),
                             ("q-double", "Q-x2")):
            with self.subTest(candidate=cid):
                self.assertEqual(wi["eligibility"][cid]["status"], "eligible")
                _, leads = findings_and_leads(wi, cid)
                hit = [item for item in leads if item["id"] == lead_id]
                self.assertTrue(hit and hit[0]["severity"] == "major", leads)
                because = _human_rules(event, "RECOMMEND", bout, "real", True, wi, [cid], None, {})
                self.assertTrue(any(lead_id in b and cid in b for b in because), because)
        # A bare figure with no marker of approximation is still a new figure and still disqualifies.
        self.assertEqual(wi["eligibility"]["r-bare-700"]["status"], "disqualified")
        # A faithful candidate that restates nothing in words carries none of these leads.
        _, leads = findings_and_leads(wi, "faithful-plain")
        self.assertFalse([item["id"] for item in leads if item["id"].startswith(("Q-", "R-"))])

    def test_proportions_in_words_match_the_sources_own(self):
        from barclays.officials.text_fidelity import ratio_words
        self.assertEqual(set(ratio_words("A third of pupils, one in three, and one third again.")), {"1in3"})
        self.assertEqual(set(ratio_words("Gains doubled; twice the rate; a twofold rise.")), {"x2"})
        self.assertEqual(set(ratio_words("Scores rose to 11 in 2025.")), set())            # a date, not a ratio
        self.assertEqual(set(ratio_words("Two-thirds of schools and half the staff.")), {"2in3", "1in2"})

    def test_a_bout_that_changes_a_decisive_check_needs_a_person(self):
        # R3-06. The card lets a bout extend new-numbers.allow; that can whitelist an invented figure.
        atr, why = have_controller()
        if atr is None:
            self.skipTest("tournament controller not available: " + why)
        d = self.copy_fixture("editorial-clear-win")
        bout = read_json(os.path.join(d, "bout.json"))
        bout["params"] = {"new-numbers": {"allow": [100, 38]}}
        write_json(os.path.join(d, "bout.json"), bout)
        verdict = run_bout(d, os.path.join(self.tmp, "out"), EVENTS, judges="sim")
        self.assertIn("BOUT_OVERRIDE:new-numbers.allow", verdict["flags"])
        self.assertTrue(any("changed settings of a decisive check" in b and "new-numbers.allow" in b
                            for b in verdict["human_decision"]["because"]))

    def test_a_bout_cannot_set_a_number_the_card_gives_no_value_for(self):
        from barclays.spec import bout_overrides
        event = {"event_id": "x", "format": {},
                 "officials": [{"id": "o", "bout_may_set": ["t", "u"], "params": {"u": 10}}]}
        with self.assertRaises(BarclaysError):                     # nothing to bound it against
            bout_overrides({"bout_id": "b", "params": {"o": {"t": 0.01}}}, event)
        with self.assertRaises(BarclaysError):                     # more than ten times below the card's value
            bout_overrides({"bout_id": "b", "params": {"o": {"u": 0.5}}}, event)
        self.assertEqual(bout_overrides({"bout_id": "b", "params": {"o": {"u": 5}}}, event)["officials"],
                         {"o": {"u": 5}})
        # The shipped software card: a per-call limit of 0.01 s would time out every candidate.
        d = self.copy_fixture("software-clear-win")
        bout = read_json(os.path.join(d, "bout.json"))
        bout["params"] = {"pass-to-pass": {"call_timeout_seconds": 0.01}}
        write_json(os.path.join(d, "bout.json"), bout)
        with self.assertRaises(BarclaysError):
            _load(d, EVENTS)

    def test_a_run_sealed_by_the_earlier_version_is_checked_by_its_own_rules(self):
        # 0.2.0 sealed files only, and databases by their rows. 0.3.0 seals directories, links and schema as well.
        # A seal says which; an older sealed run still verifies, with a warning about what its seal does not cover.
        from barclays.ledger import TREE_FORMAT, run_tree
        d = self.copy_fixture("editorial-clear-win")
        out = os.path.join(self.tmp, "out")
        verdict = run_bout(d, out, EVENTS, judges="none")
        with open(os.path.join(out, "ledger.jsonl"), encoding="utf-8") as fh:
            last = json.loads(fh.read().strip().splitlines()[-1])
        self.assertEqual(last["summary"]["tree_format"], TREE_FORMAT)

        def as_version_0_2_wrote_it(events):        # a format-1 tree and no tree_format field
            seal = events[-1]
            os.remove(os.path.join(out, "objects", seal["refs"]["tree"]))
            old_tree = run_tree(out, fmt=1)
            seal["refs"]["tree"] = put(out, old_tree)
            del seal["summary"]["tree_format"]
            seal["summary"]["tree_files"] = len(old_tree)

        rewrite_chain(out, as_version_0_2_wrote_it)
        with open(os.path.join(out, "ledger.jsonl"), encoding="utf-8") as fh:
            head = json.loads(fh.read().strip().splitlines()[-1])["hash"]
        report = audit(out, head)
        self.assertTrue(report["consistent"], report["problems"])
        self.assertTrue(any("tree format 1" in w for w in report["warnings"]))
        os.mkdir(os.path.join(out, "objects", "added-later"))        # not covered by a format-1 seal
        self.assertTrue(audit(out, head)["consistent"])

    @unittest.skipUnless(os.name == "posix", "permission bits are a POSIX matter")
    def test_a_ledger_others_can_write_is_said_out_loud(self):
        # R3-05. Permissions are outside the seal (they do not survive a copy); a warning says so.
        d = self.copy_fixture("editorial-clear-win")
        out = os.path.join(self.tmp, "out")
        verdict = run_bout(d, out, EVENTS, judges="none")
        self.assertFalse(audit(out, verdict["_ledger_head"])["warnings"])
        os.chmod(os.path.join(out, "ledger.jsonl"), 0o666)
        report = audit(out, verdict["_ledger_head"])
        self.assertTrue(report["consistent"])
        self.assertTrue(any("writable by other accounts" in w for w in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
