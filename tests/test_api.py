import pytest
from fastapi.testclient import TestClient
import os

# Configuration avant import de l'app
os.environ["CLIENTS"] = '{"test": "test-key-123"}'
os.environ["STORAGE_DIR"] = "/tmp/facturx-test"

from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key-123"}

INVOICE_JSON = {
    "invoice_number": "TEST-001",
    "issue_date": "2024-06-01",
    "due_date": "2024-07-01",
    "currency": "EUR",
    "seller": {
        "name": "ACME SAS",
        "siret": "12345678900017",
        "vat_number": "FR12345678900",
        "address": {"street": "12 rue de la Paix", "city": "Paris", "postal_code": "75001", "country": "FR"}
    },
    "buyer": {
        "name": "CLIENT SARL",
        "siret": "98765432100012",
        "vat_number": "FR98765432100",
        "address": {"street": "5 avenue Victor Hugo", "city": "Lyon", "postal_code": "69001", "country": "FR"}
    },
    "lines": [
        {"id": "1", "description": "Test", "quantity": 1, "unit": "EA", "unit_price": 100, "vat_rate": 20.0}
    ],
    "payment_terms": "Virement 30 jours",
    "bank_iban": "FR7630006000011234567890189"
}


def test_health():
    """Health check doit retourner 200."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_generate_invoice_ok():
    """Génération facture avec bonne clé doit retourner 200."""
    res = client.post("/v1/invoice/generate", json=INVOICE_JSON, headers=HEADERS)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"


def test_generate_invoice_no_key():
    """Sans clé API doit retourner 403."""
    res = client.post("/v1/invoice/generate", json=INVOICE_JSON)
    assert res.status_code == 403


def test_generate_invoice_wrong_key():
    """Mauvaise clé API doit retourner 403."""
    res = client.post("/v1/invoice/generate", json=INVOICE_JSON, headers={"X-API-Key": "fausse-cle"})
    assert res.status_code == 403


def test_generate_invoice_invalid_json():
    """JSON invalide doit retourner 422."""
    res = client.post("/v1/invoice/generate", json={}, headers=HEADERS)
    assert res.status_code == 422


def test_dry_run_ok():
    """Dry run avec facture complète doit retourner valid=True sans warnings."""
    res = client.post("/v1/invoice/dry-run", json=INVOICE_JSON, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] == True
    assert data["errors"] == []
    assert data["warnings"] == []


def test_dry_run_warnings():
    """Dry run sans IBAN doit retourner des warnings."""
    invoice = INVOICE_JSON.copy()
    del invoice["bank_iban"]
    del invoice["due_date"]
    res = client.post("/v1/invoice/dry-run", json=invoice, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data["warnings"]) > 0


def test_list_invoices():
    """Liste des factures doit retourner 200."""
    res = client.get("/v1/invoices", headers=HEADERS)
    assert res.status_code == 200
    assert "invoices" in res.json()


def test_download_not_found():
    """Téléchargement facture inexistante doit retourner 404."""
    res = client.get("/v1/invoices/inexistante.pdf", headers=HEADERS)
    assert res.status_code == 404
