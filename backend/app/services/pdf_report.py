"""
Report Engine, the PDF half (architecture doc component 12 — the text/
JSON/CSV forms are already built client-side in the frontend; this is
the one format that genuinely needs to be generated server-side).

Two entry points:
  build_wallet_report()  — a fresh report straight from a live/cached
                            examination, for exporting before a case
                            is even filed.
  build_case_report()    — rebuilt from a filed case's frozen snapshot,
                            so the PDF always matches what was on record
                            at filing time even if the VASP directory
                            or scoring logic has since changed.

Both funnel into _render(), which lays out the same "Report of
Examination (Form CS-2)" structure the frontend's text export already
uses, so the PDF, the on-screen report, and the case register all
describe the case the same way.
"""
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

NAVY = colors.HexColor("#003366")
INK = colors.HexColor("#1A1D21")
INK2 = colors.HexColor("#5A616B")
RULE = colors.HexColor("#C9CDD4")
RED = colors.HexColor("#C1272D")
AMBER = colors.HexColor("#B06B00")
GREEN = colors.HexColor("#1F7A1F")

_styles = getSampleStyleSheet()
_STYLE_TITLE = ParagraphStyle("cs_title", parent=_styles["Normal"], fontName="Helvetica-Bold",
                               fontSize=13, textColor=NAVY, spaceAfter=2)
_STYLE_SUB = ParagraphStyle("cs_sub", parent=_styles["Normal"], fontSize=9,
                             textColor=INK2, spaceAfter=10)
_STYLE_H2 = ParagraphStyle("cs_h2", parent=_styles["Normal"], fontName="Helvetica-Bold",
                            fontSize=11, textColor=NAVY, spaceBefore=14, spaceAfter=6)
_STYLE_BODY = ParagraphStyle("cs_body", parent=_styles["Normal"], fontSize=9.5,
                              textColor=INK, leading=13)
_STYLE_MUTED = ParagraphStyle("cs_muted", parent=_styles["Normal"], fontSize=8.5,
                               textColor=INK2, leading=12)
_STYLE_EV_TITLE = ParagraphStyle("cs_ev_t", parent=_styles["Normal"], fontName="Helvetica-Bold",
                                  fontSize=9.5, textColor=INK, leading=13)
_STYLE_EV_DETAIL = ParagraphStyle("cs_ev_d", parent=_styles["Normal"], fontSize=9,
                                   textColor=INK2, leading=12, spaceAfter=6)


_RISK_HEX = {"HIGH": "#C1272D", "MEDIUM": "#B06B00", "LOW": "#1F7A1F"}


def _particulars_table(address, chain, balance, first_seen, tx_count, candidate_count):
    rows = [
        ["Address", address, "Network", chain],
        ["Balance held", balance, "Transactions", str(tx_count)],
        ["First activity", first_seen, "Candidates found", str(candidate_count)],
    ]
    t = Table(rows, colWidths=[32 * mm, 62 * mm, 32 * mm, 44 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
        ("TEXTCOLOR", (2, 0), (2, -1), NAVY),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F3F4F6")),
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _candidates_table(candidates):
    header = ["#", "Service provider", "Nature", "Evidence score"]
    rows = [header]
    for i, c in enumerate(candidates, 1):
        rows.append([str(i), c["vasp_name"], c["vasp_type"], f"{c['score']}%"])
    t = Table(rows, colWidths=[10 * mm, 55 * mm, 55 * mm, 30 * mm])
    style = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FA")]),
    ]
    if len(rows) > 1:
        style.append(("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F0F4FB")))
        style.append(("FONTNAME", (1, 1), (1, 1), "Helvetica-Bold"))
    t = Table(rows, colWidths=[10 * mm, 55 * mm, 55 * mm, 30 * mm])
    t.setStyle(TableStyle(style))
    return t


