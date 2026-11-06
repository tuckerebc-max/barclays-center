"""Text fidelity officials: does a revision still say what the source said?

Five officials, all deterministic and offline:

  text.fact_ledger    every must-keep fact in the organizer's ledger is still present
  text.new_numbers    the revision introduces no number that is absent from the source and the evidence
  text.quotes         every quotation in the revision appears verbatim in the source or the evidence
  text.hedge_shift    (leads only) hedges dropped, boosters or negations added next to a ledger fact, or a
                      negation present in only one of the source and the candidate
  text.number_roles   (leads only) the numbers of a source sentence appear in another order in the candidate

What these establish: presence and absence of declared surface forms. They do not read for meaning. A fact that is
present but contradicted two sentences later passes the ledger; that is what the leads and the panel are for. A fact
missing from the ledger is not protected at all, so the ledger is part of the evidence and is hashed with the bout.
"""
from __future__ import annotations

import re
import time
from decimal import Decimal

from ..canon import read_json
from .base import Ctx, finding, lead, register, result

VERSION = "0.2.0"

_TRANS = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'", "\u2013": "-", "\u2014": "-",
                        "\u00a0": " ", "\u202f": " ", "\u2009": " ", "\u2011": "-"})
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
# '4 218' (space, no-break space, narrow no-break space or thin space as a thousands separator). The first group may
# have one to three digits, and it may not follow another digit, so '2026 150' is never read as 2026150.
_SPACE_THOUSANDS = re.compile(r"(?<![\d.,])(\d{1,3})((?: \d{3})+)(?!\d)")
_SCALE = {"thousand": 1000, "million": 10 ** 6, "billion": 10 ** 9}
_SUFFIX = {"k": 1000, "m": 10 ** 6, "bn": 10 ** 9}
_DIGIT_SCALE = re.compile(r"(?<![\w.,])(\d+(?:\.\d+)?)\s*(thousand|million|billion)\b")
_DOLLAR_SUFFIX = re.compile(r"\$(\d+(?:\.\d+)?)(k|m|bn)\b")

_UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
_TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
          "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
         "ninety": 90}
_WORD_ALT = "|".join(sorted(list(_UNITS) + list(_TEENS) + list(_TENS) + list(_SCALE) + ["hundred"],
                            key=len, reverse=True))
_WORD_RUN = re.compile(r"(?<![a-z])(?:%s)(?:(?:[\s-]+and)?[\s-]+(?:%s))*(?![a-z])" % (_WORD_ALT, _WORD_ALT))


def _plain(d: Decimal) -> str:
    return str(int(d)) if d == d.to_integral_value() else format(d.normalize(), "f")


def _scale_digits(m) -> str:
    return _plain(Decimal(m.group(1)) * _SCALE[m.group(2)])


def _scale_dollars(m) -> str:
    return "$" + _plain(Decimal(m.group(1)) * _SUFFIX[m.group(2)])


def _take_number(tokens: list, i: int):
    """Parse one number from tokens[i:]. Returns (end, value); value None means 'a bare one: leave it as a word'.
    (end == i) means no number starts here."""
    total, group, last_scale, kind = 0, 0, None, "start"
    end, k = i, i
    while k < len(tokens):
        t = tokens[k]
        if t == "and":
            nxt = tokens[k + 1] if k + 1 < len(tokens) else ""
            if kind in ("hundred", "scale") and (nxt in _UNITS or nxt in _TEENS or nxt in _TENS):
                k += 1
                continue
            break
        if t in _UNITS:
            if group % 100 == 0 or (group % 10 == 0 and 20 <= group % 100 <= 90):
                group += _UNITS[t]
                kind = "unit"
            else:
                break
        elif t in _TEENS or t in _TENS:
            if group % 100 == 0:
                group += _TEENS.get(t) or _TENS[t]
                kind = "teen" if t in _TEENS else "tens"
            else:
                break
        elif t == "hundred":
            if kind == "unit" and 0 < group < 10:
                group *= 100
                kind = "hundred"
            else:
                break
        else:  # a scale word
            sc = _SCALE[t]
            if group > 0 and (last_scale is None or sc < last_scale):
                total += group * sc
                group, last_scale, kind = 0, sc, "scale"
            else:
                break
        end = k + 1
        k += 1
    if end == i:
        return i, None
    if end == i + 1 and tokens[i] == "one":
        return end, None
    return end, total + group


