from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Risk


async def seed_demo_data(session: AsyncSession) -> None:
    existing = await session.scalar(select(Risk.id).limit(1))
    if existing:
        return

    session.add_all(
        [
            Risk(name="Stripe vendor concentration", vendor_id="stripe.com", current_score=6.2, status="current"),
            Risk(name="HubSpot sales system dependency", vendor_id="hubspot.com", current_score=5.8, status="current"),
            Risk(name="Snowflake data platform exposure", vendor_id="snowflake.com", current_score=4.9, status="current"),
        ]
    )
    await session.commit()

