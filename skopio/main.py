"""
Skopio entry point.

    python -m skopio.main                 # normal run
    python -m skopio.main --check         # validate the profile, collect nothing
    python -m skopio.main --demo          # offline sample run
    python -m skopio.main --no-email      # build the report without sending it
    python -m skopio.main --days 7        # widen the search window

Keywords live in my-profile.yaml, technical settings in config.yaml.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

from skopio import __version__, delivery, digest, keywords, profile as profile_mod
from skopio import report, scoring, sources

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "state" / "seen.json"
MAX_STATE = 4000        # number of identifiers kept


# ------------------------------------------------------------------ state
def load_state() -> dict:
    """
    Read the memory of already reported articles.

    Anything unexpected restarts from an empty memory rather than crashing:
    the worst case is a day of duplicates, which beats a run that produces
    no report at all.
    """
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("  [state] unreadable file, starting over")
            return {"seen": {}}
        if isinstance(state, dict) and isinstance(state.get("seen"), dict):
            return state
        print(f"  [state] no usable 'seen' entry in {STATE_FILE.name}, "
              f"starting over (delete the file to silence this)")
    return {"seen": {}}


def save_state(state: dict, new_ids: list[str]) -> None:
    today = date.today().isoformat()
    for identifier in new_ids:
        state["seen"][identifier] = today
    if len(state["seen"]) > MAX_STATE:
        ordered = sorted(state["seen"].items(), key=lambda kv: kv[1], reverse=True)
        state["seen"] = dict(ordered[:MAX_STATE])
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                          encoding="utf-8")


# ------------------------------------------------------------------ config
SOURCE_NAMES = ("arxiv", "openalex", "crossref", "semantic_scholar")


def check_config(config: dict) -> list[str]:
    """
    Return the list of structural problems in config.yaml. Empty means the
    file is usable. Unlike the profile, a broken config is fatal: every
    section is read without a default, so the run would crash mid-flight.
    """
    if not isinstance(config, dict):
        return ["file is empty or is not a mapping"]

    issues = [f"missing or malformed '{section}:' section"
              for section in ("window", "sources", "report", "delivery")
              if not isinstance(config.get(section), dict)]
    if issues:
        return issues

    days = config["window"].get("days")
    if not isinstance(days, int) or isinstance(days, bool) or days < 0:
        issues.append(f"window.days must be a positive integer (got {days!r})")

    for name in SOURCE_NAMES:
        entry = config["sources"].get(name)
        if not isinstance(entry, dict) or "active" not in entry:
            issues.append(f"sources.{name} is missing or has no 'active:' flag")
    if not issues and not any(config["sources"][n]["active"] for n in SOURCE_NAMES):
        issues.append("every source is inactive: nothing would be collected")

    unknown = [f for f in (config["report"].get("formats") or [])
               if f not in ("html", "md")]
    if unknown:
        issues.append(f"unknown report.formats: {', '.join(map(str, unknown))}")

    if config["delivery"].get("active"):
        channel = str(config["delivery"].get("channel", ""))
        if "smtp" not in channel and "issue" not in channel:
            issues.append(f"delivery.channel must contain 'smtp' and/or "
                          f"'issue' (got {channel!r})")
    return issues


# ------------------------------------------------------------------- demo
def demo_articles() -> list[dict]:
    """Offline sample set, matching the keywords shipped in the template."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return [
        {"id": "doi:10.0000/demo1",
         "title": "Garnet solid electrolyte with record ionic conductivity for "
                  "all-solid-state lithium batteries",
         "abstract": "We report a garnet-type solid electrolyte processed by cold "
                     "sintering. The material reaches an ionic conductivity of 1.2 "
                     "mS/cm at room temperature. Impedance spectroscopy shows that "
                     "grain boundary resistance dominates below 300 K, and cycling "
                     "against lithium metal is stable over 500 hours.",
         "authors": ["A. Example", "B. Demo"], "date": yesterday,
         "journal": "Nature Energy", "doi": "10.0000/demo1",
         "url": "https://example.org/demo1", "source": "openalex",
         "type": "article"},
        {"id": "arxiv:0000.00001",
         "title": "Dendrite suppression in sulfide electrolytes probed by "
                  "operando X-ray tomography",
         "abstract": "Lithium dendrite growth is imaged in situ during cycling. "
                     "We show that an interlayer reduces the critical current "
                     "density threshold by a factor of three. Solid electrolyte "
                     "interphase formation is quantified by XPS.",
         "authors": ["C. Test"], "date": yesterday, "journal": "arXiv", "doi": "",
         "url": "https://example.org/demo2", "source": "arxiv",
         "type": "preprint"},
        {"id": "doi:10.0000/demo3",
         "title": "Photocatalytic dye degradation over doped titania powders",
         "abstract": "Photocatalysis of organic dye degradation is studied under "
                     "visible light using doped titania nanoparticles.",
         "authors": ["D. Offtopic"], "date": yesterday,
         "journal": "Journal of Catalysis", "doi": "10.0000/demo3",
         "url": "https://example.org/demo3", "source": "crossref",
         "type": "article"},
        {"id": "doi:10.0000/demo4",
         "title": "Cathode coating strategies for high-voltage layered oxides",
         "abstract": "A conformal coating deposited by atomic layer deposition "
                     "improves capacity retention to 92 percent after 200 cycles "
                     "at 4.6 V. We attribute the gain to suppressed transition "
                     "metal dissolution, confirmed by ICP-MS.",
         "authors": ["E. Example"], "date": yesterday,
         "journal": "Advanced Energy Materials", "doi": "10.0000/demo4",
         "url": "https://example.org/demo4", "source": "openalex",
         "type": "article"},
        {"id": "doi:10.0000/demo5",
         "title": "Machine learning screening of lithium conductors",
         "abstract": "A graph neural network is trained on 20000 compounds to "
                     "predict ionic conductivity. Five candidates are synthesized "
                     "and two exceed 0.5 mS/cm.",
         "authors": ["F. Example"], "date": yesterday,
         "journal": "npj Computational Materials", "doi": "10.0000/demo5",
         "url": "https://example.org/demo5", "source": "openalex",
         "type": "article"},
    ]


