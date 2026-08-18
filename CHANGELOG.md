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

## [1.0.2] - 2026-08-18

### Fixed
- `--no-email` no longer consumes the queue: a preview run used to leave the
  next real run with nothing left to send.
- A malformed Crossref date no longer brings the whole run down.
- Irregular English plurals are matched (`battery`/`batteries`,
  `analysis`/`analyses`). Write keywords in the singular.
- A `state/seen.json` without a `seen` entry restarts cleanly instead of
  raising `KeyError`.
- Brackets in titles and parentheses in URLs no longer break the Markdown
  report.
- `--check` warns when a profile has no `!!!` keyword, which leaves Crossref
  and Semantic Scholar with nothing to query.

### Changed
- `config.yaml` is validated at startup: a broken section stops the run with
  an explicit message instead of an error halfway through.
- arXiv is queried over HTTPS through the shared HTTP helper, so it gets the
  identified User-Agent it asks for and the same retry policy as the others.
- Network errors are retried like HTTP 429 and 5xx.
- `must_read_floor` and `relevant_floor` are declared in the default options.

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
