from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SignalOut(BaseModel):
    id: str
    risk_id: str
    signal_type: str
    source: str
    value: float
    confidence: float
    freshness: float
    timestamp: datetime
    metadata_: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class AuditLogOut(BaseModel):
    id: str
    risk_id: str
    previous_score: float
    new_score: float
    explanation: str
    source: str
    signals_used: list[dict[str, Any]]
    model_version: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskOut(BaseModel):
    id: str
    name: str
    vendor_id: str
    current_score: float
    proposed_score: float | None
    confidence: float | None
    status: str
    explanation: str | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskDetailOut(RiskOut):
    signals: list[SignalOut]
    audit_logs: list[AuditLogOut]


class EventIn(BaseModel):
    risk_id: str
    signals: list[dict[str, Any]]

