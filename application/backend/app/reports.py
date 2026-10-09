"""Safe PDF assessment export from recorded server results, never browser-provided grades."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from .errors import DomainError


def assessment_pdf(snapshot: dict, learner_name: str) -> bytes:
    """Build a PDF from an authorized completed snapshot; raise if no result and escape all displayed text."""
    result = snapshot["result"]
    if not result:
        raise DomainError("report_not_ready", "Submit the assessment before downloading its report.", 409)
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=(8.27 * inch, 11.69 * inch), leftMargin=48, rightMargin=48)
    styles = getSampleStyleSheet()
    story = [Paragraph("FAULT FORGE / TRAINING REPORT", styles["Title"]), Spacer(1, 18)]
    for text in [snapshot["title"], f"Learner: {learner_name}", f"Difficulty: {snapshot['difficulty']}",
                 f"Session: {snapshot['id']}", "Synthetic educational simulation; not a practical qualification." if snapshot["synthetic"]
                 else "Simulation assessment; practical qualification requires supervised assessment."]:
        story.extend([Paragraph(escape(text), styles["BodyText"]), Spacer(1, 8)])
    rows = [["Criterion", "Recorded points"], ["Diagnosis", str(result["diagnosis_points"])],
            ["Evidence", str(result["evidence_points"])], ["Quiz", str(result["quiz_points"])],
            ["Reasoning", str(result.get("review_points", "Pending" if result["review_pending"] else "Not required"))],
            ["Total", str(result["score"]) if result["score"] is not None else f"Provisional {result['automatic_score']}/{result['automatic_max']}"]]
    table = Table(rows, colWidths=[3.2 * inch, 2.8 * inch])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9f3d1")),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 10)]))
    story.extend([Spacer(1, 15), table, Spacer(1, 20)])
    for label, text in [("Diagnostic feedback", result["explanation"]),
                        ("Instructor feedback", result.get("review_feedback", "No instructor review recorded.")),
                        ("Next exercise", result["next_step"]), ("Rubric", result["rubric_version"]),
                        ("Scenario SHA-256", result["scenario_hash"])]:
        story.extend([Paragraph(escape(label), styles["Heading3"]), Paragraph(escape(text), styles["BodyText"])])
    doc.build(story)
    return output.getvalue()
