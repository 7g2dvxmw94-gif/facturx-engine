from fastapi import FastAPI, HTTPException, Security
from fastapi.responses import Response, FileResponse
from fastapi.security import APIKeyHeader
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
import os
from pathlib import Path

from app.models.invoice import InvoiceData, CreditNoteData
from app.services.xml_generator import generate_xml, generate_credit_note_xml
from app.services.pdf_generator import generate_pdf
from app.services.facturx_builder import build_facturx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Factur-X Engine",
    description="Génération de factures électroniques conformes EN16931",
    version="1.0.0"
)

# Dossier de stockage
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "/app/storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Clé API
API_KEY = os.getenv("API_KEY", "dev-secret-key")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# Gestionnaire erreurs de validation JSON (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Données invalides",
            "detail": str(exc.errors())
        }
    )


def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail={"error": "Clé API invalide ou manquante"}
        )
    return api_key


# Préfixe v1 pour tous les endpoints
from fastapi import APIRouter
v1 = APIRouter(prefix="/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@v1.post("/invoice/generate")
async def generate_invoice(invoice_data: InvoiceData, api_key: str = Security(verify_api_key)):
    try:
        logger.info(f"Génération facture : {invoice_data.invoice_number}")

        xml_bytes = generate_xml(invoice_data)
        pdf_bytes = generate_pdf(invoice_data)
        facturx_bytes = build_facturx(pdf_bytes, xml_bytes)

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
    except ValueError as e:
        logger.error(f"Erreur validation : {e}")
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        logger.error(f"Erreur interne : {e}")
        raise HTTPException(status_code=500, detail={"error": "Erreur interne", "message": str(e)})


@v1.post("/credit-note/generate")
async def generate_credit_note(invoice_data: CreditNoteData, api_key: str = Security(verify_api_key)):
    try:
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
    except ValueError as e:
        logger.error(f"Erreur validation : {e}")
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        logger.error(f"Erreur interne : {e}")
        raise HTTPException(status_code=500, detail={"error": "Erreur interne", "message": str(e)})


@v1.get("/invoices")
async def list_invoices(api_key: str = Security(verify_api_key)):
    try:
        files = sorted(STORAGE_DIR.glob("*.pdf"), reverse=True)
        return {"count": len(files), "invoices": [f.name for f in files]}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "Erreur lecture stockage", "message": str(e)})


@v1.get("/invoices/{filename}")
async def download_invoice(filename: str, api_key: str = Security(verify_api_key)):
    try:
        filepath = STORAGE_DIR / filename
        if not filepath.exists():
            raise HTTPException(status_code=404, detail={"error": f"Facture {filename} non trouvée"})
        return FileResponse(filepath, media_type="application/pdf", filename=filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "Erreur téléchargement", "message": str(e)})


@v1.post("/invoice/validate-xml")
async def validate_invoice_xml(invoice_data: InvoiceData, api_key: str = Security(verify_api_key)):
    try:
        xml_bytes = generate_xml(invoice_data)
        return {
            "valid": True,
            "xml_preview": xml_bytes.decode("utf-8")[:2000]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "Erreur génération XML", "message": str(e)})


# Enregistrement du router v1
app.include_router(v1)
