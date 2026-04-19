from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Risk


DEMO_RISKS = [
    {"name": "Hilbert AI funding and growth exposure", "vendor_id": "hilberts.ai", "current_score": 5.9},
    {"name": "Thinking Machines Lab model dependency", "vendor_id": "thinkingmachines.ai", "current_score": 7.1},
    {"name": "Block Inc. payments platform dependency", "vendor_id": "block.xyz", "current_score": 6.4},
]

OLD_DEMO_VENDOR_IDS = ["stripe.com", "hubspot.com", "snowflake.com"]
NEW_DEMO_VENDOR_IDS = [risk["vendor_id"] for risk in DEMO_RISKS]


async def seed_demo_data(session: AsyncSession) -> None:
    old_risks = await session.scalars(
        select(Risk)
        .where(Risk.vendor_id.in_(OLD_DEMO_VENDOR_IDS))
        .options(selectinload(Risk.signals), selectinload(Risk.audit_logs))
    )
    for risk in old_risks:
        await session.delete(risk)

    existing_vendor_ids = set(
        await session.scalars(select(Risk.vendor_id).where(Risk.vendor_id.in_(NEW_DEMO_VENDOR_IDS)))
    )
    missing_risks = [
        Risk(**risk, status="current")
        for risk in DEMO_RISKS
        if risk["vendor_id"] not in existing_vendor_ids
    ]

    session.add_all(missing_risks)
    await session.commit()
