"""Production observability helpers."""

from __future__ import annotations

import logging


def configure_sentry(*, dsn: str, environment: str, release: str = "") -> None:
    if not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        environment=environment,
        release=release or None,
        send_default_pii=False,
        traces_sample_rate=0.1,
    )
