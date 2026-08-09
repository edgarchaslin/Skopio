"""
Report delivery. Two channels, selected in config.yaml.

1. SMTP (`channel: smtp`)
   The recipient comes from the `email` field of my-profile.yaml; the sending
   account comes from the environment variables below. No credential is ever
   stored in the code or in the YAML files.

       SKOPIO_SMTP_HOST      e.g. smtp.gmail.com
       SKOPIO_SMTP_PORT      e.g. 587
       SKOPIO_SMTP_USER      sending address
       SKOPIO_SMTP_PASSWORD  app password
       SKOPIO_EMAIL_TO       fallback recipient (the profile takes precedence)

2. GitHub issue (`channel: issue`)
   The report is published as an issue of the repository; GitHub then emails
   the notification to the account address. No credential to manage: the
   workflow GITHUB_TOKEN is enough. Useful when outbound SMTP is blocked by
   the institution.

       GITHUB_TOKEN          supplied automatically by Actions
       GITHUB_REPOSITORY     supplied automatically (owner/repo)

`channel: smtp+issue` enables both.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage

import requests


# ------------------------------------------------------------------- SMTP
def send_email(subject: str, html_body: str, text_body: str = "",
               recipient: str = "") -> bool:
    host = os.environ.get("SKOPIO_SMTP_HOST", "").strip()
    # A missing GitHub secret arrives as an empty string, not as a missing
    # variable: int("") used to crash. Fall back to 587 in that case.
    raw_port = os.environ.get("SKOPIO_SMTP_PORT", "").strip()
    port = int(raw_port) if raw_port.isdigit() else 587
    user = os.environ.get("SKOPIO_SMTP_USER", "").strip()
    password = os.environ.get("SKOPIO_SMTP_PASSWORD", "").strip()
    to = recipient.strip() or os.environ.get("SKOPIO_EMAIL_TO", "").strip()

    if not all([host, user, password, to]):
        print("  [email] incomplete SMTP variables - skipped")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = user
    message["To"] = to
    message.set_content(text_body or "Skopio report, HTML version attached.")
    message.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=60) as server:
                server.login(user, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=60) as server:
                server.starttls(context=context)
                server.login(user, password)
                server.send_message(message)
    except Exception as exc:                          # noqa: BLE001
        print(f"  [email] sending failed: {exc}")
        return False

    print(f"  [email] sent to {to}")
    return True


# ------------------------------------------------------------ GitHub issue
def publish_issue(subject: str, markdown_body: str, label: str = "skopio") -> bool:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()

    if not token or not repository:
        print("  [issue] GITHUB_TOKEN or GITHUB_REPOSITORY missing - skipped")
        return False

    # GitHub issues are capped at 65,536 characters.
    body = (markdown_body if len(markdown_body) < 60000
            else markdown_body[:60000] + "\n\n*(truncated)*")
    url = f"https://api.github.com/repos/{repository}/issues"
    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/vnd.github+json"}

    try:
        response = requests.post(url, headers=headers, timeout=30,
                                 json={"title": subject, "body": body,
                                       "labels": [label]})
        if response.status_code == 422:
            # label does not exist in the repository: publish without it
            response = requests.post(url, headers=headers, timeout=30,
                                     json={"title": subject, "body": body})
        response.raise_for_status()
    except Exception as exc:                          # noqa: BLE001
        print(f"  [issue] publishing failed: {exc}")
        return False

    print(f"  [issue] published: {response.json().get('html_url', '')}")
    return True


# ---------------------------------------------------------------- routing
def deliver(config: dict, profile, subject: str,
            html_body: str, markdown_body: str) -> bool:
    channel = str(config["delivery"].get("channel", "smtp"))
    ok = True
    if "smtp" in channel:
        ok = send_email(subject, html_body, markdown_body, profile.email) and ok
    if "issue" in channel:
        ok = publish_issue(subject, markdown_body, profile.slug) and ok
    return ok


def daily_subject(n_must_read: int, lead_title: str = "") -> str:
    day = date.today().strftime("%d/%m")
    if n_must_read == 0:
        return f"Skopio {day} - nothing critical"
    lead = f" - {lead_title[:60]}" if lead_title else ""
    return f"Skopio {day} - {n_must_read} to read{lead}"