# ------------------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser(description="Skopio - daily literature monitoring")
    parser.add_argument("--version", action="version", version=f"Skopio {__version__}")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--profile", default=str(ROOT / "my-profile.yaml"),
                        help="profile file holding the keywords")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--no-email", action="store_true")
    parser.add_argument("--demo", action="store_true",
                        help="offline sample run, no network call")
    parser.add_argument("--check", action="store_true",
                        help="validate the profile and exit, collecting nothing")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    config_issues = check_config(config)
    if not config_issues and args.days is not None:
        config["window"]["days"] = args.days

    # 1. Profile --------------------------------------------------------
    try:
        prof = profile_mod.load(Path(args.profile))
    except FileNotFoundError as exc:
        print(f"[!] {exc}")
        return 1

    print(f"Skopio v{__version__}")
    print(f"Profile: {prof.name} <{prof.email or 'no address'}>")
    print(f"Rules  : {keywords.summarise(prof.rules)}")
    for issue in config_issues:
        print(f"  [!] config.yaml: {issue}")
    issues = profile_mod.check(prof)
    for issue in issues:
        print(f"  [!] {issue}")

    if args.check:
        print("\nProfile and configuration are valid."
              if not (issues or config_issues)
              else "\nCheck complete - see the warnings above.")
        return 1 if config_issues else 0

    # A broken config is not a warning: every section below is read without
    # a default, so the run would crash halfway through.
    if config_issues:
        print("\n[!] fix config.yaml before running.")
        return 1

    # 2. Collection -----------------------------------------------------
    if args.demo:
        articles = demo_articles()
        print(f"\n-> demo mode: {len(articles)} sample articles")
        active_sources = ["demo"]
    else:
        terms = prof.rules.query_terms()
        priority = list(dict.fromkeys(
            t for r in prof.rules.keywords if r.level == "critical"
            for t in r.query_terms()))
        print(f"\n{len(terms)} query terms ({len(priority)} priority)")
        # The key is a secret: the environment wins over config.yaml, which
        # is committed and must therefore stay empty.
        s2_key = (os.environ.get("S2_API_KEY", "").strip()
                  or str(config.get("keys", {}).get("semantic_scholar", "") or ""))
        articles = sources.collect(config, terms, priority, prof.email, s2_key)
        active_sources = [s for s, v in config["sources"].items() if v["active"]]

    # 3. Already reported ------------------------------------------------
    state = load_state()
    n_collected = len(articles)          # before the already-seen filter
    if config["window"]["skip_already_seen"] and not args.demo:
        before = len(articles)
        articles = [a for a in articles if a["id"] not in state["seen"]]
        print(f"-> {before - len(articles)} already reported, {len(articles)} new")

    # 4. Ranking ---------------------------------------------------------
    ranked = scoring.rank(articles, prof.rules, prof.options)
    minimum = float(prof.options.get("minimum_score", 3.0))
    kept = [a for a in ranked if a["score"] >= minimum]
    print(f"-> {len(kept)} above the minimum score ({minimum})")

    enriched = digest.enrich(kept, prof.rules, int(prof.volume.get("bullets", 3)))
    groups = report.split(enriched, prof)

    # 5. Report -----------------------------------------------------------
    stats = {
        "raw": n_collected,
        "new": len(articles),
        "days": config["window"]["days"],
        "sources": active_sources,
    }
    folder = ROOT / config["report"]["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    html_body = report.render_html(groups, prof, stats)
    markdown_body = report.render_markdown(groups, prof, stats)
    if "html" in config["report"]["formats"]:
        (folder / f"{today}.html").write_text(html_body, encoding="utf-8")
    if "md" in config["report"]["formats"]:
        (folder / f"{today}.md").write_text(markdown_body, encoding="utf-8")
    print(f"-> report written to {folder.name}/{today}.*")

    # 6. Delivery ---------------------------------------------------------
    # A delivery failure must never bring the run down: the report is already
    # written and the job still has to archive it.
    n_must_read = len(groups["must_read"])
    delivered = True
    if config["delivery"]["active"] and not args.no_email:
        if n_must_read or groups["relevant"] or config["delivery"]["send_when_empty"]:
            lead = groups["must_read"][0]["title"] if n_must_read else ""
            try:
                delivered = delivery.deliver(
                    config, prof, delivery.daily_subject(n_must_read, lead),
                    html_body, markdown_body)
            except Exception as exc:                   # noqa: BLE001
                print(f"  [delivery] unexpected error: {exc}")
                delivered = False
        else:
            print("  [delivery] nothing to report - not sending")

    # 7. Memory ------------------------------------------------------------
    # Articles are only marked as seen once delivered, otherwise a failed send
    # would make them vanish for good. A --no-email run is a preview: it must
    # leave the queue exactly as it found it, or the next real run would have
    # nothing left to send.
    if args.demo:
        pass
    elif args.no_email:
        print("  [state] --no-email: preview run, articles not marked")
    elif delivered:
        save_state(state, [a["id"] for a in articles if a.get("id")])
    else:
        print("  [state] delivery failed - articles not marked, "
              "they will come back on the next run")

    print(f"Done: {n_must_read} must read, {len(groups['relevant'])} relevant, "
          f"{len(groups['radar'])} on radar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
