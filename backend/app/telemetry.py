"""OpenTelemetry tracing – auto-instruments FastAPI + SQLAlchemy.

Exports to an OTLP endpoint (Jaeger / Grafana Tempo / etc.)
Set OTEL_EXPORTER_OTLP_ENDPOINT to activate; if the SDK or exporter
package is missing the function is a safe no-op.
"""
from __future__ import annotations

from .config import OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME
from .logging_config import StructLogger as _SL
get_logger = _SL

logger = get_logger(__name__)


def setup_tracing(app=None) -> None:  # noqa: ANN001
    """Call once at startup. Instruments the FastAPI `app` if provided."""
    try:
        from opentelemetry import trace  # type: ignore
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
    except ImportError:
        logger.info("otel.sdk_not_installed – skipping tracing")
        return

    resource = Resource(attributes={SERVICE_NAME: OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    logger.info("otel.tracing.enabled", endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)

    # auto-instrument FastAPI
    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore

            FastAPIInstrumentor.instrument_app(app)
        except ImportError:
            logger.debug("otel.fastapi_instrumentor_not_installed")

    # auto-instrument SQLAlchemy
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor  # type: ignore

        SQLAlchemyInstrumentor().instrument()
    except ImportError:
        logger.debug("otel.sqlalchemy_instrumentor_not_installed")
