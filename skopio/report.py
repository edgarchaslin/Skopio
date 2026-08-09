"""
Report rendering.

Two outputs:
  - HTML: inline styles and table-based layout, so it looks the same in
          Outlook (Word rendering engine) and in a browser.
  - Markdown: archiving, grep, import into Obsidian or Zotero.

Displayed score: a RELEVANCE out of 100, anchored on the profile thresholds
(the "relevant" threshold maps to 50, the "must read" one to 78). It is
therefore comparable from one day to the next, unlike the raw score which
depends on how many keywords were matched. The raw score stays visible in
small print, for tuning.

Colour code, in order of increasing energy:
  must read = violet, relevant = teal, radar = slate.
"""

from __future__ import annotations

import html
from datetime import date

from skopio import __version__

# ---------------------------------------------------------------- palette
INK = "#101B2D"          # main text
MUTED = "#6B7C93"        # metadata
RULE = "#E3E9EF"         # separators
PAGE = "#EEF2F6"         # page background
CARD = "#FFFFFF"         # card background

LEVELS = {
    "must_read": {"colour": "#5B2A86", "light": "#F3EDF9", "label": "Must read"},
    "relevant":  {"colour": "#0E7C7B", "light": "#E9F5F5", "label": "Relevant"},
    "radar":     {"colour": "#64748B", "light": "#F1F4F7", "label": "Radar"},
}

SERIF = "Georgia, 'Iowan Old Style', 'Times New Roman', serif"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"

WIDTH = 660           # px — Outlook requires a fixed width


# -------------------------------------------------------------- relevance
def compute_thresholds(articles: list[dict], profile) -> tuple[float, float]:
    """
    Section thresholds. Two modes, chosen in the profile:

      thresholds: auto        -> daily quantiles (85th and 55th percentiles),
                                 with a floor so that a thin harvest does not
                                 promote noise.
      thresholds: {must_read: 18, relevant: 9}  -> fixed values.

    Auto is recommended: it adapts to the actual volume and spares you from
    guessing a number before seeing the first report.
    """
    setting = profile.thresholds
    if isinstance(setting, dict):
        return (float(setting.get("must_read", 18)),
                float(setting.get("relevant", 9)))

    scores = sorted((a.get("final_score", 0.0) for a in articles), reverse=True)
    if not scores:
        return 18.0, 9.0

    def percentile(p: float) -> float:
        rank = min(len(scores) - 1, int(len(scores) * (1 - p)))
        return scores[rank]

    floor_high = float(profile.options.get("must_read_floor", 12.0))
    floor_low = float(profile.options.get("relevant_floor", 6.0))
    high = max(percentile(0.85), floor_high)
    low = max(percentile(0.55), floor_low)
    if low >= high:
        low = high * 0.6
    return high, low


def relevance(score: float, high: float, low: float) -> int:
    """
    Raw score -> score out of 100, piecewise linear:
        0                   -> 0
        relevant threshold  -> 50
        must-read threshold -> 78
        2.2x must-read      -> 100 (saturation)
    Anchoring on the thresholds keeps the number readable for any profile.
    """
    s = max(0.0, float(score))
    if s <= low:
        return int(round(50.0 * s / low)) if low else 0
    if s <= high:
        return int(round(50.0 + 28.0 * (s - low) / max(high - low, 1e-6)))
    ceiling = 2.2 * high
    return int(round(min(100.0, 78.0 + 22.0 * (s - high) / max(ceiling - high, 1e-6))))


def split(articles: list[dict], profile) -> dict[str, list[dict]]:
    """Split into the three sections according to the profile thresholds."""
    high, low = compute_thresholds(articles, profile)
    v = profile.volume

    must_read = [a for a in articles if a.get("final_score", 0) >= high]
    relevant = [a for a in articles if low <= a.get("final_score", 0) < high]
    radar = [a for a in articles if a.get("final_score", 0) < low]

    groups = {
        "must_read": must_read[:int(v.get("must_read", 8))],
        "relevant": relevant[:int(v.get("relevant", 15))],
        "radar": radar[:int(v.get("radar", 25))],
    }
    for batch in groups.values():
        for article in batch:
            article["relevance"] = relevance(article.get("final_score", 0), high, low)
    return groups


