"""Send a report by email with Resend. Nothing is stored; the UI rate-limits sends."""
import html
import os
import re

import resend


def to_html(md: str) -> str:
    """Tiny markdown -> HTML (headings, bullets, bold, italics, rules). Enough for our reports."""
    out, in_list = [], False
    for line in md.splitlines():
        s = html.escape(line.strip())
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
        if s.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{s[2:]}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if s.startswith("## "):
            out.append(f"<h3>{s[3:]}</h3>")
        elif s.startswith("# "):
            out.append(f"<h2>{s[2:]}</h2>")
        elif s == "---":
            out.append("<hr>")
        elif s:
            out.append(f"<p>{s}</p>")
    if in_list:
        out.append("</ul>")
    return "<div style='font-family:sans-serif;max-width:640px'>" + "\n".join(out) + "</div>"


def send_report(to: str, markdown_report: str, subject: str = "Your cycle report") -> str:
    """Send the report; returns the Resend message id. Raises on failure."""
    resend.api_key = os.environ["RESEND_API_KEY"]
    res = resend.Emails.send({"from": os.environ["EMAIL_FROM"], "to": [to], "subject": subject,
                              "html": to_html(markdown_report), "text": markdown_report})
    return res["id"]
