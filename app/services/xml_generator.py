from lxml import etree
from decimal import Decimal, ROUND_HALF_UP
from app.models.invoice import InvoiceData
from collections import defaultdict

NAMESPACES = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

def _e(parent, tag, text=None, ns="ram", **attribs):
    elem = etree.SubElement(parent, f"{{{NAMESPACES[ns]}}}{tag}", **attribs)
    if text is not None:
        elem.text = str(text)
    return elem

def _fmt(value, decimals=2):
    q = Decimal("0." + "0" * decimals)
    return str(value.quantize(q, rounding=ROUND_HALF_UP))

def _add_date(parent, tag, date_str):
    container = etree.SubElement(parent, f"{{{NAMESPACES['ram']}}}{tag}")
    dts = etree.SubElement(container, f"{{{NAMESPACES['udt']}}}DateTimeString", format="102")
    dts.text = date_str.replace("-", "")
    return container

def generate_xml(invoice: InvoiceData) -> bytes:
    root = etree.Element(f"{{{NAMESPACES['rsm']}}}CrossIndustryInvoice", nsmap=NAMESPACES)

    ctx = _e(root, "ExchangedDocumentContext", ns="rsm")
    gm = _e(ctx, "GuidelineSpecifiedDocumentContextParameter")
    _e(gm, "ID", "urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended")

    doc = _e(root, "ExchangedDocument", ns="rsm")
    _e(doc, "ID", invoice.invoice_number)
    _e(doc, "TypeCode", "380")
    _add_date(doc, "IssueDateTime", invoice.issue_date)

    tx = _e(root, "SupplyChainTradeTransaction", ns="rsm")

    for line in invoice.lines:
        _build_line(tx, line, invoice.currency)

    agreement = _e(tx, "ApplicableHeaderTradeAgreement")
    _build_party(agreement, "SellerTradeParty", invoice.seller)
    _build_party(agreement, "BuyerTradeParty", invoice.buyer)

    _e(tx, "ApplicableHeaderTradeDelivery")

    settlement = _e(tx, "ApplicableHeaderTradeSettlement")
    _e(settlement, "InvoiceCurrencyCode", invoice.currency)

    if invoice.bank_iban:
        pm = _e(settlement, "SpecifiedTradeSettlementPaymentMeans")
        _e(pm, "TypeCode", "30")
        acc = _e(pm, "PayeePartyCreditorFinancialAccount")
        _e(acc, "IBANID", invoice.bank_iban)

    _build_vat_breakdown(settlement, invoice)
    _build_totals(settlement, invoice)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)

def _build_party(parent, tag, party):
    p = _e(parent, tag)
    _e(p, "Name", party.name)
    si = _e(p, "SpecifiedLegalOrganization")
    _e(si, "ID", party.siret, schemeID="0002")
    addr = _e(p, "PostalTradeAddress")
    _e(addr, "PostcodeCode", party.address.postal_code)
    _e(addr, "LineOne", party.address.street)
    _e(addr, "CityName", party.address.city)
    _e(addr, "CountryID", party.address.country)
    tax_reg = _e(p, "SpecifiedTaxRegistration")
    _e(tax_reg, "ID", party.vat_number, schemeID="VA")

def _build_line(parent, line, currency):
    li = _e(parent, "IncludedSupplyChainTradeLineItem")
    doc = _e(li, "AssociatedDocumentLineDocument")
    _e(doc, "LineID", line.id)
    product = _e(li, "SpecifiedTradeProduct")
    _e(product, "Name", line.description)
    agreement = _e(li, "SpecifiedLineTradeAgreement")
    gross = _e(agreement, "GrossPriceProductTradePrice")
    _e(gross, "ChargeAmount", _fmt(line.unit_price), currencyID=currency)
    net = _e(agreement, "NetPriceProductTradePrice")
    _e(net, "ChargeAmount", _fmt(line.unit_price), currencyID=currency)
    delivery = _e(li, "SpecifiedLineTradeDelivery")
    _e(delivery, "BilledQuantity", _fmt(line.quantity, decimals=4), unitCode=line.unit)
    settlement = _e(li, "SpecifiedLineTradeSettlement")
    tax = _e(settlement, "ApplicableTradeTax")
    _e(tax, "TypeCode", "VAT")
    _e(tax, "CategoryCode", "S")
    _e(tax, "RateApplicablePercent", _fmt(line.vat_rate))
    sum_elem = _e(settlement, "SpecifiedTradeSettlementLineMonetarySummation")
    _e(sum_elem, "LineTotalAmount", _fmt(line.line_total), currencyID=currency)

def _build_vat_breakdown(parent, invoice):
    vat_groups = defaultdict(lambda: {"base": Decimal("0"), "vat": Decimal("0")})
    for line in invoice.lines:
        key = str(line.vat_rate)
        vat_groups[key]["base"] += line.line_total
        vat_groups[key]["vat"] += line.vat_amount
    for rate, amounts in vat_groups.items():
        tax = _e(parent, "ApplicableTradeTax")
        _e(tax, "CalculatedAmount", _fmt(amounts["vat"]), currencyID=invoice.currency)
        _e(tax, "TypeCode", "VAT")
        _e(tax, "BasisAmount", _fmt(amounts["base"]), currencyID=invoice.currency)
        _e(tax, "CategoryCode", "S")
        _e(tax, "RateApplicablePercent", _fmt(Decimal(rate)))

def _build_totals(parent, invoice):
    sums = _e(parent, "SpecifiedTradeSettlementHeaderMonetarySummation")
    _e(sums, "LineTotalAmount",     _fmt(invoice.total_ht),  currencyID=invoice.currency)
    _e(sums, "TaxBasisTotalAmount", _fmt(invoice.total_ht),  currencyID=invoice.currency)
    _e(sums, "TaxTotalAmount",      _fmt(invoice.total_vat), currencyID=invoice.currency)
    _e(sums, "GrandTotalAmount",    _fmt(invoice.total_ttc), currencyID=invoice.currency)
    _e(sums, "DuePayableAmount",    _fmt(invoice.total_ttc), currencyID=invoice.currency)
