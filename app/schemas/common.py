

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TFBaseModel(BaseModel):
    

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class DocumentType(str, Enum):
    

    LETTER_OF_CREDIT = "letter_of_credit"
    COMMERCIAL_INVOICE = "commercial_invoice"
    BILL_OF_LADING = "bill_of_lading"
    PACKING_LIST = "packing_list"
    CERTIFICATE_OF_ORIGIN = "certificate_of_origin"
    INSPECTION_CERTIFICATE = "inspection_certificate"
    SANCTIONS_POLICY = "sanctions_policy"
    MANIFEST = "manifest"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class RiskLevel(str, Enum):
    

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BoundingBox(TFBaseModel):
    

    page: int = Field(..., ge=0, description="0-indexed page number")
    x0: float = Field(..., description="Left edge")
    y0: float = Field(..., description="Top edge")
    x1: float = Field(..., description="Right edge")
    y1: float = Field(..., description="Bottom edge")
