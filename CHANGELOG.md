# Changelog

All notable changes to Skopio are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the numbering follows [semantic versioning](https://semver.org/):

- **MAJOR** (`3.0.0`) — breaking change: you must edit your `my-profile.yaml`
  or `config.yaml` for Skopio to work again.
- **MINOR** (`2.1.0`) — new capability, backward compatible.
- **PATCH** (`2.0.1`) — bug fix, nothing to change on your side.

## [Unreleased]

<!-- Record your changes here as you go. -->

## [2.0.0] - 2026-08-09

### Changed
- Project renamed to **Skopio**. The Python package is now `skopio/`, the
  tools live in `tools/`, and the profile file is `my-profile.yaml`.
- All source code, comments, configuration keys and reports are in English.
- Environment variables renamed to the `SKOPIO_*` prefix
  (`SKOPIO_SMTP_HOST`, `SKOPIO_SMTP_PORT`, `SKOPIO_SMTP_USER`,
  `SKOPIO_SMTP_PASSWORD`, `SKOPIO_EMAIL_TO`).
- Configuration keys renamed: `window`, `sources`, `report`, `delivery`,
  and in the profile `name`, `email`, `keywords`, `thresholds`, `volume`,
  `weights`, `options`.
- Keyword levels renamed to `critical`, `important`, `useful`, `context`.
  The prefix symbols are unchanged.
- Report sections are now labelled Must read, Relevant and Radar.

### Migration from 1.x
- Rename `mon-profil.yaml` to `my-profile.yaml` and translate its keys.
- Recreate the GitHub secrets with the `SKOPIO_` prefix.
- Delete `state/seen.json` or rename its `vus` key to `seen`.

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