def _words_to_digits(m) -> str:
    tokens = [t for t in re.split(r"[\s-]+", m.group(0)) if t]
    out, i = [], 0
    while i < len(tokens):
        end, value = _take_number(tokens, i)
        if end == i:
            out.append(tokens[i])
            i += 1
        else:
            out.append(str(value) if value is not None else " ".join(tokens[i:end]))
            i = end
    return " ".join(out)


def fold_numbers(t: str) -> str:
    """One canonical spelling for numbers, in already-lowercased text: thousands separators (comma, space) removed,
    '2.9 million' / '$2.9m' -> 2900000, 'thirty-seven' -> 37, 'five thousand' -> 5000. A bare 'one' and 'a' are never
    numbers, and 'percent' stays 'percent'."""
    t = _THOUSANDS.sub("", t)
    t = _SPACE_THOUSANDS.sub(lambda m: m.group(1) + m.group(2).replace(" ", ""), t)
    t = _DIGIT_SCALE.sub(_scale_digits, t)
    t = _DOLLAR_SUFFIX.sub(_scale_dollars, t)
    return _WORD_RUN.sub(_words_to_digits, t)


# British and American spellings fold to the American form. A small explicit rule set, not a stemmer. Folding is
# applied to both sides of every comparison, so a rule that over-reaches (advise -> advize) is harmless as long as
# it never maps two different words to one: stems under three letters are left alone ('raise', 'prise' vs 'prize').
_OUR_STEMS = ("col", "behavi", "fav", "hon", "lab", "neighb", "harb", "hum", "rum", "flav", "endeav", "vig", "rig",
              "od", "sav", "tum", "val", "arm", "parl", "glam")
_OUR = re.compile(r"(?<![a-z])(%s)our(s|ed|ing|able|ite|ites|ful|less)?(?![a-z])" % "|".join(_OUR_STEMS))
_ISE = re.compile(r"(?<![a-z])([a-z]{3,})is(e|ed|es|ing|er|ers|ation|ations)(?![a-z])")
_ANALYSE = re.compile(r"(?<![a-z])analys(e|ed|ing)(?![a-z])")


def fold_spelling(t: str) -> str:
    t = _OUR.sub(lambda m: m.group(1) + "or" + (m.group(2) or ""), t)
    t = _ISE.sub(lambda m: m.group(1) + "iz" + m.group(2), t)
    return _ANALYSE.sub(lambda m: "analyz" + m.group(1), t)


def norm(text: str) -> str:
    """Lowercase, straight quotes, single spaces, one spelling for numbers ('4,218', '4 218' -> '4218';
    'thirty-seven' -> '37'; '$2.9 million' -> '$2900000') and American spelling ('randomised' -> 'randomized')."""
    t = text.translate(_TRANS).lower()
    t = fold_numbers(t)
    t = fold_spelling(t)
    return re.sub(r"\s+", " ", t).strip()


def _alt_positions(ntext: str, alt: str) -> list:
    if alt.startswith("re:"):
        return [m.start() for m in re.finditer(alt[3:], ntext)]
    a = norm(alt)
    if not a:
        return []
    pat = r"(?<![0-9a-z])" + re.escape(a) + r"(?![0-9a-z])"
    return [m.start() for m in re.finditer(pat, ntext)]


def fact_anchors(ntext: str, fact: dict):
    """Every place a fact is present. Returns (anchor positions, reason when there are none).

    A fact is a list of term groups. Each group is satisfied by any one of its alternatives. All groups must be
    satisfied inside one window of `window` characters, so a year that appears somewhere else in the document does
    not count toward a fact about enrolment.
    """
    spec = fact.get("match") or {}
    groups = spec.get("all") or []
    window = int(spec.get("window", 240))
    if not groups:
        return [], "fact has no match groups"
    positions = []
    missing = []
    for i, group in enumerate(groups):
        found = sorted({p for alt in group for p in _alt_positions(ntext, alt)})
        if not found:
            missing.append(" | ".join(group))
        positions.append(found)
    if missing:
        return [], "no occurrence of: " + "; ".join(missing)
    anchors = [a for a in sorted({p for found in positions for p in found})
               if all(any(a <= p <= a + window for p in found) for found in positions)]
    if not anchors:
        return [], f"terms occur but never together within {window} characters"
    return anchors, ""


