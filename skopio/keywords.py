"""
Parser for the compact keyword syntax.

One term per line, prefixed by a symbol stating its importance:

    !!! solid electrolyte | LLZO      critical   (queries the databases)
    !!  dendrite suppression          important  (queries the databases)
    !   impedance spectroscopy        useful
        machine learning              context
    -   photocatalysis                exclusion
    ~   Jane Doe                      tracked author
    @   Nature Energy                 preferred journal

Two operators:

    |   variants of the SAME concept, counted only once
        "CO2 capture | carbon dioxide capture" does not count twice
    &   conjunction: every term must be present
        "ionic conductivity & lithium" drops papers matching only one

One modifier, placed right after the prefix:

    ^   match in the TITLE only
        "!!^ nanoparticle" ignores papers merely name-dropping the word

Anything after a # is a comment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Recognised prefixes, longest first (order matters)
PREFIXES = [
    ("!!!", "critical"),
    ("!!", "important"),
    ("!", "useful"),
    ("-", "exclusion"),
    ("~", "author"),
    ("@", "journal"),
]

DEFAULT_WEIGHTS = {
    "critical": 3.0,
    "important": 2.0,
    "useful": 1.0,
    "context": 0.5,
}

# Levels used to build the queries sent to the databases
QUERIED_LEVELS = {"critical", "important"}


@dataclass
class Rule:
    """A single parsed line of the keywords block."""
    level: str                                    # critical | important | ...
    weight: float
    # Equivalent alternatives; each alternative is a list of terms that must
    # ALL be present (the & operator).
    alternatives: list[list[str]] = field(default_factory=list)
    title_only: bool = False
    source_line: str = ""                         # original text, for logs

    @property
    def label(self) -> str:
        """Short name of the rule, used for the report tags."""
        return " ".join(self.alternatives[0]) if self.alternatives else ""

    @property
    def queried(self) -> bool:
        return self.level in QUERIED_LEVELS

    def query_terms(self) -> list[str]:
        """
        Terms to send to the APIs. For a conjunction only the most specific
        term is queried; the other one acts as a scoring filter.
        """
        out = []
        for alt in self.alternatives:
            out.append(max(alt, key=len) if len(alt) > 1 else alt[0])
        return out


@dataclass
class RuleSet:
    """All rules of a profile, split by role."""
    keywords: list[Rule] = field(default_factory=list)
    exclusions: list[Rule] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    journals: list[str] = field(default_factory=list)

    def query_terms(self) -> list[str]:
        terms: list[str] = []
        for rule in self.keywords:
            if rule.queried:
                terms.extend(rule.query_terms())
        seen, out = set(), []
        for term in terms:
            if term.lower() not in seen:
                seen.add(term.lower())
                out.append(term)
        return out


def _split_alternatives(body: str) -> list[list[str]]:
    """'a | b & c' -> [['a'], ['b', 'c']]"""
    alternatives = []
    for block in body.split("|"):
        terms = [t.strip() for t in block.split("&") if t.strip()]
        if terms:
            alternatives.append(terms)
    return alternatives


def parse(text: str, weights: dict | None = None) -> RuleSet:
    """Turn the `keywords` block of a profile into a RuleSet."""
    scale = dict(DEFAULT_WEIGHTS)
    if weights:
        scale.update({k: float(v) for k, v in weights.items()})

    rules = RuleSet()
    for raw in (text or "").splitlines():
        # comments: cut at # unless escaped
        line = re.split(r"(?<!\\)#", raw, maxsplit=1)[0].replace(r"\#", "#")
        if not line.strip():
            continue

        body = line.strip()
        level = "context"
        for prefix, name in PREFIXES:
            if body.startswith(prefix):
                level = name
                body = body[len(prefix):]
                break

        title_only = False
        if body.lstrip().startswith("^"):
            title_only = True
            body = body.lstrip()[1:]

        body = body.strip()
        if not body:
            continue

        if level == "author":
            rules.authors.append(body)
            continue
        if level == "journal":
            rules.journals.append(body)
            continue

        rule = Rule(
            level=level,
            weight=scale.get(level, 1.0),
            alternatives=_split_alternatives(body),
            title_only=title_only,
            source_line=raw.strip(),
        )
        if not rule.alternatives:
            continue
        (rules.exclusions if level == "exclusion" else rules.keywords).append(rule)

    return rules


def summarise(rules: RuleSet) -> str:
    """One-line summary printed at startup, to check what was parsed."""
    counts: dict[str, int] = {}
    for rule in rules.keywords:
        counts[rule.level] = counts.get(rule.level, 0) + 1
    detail = ", ".join(f"{n} {level}" for level, n in sorted(counts.items()))
    return (f"{detail or 'no keyword'} | {len(rules.exclusions)} exclusions "
            f"| {len(rules.authors)} authors | {len(rules.journals)} journals")
