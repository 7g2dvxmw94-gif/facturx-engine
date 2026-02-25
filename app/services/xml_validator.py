# app/services/xml_validator.py
from lxml import etree
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

XSD_PATH = Path(__file__).parent.parent / "schemas" / "CrossIndustryInvoice_100pD22B.xsd"


def validate_xml(xml_bytes: bytes) -> tuple[bool, list[str]]:
    """
    Valide le XML contre le schéma XSD EN16931.
    Retourne (True, []) si valide, (False, [erreurs]) si invalide.
    """
    if not XSD_PATH.exists():
        logger.warning(f"XSD non trouvé à {XSD_PATH} — validation ignorée")
        return True, ["XSD non disponible, validation ignorée"]

    try:
        with open(XSD_PATH, "rb") as f:
            schema_doc = etree.parse(f)
        schema = etree.XMLSchema(schema_doc)

        xml_doc = etree.fromstring(xml_bytes)
        is_valid = schema.validate(xml_doc)

        errors = [str(e) for e in schema.error_log]
        if errors:
            logger.error(f"Erreurs XSD : {errors}")
        return is_valid, errors

    except etree.XMLSyntaxError as e:
        return False, [f"XML malformé : {e}"]
    except Exception as e:
        return False, [f"Erreur validation : {e}"]
