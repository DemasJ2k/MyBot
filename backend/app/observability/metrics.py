"""
Prometheus metrics collection for Flowrex.

Prompt 17 - Deployment Prep.

Provides:
- HTTP request metrics (count, duration)
- Trading metrics (trades, signals)
- System metrics (connections, active resources)
- /metrics endpoint for Prometheus scraping
"""

import time
import os
from typing import Callable

from fastapi import FastAPI, Response, Request
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary,
        generate_latest, REGISTRY, CONTENT_TYPE_LATEST
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False


# ============================================================================
# Metrics Definitions
# ============================================================================

if HAS_PROMETHEUS:
    # HTTP Metrics
    http_requests_total = Counter(
        'flowrex_http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )

    http_request_duration_seconds = Histogram(
        'flowrex_http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint'],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
    )

    http_requests_in_progress = Gauge(
        'flowrex_http_requests_in_progress',
        'HTTP requests currently being processed',
        ['method', 'endpoint']
    )

    # Trading Metrics
    trades_executed_total = Counter(
        'flowrex_trades_executed_total',
        'Total trades executed',
        ['symbol', 'side', 'execution_mode']
    )

    trades_failed_total = Counter(
        'flowrex_trades_failed_total',
        'Total failed trade attempts',
        ['symbol', 'reason']
    )

    signals_generated_total = Counter(
        'flowrex_signals_generated_total',
        'Total signals generated',
        ['strategy', 'signal_type']
    )

    signals_rejected_total = Counter(
        'flowrex_signals_rejected_total',
        'Total signals rejected by risk engine',
        ['strategy', 'rejection_reason']
    )

    # Strategy Metrics
    active_strategies = Gauge(
        'flowrex_active_strategies',
        'Number of active trading strategies'
    )

    strategy_pnl = Gauge(
        'flowrex_strategy_pnl',
        'Strategy profit/loss',
        ['strategy']
    )

    # Connection Metrics
    websocket_connections = Gauge(
        'flowrex_websocket_connections',
        'Number of active WebSocket connections'
    )

    database_connections = Gauge(
        'flowrex_database_connections',
        'Number of active database connections'
    )

    redis_connections = Gauge(
        'flowrex_redis_connections',
        'Number of active Redis connections'
    )

    # Backtest Metrics
    backtests_running = Gauge(
        'flowrex_backtests_running',
        'Number of backtests currently running'
    )

    backtests_completed_total = Counter(
        'flowrex_backtests_completed_total',
        'Total backtests completed',
        ['status']
    )

    # AI Agent Metrics
    agent_tasks_total = Counter(
        'flowrex_agent_tasks_total',
        'Total agent tasks processed',
        ['agent_type', 'status']
    )

    agent_processing_seconds = Summary(
        'flowrex_agent_processing_seconds',
        'Agent task processing time',
        ['agent_type']
    )

else:
    # Stub implementations when prometheus_client is not installed
    class StubMetric:
        def labels(self, **kwargs): return self
        def inc(self, amount=1): pass
        def dec(self, amount=1): pass
        def set(self, value): pass
        def observe(self, value): pass

    http_requests_total = StubMetric()
    http_request_duration_seconds = StubMetric()
    http_requests_in_progress = StubMetric()
    trades_executed_total = StubMetric()
    trades_failed_total = StubMetric()
    signals_generated_total = StubMetric()
    signals_rejected_total = StubMetric()
    active_strategies = StubMetric()
    strategy_pnl = StubMetric()
    websocket_connections = StubMetric()
    database_connections = StubMetric()
    redis_connections = StubMetric()
    backtests_running = StubMetric()
    backtests_completed_total = StubMetric()
    agent_tasks_total = StubMetric()
    agent_processing_seconds = StubMetric()


# ============================================================================
# Metrics Middleware
# ============================================================================

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    # Endpoints to exclude from detailed metrics (high cardinality)
    EXCLUDE_PATHS = {"/metrics", "/health", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and record metrics."""
        # Skip metrics endpoint itself to avoid recursion
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)

        # Normalize path to reduce cardinality (remove IDs)
        path = self._normalize_path(request.url.path)
        method = request.method

        # Track in-progress requests
        if HAS_PROMETHEUS:
            http_requests_in_progress.labels(method=method, endpoint=path).inc()

        # Record request timing
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            # Record metrics
            duration = time.perf_counter() - start_time

            if HAS_PROMETHEUS:
                http_requests_total.labels(
                    method=method,
                    endpoint=path,
                    status=status
                ).inc()

                http_request_duration_seconds.labels(
                    method=method,
                    endpoint=path
                ).observe(duration)

                http_requests_in_progress.labels(method=method, endpoint=path).dec()

        return response

    def _normalize_path(self, path: str) -> str:
        """Normalize path to reduce cardinality.
        
        Replaces numeric IDs and UUIDs with placeholders.
        """
        parts = path.split("/")
        normalized = []
        
        for part in parts:
            if not part:
                continue
            # Replace numeric IDs
            if part.isdigit():
                normalized.append("{id}")
            # Replace UUIDs
            elif len(part) == 36 and part.count("-") == 4:
                normalized.append("{uuid}")
            else:
                normalized.append(part)
        
        return "/" + "/".join(normalized) if normalized else "/"


# ============================================================================
# Setup Function
# ============================================================================

def setup_metrics(app: FastAPI) -> None:
    """Setup Prometheus metrics collection.
    
    Args:
        app: FastAPI application instance
    """
    metrics_enabled = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    
    if not metrics_enabled:
        return

    if not HAS_PROMETHEUS:
        import logging
        logging.getLogger(__name__).warning(
            "prometheus_client not installed - metrics disabled. "
            "Install with: pip install prometheus-client"
        )
        return

    # Add metrics middleware
    app.add_middleware(MetricsMiddleware)

    # Add metrics endpoint
    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        """Prometheus metrics endpoint."""
        return Response(
            content=generate_latest(REGISTRY),
            media_type=CONTENT_TYPE_LATEST
        )


# ============================================================================
# Helper Functions
# ============================================================================

def record_trade(symbol: str, side: str, execution_mode: str) -> None:
    """Record a successful trade execution."""
    trades_executed_total.labels(
        symbol=symbol,
        side=side,
        execution_mode=execution_mode
    ).inc()


def record_trade_failure(symbol: str, reason: str) -> None:
    """Record a failed trade attempt."""
    trades_failed_total.labels(symbol=symbol, reason=reason).inc()


def record_signal(strategy: str, signal_type: str) -> None:
    """Record a generated signal."""
    signals_generated_total.labels(
        strategy=strategy,
        signal_type=signal_type
    ).inc()


def record_signal_rejection(strategy: str, reason: str) -> None:
    """Record a rejected signal."""
    signals_rejected_total.labels(
        strategy=strategy,
        rejection_reason=reason
    ).inc()
