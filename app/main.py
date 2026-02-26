from fastapi import FastAPI, HTTPException, Security
from fastapi.responses import Response, FileResponse
from fastapi.security import APIKeyHeader
import logging
import os
from pathlib import Path

from app.models.invoice import InvoiceData, CreditNoteData
from app.services.xml_generator import generate_xml
from app.services.pdf_generator import generate_pdf
from app.services.facturx_builder import build_facturx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Factur-X Engine",
    description="Génération de factures électroniques conformes EN16931",
    version="1.0.0"
)

# Dossier de stockage des factures
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "/app/storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Clé API
API_KEY = os.getenv("API_KEY", "dev-secret-key")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Clé API invalide")
    return api_key


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/invoice/generate")
async def generate_invoice(invoice_data: InvoiceData, api_key: str = Security(verify_api_key)):
    logger.info(f"Génération facture : {invoice_data.invoice_number}")

    xml_bytes = generate_xml(invoice_data)
    pdf_bytes = generate_pdf(invoice_data)
    facturx_bytes = build_facturx(pdf_bytes, xml_bytes)

    # Sauvegarde sur disque
    filename = f"facture_{invoice_data.invoice_number}.pdf"
    filepath = STORAGE_DIR / filename
    with open(filepath, "wb") as f:
        f.write(facturx_bytes)
    logger.info(f"Facture sauvegardée : {filepath}")

    return Response(
        content=facturx_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/invoices")
async def list_invoices(api_key: str = Security(verify_api_key)):
    """Liste toutes les factures stockées."""
    files = sorted(STORAGE_DIR.glob("*.pdf"), reverse=True)
    return {
        "count": len(files),
        "invoices": [f.name for f in files]
    }


@app.get("/invoices/{filename}")
async def download_invoice(filename: str, api_key: str = Security(verify_api_key)):
    """Télécharge une facture stockée."""
    filepath = STORAGE_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    return FileResponse(filepath, media_type="application/pdf", filename=filename)


@app.post("/credit-note/generate")
async def generate_credit_note(invoice_data: CreditNoteData, api_key: str = Security(verify_api_key)):
    """Génère un avoir (TypeCode 381) annulant une facture existante."""
    from app.models.invoice import CreditNoteData
    from app.services.xml_generator import generate_credit_note_xml

    logger.info(f"Génération avoir : {invoice_data.invoice_number}")

    xml_bytes = generate_credit_note_xml(invoice_data)
    pdf_bytes = generate_pdf(invoice_data)
    facturx_bytes = build_facturx(pdf_bytes, xml_bytes)

    filename = f"avoir_{invoice_data.invoice_number}.pdf"
    filepath = STORAGE_DIR / filename
    with open(filepath, "wb") as f:
        f.write(facturx_bytes)
    logger.info(f"Avoir sauvegardé : {filepath}")

    return Response(
        content=facturx_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/invoice/validate-xml")
async def validate_invoice_xml(invoice_data: InvoiceData, api_key: str = Security(verify_api_key)):
    xml_bytes = generate_xml(invoice_data)
    is_valid, errors = validate_xml(xml_bytes)
    return {
        "valid": is_valid,
        "errors": errors,
        "xml_preview": xml_bytes.decode("utf-8")[:2000]
    }