def match_fact(ntext: str, fact: dict):
    """Is the fact present? Returns (present, first anchor position or None, reason)."""
    anchors, reason = fact_anchors(ntext, fact)
    return (True, anchors[0], "") if anchors else (False, None, reason)


_PARA = "\u00b6"  # marks a paragraph break in text prepared by _norm_para
_BOUNDARY = re.compile(r"(?<=[.?!])[\"')\]*_]*\s+|\s*" + _PARA + r"\s*")
_ABBREV = re.compile(r"(?<![a-z])(?:dr|mr|mrs|ms|prof|st|vs|no|fig|e\.g|i\.e)\.$")


def _bounds(ntext: str) -> list:
    out = []
    for m in _BOUNDARY.finditer(ntext):
        if _PARA not in m.group(0) and _ABBREV.search(ntext[max(0, m.start() - 8):m.start()]):
            continue  # 'dr. okafor' does not end a sentence
        out.append((m.start(), m.end()))
    return out


def _sentence_at(ntext: str, pos: int) -> str:
    start, end = 0, len(ntext)
    for b0, b1 in _bounds(ntext):
        if b1 <= pos:
            start = b1
        elif b0 >= pos:
            end = b0
            break
    return ntext[start:end].replace(_PARA, " ").strip()


def _norm_para(text: str) -> str:
    """norm() that keeps paragraph breaks as a marker, so a heading or a paragraph is not glued to the next sentence."""
    return norm(re.sub(r"\n[ \t]*\n+", " " + _PARA + " ", text))


def _load_ledger(ctx: Ctx):
    src = ctx.source("fact_ledger")
    if not src:
        return None, "the bout declares no fact_ledger source"
    ledger = read_json(src["abs"])
    facts = ledger.get("facts") if isinstance(ledger, dict) else None
    if not isinstance(facts, list) or not facts:
        return None, "fact ledger has no facts"
    return facts, ""


def _read(path: str) -> str:
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8", errors="replace")


def _reference_texts(ctx: Ctx) -> list:
    """The source draft plus any evidence documents: the only places a number or quotation may come from."""
    out = []
    src = ctx.source("source_draft")
    if src:
        out.append(_read(src["abs"]))
    for item in ctx.source("evidence") or []:
        out.append(_read(item["abs"]))
    return out


@register("text.fact_ledger")
def fact_ledger(ctx: Ctx) -> dict:
    started = time.time()
    name = "text.fact_ledger"
    facts, why = _load_ledger(ctx)
    if facts is None:
        return result(ctx, name, VERSION, "deterministic", "unverified", why, started=started)
    src = ctx.source("source_draft")
    if not src:
        return result(ctx, name, VERSION, "deterministic", "unverified", "the bout declares no source_draft",
                      started=started)
    nsource = norm(_read(src["abs"]))

    # Guard the guard: a ledger that does not match its own source would disqualify everyone for the wrong reason.
    broken = [f.get("id", "?") for f in facts if f.get("must_keep", True) and not match_fact(nsource, f)[0]]
    if broken:
        return result(ctx, name, VERSION, "deterministic", "unverified",
                      "ledger does not match the source draft for: " + ", ".join(broken) +
                      ". Fix the ledger; no candidate is judged against a broken one.", started=started)

    ntext = norm(ctx.all_text())
    findings = []
    kept = 0
    for fact in facts:
        fid = str(fact.get("id", "?"))
        present, _, reason = match_fact(ntext, fact)
        if present:
            kept += 1
            continue
        if not fact.get("must_keep", True):
            continue
        _, spos, _ = match_fact(nsource, fact)
        findings.append(finding(
            fid, "critical" if fact.get("critical", True) else "major",
            f"Fact {fid} is not present: {fact.get('statement', '')}",
            locator="(absent from the candidate)",
            evidence={"reason": reason, "source_sentence": _sentence_at(nsource, spos or 0)[:300]}))
    must = sum(1 for f in facts if f.get("must_keep", True))
    status = "fail" if findings else "pass"
    summary = (f"{len(findings)} of {must} must-keep facts missing" if findings
               else f"all {must} must-keep facts present")
    return result(ctx, name, VERSION, "deterministic", status, summary, findings=findings,
                  metrics={"facts_total": len(facts), "must_keep": must, "kept": kept, "missing": len(findings)},
                  started=started)


