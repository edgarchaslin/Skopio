"""
Profile loading.

One repository = one person = one `my-profile.yaml` at the root. For most
users this is the only file they will ever edit.

Technical settings (queried sources, window, delivery channel) live in
`config.yaml`, with defaults that suit most cases.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from skopio import keywords
from skopio.keywords import RuleSet

DEFAULT_VOLUME = {"must_read": 8, "relevant": 15, "radar": 25, "bullets": 3}
DEFAULT_OPTIONS = {
    "exclusion_penalty": -4.0,
    "author_bonus": 3.0,
    "journal_bonus": 2.0,
    "recency_bonus": 1.5,
    "no_abstract_penalty": -2.0,
    "minimum_score": 3.0,
    "must_read_floor": 12.0,     # auto thresholds only
    "relevant_floor": 6.0,
}


@dataclass
class Profile:
    name: str
    path: Path
    rules: RuleSet
    email: str = ""
    thresholds: dict | str = "auto"
    volume: dict = field(default_factory=lambda: dict(DEFAULT_VOLUME))
    options: dict = field(default_factory=lambda: dict(DEFAULT_OPTIONS))
    report_title: str = "Skopio"

    @property
    def slug(self) -> str:
        base = unicodedata.normalize("NFKD", self.name)
        base = "".join(c for c in base if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "profile"


def _merge(defaults: dict, provided: dict | None) -> dict:
    out = dict(defaults)
    if provided:
        out.update({k: v for k, v in provided.items() if v is not None})
    return out


def load(path: Path) -> Profile:
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} not found. Copy the template and fill it in."
        )

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    block = data.get("keywords", "")
    if isinstance(block, list):        # tolerate a YAML list instead of a block
        block = "\n".join(str(x) for x in block)

    return Profile(
        name=str(data.get("name") or "").strip() or "Skopio",
        path=path,
        rules=keywords.parse(block, data.get("weights")),
        email=str(data.get("email") or "").strip(),
        thresholds=data.get("thresholds", "auto"),
        volume=_merge(DEFAULT_VOLUME, data.get("volume")),
        options=_merge(DEFAULT_OPTIONS, data.get("options")),
        report_title=str(data.get("report_title") or "Skopio"),
    )


def check(profile: Profile) -> list[str]:
    """Return the list of detected problems. Empty means the profile is sound."""
    issues = []

    # the classic mistake: running Skopio without editing the template
    placeholders = ("first last", "first.last", "my-lab.org", "example.org")
    if any(p in profile.name.lower() or p in profile.email.lower()
           for p in placeholders):
        issues.append("profile is still the template: replace the name, the "
                      "address and above all the keywords with your own")

    if not [r for r in profile.rules.keywords if r.queried]:
        issues.append("no !! or !!! keyword: no query will be sent")
    elif not [r for r in profile.rules.keywords if r.level == "critical"]:
        issues.append("no !!! keyword: Crossref and Semantic Scholar are only "
                      "given the critical terms and will return nothing")
    if len(profile.rules.keywords) < 5:
        issues.append("fewer than 5 keywords: results will be very thin")
    if not profile.rules.exclusions:
        issues.append("no exclusion: expect noise during the first days")
    if not profile.email:
        issues.append("empty 'email' field: required to receive the report")
    elif "@" not in profile.email:
        issues.append(f"invalid address ({profile.email})")
    return issues