# -------------------------------------------------------------- fragments
def _bar(score: int, colour: str, width: int = 100) -> str:
    """Table-based gauge: the only construct reliable in Outlook."""
    filled = max(3, min(100, int(score)))
    empty = 100 - filled
    empty_cell = (f'<td width="{empty}%" bgcolor="{RULE}" '
                  f'style="font-size:0;line-height:0;">&nbsp;</td>') if empty else ""
    return (
        f'<table role="presentation" width="{width}" cellpadding="0" cellspacing="0" '
        f'border="0" style="width:{width}px;border-collapse:collapse;height:6px;">'
        f'<tr style="height:6px;">'
        f'<td width="{filled}%" bgcolor="{colour}" style="font-size:0;line-height:0;">&nbsp;</td>'
        f'{empty_cell}</tr></table>'
    )


def _bullets(article: dict, colour: str) -> str:
    """Table-based bullets: <ul> margins are unmanageable in Outlook."""
    rows = ""
    for bullet in article.get("bullets", []):
        rows += (
            f'<tr>'
            f'<td width="14" valign="top" style="padding:0 8px 8px 0;color:{colour};'
            f'font-family:{SANS};font-size:14px;line-height:1.55;">&#9642;</td>'
            f'<td valign="top" style="padding:0 0 8px 0;font-family:{SANS};font-size:14px;'
            f'line-height:1.55;color:{INK};">{html.escape(bullet)}</td>'
            f'</tr>')
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            f'width="100%" style="width:100%;">{rows}</table>')


def _tags(article: dict, colour: str, light: str) -> str:
    return "".join(
        f'<span style="font-family:{MONO};font-size:10px;letter-spacing:.04em;'
        f'color:{colour};background:{light};padding:3px 7px;margin-right:5px;'
        f'white-space:nowrap;">{html.escape(t)}</span>'
        for t in article.get("tags", []))


def _card(article: dict, level: str, number: int) -> str:
    style = LEVELS[level]
    colour, light = style["colour"], style["light"]
    e = html.escape
    score = article.get("relevance", 50)

    authors = ", ".join(article.get("authors", [])[:3])
    if len(article.get("authors", [])) > 3:
        authors += " et al."
    journal = article.get("journal") or article.get("source", "")

    preprint = ""
    if article.get("preprint_url"):
        preprint = (f'<a href="{e(article["preprint_url"])}" style="color:{MUTED};'
                    f'text-decoration:underline;">arXiv preprint</a> &nbsp;&middot;&nbsp; ')

    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="width:100%;border-collapse:collapse;margin-bottom:14px;">
<tr>
  <td width="4" bgcolor="{colour}" style="font-size:0;line-height:0;width:4px;">&nbsp;</td>
  <td bgcolor="{CARD}" style="padding:18px 20px 18px 18px;border:1px solid {RULE};border-left:none;">

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td valign="top" style="font-family:{MONO};font-size:10px;letter-spacing:.1em;
          text-transform:uppercase;color:{MUTED};padding-bottom:6px;">
        {number:02d} &nbsp;&middot;&nbsp; {e(journal)} &nbsp;&middot;&nbsp; {e(article.get('date', ''))}
      </td>
      <td valign="top" align="right" width="86" style="padding-bottom:6px;">
        <span style="font-family:{MONO};font-size:23px;font-weight:700;color:{colour};
              line-height:1;">{score}</span><span style="font-family:{MONO};font-size:11px;
              color:{MUTED};"> /100</span>
      </td>
    </tr>
    <tr><td colspan="2" style="padding-bottom:12px;">{_bar(score, colour, WIDTH - 46)}</td></tr>
    <tr><td colspan="2">
      <a href="{e(article.get('url', '#'))}" style="font-family:{SERIF};font-size:17px;
         line-height:1.4;color:{INK};text-decoration:none;font-weight:700;">{e(article.get('title', ''))}</a>
      <div style="font-family:{SANS};font-size:12px;color:{MUTED};padding:6px 0 14px 0;">
        {e(authors)}
      </div>
    </td></tr>
    <tr><td colspan="2">{_bullets(article, colour)}</td></tr>
    <tr><td colspan="2" style="padding-top:10px;border-top:1px solid {RULE};">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="padding-top:8px;">{_tags(article, colour, light)}</td>
        <td align="right" style="padding-top:8px;font-family:{MONO};font-size:10px;color:{MUTED};">
          {preprint}raw {article.get('final_score', 0):.1f}
        </td>
      </tr></table>
    </td></tr>
    </table>

  </td>
