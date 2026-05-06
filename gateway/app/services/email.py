"""
SMTP email helper.

Reads configuration from environment variables:
  SMTP_HOST       — required (if empty, send_email raises RuntimeError)
  SMTP_PORT       — default 587
  SMTP_USER       — optional (no auth attempted if missing)
  SMTP_PASSWORD   — optional
  SMTP_FROM       — required (sender address)
  SMTP_FROM_NAME  — default "AIcruit"

Uses Python stdlib only (smtplib, email.message). No new dependencies.

NOTE: Sending is currently disabled — `send_email` short-circuits and returns a
success response WITHOUT actually transmitting any email. The full SMTP code is
preserved below (commented out) for when delivery is re-enabled. Toggle by
flipping `EMAIL_SEND_DISABLED` (default True) or removing the early-return.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Iterable, List, Union

logger = logging.getLogger(__name__)

# Master switch — when True, send_email logs the intended message and returns
# {"sent": True, ...} without contacting any SMTP server.
EMAIL_SEND_DISABLED = os.getenv("EMAIL_SEND_DISABLED", "true").strip().lower() in ("1", "true", "yes", "on")


def _get_smtp_config() -> dict:
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": int(os.getenv("SMTP_PORT", "587") or "587"),
        "user": os.getenv("SMTP_USER", "").strip() or None,
        "password": os.getenv("SMTP_PASSWORD", "") or None,
        "from_addr": os.getenv("SMTP_FROM", "").strip(),
        "from_name": os.getenv("SMTP_FROM_NAME", "AIcruit").strip() or "AIcruit",
    }


def send_email(
    to: Union[str, Iterable[str]],
    subject: str,
    body: str,
    html: bool = False,
) -> dict:
    """
    Pretend to send an email — currently disabled.

    Behavior while EMAIL_SEND_DISABLED is True:
      - Validates recipients.
      - Logs subject + recipients + body preview.
      - Returns {"sent": True, "to": [...], "dry_run": True} WITHOUT transmitting.

    Returns: {"sent": True, "to": [<recipient>, ...], "dry_run": bool}
    """
    if isinstance(to, str):
        recipients: List[str] = [to]
    else:
        recipients = [r for r in to if r]

    if not recipients:
        raise ValueError("At least one recipient is required")

    if EMAIL_SEND_DISABLED:
        preview = (body or "").strip().replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:157] + "..."
        logger.info(
            "EMAIL DRY-RUN | to=%s | subject=%r | body_preview=%r",
            recipients,
            subject,
            preview,
        )
        return {"sent": True, "to": recipients, "dry_run": True}

    # ----------------------------------------------------------------------
    # Real SMTP delivery (currently unreachable while EMAIL_SEND_DISABLED is True).
    # ----------------------------------------------------------------------
    cfg = _get_smtp_config()
    if not cfg["host"]:
        raise RuntimeError("SMTP not configured")
    if not cfg["from_addr"]:
        raise RuntimeError("SMTP_FROM not configured")

    msg = EmailMessage()
    msg["Subject"] = subject or "(no subject)"
    msg["From"] = f'{cfg["from_name"]} <{cfg["from_addr"]}>'
    msg["To"] = ", ".join(recipients)

    if html:
        msg.set_content("This message contains HTML; please use an HTML-capable email client.")
        msg.add_alternative(body or "", subtype="html")
    else:
        msg.set_content(body or "")

    context = ssl.create_default_context()
    try:
        if cfg["port"] == 465:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=30) as smtp:
                if cfg["user"] and cfg["password"]:
                    smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
                smtp.ehlo()
                try:
                    smtp.starttls(context=context)
                    smtp.ehlo()
                except smtplib.SMTPException:
                    logger.warning("SMTP server does not support STARTTLS; sending plaintext")
                if cfg["user"] and cfg["password"]:
                    smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg)
    except Exception as exc:
        logger.error(f"SMTP send failed for {recipients}: {exc}")
        raise

    logger.info(f"Email sent to {recipients} | subject={subject!r}")
    return {"sent": True, "to": recipients, "dry_run": False}
