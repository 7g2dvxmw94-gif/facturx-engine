# app/services/pdf_generator.py
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from app.models.invoice import InvoiceData


def generate_pdf(invoice: InvoiceData) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()
    story = []

    # En-tête
    story.append(Paragraph(f"<b>FACTURE N° {invoice.invoice_number}</b>",
                           ParagraphStyle("title", fontSize=18, spaceAfter=6)))
    story.append(Paragraph(f"Date d'émission : {invoice.issue_date}", styles["Normal"]))
    if invoice.due_date:
        story.append(Paragraph(f"Date d'échéance : {invoice.due_date}", styles["Normal"]))
    story.append(Spacer(1, 0.5*cm))

    # Vendeur / Acheteur
    parties_data = [
        ["VENDEUR", "ACHETEUR"],
        [invoice.seller.name, invoice.buyer.name],
        [invoice.seller.address.street, invoice.buyer.address.street],
        [f"{invoice.seller.address.postal_code} {invoice.seller.address.city}",
         f"{invoice.buyer.address.postal_code} {invoice.buyer.address.city}"],
        [f"SIRET : {invoice.seller.siret}", f"SIRET : {invoice.buyer.siret}"],
        [f"TVA : {invoice.seller.vat_number}", f"TVA : {invoice.buyer.vat_number}"],
    ]
    parties_table = Table(parties_data, colWidths=[8.5*cm, 8.5*cm])
    parties_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 10),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("PADDING",    (0, 0), (-1, -1), 6),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 0.8*cm))

    # Lignes de facture
    lines_data = [["#", "Description", "Qté", "Unité", "PU HT", "TVA %", "Total HT"]]
    for line in invoice.lines:
        lines_data.append([
            line.id,
            line.description,
            str(line.quantity),
            line.unit,
            f"{line.unit_price:.2f} €",
            f"{line.vat_rate:.0f}%",
            f"{line.line_total:.2f} €",
        ])

    lines_table = Table(
        lines_data,
        colWidths=[0.7*cm, 6*cm, 1.5*cm, 1.5*cm, 2*cm, 1.5*cm, 2.5*cm]
    )
    lines_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3498db")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ALIGN",      (2, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
        ("PADDING",    (0, 0), (-1, -1), 5),
    ]))
    story.append(lines_table)
    story.append(Spacer(1, 0.5*cm))

    # Totaux
    totals_data = [
        ["Total HT :",  f"{invoice.total_ht:.2f} €"],
        ["Total TVA :", f"{invoice.total_vat:.2f} €"],
        ["Total TTC :", f"{invoice.total_ttc:.2f} €"],
    ]
    totals_table = Table(totals_data, colWidths=[13*cm, 4*cm], hAlign="RIGHT")
    totals_table.setStyle(TableStyle([
        ("ALIGN",      (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME",   (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 2), (-1, 2), 11),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",  (0, 2), (-1, 2), colors.white),
        ("LINEABOVE",  (0, 2), (-1, 2), 1, colors.black),
        ("PADDING",    (0, 0), (-1, -1), 5),
    ]))
    story.append(totals_table)

    # Pied de page
    story.append(Spacer(1, 1*cm))
    if invoice.payment_terms:
        story.append(Paragraph(f"<b>Conditions de paiement :</b> {invoice.payment_terms}",
                               styles["Normal"]))
    if invoice.bank_iban:
        story.append(Paragraph(f"<b>IBAN :</b> {invoice.bank_iban}", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()
