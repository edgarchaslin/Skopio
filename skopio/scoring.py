"""
Article scoring against the rules of a profile.

Each rule counts ONCE, whatever the number of variants or occurrences. That
is what prevents a paper repeating the same term a dozen times from crowding
out a paper touching five different topics.

  match in the title    -> weight x 2
  match in the abstract -> weight x 1
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from skopio.keywords import Rule, RuleSet

# Compiled patterns are cached: the same term is tested against hundreds of
# articles on every run.
_CACHE: dict[str, re.Pattern] = {}


def flatten(text: str) -> str:
    """Lowercase, no accents, no Unicode subscripts (CO₂ -> co2)."""
    if not text:
        return ""
    digits = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4", "₅": "5",
              "₆": "6", "₇": "7", "₈": "8", "₉": "9",
              "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4"}
    for k, v in digits.items():
        text = text.replace(k, v)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower())


def _plural(word: str) -> str:
    """
    Sub-pattern matching a word in the singular and in the plural.

    Write keywords in the SINGULAR: 'analyses' cannot be reduced to
    'analysis' without a lexicon, since 'phases' reduces to 'phase'. The
    other direction is unambiguous and is what this handles.

    Abstracts use either form, and the
    irregular cases are exactly the ones that matter here: battery/batteries,
    property/properties, analysis/analyses. Words of three letters or less are
    left alone: they are acronyms (SEI, XPS) or formulas, where a trailing
    's' means something else entirely.
    """
    if len(word) <= 3:
        return re.escape(word)
    if word.endswith("ies"):                              # batteries -> battery
        return re.escape(word[:-3]) + "(?:y|ies)"
    if word.endswith("is"):                               # analysis -> analyses
        return re.escape(word[:-2]) + "[ie]s"
    if word.endswith("s"):                                # process -> processes
        return re.escape(word) + "(?:es)?"
    if word.endswith("y") and word[-2] not in "aeiou":    # battery -> batteries
        return re.escape(word[:-1]) + "(?:y|ies)"         # but alloy -> alloys
    return re.escape(word) + "(?:es|s)?"


def _pattern(term: str) -> re.Pattern:
    """
    Pattern for a term, tolerating English plurals and up to two inserted
    words ('ionic conductivity' matches 'ionic charge conductivities').
    """
    if term in _CACHE:
        return _CACHE[term]
    words = flatten(term).split()
    if not words:
        pattern = re.compile(r"(?!)")                    # never matches
    else:
        body = r"\W+(?:\w+\W+){0,2}?".join(_plural(w) for w in words)
        pattern = re.compile(rf"\b{body}\b")
    _CACHE[term] = pattern
    return pattern


def contains(flat_text: str, term: str) -> bool:
    return _pattern(term).search(flat_text) is not None


def _rule_matches(rule: Rule, title: str, abstract: str) -> str:
    """Return 'title', 'abstract' or '' depending on where the rule fires."""
    for alternative in rule.alternatives:
        if all(contains(title, t) for t in alternative):
            return "title"
    if rule.title_only:
        return ""
    for alternative in rule.alternatives:
        if all(contains(abstract, t) for t in alternative):
            return "abstract"
    return ""


def score_article(article: dict, rules: RuleSet, options: dict,
                  today: date | None = None) -> dict:
    """Add score, matches and excluded to the article."""
    today = today or date.today()
    title = flatten(article.get("title", ""))
    abstract = flatten(article.get("abstract", ""))

    score = 0.0
    matches: list[str] = []

    for rule in rules.keywords:
        where = _rule_matches(rule, title, abstract)
        if where == "title":
            score += rule.weight * 2.0
            matches.append(rule.label)
        elif where == "abstract":
            score += rule.weight
            matches.append(rule.label)

    # --- exclusions: drop on title, penalise on abstract ------------------
    excluded = False
    penalty = float(options.get("exclusion_penalty", -4.0))
    for rule in rules.exclusions:
        where = _rule_matches(rule, title, abstract)
        if where == "title":
            excluded = True
            break
        if where == "abstract":
            score += penalty

    # --- tracked authors: family name AND first initial -------------------
    author_bonus = float(options.get("author_bonus", 3.0))
    for name in rules.authors:
        parts = flatten(name).split()
        if len(parts) < 2:
            continue
        family, initial = parts[-1], parts[0][0]
        for author in article.get("authors", []):
            p = flatten(author).split()
            if len(p) >= 2 and p[-1] == family and p[0][0] == initial:
                score += author_bonus
                matches.append(f"author:{name}")
                break
        else:
            continue
        break

    # --- preferred journals ------------------------------------------------
    journal = flatten(article.get("journal", ""))
    if journal:
        for name in rules.journals:
            if flatten(name) in journal:
                score += float(options.get("journal_bonus", 2.0))
                break

    # --- recency -----------------------------------------------------------
    try:
        published = date.fromisoformat(article.get("date", "")[:10])
        days = max(0, (today - published).days)
        score += float(options.get("recency_bonus", 1.5)) / (1 + 0.5 * days)
    except (ValueError, TypeError):
        pass

    # --- no abstract: nothing can be extracted from it ---------------------
    if len(article.get("abstract", "")) < 100:
        score += float(options.get("no_abstract_penalty", -2.0))

    article["score"] = round(score, 2)
    article["matches"] = list(dict.fromkeys(matches))     # unique, order kept
    article["excluded"] = excluded
    return article


def rank(articles: list[dict], rules: RuleSet, options: dict) -> list[dict]:
    """Score, drop excluded articles, sort by descending score."""
    scored = [score_article(dict(a), rules, options) for a in articles]
    kept = [a for a in scored if not a["excluded"]]
    kept.sort(key=lambda a: a["score"], reverse=True)
    return kept