_NUM = re.compile(r"(?<![\w.,])\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?![\dA-Za-z])")


def numbers_in(text: str) -> list:
    """[(value, line number, line excerpt)] by surface form, thousands commas removed ('$4.2 million' yields '4.2').
    Kept for callers that want the raw digits; the officials use canonical_numbers()."""
    out = []
    for lineno, line in enumerate(text.translate(_TRANS).splitlines(), 1):
        for m in _NUM.finditer(line):
            value = m.group(1).replace(",", "") + (m.group(2) or "")
            out.append((value, lineno, line.strip()[:200]))
    return out


_PERCENT = re.compile(r"\s*(?:%|percent\b|per cent\b)")
_ORDINAL = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(?:st|nd|rd|th)\b")


def canonical_numbers(text: str) -> list:
    """[(value, line number, line excerpt)] after number normalisation: '$2,900,000', '2.9 million' and '$2.9M' are
    all '2900000'; 'thirty-seven' is '37'; '4 218' is '4218'.

    A figure's kind is part of the figure. '37%' and '37 percent' are both '37%', which is not '37': a revision
    that turns "37 schools" into "37% of students" has invented a figure even though the digits are in the source.
    Likewise '37th' is '37th'. (The second independent review passed both through version 0.2.)
    """
    out = []
    for lineno, line in enumerate(text.translate(_TRANS).splitlines(), 1):
        folded = fold_numbers(line.lower())
        for m in _NUM.finditer(folded):
            value = m.group(1).replace(",", "") + (m.group(2) or "")
            if _PERCENT.match(folded, m.end()):
                value += "%"
            out.append((value, lineno, line.strip()[:200]))
        for m in _ORDINAL.finditer(folded):
            out.append((m.group(1).replace(",", "") + "th", lineno, line.strip()[:200]))
    return out


_CUE = re.compile(r"(?:about|around|approximately|approx\.?|roughly|nearly|almost|over|under|more than|less than|"
                  r"fewer than|at least|at most|some|close to|just over|just under|up to|well over|upwards of)"
                  r"\s*\(?\s*\$?\s*$")


def cued_numbers(text: str) -> set:
    """Figures the writer marked as approximate ("more than 4,000", "about four thousand two hundred").

    Only these may be accepted as roundings. A bare "40 schools" where the source says 37 is a different figure,
    not a rounding, however close it is.
    """
    out = set()
    for line in text.translate(_TRANS).splitlines():
        folded = fold_numbers(line.lower())
        for m in _NUM.finditer(folded):
            if _CUE.search(folded[max(0, m.start() - 24):m.start()]):
                value = m.group(1).replace(",", "") + (m.group(2) or "")
                out.add(value + "%" if _PERCENT.match(folded, m.end()) else value)
    return out


_SMALLWORD = {"a": "1", "an": "1", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
              "seven": "7", "eight": "8", "nine": "9", "ten": "10", "hundred": "100"}
_FRACTION = {"half": "2", "halves": "2", "third": "3", "thirds": "3", "quarter": "4", "quarters": "4",
             "fifth": "5", "fifths": "5", "tenth": "10", "tenths": "10"}
_RATIO_IN = re.compile(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(in|out of)\s+(?:every\s+)?"
                       r"(\d+|two|three|four|five|six|seven|eight|nine|ten|hundred)\b")
_RATIO_FRAC = re.compile(r"\b(a|an|one|two|three|four)[\s-]+(half|halves|third|thirds|quarter|quarters|fifth|fifths|"
                         r"tenth|tenths)\b")
_RATIO_HALF = re.compile(r"\bhalf\b")
_RATIO_MULT = re.compile(r"\b(doubl\w*|twice|tripl\w*|thrice|quadrupl\w*|halv\w+|"
                         r"(?:two|three|four|five|ten|\d+)[- ]?fold)\b")


