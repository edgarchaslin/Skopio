"""
Article retrieval from the bibliographic databases.

Every `fetch_*` function returns a list of normalised dictionaries:

    {
        "id":       str   stable identifier (doi: or arxiv:)
        "title":    str
        "abstract": str
        "authors":  list[str]
        "date":     str   ISO YYYY-MM-DD
        "journal":  str
        "doi":      str | ""
        "url":      str
        "source":   str   arxiv | openalex | crossref | semantic_scholar
        "type":     str   preprint | article
    }
"""

from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import requests

USER_AGENT = "skopio/2.0 (academic literature monitoring)"
TIMEOUT = 30
ARXIV_DELAY = 3.0  # arXiv explicitly requires >= 3 s between requests


# ------------------------------------------------------------------ helpers
def _normalise_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _get(url: str, params: dict | None = None, headers: dict | None = None,
         attempts: int = 4):
    """
    GET with retry on 429 / 5xx.

    GitHub runners share their IP addresses across thousands of jobs, so
    OpenAlex rate-limits them far more aggressively than a personal machine.
    Without backoff, roughly half the requests of a run are lost.
    """
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    response = None
    for attempt in range(attempts):
        response = requests.get(url, params=params, headers=h, timeout=TIMEOUT)
        if response.status_code in (429, 500, 502, 503, 504):
            header = response.headers.get("Retry-After", "")
            wait = float(header) if header.replace(".", "").isdigit() else 0
            wait = min(max(wait, 2 ** attempt * 2), 30)
            print(f"    ({response.status_code}) retrying in {wait:.0f} s")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response
    response.raise_for_status()
    return response


def _clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)          # JATS / HTML markup
    return re.sub(r"\s+", " ", text).strip()


# -------------------------------------------------------------------- arXiv
def fetch_arxiv(terms: list[str], categories: list[str], since: date,
                max_results: int = 150) -> list[dict]:
    """
    arXiv does not reliably support a date filter inside search_query, so we
    sort by submission date and cut client-side.
    """
    articles: list[dict] = []
    category_query = " OR ".join(f"cat:{c}" for c in categories)

    # arXiv limits query length, so terms are sent in small batches
    batches = [terms[i:i + 6] for i in range(0, len(terms), 6)]

    for batch in batches:
        # title AND abstract: searching the abstract alone misses papers
        # whose topic only appears in the title
        term_query = " OR ".join(f'(ti:"{t}" OR abs:"{t}")' for t in batch)
        params = {
            "search_query": f"({category_query}) AND ({term_query})",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": min(max_results, 100),
        }
        url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                payload = response.read()
        except Exception as exc:                     # noqa: BLE001
            print(f"  [arxiv] request failed: {exc}")
            time.sleep(ARXIV_DELAY)
            continue

        ns = {"a": "http://www.w3.org/2005/Atom"}
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            print(f"  [arxiv] unreadable XML: {exc}")
            time.sleep(ARXIV_DELAY)
            continue

        for entry in root.findall("a:entry", ns):
            published = (entry.findtext("a:published", "", ns) or "")[:10]
            if not published or published < since.isoformat():
                continue
            link = entry.findtext("a:id", "", ns)
            arxiv_id = link.rsplit("/", 1)[-1]
            articles.append({
                "id": f"arxiv:{arxiv_id.split('v')[0]}",
                "title": _clean(entry.findtext("a:title", "", ns)),
                "abstract": _clean(entry.findtext("a:summary", "", ns)),
                "authors": [a.findtext("a:name", "", ns)
                            for a in entry.findall("a:author", ns)],
                "date": published,
                "journal": "arXiv",
                "doi": entry.findtext("{http://arxiv.org/schemas/atom}doi", "", ns) or "",
                "url": link,
                "source": "arxiv",
                "type": "preprint",
            })
        time.sleep(ARXIV_DELAY)

    return articles


