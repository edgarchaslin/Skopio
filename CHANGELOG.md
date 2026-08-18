# Changelog

All notable changes to Skopio are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the numbering follows [semantic versioning](https://semver.org/):

- **MAJOR** (`2.0.0`) — breaking change: you must edit your `my-profile.yaml`
  or `config.yaml` for Skopio to work again.
- **MINOR** (`1.1.0`) — new capability, backward compatible.
- **PATCH** (`1.0.1`) — bug fix, nothing to change on your side.

## [Unreleased]

<!-- Record your changes here as you go. -->

## [1.0.1] - 2026-08-18

### Fixed
- The Semantic Scholar API key is now read from the `S2_API_KEY` environment
  variable, as the documentation always claimed. It was ignored until now, so
  the source ran on the anonymous quota even when the secret was set.
- Preprints and their published version are now merged again. An arXiv record
  carries no DOI and was filed under its title while the published version was
  filed under its DOI, so the same paper could be reported twice.
- The report footer counted the collected references after the already-seen
  filter: both counters showed the same number and understated the harvest.
- `--days 0` is no longer ignored.

### Changed
- The version number is declared once, in `skopio/__init__.py`, and the
  User-Agent sent to the databases derives from it.
- The daily workflow rebases before pushing the archive, so a commit landed
  in the meantime no longer fails the job after the report has been sent.

## [1.0.0] - 2026-08-07

### Added
- Daily collection from arXiv, OpenAlex and Crossref, with deduplication on
  DOI then normalised title, merging preprints with published versions.
- Compact keyword syntax with prefixes (`!!!`, `!!`, `!`, `-`, `~`, `@`),
  the `|` (equivalent variants) and `&` (conjunction) operators, and the
  `^` modifier (title only).
- Weighted scoring converted into a relevance score out of 100, anchored on
  the profile thresholds.
- Automatic section thresholds adapting to the daily volume.
- Local extraction of 2 to 3 key sentences from the abstract, no language
  model involved.
- Outlook-compatible HTML report (table layout, inline styles) plus Markdown.
- Delivery over SMTP or as a GitHub issue.
- Memory of already-sent articles, not updated when delivery fails.
- `suggest_keywords` tool drafting keywords from an ORCID, a DOI list or an
  author name, via OpenAlex.
- Scheduled execution through GitHub Actions, no machine to keep running.
