# Skopio

Skopio queries arXiv, OpenAlex and Crossref every morning, ranks new papers
against your keywords, and emails you a report.

- **Free.** No paid API, no server. Runs on GitHub Actions within the free
  tier, with your machine switched off.
- **Personal.** One repository per person: your keywords, your address, your
  settings.
- **No AI.** Ranking is a weighted keyword score; the bullets are sentences
  taken verbatim from the authors' abstract.

---

## Contents

1. [What you receive](#1-what-you-receive)
2. [Installation](#2-installation)
3. [Writing your keywords](#3-writing-your-keywords)
4. [Finding keywords when you don't know where to start](#4-finding-keywords-when-you-dont-know-where-to-start)
5. [Tuning the ranking](#5-tuning-the-ranking)
6. [Command reference](#6-command-reference)
7. [Versioning and releases](#7-versioning-and-releases)
8. [Sharing Skopio with colleagues](#8-sharing-skopio-with-colleagues)
9. [Troubleshooting](#9-troubleshooting)
10. [How it works](#10-how-it-works)

---

## 1. What you receive

One email per working day, in three sections:

| Section | Content |
|---|---|
| **Must read** | Strong match. A handful of papers with 2–3 key sentences and a relevance score out of 100. |
| **Relevant** | Worth a look if time allows. Same format. |
| **Radar** | Weak signal. Titles only. |

A paper is never reported twice. A missed day is picked up automatically on
the next run.

---

## 2. Installation

Around 30 minutes. No programming knowledge required, but follow the steps in
order.

### 2.1 Prerequisites

| Item | Where |
|---|---|
| GitHub account | [github.com](https://github.com) — free |
| Git | [git-scm.com](https://git-scm.com) — check with `git --version` |
| Python 3.10 or later | [python.org](https://python.org) — check with `python --version` |
| A sending email account | see 2.5 — **your institutional address will not work** |

### 2.2 Get the project

If someone shared a **template repository** with you, click **Use this
template → Create a new repository**, name it `skopio`, tick **Private**, then
clone it:

```bash
git clone https://github.com/YOUR-ACCOUNT/skopio.git
cd skopio
```

Otherwise, download the files into a `skopio` folder with this exact layout:

```
skopio/
├── my-profile.yaml              ← YOUR keywords (the main file)
├── config.yaml                  technical settings
├── requirements.txt
├── README.md
├── CHANGELOG.md
├── .gitignore
├── .github/workflows/
│   ├── daily.yml                the daily schedule
│   └── release.yml              automatic release publishing
├── skopio/                      the program (do not edit)
│   ├── __init__.py
│   ├── keywords.py
│   ├── profile.py
│   ├── sources.py
│   ├── scoring.py
│   ├── digest.py
│   ├── report.py
│   ├── delivery.py
│   └── main.py
├── tools/
│   ├── suggest_keywords.py      helps you find keywords
│   └── version.py               prepares a new release
├── reports/                     reports accumulate here
└── state/                       memory of already-sent papers
```

> **On Windows.** File Explorer refuses to create a folder starting with a
> dot: type `.github.` with a trailing dot and it will fix it. Also enable
> "File name extensions" in the View tab, otherwise you will end up with
> `__init__.py.txt`.

### 2.3 Check it runs, offline

Open a terminal in the `skopio` folder:

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
python -m skopio.main --demo --no-email
```

You should see a summary ending with `Done:`. A file has appeared in
`reports/`: open it in a browser, that is the format you will receive. Nothing
was sent and no data was fetched.

If you get `No module named 'skopio'`, you are in the wrong folder: the
command runs from `skopio/`, the one containing `my-profile.yaml`.

### 2.4 Fill in your profile

Open `my-profile.yaml`. Replace `name`, `email`, and **the whole `keywords`
block** with your own terms — section 3 covers the syntax, section 4 how to
find them.

The address serves two purposes: receiving the report, and identifying you to
OpenAlex and Crossref, which grant a far larger quota to identified requests.

Then validate:

```bash
python -m skopio.main --check
```

Skopio re-reads your file and reports problems: profile still on the template,
too few keywords, no exclusions, missing address.

Open `config.yaml` too, to set `sources.arxiv.categories` for your field — the
full list is at [arxiv.org/category_taxonomy](https://arxiv.org/category_taxonomy).

Then run a real collection without sending anything:

```bash
python -m skopio.main --days 7 --no-email
```

Allow 2 to 4 minutes: arXiv requires a 3-second gap between requests. Open the
report and adjust your keywords. **As long as you pass `--no-email` you can
repeat this as often as you like**: nothing is sent, and papers are only
marked as seen after a successful delivery.

### 2.5 Choose a delivery channel

**Important.** Receiving reports at your institutional address is fine;
*sending* from it usually is not. Microsoft 365 has disabled basic SMTP
authentication, and internal relays are only reachable from the institution
network — which a GitHub runner is not on. So you need either an external
sending account or no SMTP at all.

**Option A — a Gmail account** (recommended, full formatting)

1. Create or use a Gmail account.
2. Enable two-step verification: *myaccount.google.com → Security*.
3. Create a 16-character **app password**. The ordinary account password will
   not work.
4. In `config.yaml`, leave `channel: "smtp"`.

**Option B — GitHub issues** (no password to manage)

Set `channel: "issue"` in `config.yaml`. The report is published as an issue
of your repository and GitHub emails the notification to your account address
— put your institutional address there. Plainer formatting, but nothing to
rotate, and GitHub notifications usually get through corporate spam filters
more reliably than an unknown Gmail sender.

### 2.6 Create the GitHub repository

If you started from a template, this is already done: skip to 2.7.

Otherwise, on github.com: **New repository** → name `skopio` → **Private** →
tick neither README nor .gitignore → Create. Then:

```bash
git init
git add .
git commit -m "Initial setup"
git branch -M main
git remote add origin https://github.com/YOUR-ACCOUNT/skopio.git
git push -u origin main
```

Check on GitHub that `.github/workflows/daily.yml` is present — it is the file
most often left behind, and without it nothing ever triggers.

### 2.7 Register your credentials

*Settings → Secrets and variables → Actions → New repository secret*.

With the `smtp` channel, create these five secrets:

| Name | Value |
|---|---|
| `SKOPIO_SMTP_HOST` | `smtp.gmail.com` |
| `SKOPIO_SMTP_PORT` | `587` |
| `SKOPIO_SMTP_USER` | the full sending Gmail address |
| `SKOPIO_SMTP_PASSWORD` | the app password, **with no spaces** |
| `SKOPIO_EMAIL_TO` | fallback recipient |

With the `issue` channel, no secret is needed.

Names are case-sensitive and must match exactly.

### 2.8 Allow the workflow to write

*Settings → Actions → General → Workflow permissions* → tick **Read and write
permissions** → Save.

Without this the report is delivered but never archived in your repository.

### 2.9 First run

**Actions** tab → **Skopio daily run** → **Run workflow**. Expand the logs,
check the email arrived and that a `Skopio report …` commit appears in the
history.

After that it is automatic: Monday to Friday, around 08:23 Paris time in
summer. To change the time, edit the `cron` line in `daily.yml` — note that
**it is expressed in UTC**.

---

## 3. Writing your keywords

Everything happens in `my-profile.yaml`. One term per line, prefixed by a
symbol stating its importance.

```yaml
keywords: |
  !!! solid electrolyte | solid-state electrolyte
  !!! ionic conductivity & lithium
  !!  dendrite suppression
  !   impedance spectroscopy
      machine learning
  -   photocatalysis
  ~   Marie Curie
  @   Nature Energy
```

### Prefixes

| Prefix | Meaning | Queries the databases? |
|---|---|---|
| `!!!` | **Critical** — must surface even alone | yes |
| `!!` | **Important** — counts heavily | yes |
| `!` | **Useful** — reinforces a paper found otherwise | no |
| *(none)* | **Context** — small bonus | no |
| `-` | **Exclusion** — drops the paper | — |
| `~` | Tracked author (First Last) | — |
| `@` | Preferred journal | — |

Only `!!!` and `!!` generate queries. The others merely rank papers already
collected, which is how Skopio stays precise without multiplying requests.

### The two operators

**`|` — variants of the same concept**, counted only once.

```yaml
!!! CO2 capture | carbon dioxide capture | CO₂ capture
```

A paper using all three forms does not count three times. This stops a
repetitive paper from crowding out one that touches five different topics.

**`&` — every term must be present.**

```yaml
!!! ionic conductivity & lithium
```

This is how you track a specific material without receiving everything that
uses the same word in another context. It is the most effective tool against
noise.

### The `^` modifier

Placed right after the prefix, it restricts matching to the **title**.

```yaml
!!^ nanoparticle
```

Useful for a common word name-dropped in dozens of abstracts by papers that
are not actually about it.

### What you do not need to write

Skopio already ignores accents, subscripts (`CO₂` = `CO2`), hyphens and
English plurals (`loss` matches `losses`). It also tolerates up to two
inserted words: `ionic conductivity` matches `ionic charge conductivities`.

**Write in English**: that is the language of the queried databases.

### How many lines?

Between 25 and 60. Below 15 the report is thin; above 100 it gets chatty. And
**write exclusions from the start** — they often matter as much as the
positive keywords.

---

## 4. Finding keywords when you don't know where to start

### Automatic, no AI

A tool drafts a starting point from your own publications, through OpenAlex:

```bash
python tools/suggest_keywords.py --orcid 0000-0002-1825-0097
```

It fetches your papers, extracts the topics OpenAlex assigned to them and the
phrases recurring most in your titles and abstracts, then proposes a weighting
based on frequency. It also lists your frequent coauthors and the journals you
publish in.

Without an ORCID:

```bash
python tools/suggest_keywords.py --doi 10.1038/xxxxx 10.1103/yyyyy
python tools/suggest_keywords.py --author "Marie Curie"
```

DOIs are the next most reliable route: give five to ten papers representative
of what you want to track — they need not be your own. A bare name exposes you
to namesakes.

To keep the output:

```bash
python tools/suggest_keywords.py --orcid 0000-... > draft.txt
```

**Review and prune the draft.** The tool cannot tell what interests you *today*
from what you published on ten years ago. Budget a quarter of an hour to drop
the off-topic entries, group variants with `|` and add your exclusions.

### Manual

Take the ten papers you would have wanted to receive this month. For each,
note the system studied, the phenomenon, the technique. Terms appearing in
more than half become `!!!`, those in a third become `!!`, the rest `!`.

Then add the terms that would make you **discard** a paper: that is your
exclusion list, and it makes the difference between a report you read and one
you stop opening.

---

## 5. Tuning the ranking

Everything here is optional; the defaults work.

### Section thresholds

```yaml
thresholds: auto
```

In `auto` mode the thresholds adapt daily to the actual volume: the top 15 %
go to "Must read", the next 45 % to "Relevant". A floor prevents noise from
being promoted on a thin day. This is the recommended setting because it
spares you from guessing a number before seeing the first report.

Once calibrated you can freeze them:

```yaml
thresholds:
  must_read: 18
  relevant: 9
```

Each paper shows its raw score in small print at the bottom of its card: that
is what tells you where to set the thresholds.

### Volume

```yaml
volume:
  must_read: 8
  relevant: 15
  radar: 25
  bullets: 3        # 2 makes the report noticeably denser
```

### Prefix scale

```yaml
weights:
  critical: 3.0
  important: 2.0
  useful: 1.0
  context: 0.5
```

Raising `critical` to 4.0 widens the gap between the core of your topic and
its periphery. Only worth touching after a week of observation.

### Fine tuning

```yaml
options:
  minimum_score: 3.0          # below this, the paper never appears
  author_bonus: 3.0
  journal_bonus: 2.0
  recency_bonus: 1.5          # advantage given to same-day papers
  exclusion_penalty: -4.0     # exclusion found in the abstract
  no_abstract_penalty: -2.0
  must_read_floor: 12.0       # auto mode only
  relevant_floor: 6.0
```

### How to calibrate

Watch the **Radar** section of your first reports. What surfaces there
wrongly points to a term to exclude; what is wrongly demoted points to a
weight to raise. Two or three iterations over a week are enough.

---

## 6. Command reference

```bash
python -m skopio.main --check              # validate the profile, collect nothing
python -m skopio.main --demo --no-email    # offline sample run
python -m skopio.main --days 7 --no-email  # real collection, no delivery
python -m skopio.main                      # full run, as GitHub does daily

python tools/suggest_keywords.py --orcid 0000-0002-1825-0097
python tools/version.py minor              # prepare the next release
```

| Option | Effect |
|---|---|
| `--check` | validate the profile and exit |
| `--demo` | built-in sample set, no network call |
| `--no-email` | build the report without delivering it |
| `--days N` | widen the search window |
| `--profile PATH` | use another profile file |
| `--config PATH` | use another configuration file |
| `--version` | print the version and exit |

---

## 7. Versioning and releases

Skopio follows [semantic versioning](https://semver.org/) and keeps a
[CHANGELOG](CHANGELOG.md). A GitHub release is created automatically whenever
a new version number is pushed.

### The full cycle

1. **Edit the code.** As you go, record what changed under `## [Unreleased]`
   in `CHANGELOG.md`. Three headings are enough: `### Added`, `### Changed`,
   `### Fixed`.

2. **When you want to publish:**

   ```bash
   python tools/version.py patch   # 2.0.0 -> 2.0.1  (bug fix)
   python tools/version.py minor   # 2.0.0 -> 2.1.0  (new capability)
   python tools/version.py major   # 2.0.0 -> 3.0.0  (breaking change)
   ```

   The tool updates `skopio/__init__.py` and turns the `[Unreleased]` section
   into a dated one. It commits nothing, so you can review first.

3. **Commit and push.**

4. **GitHub does the rest**: `release.yml` detects the new number, creates the
   `v2.1.0` tag and publishes a release using the matching CHANGELOG section
   as notes.

As long as `__version__` is unchanged you can push freely: no release is
created. The version number is what triggers everything.

### Choosing the right bump

| Bump | When | Example |
|---|---|---|
| **patch** `2.0.1` | bug fix, nothing to change for users | crash on an empty abstract |
| **minor** `2.1.0` | new capability, existing files still work | an extra source, a new optional setting |
| **major** `3.0.0` | users must edit `my-profile.yaml` or `config.yaml` | a renamed setting, a change in keyword syntax |

The question that decides it: does someone updating have to touch their files?
If yes, it is a major release.

### Working with the daily bot

The daily workflow pushes a commit every morning (reports and memory), so your
local clone will almost always be behind when you want to push.

Always update before pushing, in **rebase** mode. In PyCharm: *Settings →
Version Control → Git* → tick **Update method: Rebase**, then use `Ctrl+T`
before each push. Otherwise you accumulate pointless merge commits and will
eventually hit a conflict in `state/seen.json` — a generated file, never worth
merging by hand: keep the remote version.

`release.yml` ignores commits touching only `reports/` and `state/`, so the
bot never triggers a release.

### Risky changes

For a change that could break tomorrow's run, use a branch rather than working
directly on `main`:

```bash
git checkout -b test-new-source
```

Scheduled workflows only run from the default branch, so the daily job keeps
working from `main` while you experiment.

---

## 8. Sharing Skopio with colleagues

Everyone gets their own repository, keywords and credentials. Nobody
administers anyone else's settings.

To distribute, publish your repository as a **template**:

1. Reset `my-profile.yaml` to the shipped template, set `state/seen.json` back
   to `{"seen": {}}`, and clear `reports/`.
2. *Settings → General* → tick **Template repository**.
3. Send the link.

Each person then clicks **Use this template → Create a new repository**, ticks
**Private**, and follows this README from section 2.2.

> **Why a template rather than a fork?** GitHub disables scheduled workflows in
> forked repositories by default, so the daily run would never fire. A
> repository created from a template does not have that problem and is not
> linked to yours.

One thing worth sharing is the sending Gmail account: the same app password
can serve everyone, with each person setting their own `SKOPIO_EMAIL_TO`. That
removes the most awkward installation step for them.

---

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `No module named 'skopio'` | command run from the wrong folder |
| `my-profile.yaml not found` | file missing or renamed |
| No workflow in the Actions tab | `daily.yml` must be in `.github/workflows/`, not `.github/` |
| `403` on the archiving step | write permissions not enabled (§ 2.8) |
| `incomplete SMTP variables` | a secret is missing or misspelled |
| `535 Authentication failed` | ordinary Gmail password instead of an app password, or a revoked app password |
| Email not received, run green | check spam, and the `email` field of the profile |
| Empty report several days running | keywords too restrictive, or `minimum_score` too high |
| Too much noise | add exclusions, use `&`, raise `minimum_score` |
| Scheduled run did not fire | GitHub drops scheduled runs under load; a missed day is picked up the next run |
| `429` errors in the logs | OpenAlex rate limiting; Skopio retries on its own |

---

## 10. How it works

**Collection.** The `!!!` and `!!` terms are sent to arXiv (title and abstract
search), OpenAlex and Crossref over a multi-day window. Duplicates are merged
on DOI, then on normalised title; when a preprint and its published version
coexist, the published one is kept with a link to the preprint.

**Ranking.** A rule counts once, however many variants or occurrences it has;
a match in the title is worth double a match in the abstract. Author, journal
and recency bonuses are added, exclusion penalties subtracted.

**Bullets.** No language model: Skopio picks 2 to 3 sentences from the
original abstract, favouring those carrying a figure with a unit, result
phrasing (*we show*, *results in*) or a high keyword density. Background
phrasing is penalised. The sentences remain the authors' own, word for word.

**Score out of 100.** The raw score depends on how many keywords matched and
is not readable as such. It is mapped onto a relevance score anchored on the
thresholds: the "relevant" threshold is 50, the "must read" one 78, saturating
above.

**Memory.** `state/seen.json` records what has been sent; nothing is reported
twice. If delivery fails the articles are not marked, so they come back on the
next run rather than disappearing.

**Cost.** Zero. One run uses about 3 minutes of the free 2,000 monthly GitHub
Actions minutes, under 5 % of the quota for a full month.
