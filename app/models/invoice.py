# app/models/invoice.py
from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal


class Address(BaseModel):
    street: str
    city: str
    postal_code: str
    country: str = "FR"


class Party(BaseModel):
    name: str
    siret: str
    vat_number: str
    address: Address
    email: Optional[str] = None


class InvoiceLine(BaseModel):
    id: str
    description: str
    quantity: Decimal
    unit: str = "EA"
    unit_price: Decimal
    vat_rate: Decimal

    @property
    def line_total(self) -> Decimal:
        return self.quantity * self.unit_price

    @property
    def vat_amount(self) -> Decimal:
        return self.line_total * self.vat_rate / 100


class CreditNoteData(BaseModel):
    """Structure d un avoir - identique a une facture mais avec reference a la facture originale."""
    invoice_number: str
    issue_date: str
    currency: str = "EUR"
    seller: Party
    buyer: Party
    lines: List[InvoiceLine] = Field(min_length=1)
    original_invoice_number: str  # Numéro de la facture annulée

    @property
    def total_ht(self) -> Decimal:
        return sum(line.line_total for line in self.lines)

    @property
    def total_vat(self) -> Decimal:
        return sum(line.vat_amount for line in self.lines)

    @property
    def total_ttc(self) -> Decimal:
        return self.total_ht + self.total_vat


class InvoiceData(BaseModel):
    invoice_number: str
    issue_date: str
    due_date: Optional[str] = None
    currency: str = "EUR"
    seller: Party
    buyer: Party
    lines: List[InvoiceLine] = Field(min_length=1)
    payment_terms: Optional[str] = None
    bank_iban: Optional[str] = None

    @property
    def total_ht(self) -> Decimal:
        return sum(line.line_total for line in self.lines)

    @property
    def total_vat(self) -> Decimal:
        return sum(line.vat_amount for line in self.lines)

    @property
    def total_ttc(self) -> Decimal:
        return self.total_ht + self.total_vat