def ratio_words(text: str) -> dict:
    """Proportions and multiples stated in words: {key: (line number, phrase, excerpt)}.

    Keys are canonical ("1in3" for "a third", "one third" and "one in three"; "x2" for "double" and "twice"), so a
    candidate that restates the source's own proportion in the same terms matches it. A deliberately short list:
    it finds the plain cases, not "most", "a majority" or "nearly all".
    """
    out: dict = {}
    for lineno, line in enumerate(text.translate(_TRANS).splitlines(), 1):
        low = line.lower()
        excerpt = line.strip()[:160]

        def add(key, m):
            out.setdefault(key, (lineno, m.group(0), excerpt))

        for m in _RATIO_IN.finditer(low):
            a, b = _SMALLWORD.get(m.group(1), m.group(1)), _SMALLWORD.get(m.group(3), m.group(3))
            if m.group(2) == "in" and 1800 <= int(b) <= 2200:
                continue                      # "11 in 2025" is a date, not a proportion
            add(f"{a}in{b}", m)
        spans = []
        for m in _RATIO_FRAC.finditer(low):
            add(f"{_SMALLWORD[m.group(1)]}in{_FRACTION[m.group(2)]}", m)
            spans.append((m.start(), m.end()))
        for m in _RATIO_HALF.finditer(low):
            if not any(a <= m.start() < b for a, b in spans):
                add("1in2", m)
        for m in _RATIO_MULT.finditer(low):
            w = m.group(1)
            if w.startswith("doubl") or w == "twice":
                key = "x2"
            elif w.startswith("tripl") or w == "thrice":
                key = "x3"
            elif w.startswith("quadrupl"):
                key = "x4"
            elif w.startswith("halv"):
                key = "1in2"
            else:
                n = re.split(r"[- ]?fold", w)[0]
                key = "x" + _SMALLWORD.get(n, n)
            add(key, m)
    return out


def _digits(value: str) -> str:
    return value[:-1] if value.endswith("%") else value[:-2] if value.endswith("th") else value


def _significant(value: str) -> int:
    digits = _digits(value)
    return len((digits.replace(".", "").lstrip("0") if "." in digits else digits.lstrip("0").rstrip("0")) or "0")


def rounding_of(value: str, allowed: set, tolerance: float):
    """The source figure `value` is a rounding of, or None.

    Writers round: 4,218 becomes "more than 4,000" or "about 4,200". That is not a new figure. The rule is
    objective: same kind of figure (plain, percent), strictly fewer significant digits, and within `tolerance`
    (10 percent unless the event card says otherwise) of a figure the source or the evidence does contain. The
    caller applies it only to figures the writer marked as approximate (cued_numbers).
    "Nearly 5,000" for 4,218 is 18 percent away and is still a new figure; a bare "40 schools" for 37 has no
    marker and is still a new figure.
    """
    if tolerance <= 0 or value.endswith("th"):
        return None
    try:
        x = float(_digits(value))
    except ValueError:
        return None
    for other in sorted(allowed):
        if other.endswith("%") != value.endswith("%") or other.endswith("th"):
            continue
        try:
            m = float(_digits(other))
        except ValueError:
            continue
        if m > 0 and _significant(value) < _significant(other) and abs(x - m) <= tolerance * m:
            return other
    return None