</tr></table>"""


def _section_header(level: str, count: int, subtitle: str = "") -> str:
    style = LEVELS[level]
    sub = (f'<div style="font-family:{SANS};font-size:12px;color:{MUTED};'
           f'padding-top:7px;">{subtitle}</div>') if subtitle else ""
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="width:100%;margin:26px 0 12px 0;">
<tr><td>
  <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
    <td bgcolor="{style['colour']}" style="padding:5px 11px;font-family:{MONO};font-size:11px;
        font-weight:700;letter-spacing:.14em;color:#FFFFFF;text-transform:uppercase;">
      {style['label']}
    </td>
    <td bgcolor="{style['light']}" style="padding:5px 11px;font-family:{MONO};font-size:11px;
        font-weight:700;color:{style['colour']};">{count}</td>
  </tr></table>
  {sub}
</td></tr></table>"""


def _radar_row(article: dict) -> str:
    e = html.escape
    colour = LEVELS["radar"]["colour"]
    return f"""
<tr>
  <td width="34" valign="top" align="left" style="padding:9px 0;border-bottom:1px solid {RULE};
      font-family:{MONO};font-size:12px;font-weight:700;color:{colour};">
    {article.get('relevance', 0)}
  </td>
  <td valign="top" style="padding:9px 0;border-bottom:1px solid {RULE};">
    <a href="{e(article.get('url', '#'))}" style="font-family:{SANS};font-size:13px;line-height:1.45;
       color:{INK};text-decoration:none;">{e(article.get('title', ''))}</a>
    <span style="font-family:{MONO};font-size:10px;color:{MUTED};white-space:nowrap;">
      &nbsp;&mdash; {e(article.get('journal') or article.get('source', ''))}</span>
  </td>
</tr>"""


def _stat_tile(value, label: str, colour: str) -> str:
    return (f'<td width="25%" align="center" style="padding:12px 4px;">'
            f'<div style="font-family:{MONO};font-size:20px;font-weight:700;'
            f'color:{colour};line-height:1;">{value}</div>'
            f'<div style="font-family:{MONO};font-size:9px;letter-spacing:.1em;'
            f'text-transform:uppercase;color:{MUTED};padding-top:5px;">{label}</div></td>')


