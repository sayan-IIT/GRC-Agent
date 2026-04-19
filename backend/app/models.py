from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    vendor_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    current_score: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    proposed_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="current")
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    signals: Mapped[list["Signal"]] = relationship(back_populates="risk", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="risk", cascade="all, delete-orphan")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    risk_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("risks.id"), index=True)
    signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    freshness: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    risk: Mapped[Risk] = relationship(back_populates="signals")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    risk_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("risks.id"), index=True)
    previous_score: Mapped[float] = mapped_column(Float, nullable=False)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    signals_used: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="v1")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    risk: Mapped[Risk] = relationship(back_populates="audit_logs")

