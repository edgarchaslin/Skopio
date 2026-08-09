#!/usr/bin/env python3
"""
Prepare a new release.

    python tools/version.py               show the current version
    python tools/version.py patch         1.0.0 -> 1.0.1
    python tools/version.py minor         1.0.0 -> 1.1.0
    python tools/version.py major         1.0.0 -> 2.0.0
    python tools/version.py 2.4.2         explicit value

The tool updates skopio/__init__.py and turns the "[Unreleased]" section of
the CHANGELOG into a dated section for the new version.

It neither commits nor pushes: review first, then commit from your IDE. The
push is what triggers the GitHub release.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "skopio" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"

PATTERN = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')
HELP_COMMENT = "<!-- Record your changes here as you go. -->"


def current_version() -> str:
    found = PATTERN.search(INIT.read_text(encoding="utf-8"))
    if not found:
        raise SystemExit("__version__ not found in skopio/__init__.py")
    return found.group(1)


def bump(version: str, level: str) -> str:
    try:
        major, minor, patch = (int(x) for x in version.split("."))
    except ValueError:
        raise SystemExit(f"unreadable version: {version} (expected X.Y.Z)")
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write_version(new: str) -> None:
    text = INIT.read_text(encoding="utf-8")
    INIT.write_text(PATTERN.sub(f'__version__ = "{new}"', text), encoding="utf-8")


def roll_changelog(new: str) -> bool:
    """Turn [Unreleased] into a dated section and recreate an empty one."""
    if not CHANGELOG.exists():
        return False
    text = CHANGELOG.read_text(encoding="utf-8")
    header = "## [Unreleased]"
    start = text.find(header)
    if start == -1:
        return False

    # body = everything after the header up to the next level-2 heading
    after = start + len(header)
    following = text.find("\n## ", after)
    end = following if following != -1 else len(text)
    body = text[after:end]

    # strip help comments: they must not end up in the release notes
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()
    if not body:
        body = "- (no documented change)"

    replacement = (
        f"{header}\n\n{HELP_COMMENT}\n\n"
        f"## [{new}] - {date.today().isoformat()}\n\n{body}\n"
    )
    CHANGELOG.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a new Skopio release")
    parser.add_argument("target", nargs="?", default="",
                        help="major | minor | patch | X.Y.Z")
    args = parser.parse_args()

    current = current_version()
    if not args.target:
        print(current)
        return 0

    if args.target in ("major", "minor", "patch"):
        new = bump(current, args.target)
    elif re.fullmatch(r"\d+\.\d+\.\d+", args.target):
        new = args.target
    else:
        raise SystemExit("invalid target: major, minor, patch or X.Y.Z")

    write_version(new)
    rolled = roll_changelog(new)

    print(f"{current} -> {new}")
    print("  skopio/__init__.py updated")
    print("  CHANGELOG.md: [Unreleased] section rolled over" if rolled
          else "  CHANGELOG.md: no [Unreleased] section - complete it manually")
    print("\nReview CHANGELOG.md, then commit and push.")
    print("The GitHub release will be created automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
