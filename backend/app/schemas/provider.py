from typing import Literal

from pydantic import BaseModel, Field

ProviderType = Literal["LAB", "PHARMACY"]


class ProviderCreate(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=200)
    provider_type: ProviderType
    district: str = Field(min_length=2, max_length=64)
    area: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=32)
    licence_number: str | None = Field(default=None, max_length=64)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    owner_user_id: str | None = None


class LabTestCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=2, max_length=200)
    sample_type: str | None = Field(default=None, max_length=64)
    price_bdt: float = Field(ge=0, le=1_000_000)
    turnaround_hours: int | None = Field(default=None, ge=1, le=720)


class LabOrderCreate(BaseModel):
    provider_id: str
    lab_test_id: str
    patient_user_id: str | None = None
    consultation_id: str | None = None
    share_with_doctor: bool = True


class LabOrderStatusUpdate(BaseModel):
    status: Literal["ACCEPTED", "SAMPLE_COLLECTED", "PROCESSING", "CANCELLED"]


class LabResultUpload(BaseModel):
    result_summary: str = Field(min_length=1, max_length=4000)
    result_values: dict | None = None
    is_abnormal: bool = False
    result_file_id: str | None = None


class ConsentUpdate(BaseModel):
    share_with_doctor: bool


class StockUpsert(BaseModel):
    brand_name: str = Field(min_length=1, max_length=200)
    strength: str | None = Field(default=None, max_length=64)
    unit_price_bdt: float = Field(ge=0, le=1_000_000)
    quantity_available: int = Field(ge=0, le=1_000_000)


class CheckoutRequest(BaseModel):
    purpose: Literal["CONSULTATION", "LAB_ORDER"]
    method: Literal["bkash", "nagad", "rocket", "sslcommerz"]
    idempotency_key: str = Field(min_length=8, max_length=128)
    appointment_id: str | None = None
    lab_order_id: str | None = None
    payer_msisdn: str | None = Field(default=None, max_length=20)


class PaymentCallback(BaseModel):
    reference: str = Field(min_length=4, max_length=64)
    status: Literal["COMPLETED", "FAILED"]
    gateway_reference: str | None = Field(default=None, max_length=128)
    signature: str = Field(min_length=16, max_length=256)
    failure_reason: str | None = Field(default=None, max_length=300)


class RefundRequest(BaseModel):
    amount_bdt: float | None = Field(default=None, gt=0, le=1_000_000)
    reason: str | None = Field(default=None, max_length=300)
