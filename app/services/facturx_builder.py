from facturx.facturx import generate_from_binary
import logging

logger = logging.getLogger(__name__)


def build_facturx(pdf_bytes: bytes, xml_bytes: bytes) -> bytes:
    try:
        pdf_metadata = {
            "author": "Factur-X Engine",
            "keywords": "Factur-X, EN16931",
            "title": "Facture",
            "subject": "Facture electronique Factur-X",
        }
        result_pdf = generate_from_binary(
            pdf_bytes,
            xml_bytes,
            check_xsd=True,
            pdf_metadata=pdf_metadata,
        )
        logger.info("Factur-X généré avec succès")
        return result_pdf
    except Exception as e:
        logger.error(f"Erreur : {e}")
        raise