def _risk_table(factors):
    rows = [["Indicator", "Points"]] + [[f["name"], f"+{f['points']}"] for f in factors]
    t = Table(rows, colWidths=[130 * mm, 20 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _render(*, case_number, officer, designation, address, chain, balance, first_seen,
            tx_count, candidates, risk_score, risk_level, risk_remark, risk_factors) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
        title=f"ChainScope Report — {address}",
    )
    story = []

    story.append(Paragraph("GOVERNMENT OF INDIA &middot; MINISTRY OF HOME AFFAIRS", _STYLE_SUB))
    story.append(Paragraph("INDIAN CYBERCRIME COORDINATION CENTRE (I4C)", _STYLE_SUB))
    story.append(Paragraph(
        f"CHAINSCOPE &mdash; REPORT OF EXAMINATION{' (' + case_number + ')' if case_number else ''} &middot; FORM CS-2",
        _STYLE_TITLE))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))
    story.append(Paragraph(
        f"Issued on: {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Officer: {officer} &nbsp;&nbsp;|&nbsp;&nbsp; Designation: {designation}",
        _STYLE_MUTED))

    story.append(Paragraph("1. Particulars of the Address", _STYLE_H2))
    story.append(_particulars_table(address, chain, balance, first_seen, tx_count, len(candidates)))

    story.append(Paragraph("2. Finding", _STYLE_H2))
    top = candidates[0] if candidates else None
    if top:
        story.append(Paragraph(
            f"The address is most probably associated with <b>{top['vasp_name']}</b>, "
            f"a {top['vasp_type'].lower()}, at a confidence of <b>{top['score']}%</b>.",
            _STYLE_BODY))
        story.append(Spacer(1, 6))
        story.append(_candidates_table(candidates))
    else:
        story.append(Paragraph(
            "No interaction with any cluster on record was found. Attribution could not "
            "be established on the available material.", _STYLE_BODY))

    if top:
        story.append(Paragraph("3. Grounds for the Finding", _STYLE_H2))
        items = []
        for e in top["evidence"]:
            items.append(ListItem(
                Paragraph(f"<b>{e['title']}</b><br/><font color='#5A616B'>{e['detail']}</font>",
                          _STYLE_EV_DETAIL),
                leftIndent=0,
            ))
        story.append(ListFlowable(items, bulletType="a", leftIndent=14, bulletFontSize=9))

    section_no = 4 if top else 3
    story.append(Paragraph(f"{section_no}. Risk Grading", _STYLE_H2))
    rc_hex = _RISK_HEX.get(risk_level, "#1A1D21")
    story.append(Paragraph(
        f"Score: <b>{risk_score} / 100</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Grading: <font color='{rc_hex}'><b>{risk_level}</b></font>",
        _STYLE_BODY))
    story.append(Paragraph(risk_remark, _STYLE_BODY))
    story.append(Spacer(1, 6))
    story.append(_risk_table(risk_factors))

    story.append(Paragraph(f"{section_no + 1}. Caveat", _STYLE_H2))
    story.append(Paragraph(
        "Attribution is probabilistic and rests upon the grounds set out above. A cluster "
        "match indicates likely association and not established ownership. This report is "
        "to be read alongside, and not in place of, the usual investigative procedure.",
        _STYLE_BODY))

    story.append(Spacer(1, 26))
    story.append(HRFlowable(width="45%", thickness=0.75, color=RULE))
    story.append(Paragraph("Signature of the Examining Officer", _STYLE_MUTED))

    doc.build(story)
    return buf.getvalue()


def build_wallet_report(*, officer: str, designation: str, wallet, candidates: list,
                         risk_score: int, risk_level: str, risk_remark: str,
                         risk_factors: list) -> bytes:
    """candidates: list of Candidate dataclasses from services/attribution.py."""
    cand_dicts = [
        {"vasp_name": c.vasp.name, "vasp_type": c.vasp.vasp_type, "score": c.score,
         "evidence": c.evidence}
        for c in candidates
    ]
    return _render(
        case_number=None, officer=officer, designation=designation,
        address=wallet.address, chain=wallet.chain, balance=wallet.balance_display,
        first_seen=wallet.first_seen, tx_count=wallet.tx_count,
        candidates=cand_dicts, risk_score=risk_score, risk_level=risk_level,
        risk_remark=risk_remark, risk_factors=risk_factors,
    )


def build_case_report(*, officer: str, designation: str, case) -> bytes:
    """Rebuilt purely from the case's frozen snapshot — matches what was on record at filing time."""
    snap = case.snapshot or {}
    return _render(
        case_number=case.case_number, officer=officer, designation=designation,
        address=case.wallet_address, chain=case.chain,
        balance=snap.get("balance_display", "unknown"),
        first_seen=snap.get("first_seen", "unknown"),
        tx_count=snap.get("tx_count", 0),
        candidates=snap.get("candidates", []),
        risk_score=case.risk_score, risk_level=case.risk_level,
        risk_remark=snap.get("risk_remark", ""),
        risk_factors=snap.get("risk_factors", []),
    )
