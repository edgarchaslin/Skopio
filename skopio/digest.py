"""
Local digest, no API call.

Instead of a language model, Skopio extracts 2 to 3 sentences from the
original abstract: the ones carrying a result. Sentences are ranked on three
simple, robust signals:

  - a figure with a unit (GHz, %, nm, K...) — almost always the sentence
    holding the result;
  - result phrasing ("we show", "results in", "enhancement of");
  - density of the profile keywords.

This is not a summary but a highlight. The sentence stays the authors' own,
so nothing is distorted — but nothing is rephrased either.
"""

from __future__ import annotations

import re

from skopio.keywords import RuleSet
from skopio.scoring import contains, flatten

# Phrasing signalling a result rather than background
RESULT_MARKERS = [
    "we show", "we report", "we demonstrate", "we find", "we observe",
    "we present", "here we", "results in", "leads to", "reveals",
    "enables", "achieves", "reaches", "exhibits", "yields",
    "enhancement", "reduction", "improvement", "increase", "decrease",
    "record", "highest", "lowest", "unprecedented", "for the first time",
]

# Background phrasing: pushed down the ranking
BACKGROUND_MARKERS = [
    "have attracted", "has attracted", "in recent years", "is a promising",
    "are promising", "has been widely", "have been widely", "is well known",
    "plays an important role", "is of great interest",
]

UNITS = (r"(?:ghz|mhz|thz|khz|nm|pm|um|µm|mm|mev|ev|kv|mv|%|k\b|°c|"
         r"wt\.?%|at\.?%|emu|oe|tesla|mah|wh|kj|mpa|gpa)")


def _sentences(text: str) -> list[str]:
    """Sentence splitting, tolerant of abbreviations and formulas."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    # do not split after "et al.", "vs.", "approx.", nor between digits
    text = re.sub(r"\b(et al|vs|approx|ca|cf|Fig|Ref|e\.g|i\.e)\.", r"\1<DOT>", text)
    text = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", text)
    raw = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text)
    return [s.replace("<DOT>", ".").strip() for s in raw if len(s.strip()) > 30]


def _score_sentence(sentence: str, position: int, total: int,
                    rules: RuleSet) -> float:
    s = flatten(sentence)
    score = 0.0

    # figures with units: the most reliable signal
    if re.search(rf"\d+(?:[.,]\d+)?\s*{UNITS}", s):
        score += 4.0
    elif re.search(r"\b\d+(?:[.,]\d+)?\b", s):
        score += 1.5

    for marker in RESULT_MARKERS:
        if marker in s:
            score += 2.0
            break
    for marker in BACKGROUND_MARKERS:
        if marker in s:
            score -= 3.0
            break

    # keyword density, weighted as in article scoring
    for rule in rules.keywords:
        for alternative in rule.alternatives:
            if all(contains(s, t) for t in alternative):
                score += 0.5 * rule.weight / 3.0
                break

    # abstracts often close on the significance of the results
    if position >= total - 2:
        score += 1.0
    # the first sentence is nearly always background
    if position == 0:
        score -= 1.5

    # endless sentences read poorly as bullets
    if len(sentence) > 320:
        score -= 2.0

    return score


def bullets(article: dict, rules: RuleSet, maximum: int = 3) -> list[str]:
    """Pick the result-bearing sentences, in original abstract order."""
    sentences = _sentences(article.get("abstract", ""))
    if not sentences:
        return ["No abstract provided by the source — open the article."]
    if len(sentences) <= maximum:
        return [_shorten(s) for s in sentences]

    scored = [(_score_sentence(s, i, len(sentences), rules), i, s)
              for i, s in enumerate(sentences)]
    scored.sort(key=lambda t: t[0], reverse=True)
    kept = sorted(scored[:maximum], key=lambda t: t[1])   # back to original order
    return [_shorten(s) for _, _, s in kept]


def _shorten(sentence: str, limit: int = 260) -> str:
    if len(sentence) <= limit:
        return sentence
    return sentence[:limit].rsplit(" ", 1)[0] + "..."


def tags(article: dict, maximum: int = 4) -> list[str]:
    """The keywords actually matched, most specific first."""
    found = [m for m in article.get("matches", []) if not m.startswith("author:")]
    authors = [m.split(":", 1)[1] for m in article.get("matches", [])
               if m.startswith("author:")]
    found.sort(key=len, reverse=True)          # long phrase before acronym
    return (authors + found)[:maximum]


def enrich(articles: list[dict], rules: RuleSet, n_bullets: int = 3) -> list[dict]:
    """Add bullets, tags and final_score. No network, no cost."""
    for article in articles:
        article["bullets"] = bullets(article, rules, n_bullets)
        article["tags"] = tags(article)
        article["final_score"] = article.get("score", 0.0)
    articles.sort(key=lambda a: a["final_score"], reverse=True)
    return articles
