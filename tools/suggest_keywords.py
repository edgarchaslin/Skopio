#!/usr/bin/env python3
"""
Draft a `keywords` block from your own publications.

No AI involved: the tool pulls your papers from OpenAlex, then extracts
(1) the topics OpenAlex already assigned to them and (2) the phrases
appearing unusually often in your titles and abstracts. The result is a
starting point to review and prune, not a finished profile.

USAGE

    python tools/suggest_keywords.py --orcid 0000-0002-1825-0097
    python tools/suggest_keywords.py --doi 10.1038/xxxxx 10.1103/yyyyy
    python tools/suggest_keywords.py --author "Marie Curie"
    python tools/suggest_keywords.py --orcid 0000-... > draft.txt

Then review it, drop what is off-topic, add your exclusions, and paste the
result into my-profile.yaml.

The ORCID is the most reliable route: it avoids namesakes. Find yours on
orcid.org.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from collections import Counter

import requests

API = "https://api.openalex.org"
UA = "skopio-keyword-suggestion/2.0"

# Stop words: common English plus the boilerplate vocabulary of abstracts
STOPWORDS = set("""
a an the and or but if of in on at to for with from by as is are was were be
been being this that these those we our us it its their his her they them he
she which who whom what when where how why not no nor so than then there here
can could may might must shall should will would do does did done have has had
using used use uses show shows shown showed demonstrate demonstrated report
reported present presented study studies studied investigate investigated
observe observed found find results result work paper article research
analysis approach method methods based new novel recent recently high low
large small different various several many more most such also however
moreover furthermore therefore thus while whereas between among within during
after before both each other others same first second third due via over under
above below well good better best significant significantly important
potential possible propose proposed proposes development developed
characterization characterized properties property effect effects
performance performances application applications system systems
material materials structure structures process processes measurement
measurements value values increase decrease compared comparison
measured reveals reveal exhibit exhibits obtain obtained achieve achieved
enable enables allow allows provide provides suggest suggests indicate
indicates towards toward respectively addition order given
""".split())

# Phrases too generic to be useful keywords
BANNED = {"open access", "creative commons", "all rights reserved",
          "supplementary information", "corresponding author"}


def _get(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, headers={"User-Agent": UA},
                            timeout=30)
    response.raise_for_status()
    return response.json()


def _abstract(inverted_index: dict | None) -> str:
    if not inverted_index:
        return ""
    positions = [(i, word) for word, idx in inverted_index.items() for i in idx]
    positions.sort()
    return " ".join(word for _, word in positions)


# ------------------------------------------------------------- retrieval
def works_by_orcid(orcid: str, email: str, limit: int = 100) -> list[dict]:
    orcid = orcid.strip().replace("https://orcid.org/", "")
    data = _get(f"{API}/works", {
        "filter": f"authorships.author.orcid:{orcid}",
        "per-page": min(limit, 100),
        "sort": "publication_date:desc",
        "mailto": email,
    })
    return data.get("results", [])


def works_by_doi(dois: list[str], email: str) -> list[dict]:
    out = []
    for doi in dois:
        doi = doi.strip().replace("https://doi.org/", "")
        try:
            out.append(_get(f"{API}/works/doi:{doi}", {"mailto": email}))
        except Exception as exc:                        # noqa: BLE001
            print(f"# skipped DOI ({doi}): {exc}", file=sys.stderr)
    return out


def works_by_name(name: str, email: str, limit: int = 100) -> list[dict]:
    authors = _get(f"{API}/authors", {"search": name, "per-page": 5,
                                      "mailto": email}).get("results", [])
    if not authors:
        return []
    if len(authors) > 1:
        print("# Several authors matched - the first one is used:", file=sys.stderr)
        for author in authors[:5]:
            institution = ((author.get("last_known_institutions") or [{}])[0]
                           .get("display_name", "?"))
            print(f"#   {author.get('display_name')} - {institution} - "
                  f"{author.get('works_count')} works - "
                  f"{author.get('orcid') or 'no ORCID'}", file=sys.stderr)
        print("# If that is the wrong one, rerun with --orcid.", file=sys.stderr)
    identifier = authors[0]["id"].rsplit("/", 1)[-1]
    data = _get(f"{API}/works", {
        "filter": f"authorships.author.id:{identifier}",
        "per-page": min(limit, 100),
        "sort": "publication_date:desc",
        "mailto": email,
    })
    return data.get("results", [])


# --------------------------------------------------------------- analysis
def phrases(texts: list[str], n: int) -> Counter:
    """Count n-word phrases, discarding any containing a stop word."""
    counts: Counter = Counter()
    for text in texts:
        words = re.findall(r"[a-z0-9][a-z0-9\-]{1,}", text.lower())
        for i in range(len(words) - n + 1):
            group = words[i:i + n]
            # a stop word anywhere disqualifies: "spectroscopy for all" is not
            # a keyword, "impedance spectroscopy" is
            if any(w in STOPWORDS for w in group):
                continue
            if any(len(w) < 3 for w in group):
                continue
            phrase = " ".join(group)
            if phrase in BANNED:
                continue
            counts[phrase] += 1
    return counts


def openalex_topics(works: list[dict]) -> Counter:
    """Topics already assigned by OpenAlex: the most reliable source."""
    counts: Counter = Counter()
    for work in works:
        for field in ("topics", "concepts"):
            for item in (work.get(field) or []):
                name = item.get("display_name", "")
                level = item.get("level", item.get("subfield", {}) and 2)
                # drop concepts that are too general (level 0 or 1)
                if name and (not isinstance(level, int) or level >= 2):
                    counts[name] += 1
    return counts


def journals(works: list[dict]) -> Counter:
    counts: Counter = Counter()
    for work in works:
        source = ((work.get("primary_location") or {}).get("source") or {})
        name = source.get("display_name", "")
        if name and "arxiv" not in name.lower():
            counts[name] += 1
    return counts


def coauthors(works: list[dict], self_name: str = "") -> Counter:
    counts: Counter = Counter()
    for work in works:
        for authorship in (work.get("authorships") or []):
            name = (authorship.get("author") or {}).get("display_name", "")
            if name and name.lower() != self_name.lower():
                counts[name] += 1
    return counts


# ----------------------------------------------------------------- output
def _prefix(frequency: int, total: int) -> str:
    share = frequency / max(total, 1)
    if share >= 0.30:
        return "!!!"
    if share >= 0.15:
        return "!!"
    if share >= 0.07:
        return "!"
    return "   "


def build(works: list[dict], self_name: str = "") -> str:
    texts = []
    for work in works:
        title = work.get("display_name") or ""
        texts.append(f"{title}. {_abstract(work.get('abstract_inverted_index'))}")

    total = len(works)
    topics = openalex_topics(works)
    bigrams = phrases(texts, 2)
    trigrams = phrases(texts, 3)

    # a three-word phrase absorbs the two-word ones it contains
    for phrase, n in list(trigrams.items()):
        if n >= 2:
            a, b, c = phrase.split()
            bigrams[f"{a} {b}"] -= n
            bigrams[f"{b} {c}"] -= n

    lines = [
        f"# Draft generated from {total} publications.",
        "# REVIEW IT: drop what is off-topic, group variants with |,",
        "# add your exclusions (- prefix). Do not paste as is.",
        "",
        "keywords: |",
        "  # --- topics identified by OpenAlex -------------------------------",
    ]

    for topic, n in topics.most_common(14):
        lines.append(f"  {_prefix(n, total)} {topic.lower():<45}# {n}/{total}")

    lines += ["", "  # --- frequent phrases in your titles and abstracts ---------------"]
    candidates = [(p, n) for p, n in trigrams.most_common(40)
                  if n >= max(2, total * 0.05)]
    candidates += [(p, n) for p, n in bigrams.most_common(60)
                   if n >= max(3, total * 0.08)]
    seen: set[str] = set()
    for phrase, n in sorted(candidates, key=lambda x: -x[1])[:28]:
        if phrase in seen or any(phrase in s for s in seen):
            continue
        seen.add(phrase)
        lines.append(f"  {_prefix(n, total)} {phrase:<45}# {n}/{total}")

    lines += ["", "  # --- exclusions: TO BE COMPLETED by you -------------------------",
              "  # Watch the Radar section of your first reports: the off-topic",
              "  # subjects showing up there belong here.",
              "  # -   neighbouring field outside your scope", ""]

    co = coauthors(works, self_name)
    if co:
        lines.append("  # --- frequent coauthors (prune: keep those you want to track) ---")
        for name, n in co.most_common(10):
            lines.append(f"  # ~   {name:<43}# {n} joint papers")
        lines.append("")

    venues = journals(works)
    if venues:
        lines.append("  # --- journals you publish in ------------------------------------")
        for name, n in venues.most_common(8):
            lines.append(f"  @   {name:<45}# {n} papers")

    return "\n".join(lines)


def _profile_email() -> str:
    """Reuse the address from my-profile.yaml when available."""
    path = pathlib.Path(__file__).resolve().parent.parent / "my-profile.yaml"
    if not path.exists():
        return "skopio@example.org"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("email:"):
            value = line.split(":", 1)[1].strip().strip('"\'')
            if "@" in value:
                return value
    return "skopio@example.org"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Draft a keywords block from your publications (no AI)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--orcid", help="ORCID identifier, e.g. 0000-0002-1825-0097")
    group.add_argument("--doi", nargs="+", help="one or more DOIs")
    group.add_argument("--author", help="full name (less reliable: namesakes)")
    parser.add_argument("--email", default="",
                        help="your address, passed to OpenAlex for a larger "
                             "quota. Defaults to the one in my-profile.yaml")
    parser.add_argument("--limit", type=int, default=100,
                        help="maximum number of publications analysed")
    args = parser.parse_args()

    email = args.email or _profile_email()

    if args.orcid:
        works = works_by_orcid(args.orcid, email, args.limit)
        name = ""
    elif args.doi:
        works = works_by_doi(args.doi, email)
        name = ""
    else:
        works = works_by_name(args.author, email, args.limit)
        name = args.author

    if not works:
        print("No publication found. Check the identifier, or use --doi with "
              "a few representative articles.", file=sys.stderr)
        return 1

    with_abstract = sum(1 for w in works if w.get("abstract_inverted_index"))
    print(f"# {len(works)} publications, {with_abstract} with an abstract.",
          file=sys.stderr)
    print(build(works, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