# ----------------------------------------------------------------- OpenAlex
def _rebuild_abstract(inverted_index: dict | None) -> str:
    """OpenAlex stores abstracts as an inverted index word -> positions."""
    if not inverted_index:
        return ""
    positions = [(i, word) for word, idx in inverted_index.items() for i in idx]
    positions.sort()
    return " ".join(word for _, word in positions)


def fetch_openalex(terms: list[str], since: date, email: str,
                   max_results: int = 120, require_abstract: bool = True) -> list[dict]:
    articles: list[dict] = []
    # smaller batches mean lighter requests and fewer 429s
    batches = [terms[i:i + 8] for i in range(0, len(terms), 8)]

    for batch in batches:
        search = " OR ".join(f'"{t}"' for t in batch)
        params = {
            "filter": f"from_publication_date:{since.isoformat()},"
                      f"title_and_abstract.search:{search}",
            "per-page": min(max_results, 100),
            "sort": "publication_date:desc",
            "mailto": email,
        }
        try:
            data = _get("https://api.openalex.org/works", params=params).json()
        except Exception as exc:                     # noqa: BLE001
            print(f"  [openalex] request failed: {exc}")
            time.sleep(2)
            continue

        for work in data.get("results", []):
            abstract = _rebuild_abstract(work.get("abstract_inverted_index"))
            if require_abstract and len(abstract) < 80:
                continue
            doi = (work.get("doi") or "").replace("https://doi.org/", "")
            journal = ((work.get("primary_location") or {}).get("source") or {}).get(
                "display_name", "") or ""
            articles.append({
                "id": f"doi:{doi.lower()}" if doi else f"openalex:{work.get('id', '')}",
                "title": _clean(work.get("display_name") or ""),
                "abstract": _clean(abstract),
                "authors": [(a.get("author") or {}).get("display_name", "")
                            for a in (work.get("authorships") or [])][:15],
                "date": work.get("publication_date", "")[:10],
                "journal": journal,
                "doi": doi,
                "url": work.get("doi") or work.get("id", ""),
                "source": "openalex",
                "type": "article",
            })
        time.sleep(1.5)

    return articles


# ----------------------------------------------------------------- Crossref
def fetch_crossref(terms: list[str], since: date, email: str,
                   max_results: int = 80) -> list[dict]:
    articles: list[dict] = []
    # Crossref has no OR operator: one request per term, on the heaviest ones
    for term in terms:
        params = {
            "query.bibliographic": term,
            "filter": f"from-created-date:{since.isoformat()},type:journal-article",
            "rows": min(max_results, 25),
            "sort": "created",
            "order": "desc",
            "mailto": email,
        }
        try:
            items = _get("https://api.crossref.org/works",
                         params=params).json().get("message", {}).get("items", [])
        except Exception as exc:                     # noqa: BLE001
            print(f"  [crossref] failed on '{term}': {exc}")
            continue

        for item in items:
            doi = (item.get("DOI") or "").lower()
            parts = (item.get("created") or {}).get("date-parts", [[None]])[0]
            published = "-".join(f"{p:02d}" if i else str(p)
                                 for i, p in enumerate(parts) if p) if parts[0] else ""
            articles.append({
                "id": f"doi:{doi}" if doi else "",
                "title": _clean(" ".join(item.get("title") or [])),
                "abstract": _clean(item.get("abstract") or ""),
                "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip()
                            for a in (item.get("author") or [])][:15],
                "date": published,
                "journal": " ".join(item.get("container-title") or []),
                "doi": doi,
                "url": item.get("URL", ""),
                "source": "crossref",
                "type": "article",
            })
        time.sleep(0.3)

    return articles


