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

import json
import time

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)
        return json.dumps(log_data, ensure_ascii=False)

# Supprime les handlers existants et applique le notre
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
for h in root_logger.handlers[:]:
    root_logger.removeHandler(h)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
root_logger.addHandler(handler)
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


import json as json_module

def _load_api_keys() -> dict:
    clients_json = os.getenv("CLIENTS", "{}")
    try:
        return json_module.loads(clients_json)
    except Exception:
        api_key = os.getenv("API_KEY", "dev-secret-key")
        return {"default": api_key}


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    clients = _load_api_keys()
    for client_name, client_key in clients.items():
        if api_key == client_key:
            return client_name
    raise HTTPException(
        status_code=403,
        detail={"error": "Clé API invalide ou manquante"}
    )


# Préfixe v1 pour tous les endpoints
from fastapi import APIRouter
v1 = APIRouter(prefix="/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@v1.post("/invoice/generate")
async def generate_invoice(invoice_data: InvoiceData, api_key: str = Security(verify_api_key)):
    try:
        start = time.time()
        logger.info("Génération facture", extra={"extra": {"client": api_key, "invoice_number": invoice_data.invoice_number, "seller": invoice_data.seller.name, "buyer": invoice_data.buyer.name, "total_ttc": str(invoice_data.total_ttc)}})

        xml_bytes = generate_xml(invoice_data)
        pdf_bytes = generate_pdf(invoice_data)
        facturx_bytes = build_facturx(pdf_bytes, xml_bytes)

        filename = f"facture_{invoice_data.invoice_number}.pdf"
        filepath = STORAGE_DIR / filename
        with open(filepath, "wb") as f:
            f.write(facturx_bytes)
        duration = round((time.time() - start) * 1000)
        logger.info("Facture générée", extra={"extra": {"invoice_number": invoice_data.invoice_number, "filename": filename, "duration_ms": duration}})

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


@v1.post("/invoice/dry-run")
async def dry_run_invoice(invoice_data: InvoiceData, api_key: str = Security(verify_api_key)):
    """Valide une facture sans générer le PDF. Retourne les erreurs et warnings EN16931."""
    try:
        start = time.time()
        warnings = []
        errors = []

        # Validation des données métier
        if not invoice_data.bank_iban:
            warnings.append("IBAN manquant - recommandé pour paiement virement")
        if not invoice_data.due_date:
            warnings.append("Date échéance manquante - recommandée EN16931")
        if not invoice_data.payment_terms:
            warnings.append("Conditions de paiement manquantes - recommandées")
        for line in invoice_data.lines:
            if line.vat_rate not in [0, 5.5, 10, 20]:
                warnings.append(f"Taux TVA inhabituels sur ligne {line.id} : {line.vat_rate}%")
            if line.quantity <= 0:
                errors.append(f"Quantité invalide sur ligne {line.id} : doit être > 0")
            if line.unit_price < 0:
                errors.append(f"Prix unitaire négatif sur ligne {line.id}")

        # Génération XML et validation XSD
        xml_bytes = generate_xml(invoice_data)

        duration = round((time.time() - start) * 1000)
        logger.info("Dry run effectué", extra={"extra": {
            "invoice_number": invoice_data.invoice_number,
            "warnings": len(warnings),
            "errors": len(errors),
            "duration_ms": duration
        }})

        return {
            "valid": len(errors) == 0,
            "invoice_number": invoice_data.invoice_number,
            "total_ht": str(invoice_data.total_ht),
            "total_vat": str(invoice_data.total_vat),
            "total_ttc": str(invoice_data.total_ttc),
            "errors": errors,
            "warnings": warnings,
            "duration_ms": duration,
            "xml_preview": xml_bytes.decode("utf-8")[:1000]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "Erreur dry run", "message": str(e)})


# Enregistrement du router v1
app.include_router(v1)
