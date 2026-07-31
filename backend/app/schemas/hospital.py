from typing import Literal

from pydantic import BaseModel, Field

WardType = Literal["general", "icu", "emergency", "hdu", "maternity", "paediatric"]


class HospitalCreate(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=200)
    district: str = Field(min_length=2, max_length=64)
    area: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=32)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    has_emergency: bool = True


class HospitalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    district: str | None = Field(default=None, min_length=2, max_length=64)
    area: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=32)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    has_emergency: bool | None = None
    is_active: bool | None = None


class WardCreate(BaseModel):
    ward_type: WardType
    name: str = Field(min_length=2, max_length=120)
    total_beds: int = Field(ge=0, le=5000)
    occupied_beds: int = Field(default=0, ge=0, le=5000)


class BedStatusUpdate(BaseModel):
    occupied_beds: int = Field(ge=0, le=5000)
    total_beds: int | None = Field(default=None, ge=0, le=5000)


class StaffAssign(BaseModel):
    user_id: str
    staff_role: Literal["WARD_MANAGER", "HOSPITAL_ADMIN"] = "WARD_MANAGER"


class WardResponse(BaseModel):
    id: str
    ward_type: str
    name: str
    total_beds: int
    occupied_beds: int
    available_beds: int
    occupancy_rate: float
    updated_at: str | None = None


class HospitalResponse(BaseModel):
    id: str
    code: str
    name: str
    district: str
    area: str | None = None
    address: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    has_emergency: bool
    is_active: bool
    wards: list[WardResponse] = []
    total_beds: int = 0
    available_beds: int = 0


class NearbyHospital(BaseModel):
    id: str
    code: str
    name: str
    district: str
    area: str | None = None
    phone: str | None = None
    distance_km: float | None = None
    has_emergency: bool
    available_beds: int
    available_icu_beds: int
    matched_ward: str | None = None
