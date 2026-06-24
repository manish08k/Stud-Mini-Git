from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable, Optional

from .config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONNECT_RETRIES,
    KAFKA_CONNECT_RETRY_DELAY,
    KAFKA_CONSUMER_GROUP,
    KAFKA_ENABLED,
    KAFKA_TOPIC_EVENTS,
)
from .logging_config import StructLogger as _SL

logger = _SL(__name__)


class _NoOpProducer:
    def send(self, topic: str, payload: dict) -> None:
        logger.debug("kafka.noop", topic=topic)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class KafkaProducer:
    def __init__(self) -> None:
        self._producer: Any = None
        if not KAFKA_ENABLED:
            logger.info("kafka.disabled")
            return
        self._connect_with_retry()

    def _connect_with_retry(self) -> None:
        for attempt in range(1, KAFKA_CONNECT_RETRIES + 1):
            try:
                from kafka import KafkaProducer as _KP  # type: ignore

                self._producer = _KP(
                    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: json.dumps(v, default=str).encode(),
                    acks="all",
                    retries=5,
                    retry_backoff_ms=500,
                )
                logger.info("kafka.producer.ready", servers=KAFKA_BOOTSTRAP_SERVERS)
                return
            except Exception as exc:
                logger.warning(
                    "kafka.producer.connect_failed",
                    attempt=attempt,
                    of=KAFKA_CONNECT_RETRIES,
                    reason=str(exc),
                )
                if attempt < KAFKA_CONNECT_RETRIES:
                    time.sleep(KAFKA_CONNECT_RETRY_DELAY * attempt)
        logger.error("kafka.producer.gave_up", retries=KAFKA_CONNECT_RETRIES)

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

    def is_ready(self) -> bool:
        return self._producer is not None


_producer_lock = threading.Lock()
_producer_instance: Optional[KafkaProducer] = None


def get_producer() -> KafkaProducer:
    global _producer_instance
    with _producer_lock:
        if _producer_instance is None:
            _producer_instance = KafkaProducer()
    return _producer_instance


def emit_event(event_type: str, data: dict) -> None:
    payload = {"event": event_type, **data}
    get_producer().send(KAFKA_TOPIC_EVENTS, payload)


def start_consumer(
    topic: str,
    handler: Callable[[dict], None],
    group_id: str = KAFKA_CONSUMER_GROUP,
) -> Optional[threading.Thread]:
    if not KAFKA_ENABLED:
        return None
    try:
        from kafka import KafkaConsumer as _KC  # type: ignore
    except ImportError:
        logger.warning("kafka.consumer.import_error")
        return None

    def _loop() -> None:
        for attempt in range(1, KAFKA_CONNECT_RETRIES + 1):
            try:
                consumer = _KC(
                    topic,
                    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                    group_id=group_id,
                    value_deserializer=lambda b: json.loads(b.decode()),
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                )
                logger.info("kafka.consumer.started", topic=topic, group=group_id)
                for message in consumer:
                    try:
                        handler(message.value)
                    except Exception as exc:
                        logger.error("kafka.consumer.handler_error", reason=str(exc))
                return
            except Exception as exc:
                logger.warning("kafka.consumer.connect_failed", attempt=attempt, reason=str(exc))
                if attempt < KAFKA_CONNECT_RETRIES:
                    time.sleep(KAFKA_CONNECT_RETRY_DELAY * attempt)
        logger.error("kafka.consumer.gave_up")

    t = threading.Thread(target=_loop, daemon=True, name=f"kafka-consumer-{topic}")
    t.start()
    return t
