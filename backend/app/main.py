import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.crustdata import CrustDataAdapter
from app.agents.workflow import build_risk_workflow
from app.config import get_settings
from app.db import AsyncSessionLocal, engine, get_session
from app.models import AuditLog, Base, Risk, Signal
from app.schemas import EventIn, RiskDetailOut, RiskOut
from app.seed import seed_demo_data
from app.streaming import RiskSignalBus, consume_risk_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()
workflow = build_risk_workflow()
signal_bus = RiskSignalBus()
consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)
    await signal_bus.start()
    consumer_task = asyncio.create_task(consume_risk_signals(process_signal_event))
    yield
    if consumer_task:
        consumer_task.cancel()
    await signal_bus.stop()


app = FastAPI(title="AI GRC Risk Intelligence Platform", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "source": "CrustData API"}


@app.get("/risks", response_model=list[RiskOut])
async def list_risks(session: AsyncSession = Depends(get_session)) -> list[Risk]:
    result = await session.execute(select(Risk).order_by(Risk.updated_at.desc()))
    return list(result.scalars().all())


@app.get("/risks/{risk_id}", response_model=RiskDetailOut)
async def get_risk(risk_id: str, session: AsyncSession = Depends(get_session)) -> Risk:
    risk = await _load_risk(session, risk_id)
    return risk


@app.post("/risks/{risk_id}/fetch-external-signals", response_model=RiskDetailOut)
async def fetch_external_signals(risk_id: str, session: AsyncSession = Depends(get_session)) -> Risk:
    risk = await _load_risk(session, risk_id)
    adapter = CrustDataAdapter(settings.crustdata_api_key)
    raw = await adapter.fetch_vendor_signals(risk.vendor_id)
    signals = adapter.normalize_signals(raw)
    await persist_signals(session, risk.id, signals)
    await signal_bus.publish(risk.id, signals)
    await process_signal_event(risk.id, signals)
    await session.refresh(risk)
    return await _load_risk(session, risk_id)


@app.post("/events")
async def events(event: EventIn, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    logger.info("Received webhook fallback event for risk %s", event.risk_id)
    await _load_risk(session, event.risk_id)
    await persist_signals(session, event.risk_id, event.signals)
    await process_signal_event(event.risk_id, event.signals)
    return {"status": "accepted"}


@app.post("/risks/{risk_id}/approve", response_model=RiskDetailOut)
async def approve_risk(risk_id: str, session: AsyncSession = Depends(get_session)) -> Risk:
    risk = await _load_risk(session, risk_id)
    if risk.proposed_score is None:
        raise HTTPException(status_code=400, detail="No proposed score to approve")

    previous = risk.current_score
    risk.current_score = risk.proposed_score
    risk.status = "approved"
    risk.explanation = f"Approved human-in-the-loop update. Based on CrustData API signal. Previous score {previous}."
    session.add(
        AuditLog(
            risk_id=risk.id,
            previous_score=previous,
            new_score=risk.current_score,
            explanation="Human approved AI suggested update based on CrustData API signal",
            source="CrustData",
            signals_used=[_signal_to_dict(signal) for signal in risk.signals],
            model_version=settings.model_version,
        )
    )
    await session.commit()
    logger.info("Human approved risk %s score change %s -> %s", risk.id, previous, risk.current_score)
    return await _load_risk(session, risk_id)


@app.post("/risks/{risk_id}/reject", response_model=RiskDetailOut)
async def reject_risk(risk_id: str, session: AsyncSession = Depends(get_session)) -> Risk:
    risk = await _load_risk(session, risk_id)
    if risk.proposed_score is None:
        raise HTTPException(status_code=400, detail="No proposed score to reject")

    previous = risk.current_score
    risk.status = "rejected"
    session.add(
        AuditLog(
            risk_id=risk.id,
            previous_score=previous,
            new_score=previous,
            explanation="Human rejected AI suggested update based on CrustData API signal",
            source="CrustData",
            signals_used=[_signal_to_dict(signal) for signal in risk.signals],
            model_version=settings.model_version,
        )
    )
    await session.commit()
    logger.info("Human rejected risk %s proposed score %s", risk.id, risk.proposed_score)
    return await _load_risk(session, risk_id)


async def process_signal_event(risk_id: str, signals: list[dict[str, Any]]) -> None:
    async with AsyncSessionLocal() as session:
        risk = await _load_risk(session, risk_id)
        state = await workflow.ainvoke(
            {
                "risk_id": risk.id,
                "risk_name": risk.name,
                "current_score": risk.current_score,
                "internal_score": risk.current_score / 10,
                "manual_score": 0.55,
                "signals": signals,
            }
        )
        scoring = state["scoring"]
        explanation = state["explanation"]
        audit_record = state["audit_record"]

        risk.proposed_score = scoring["proposed_score"]
        risk.confidence = scoring["confidence"]
        risk.status = "proposed"
        risk.explanation = _format_explanation(explanation)

        session.add(
            AuditLog(
                risk_id=risk.id,
                previous_score=audit_record["previous_score"],
                new_score=audit_record["proposed_score"],
                explanation=risk.explanation,
                source="CrustData",
                signals_used=audit_record["signals_used"],
                model_version=audit_record["model_version"],
            )
        )
        await session.commit()
        logger.info("Agents completed risk %s proposal at score %s", risk.id, risk.proposed_score)


async def persist_signals(session: AsyncSession, risk_id: str, signals: list[dict[str, Any]]) -> None:
    for signal in signals:
        session.add(
            Signal(
                risk_id=risk_id,
                signal_type=signal["signal_type"],
                source=signal["source"],
                value=signal["value"],
                confidence=signal["confidence"],
                freshness=signal["freshness"],
                metadata_=signal.get("metadata", {}),
                timestamp=datetime.fromisoformat(signal["timestamp"]),
            )
        )
    await session.commit()
    logger.info("Persisted %s normalized signals for risk %s", len(signals), risk_id)


async def _load_risk(session: AsyncSession, risk_id: str) -> Risk:
    result = await session.execute(
        select(Risk)
        .where(Risk.id == risk_id)
        .options(selectinload(Risk.signals), selectinload(Risk.audit_logs))
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")
    return risk


def _format_explanation(explanation: dict[str, Any]) -> str:
    drivers = "; ".join(explanation["key_drivers"])
    evidence = "; ".join(explanation["evidence"])
    return (
        f"{explanation['summary']}\n"
        f"Analysis Method: {explanation['analysis_method']}\n"
        f"Key Drivers: {drivers}\n"
        f"Evidence: {evidence}\n"
        f"Confidence: {explanation['confidence']}"
    )


def _signal_to_dict(signal: Signal) -> dict[str, Any]:
    return {
        "signal_type": signal.signal_type,
        "source": signal.source,
        "value": signal.value,
        "confidence": signal.confidence,
        "freshness": signal.freshness,
        "timestamp": signal.timestamp.isoformat(),
        "metadata": signal.metadata_,
    }
