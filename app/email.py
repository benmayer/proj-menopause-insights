"""Send a report by email with Resend. Nothing is stored; the UI rate-limits sends.

The cycle chart is embedded as an inline (CID) attachment, never hosted: it is built from the
user's own data, so a public image URL would leak it.
"""
import base64
import html
import os
import re

import resend

CHART_CID = "cycle-chart"

# Email clients ignore <style> blocks and CSS classes, so every style is inline.
_FONT = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
_INK, _MUTED, _ACCENT = "#2c3e50", "#6b7785", "#8e44ad"


def _inline(text: str) -> str:
    """Escape, then apply **bold**, *italic* and keep [S1]-style citation tags subtle."""
    s = html.escape(text)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s


def _chart_block(cid: str) -> str:
    return (f"<p style='margin:20px 0'><img src='cid:{cid}' alt='Cycle length over time' width='600' "
            f"style='display:block;width:100%;max-width:600px;height:auto;border:0'>"
            f"<span style='display:block;font-size:12px;color:{_MUTED};margin-top:6px'>Green band: 21-35 days, "
            f"the typical range used by the NHS. Dots mark long, short and skipped cycles.</span></p>")


def _blocks(md: str) -> list[str]:
    """Markdown -> list of HTML blocks (headings, bullets, bold/italic, rules, disclaimer box)."""
    out: list[str] = []
    in_list = in_sources = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    size = lambda: "13px" if in_sources else "16px"  # noqa: E731
    color = lambda: _MUTED if in_sources else _INK  # noqa: E731

    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith(("- ", "* ")):
            if not in_list:
                out.append(f"<ul style='margin:8px 0 16px;padding-left:22px;color:{color()};"
                           f"font-size:{size()};line-height:1.6'>")
                in_list = True
            out.append(f"<li style='margin:4px 0'>{_inline(line[2:])}</li>")
            continue
        close_list()
        if not line:
            continue
        if m := re.match(r"(#{1,6})\s+(.*)", line):
            level, text = len(m.group(1)), _inline(m.group(2))
            if level == 1:
                out.append(f"<h1 style='font-size:26px;color:{_INK};margin:0 0 4px;font-weight:700'>{text}</h1>")
            elif level == 2:
                out.append(f"<h2 style='font-size:20px;color:{_ACCENT};margin:30px 0 8px;font-weight:600'>{text}</h2>")
            else:
                out.append(f"<h3 style='font-size:16px;color:{_INK};margin:22px 0 6px;font-weight:600'>{text}</h3>")
        elif line == "---":
            out.append("<hr style='border:0;border-top:1px solid #e3e7ea;margin:24px 0'>")
            in_sources = True
        elif re.fullmatch(r"\*\*[^*]+\*\*", line):  # a bold-only line is a sub-heading (e.g. "Worth acting on soon")
            out.append(f"<p style='margin:16px 0 4px;font-size:{size()};color:{color()}'>{_inline(line)}</p>")
        elif re.fullmatch(r"\*[^*]+\*", line) and "not medical advice" in line.lower():
            out.append(f"<div style='margin-top:12px;padding:12px 14px;background:#f4f1f8;border-left:3px solid "
                       f"{_ACCENT};border-radius:4px;font-size:13px;line-height:1.5;color:{_MUTED}'>"
                       f"{_inline(line)}</div>")
        else:
            out.append(f"<p style='margin:0 0 14px;font-size:{size()};line-height:1.6;color:{color()}'>"
                       f"{_inline(line)}</p>")
    close_list()
    return out


def to_html(md: str, chart_cid: str | None = None) -> str:
    """Report markdown -> a self-contained, email-safe HTML document (table layout, inline styles).

    If chart_cid is given, <img src="cid:..."> is placed after the "Your cycle" section; the caller
    must attach the PNG with the same content_id.
    """
    # Split into [title+intro, section, section, ...] and place the chart between sections.
    parts = re.split(r"(?m)^(?=##+ )", md)
    at = next((i for i, p in enumerate(parts) if re.match(r"##+ Your cycle", p)), 1)
    body: list[str] = []
    for i, part in enumerate(parts):
        body += _blocks(part)
        if chart_cid and len(parts) >= 3 and i == at:
            body.append(_chart_block(chart_cid))
    if chart_cid and len(parts) < 3:
        body.insert(min(1, len(body)), _chart_block(chart_cid))
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'></head>"
        f"<body style='margin:0;padding:0;background:#f2f4f6;font-family:{_FONT}'>"
        "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='background:#f2f4f6'><tr>"
        "<td align='center' style='padding:24px 12px'>"
        "<table role='presentation' width='640' cellpadding='0' cellspacing='0' "
        "style='width:100%;max-width:640px;background:#ffffff;border-radius:8px'><tr>"
        "<td style='padding:28px 32px'>" + "\n".join(body) + "</td></tr></table></td></tr></table></body></html>"
    )


def send_report(to: str, markdown_report: str, subject: str = "Your cycle report",
                chart_png: bytes | None = None) -> str:
    """Send the report (HTML + plain-text fallback); returns the Resend message id. Raises on failure."""
    resend.api_key = os.environ["RESEND_API_KEY"]
    params = {"from": os.environ["EMAIL_FROM"], "to": [to], "subject": subject,
              "html": to_html(markdown_report, CHART_CID if chart_png else None), "text": markdown_report}
    if chart_png:
        params["attachments"] = [{"content": base64.b64encode(chart_png).decode(), "filename": "cycle-chart.png",
                                  "content_type": "image/png", "content_id": CHART_CID}]
    return resend.Emails.send(params)["id"]
