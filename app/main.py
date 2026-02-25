# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
import logging

from app.models.invoice import InvoiceData
from app.services.xml_generator import generate_xml
from app.services.pdf_generator import generate_pdf
from app.services.facturx_builder import build_facturx
from app.services.xml_validator import validate_xml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Factur-X Engine",
    description="Génération de factures électroniques conformes EN16931",
    version="1.0.0"
)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/invoice/generate")
async def generate_invoice(invoice_data: InvoiceData):
    """
    Reçoit un JSON facture et retourne un fichier Factur-X (PDF/A-3).
    """
    logger.info(f"Génération facture : {invoice_data.invoice_number}")

    # Étape 1 : Génération XML
    xml_bytes = generate_xml(invoice_data)
    logger.info("XML généré")

    # Étape 2 : Validation XSD
    is_valid, errors = validate_xml(xml_bytes)
    if not is_valid and "ignorée" not in str(errors):
        raise HTTPException(
            status_code=422,
            detail={"message": "XML non conforme EN16931", "errors": errors}
        )

    # Étape 3 : Génération PDF
    pdf_bytes = generate_pdf(invoice_data)
    logger.info("PDF généré")

    # Étape 4 : Construction Factur-X final
    facturx_bytes = build_facturx(pdf_bytes, xml_bytes)
    logger.info("Factur-X construit")

    filename = f"facture_{invoice_data.invoice_number}.pdf"
    return Response(
        content=facturx_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/invoice/validate-xml")
async def validate_invoice_xml(invoice_data: InvoiceData):
    """Génère et valide le XML sans produire le PDF."""
    xml_bytes = generate_xml(invoice_data)
    is_valid, errors = validate_xml(xml_bytes)
    return {
        "valid": is_valid,
        "errors": errors,
        "xml_preview": xml_bytes.decode("utf-8")[:2000]
    }