@register("text.new_numbers")
def new_numbers(ctx: Ctx) -> dict:
    started = time.time()
    name = "text.new_numbers"
    refs = _reference_texts(ctx)
    if not refs:
        return result(ctx, name, VERSION, "deterministic", "unverified",
                      "no source_draft or evidence to compare numbers against", started=started)
    allowed = {v for text in refs for v, _, _ in canonical_numbers(text)}
    allowed |= {str(x) for x in ctx.params.get("allow", [])}
    small = int(ctx.params.get("ignore_integers_upto", 10))
    policy = ctx.params.get("policy", "fail")
    tolerance = float(ctx.params.get("rounding_tolerance", 0.1))
    findings, leads = [], []
    seen = set()
    cand_text = ctx.all_text()
    cand_numbers = canonical_numbers(cand_text)
    cued = cued_numbers(cand_text)
    for value, lineno, excerpt in cand_numbers:
        if value in allowed or value in seen:
            continue
        # Small counts are ignored because prose is full of them ("three times a week", "grades 1 through 3").
        # That is a known gap: "nine of them saw no gains" is an invented figure and passes. Percentages are
        # never ignored: "nine percent" is a claim.
        if not value.endswith("%") and "." not in value and int(_digits(value)) <= small:
            continue
        rounded_from = rounding_of(value, allowed, tolerance) if value in cued else None
        if rounded_from is not None:
            seen.add(value)
            # Major, so the event's open-leads rule sends a finalist that carries it to a person. The check cannot
            # tell a rounding ("about $700" for $688) from a figure swapped in under the source's own "about"
            # (third review, R3-03): both look the same on the page.
            leads.append(lead(f"R-{value}", f"{value} is not in the source. It is marked as approximate and is "
                                            f"within {tolerance:.0%} of {rounded_from}, so it is recorded as a "
                                            f"possible rounding, not accepted as one. A person must confirm it "
                                            f"is the same quantity (line {lineno}: {excerpt})",
                              locator=f"L{lineno}", severity="major"))
            continue
        seen.add(value)
        claim = f"Number {value} does not appear in the source or the evidence"
        if policy == "fail":
            findings.append(finding(f"N-{value}", "major", claim, locator=f"L{lineno}", evidence={"line": excerpt}))
        else:
            leads.append(lead(f"N-{value}", claim + f" (line {lineno}: {excerpt})", locator=f"L{lineno}",
                              severity="major"))
    cand_values = {v for v, _, _ in cand_numbers}
    src = ctx.source("source_draft")
    dropped = []
    if src:
        for value, lineno, excerpt in canonical_numbers(_read(src["abs"])):
            if value not in cand_values and value not in dropped:
                dropped.append(value)
                leads.append(lead(f"D-{value}", f"Source number {value} is absent from the candidate "
                                                f"(source line {lineno}: {excerpt})", severity="minor"))
    # Proportions and multiples stated in words ("a third", "one in three", "double"). They carry no digits, so
    # the figure check above cannot see them. They may restate a figure faithfully or invent one; that takes a
    # reader, so each one the source does not state in the same terms is a major lead, never a finding.
    stated = set()
    for text in refs:
        stated |= set(ratio_words(text))
    loose = 0
    for key, (lineno, phrase, excerpt) in sorted(ratio_words(cand_text).items()):
        if key in stated:
            continue
        loose += 1
        leads.append(lead(f"Q-{key}", f"'{phrase}' states a proportion or multiple in words that the source does "
                                      f"not state in those terms. It may restate a figure or invent one; a "
                                      f"person must check (line {lineno}: {excerpt})",
                          locator=f"L{lineno}", severity="major"))
    status = "fail" if findings else "pass"
    summary = (f"{len(findings)} number(s) with no support in the source or evidence" if findings
               else "no unsupported numbers")
    return result(ctx, name, VERSION, "deterministic", status, summary, findings=findings, leads=leads,
                  metrics={"new_numbers": len(seen), "dropped_source_numbers": len(dropped),
                           "proportions_in_words_not_in_source": loose}, started=started)


_DQUOTE = re.compile(r'"((?:[^"\n]|\n(?![ \t]*\n))+)"')
# A single quote opens after a non-word character and closes before one; an apostrophe between two letters
# (don't, evaluator's) belongs to the word.
_SQUOTE = re.compile(r"(?<![\w'])'(?=[^\s'])((?:[^'\n]|(?<=\w)'(?=\w)|\n(?![ \t]*\n))+?)(?<=[^\s'])'(?![\w'])")
_ELLIPSIS = re.compile(r"\s*\[?\s*(?:\.\.\.|\u2026)\s*\]?\s*")
_QUOTE_MAX = 1200


def quotations(text: str) -> list:
    """[(start offset, quoted text)] for straight and curly, double and single quotation marks, across line breaks
    (not across a blank line). `text` must already have curly marks straightened."""
    spans = [(m.start(), m.end(), m.group(1)) for m in _DQUOTE.finditer(text) if len(m.group(1)) <= _QUOTE_MAX]
    for m in _SQUOTE.finditer(text):
        if len(m.group(1)) <= _QUOTE_MAX and not any(a <= m.start() < b for a, b, _ in spans):
            spans.append((m.start(), m.end(), m.group(1)))
    return [(a, q) for a, _, q in sorted(spans)]


def _segments(q: str) -> list:
    """The pieces of a quotation around ellipses, normalised, empty pieces dropped."""
    out = []
    for piece in _ELLIPSIS.split(q):
        n = norm(piece).strip(" .,;:!?\"'")
        if n:
            out.append(n)
    return out


def _in_order(ref: str, segments: list) -> bool:
    pos = 0
    for seg in segments:
        at = ref.find(seg, pos)
        if at < 0:
            return False
        pos = at + len(seg)
    return True