# ------------------------------------------------------------------- HTML
def render_html(groups: dict[str, list[dict]], profile, stats: dict) -> str:
    day = date.today().strftime("%d.%m.%Y")
    title = profile.report_title
    body = []

    for level, subtitle in (("must_read", "Strong match with your topics."),
                            ("relevant", "Worth a look if time allows.")):
        articles = groups[level]
        if not articles:
            continue
        body.append(_section_header(level, len(articles), subtitle))
        body.append("".join(_card(a, level, i + 1)
                            for i, a in enumerate(articles)))

    if groups["radar"]:
        body.append(_section_header("radar", len(groups["radar"]),
                                    "Weak signal: titles only, worth a glance."))
        body.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0" bgcolor="{CARD}" style="width:100%;border:1px solid {RULE};'
            f'border-collapse:collapse;">'
            f'<tr><td style="padding:4px 18px 10px 18px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            + "".join(_radar_row(a) for a in groups["radar"])
            + '</table></td></tr></table>')

    if not any(groups.values()):
        body.append(
            f'<table role="presentation" width="100%" bgcolor="{CARD}" cellpadding="0" '
            f'cellspacing="0" border="0" style="border:1px solid {RULE};"><tr>'
            f'<td style="padding:44px 24px;text-align:center;font-family:{SANS};'
            f'font-size:14px;color:{MUTED};">Nothing new within the scanned window.<br>'
            f'The sources answered fine &mdash; the stream is simply quiet.</td></tr></table>')

    tiles = (_stat_tile(stats["new"], "new", INK)
             + _stat_tile(len(groups["must_read"]), "must read",
                          LEVELS["must_read"]["colour"])
             + _stat_tile(len(groups["relevant"]), "relevant",
                          LEVELS["relevant"]["colour"])
             + _stat_tile(len(groups["radar"]), "radar", LEVELS["radar"]["colour"]))

    return f"""<!DOCTYPE html>
<html lang="en" xmlns:v="urn:schemas-microsoft-com:vml"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="x-apple-disable-message-reformatting">
<title>{html.escape(title)} &mdash; {day}</title>
<!--[if mso]><style>table,td,div,span{{font-family:Arial,sans-serif !important;}}</style><![endif]-->
</head>
<body style="margin:0;padding:0;background:{PAGE};-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="{PAGE}" style="width:100%;background:{PAGE};">
<tr><td align="center" style="padding:26px 10px 40px 10px;">

<table role="presentation" width="{WIDTH}" cellpadding="0" cellspacing="0" border="0"
       style="width:{WIDTH}px;max-width:100%;">

  <!-- banner -->
  <tr><td bgcolor="{INK}" style="padding:26px 24px 22px 24px;">
    <div style="font-family:{MONO};font-size:10px;letter-spacing:.22em;
         text-transform:uppercase;color:#8FA3BC;">Skopio &middot; {day}</div>
    <div style="font-family:{SERIF};font-size:25px;line-height:1.3;color:#FFFFFF;
         padding-top:10px;font-weight:700;">{html.escape(title)}</div>
  </td></tr>

  <!-- counters -->
  <tr><td bgcolor="{CARD}" style="border:1px solid {RULE};border-top:none;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="width:100%;"><tr>{tiles}</tr></table>
  </td></tr>

  <tr><td style="padding-top:4px;font-family:{MONO};font-size:10px;color:{MUTED};
       letter-spacing:.04em;">
    {stats['raw']} references collected over {stats['days']} days &middot;
    {', '.join(stats['sources'])}
  </td></tr>

  <tr><td>{''.join(body)}</td></tr>

  <tr><td style="padding-top:26px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td style="border-top:1px solid #CBD5E0;padding-top:14px;font-family:{MONO};
        font-size:10px;line-height:1.8;color:{MUTED};">
      Relevance out of 100: weighted keyword score, anchored on the thresholds
      of <span style="color:{INK};">{html.escape(profile.path.name)}</span>.<br>
      Bullets are sentences taken verbatim from the authors' abstract, never rephrased.<br>
      <span style="color:#9AA8B8;">Skopio v{__version__}</span>
    </td></tr></table>
  </td></tr>

</table></td></tr></table></body></html>"""


# --------------------------------------------------------------- Markdown
def render_markdown(groups: dict[str, list[dict]], profile, stats: dict) -> str:
    day = date.today().isoformat()
    lines = [f"# {profile.report_title}", "",
             f"*Skopio v{__version__}*", "",
             f"**{day}** — {stats['raw']} references collected, "
             f"{stats['new']} new over {stats['days']} days.", "",
             f"`{len(groups['must_read'])} must read` · "
             f"`{len(groups['relevant'])} relevant` · "
             f"`{len(groups['radar'])} radar`", ""]

    for level in ("must_read", "relevant"):
        articles = groups[level]
        if not articles:
            continue
        lines += [f"## {LEVELS[level]['label']} ({len(articles)})", ""]
        for i, article in enumerate(articles, 1):
            authors = ", ".join(article.get("authors", [])[:3])
            if len(article.get("authors", [])) > 3:
                authors += " et al."
            lines += [f"### {i}. {article.get('relevance', 0)}/100 — "
                      f"[{article['title']}]({article.get('url', '')})",
                      f"*{article.get('journal', '')} — {article.get('date', '')} — "
                      f"raw score {article.get('final_score', 0):.1f}*", "",
                      authors, ""]
            lines += [f"- {b}" for b in article.get("bullets", [])]
            if article.get("tags"):
                lines += ["", "`" + "` `".join(article["tags"]) + "`"]
            lines += ["", "---", ""]

    if groups["radar"]:
        lines += [f"## Radar ({len(groups['radar'])})", "",
                  "| Score | Article | Source |", "|---:|---|---|"]
        for article in groups["radar"]:
            safe_title = article["title"].replace("|", "\\|")
            lines.append(f"| {article.get('relevance', 0)} | "
                         f"[{safe_title}]({article.get('url', '')}) "
                         f"| {article.get('journal') or article.get('source', '')} |")
        lines.append("")

    return "\n".join(lines)
