import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.config import get_settings

logger = logging.getLogger(__name__)


class RiskSignalBus:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.producer: AIOKafkaProducer | None = None
        self.kafka_available = False

    async def start(self) -> None:
        try:
            self.producer = AIOKafkaProducer(bootstrap_servers=self.settings.kafka_bootstrap_servers)
            await self.producer.start()
            self.kafka_available = True
            logger.info("Kafka producer connected to %s", self.settings.kafka_bootstrap_servers)
        except Exception as exc:
            self.kafka_available = False
            self.producer = None
            logger.warning("Kafka unavailable; webhook /events fallback remains active: %s", exc)

    async def stop(self) -> None:
        if self.producer:
            await self.producer.stop()

    async def publish(self, risk_id: str, signals: list[dict[str, Any]]) -> bool:
        payload = {"risk_id": risk_id, "signals": signals}
        if not self.kafka_available or not self.producer:
            logger.warning("Kafka unavailable; publish skipped and FastAPI processing fallback used")
            return False

        await self.producer.send_and_wait(
            self.settings.kafka_topic,
            json.dumps(payload).encode("utf-8"),
        )
        logger.info("Published %s signals to Kafka topic %s", len(signals), self.settings.kafka_topic)
        return True


async def consume_risk_signals(handler: Callable[[str, list[dict[str, Any]]], Awaitable[None]]) -> None:
    settings = get_settings()
    consumer = AIOKafkaConsumer(
        settings.kafka_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="grc-risk-intelligence",
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        auto_offset_reset="latest",
    )
    try:
        await consumer.start()
        logger.info("Kafka consumer listening on topic %s", settings.kafka_topic)
        async for message in consumer:
            payload = message.value
            logger.info("Kafka consumer received risk signal event for %s", payload["risk_id"])
            await handler(payload["risk_id"], payload["signals"])
    except Exception as exc:
        logger.warning("Kafka consumer unavailable; use POST /events fallback: %s", exc)
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass

