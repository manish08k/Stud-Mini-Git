"""Kafka integration – optional event streaming.

Set KAFKA_ENABLED=true and KAFKA_BOOTSTRAP_SERVERS to activate.
When disabled the producer is a no-op so the rest of the app is unaffected.
"""
from __future__ import annotations

import json
import threading
from typing import Any, Callable, Optional

from .config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP,
    KAFKA_ENABLED,
    KAFKA_TOPIC_EVENTS,
)
from .logging_config import StructLogger as _SL
get_logger = _SL

logger = get_logger(__name__)


class _NoOpProducer:
    """Silently drops messages when Kafka is disabled."""

    def send(self, topic: str, payload: dict) -> None:  # noqa: D401
        logger.debug("kafka.noop", topic=topic)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class KafkaProducer:
    """Thread-safe wrapper around kafka-python KafkaProducer."""

    def __init__(self) -> None:
        self._producer: Any = None
        if not KAFKA_ENABLED:
            logger.info("kafka.disabled")
            return
        try:
            from kafka import KafkaProducer as _KP  # type: ignore

            self._producer = _KP(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                acks="all",
                retries=3,
            )
            logger.info("kafka.producer.ready", servers=KAFKA_BOOTSTRAP_SERVERS)
        except Exception as exc:
            logger.warning("kafka.producer.failed", reason=str(exc))

    def send(self, topic: str, payload: dict) -> None:
        if self._producer is None:
            return
        try:
            self._producer.send(topic, payload)
        except Exception as exc:
            logger.error("kafka.send.error", topic=topic, reason=str(exc))

    def flush(self) -> None:
        if self._producer:
            self._producer.flush()

    def close(self) -> None:
        if self._producer:
            self._producer.close()


# ── singleton ─────────────────────────────────────────────────────────────────
_producer_lock = threading.Lock()
_producer_instance: Optional[KafkaProducer] = None


def get_producer() -> KafkaProducer:
    global _producer_instance
    with _producer_lock:
        if _producer_instance is None:
            _producer_instance = KafkaProducer()
    return _producer_instance


def emit_event(event_type: str, data: dict) -> None:
    """Convenience: publish a typed event to the default events topic."""
    payload = {"event": event_type, **data}
    get_producer().send(KAFKA_TOPIC_EVENTS, payload)


# ── consumer helper (run in background thread) ────────────────────────────────

def start_consumer(
    topic: str,
    handler: Callable[[dict], None],
    group_id: str = KAFKA_CONSUMER_GROUP,
) -> Optional[threading.Thread]:
    """Start a background Kafka consumer thread. Returns the thread or None."""
    if not KAFKA_ENABLED:
        return None
    try:
        from kafka import KafkaConsumer as _KC  # type: ignore
    except ImportError:
        logger.warning("kafka.consumer.import_error")
        return None

    def _loop() -> None:
        consumer = _KC(
            topic,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=group_id,
            value_deserializer=lambda b: json.loads(b.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        logger.info("kafka.consumer.started", topic=topic, group=group_id)
        for message in consumer:
            try:
                handler(message.value)
            except Exception as exc:
                logger.error("kafka.consumer.handler_error", reason=str(exc))

    t = threading.Thread(target=_loop, daemon=True, name=f"kafka-consumer-{topic}")
    t.start()
    return t