@register("text.quotes")
def quotes(ctx: Ctx) -> dict:
    started = time.time()
    name = "text.quotes"
    refs = _reference_texts(ctx)
    if not refs:
        return result(ctx, name, VERSION, "deterministic", "unverified",
                      "no source_draft or evidence to verify quotations against", started=started)
    nrefs = [norm(t) for t in refs]
    min_words = int(ctx.params.get("min_words", 3))
    findings = []
    checked = 0
    text = ctx.all_text().translate(_TRANS)
    for start, q in quotations(text):
        segs = _segments(q)
        if sum(len(x.split()) for x in segs) < min_words:
            continue
        checked += 1
        # Each piece around an ellipsis must appear verbatim, in order, inside one source document.
        if not any(_in_order(ref, segs) for ref in nrefs):
            line = text.count("\n", 0, start) + 1
            findings.append(finding(f"Q-{checked}", "critical",
                                    "Quotation does not appear verbatim in the source or the evidence",
                                    locator=f"L{line}", evidence={"quotation": q.strip()[:300]}))
    status = "fail" if findings else "pass"
    summary = (f"{len(findings)} of {checked} quotation(s) not found verbatim" if findings
               else f"{checked} quotation(s) verified verbatim")
    return result(ctx, name, VERSION, "deterministic", status, summary, findings=findings,
                  metrics={"quotations_checked": checked, "unverified_quotations": len(findings)}, started=started)


HEDGES = ("may", "might", "could", "suggests", "suggest", "suggested", "preliminary", "early", "appears", "appear",
          "approximately", "about", "roughly", "estimated", "estimate", "likely", "possibly", "pilot", "tentative",
          "not yet")
BOOSTERS = ("proves", "proven", "prove", "proved", "definitively", "clearly", "guarantees", "guarantee", "always",
            "dramatically", "undeniably", "conclusively", "transformed", "transforms", "every", "certainly")
NEGATIONS = ("not", "no", "never", "fewer", "without", "failed", "declined", "decline", "less")


_NEG = re.compile(r"(?<![a-z])(?:not|no|never|without|neither|nor|cannot)(?![a-z])|n't(?![a-z])|failed to(?![a-z])")
_MAX_SENTENCES = 6


def _cues(sentence: str, words) -> set:
    return {w for w in words if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", sentence)}


def _sentences_for(ntext: str, fact: dict) -> list:
    """The distinct sentences in which the fact is present, in order of appearance (every window, not the first)."""
    anchors, _ = fact_anchors(ntext, fact)
    out = []
    for a in anchors:
        sent = _sentence_at(ntext, a)
        if sent not in out:
            out.append(sent)
    # A sentence that holds every term group is the fact's own sentence. One that holds only the anchor term
    # ("students" near "4,218" in the next sentence) is used only when the fact is split across sentences.
    whole = [x for x in out if match_fact(x, fact)[0]]
    return (whole or out)[:_MAX_SENTENCES]


@register("text.hedge_shift")
def hedge_shift(ctx: Ctx) -> dict:
    """Leads only. Compares each sentence carrying a ledger fact in the candidate with the source's sentence(s)."""
    started = time.time()
    name = "text.hedge_shift"
    facts, why = _load_ledger(ctx)
    src = ctx.source("source_draft")
    if facts is None or not src:
        return result(ctx, name, VERSION, "deterministic", "not_applicable", why or "no source_draft",
                      started=started)
    nsource = _norm_para(_read(src["abs"]))
    ntext = _norm_para(ctx.all_text())
    leads = []
    for fact in facts:
        fid = str(fact.get("id", "?"))
        s_sents = _sentences_for(nsource, fact)
        c_sents = _sentences_for(ntext, fact)
        if not (s_sents and c_sents):
            continue
        s_hedges = set().union(*(_cues(x, HEDGES) for x in s_sents))
        s_boost = set().union(*(_cues(x, BOOSTERS) for x in s_sents))
        s_negs = set().union(*(_cues(x, NEGATIONS) for x in s_sents))
        s_polarity = {bool(_NEG.search(x)) for x in s_sents}
        for n, c_sent in enumerate(c_sents):
            tag = fid if n == 0 else f"{fid}.{n + 1}"
            # A lead only when the candidate's sentence keeps no hedge at all; rewording one hedge as another is normal.
            lost = s_hedges if (s_hedges and not _cues(c_sent, HEDGES)) else set()
            added = _cues(c_sent, BOOSTERS) - s_boost
            negs = _cues(c_sent, NEGATIONS) - s_negs
            c_neg = bool(_NEG.search(c_sent))
            if lost:
                leads.append(lead(f"H-{tag}", f"Near fact {fid} the source hedges with {sorted(lost)} and the "
                                              f"candidate does not. Check whether the claim was strengthened. "
                                              f"Candidate: \"{c_sent[:220]}\"", locator=f"fact:{fid}",
                                  severity="major"))
            if added:
                leads.append(lead(f"B-{tag}", f"Near fact {fid} the candidate adds {sorted(added)}. Check whether "
                                              f"the source supports that strength. Candidate: \"{c_sent[:220]}\"",
                                  locator=f"fact:{fid}", severity="major"))
            if negs:
                leads.append(lead(f"G-{tag}", f"Near fact {fid} the candidate adds {sorted(negs)}. The fact's terms "
                                              f"are present; check that its meaning is not reversed. Candidate: "
                                              f"\"{c_sent[:220]}\"", locator=f"fact:{fid}", severity="major"))
            if c_neg not in s_polarity:
                had = "has a negation" if c_neg else "has no negation"
                leads.append(lead(f"P-{tag}", f"Near fact {fid} the polarity may have changed: the candidate's "
                                              f"sentence {had}, the source's sentence for this fact "
                                              f"{'has no negation' if c_neg else 'has a negation'}. Candidate: "
                                              f"\"{c_sent[:220]}\"", locator=f"fact:{fid}", severity="major"))
    return result(ctx, name, VERSION, "deterministic", "pass",
                  f"{len(leads)} lead(s) for reviewers; this official never fails a candidate", leads=leads,
                  metrics={"leads": len(leads)}, started=started)


def _numbered_sentences(text: str) -> list:
    """[(sentence, [distinct numbers in order of first appearance])] for sentences with at least one number."""
    out = []
    for line in fold_numbers(text.translate(_TRANS).lower()).splitlines():
        for sent in re.split(r"(?<=[.!?])\s+(?=\S)", line.strip()):
            order = []
            for m in _NUM.finditer(sent):
                v = m.group(1).replace(",", "") + (m.group(2) or "")
                if v not in order:
                    order.append(v)
            if order:
                out.append((sent, order))
    return out


def _join(values: list) -> str:
    return values[0] if len(values) == 1 else ", ".join(values[:-1]) + " and " + values[-1]


@register("text.number_roles")
def number_roles(ctx: Ctx) -> dict:
    """Leads only. A source sentence that carries two or more distinct numbers fixes which number goes with which
    phrase only by their order. When the candidate has a sentence with the same numbers in another order, a reviewer
    should check that the roles were not swapped. Conservative: a candidate that spreads the numbers over several
    sentences, or keeps any sentence in the source order, raises nothing."""
    started = time.time()
    name = "text.number_roles"
    src = ctx.source("source_draft")
    if not src:
        return result(ctx, name, VERSION, "deterministic", "not_applicable", "no source_draft", started=started)
    cand = _numbered_sentences(ctx.all_text())
    leads, seen = [], set()
    for s_sent, s_order in _numbered_sentences(_read(src["abs"])):
        if len(s_order) < 2:
            continue
        holders = [order for _, order in cand if set(s_order) <= set(order)]
        if not holders:
            continue
        same = [o for o in holders if [v for v in o if v in s_order] == s_order]
        if same:
            continue
        key = tuple(s_order)
        if key in seen:
            continue
        seen.add(key)
        opposite = "opposite " if len(s_order) == 2 else "a different "
        leads.append(lead("R-" + "-".join(s_order),
                          f"The numbers {_join(s_order)} appear in {opposite}order to the source; check which number "
                          f"belongs to which group. Source: \"{s_sent[:200]}\"",
                          locator="numbers:" + ",".join(s_order), severity="major"))
    return result(ctx, name, VERSION, "deterministic", "pass",
                  f"{len(leads)} lead(s) for reviewers; this official never fails a candidate", leads=leads,
                  metrics={"leads": len(leads)}, started=started)