# --------------------------------------------------------- Semantic Scholar
def fetch_semantic_scholar(terms: list[str], since: date, api_key: str = "",
                           max_results: int = 50) -> list[dict]:
    articles: list[dict] = []
    headers = {"x-api-key": api_key} if api_key else {}
    fields = "title,abstract,authors,publicationDate,venue,externalIds,url"

    for term in terms:
        params = {
            "query": term,
            "fields": fields,
            "limit": min(max_results, 20),
            "publicationDateOrYear": f"{since.isoformat()}:",
        }
        try:
            items = _get("https://api.semanticscholar.org/graph/v1/paper/search",
                         params=params, headers=headers).json().get("data", [])
        except Exception as exc:                     # noqa: BLE001
            print(f"  [s2] failed on '{term}': {exc}")
            time.sleep(2)
            continue

        for item in items:
            doi = ((item.get("externalIds") or {}).get("DOI") or "").lower()
            articles.append({
                "id": f"doi:{doi}" if doi else f"s2:{item.get('paperId', '')}",
                "title": _clean(item.get("title") or ""),
                "abstract": _clean(item.get("abstract") or ""),
                "authors": [a.get("name", "") for a in (item.get("authors") or [])][:15],
                "date": (item.get("publicationDate") or "")[:10],
                "journal": item.get("venue", "") or "",
                "doi": doi,
                "url": item.get("url", ""),
                "source": "semantic_scholar",
                "type": "article",
            })
        time.sleep(1.5)

    return articles


# -------------------------------------------------------------- aggregation
SOURCE_PRIORITY = {"openalex": 3, "crossref": 2, "semantic_scholar": 1, "arxiv": 0}


def deduplicate(articles: list[dict]) -> list[dict]:
    """
    Merge on DOI, then on normalised title. On a duplicate the published
    version wins, but the richest abstract is kept, along with a link to the
    associated arXiv preprint.
    """
    by_key: dict[str, dict] = {}
    for article in articles:
        if not article.get("title"):
            continue
        key = (f"doi:{article['doi'].lower()}" if article.get("doi")
               else f"t:{_normalise_title(article['title'])}")
        previous = by_key.get(key)
        if previous is None:
            by_key[key] = article
            continue
        winner, loser = (article, previous) if (
            SOURCE_PRIORITY.get(article["source"], 0)
            > SOURCE_PRIORITY.get(previous["source"], 0)
        ) else (previous, article)
        if len(loser.get("abstract", "")) > len(winner.get("abstract", "")):
            winner["abstract"] = loser["abstract"]
        if loser["source"] == "arxiv":
            winner["preprint_url"] = loser["url"]
        by_key[key] = winner
    return list(by_key.values())


def collect(config: dict, query_terms: list[str], priority_terms: list[str],
            email: str = "", s2_key: str = "",
            since: date | None = None) -> list[dict]:
    """
    Entry point: query every active source and deduplicate.

    `query_terms`    : the !! and !!! keywords of the profile.
    `priority_terms` : the !!! only, for Crossref, which has no OR operator
                       and therefore costs one request per term.
    `email`          : passed to OpenAlex and Crossref, which grant a far
                       more generous quota to identified requests.
    """
    if since is None:
        since = date.today() - timedelta(days=config["window"]["days"])

    src = config["sources"]
    articles: list[dict] = []

    if src["arxiv"]["active"]:
        print("-> arXiv...")
        articles += fetch_arxiv(query_terms, src["arxiv"]["categories"], since,
                                src["arxiv"]["max_results"])
        print(f"   {len(articles)} entries")

    if src["openalex"]["active"]:
        print("-> OpenAlex...")
        n = len(articles)
        articles += fetch_openalex(query_terms, since, email,
                                   src["openalex"]["max_results"],
                                   src["openalex"]["require_abstract"])
        print(f"   {len(articles) - n} entries")

    if src["crossref"]["active"]:
        print("-> Crossref...")
        n = len(articles)
        articles += fetch_crossref(priority_terms[:25], since, email,
                                   src["crossref"]["max_results"])
        print(f"   {len(articles) - n} entries")

    if src["semantic_scholar"]["active"]:
        print("-> Semantic Scholar...")
        n = len(articles)
        articles += fetch_semantic_scholar(priority_terms[:12], since, s2_key,
                                           src["semantic_scholar"]["max_results"])
        print(f"   {len(articles) - n} entries")

    unique = deduplicate(articles)
    print(f"-> {len(articles)} raw entries, {len(unique)} after deduplication")
    return unique
