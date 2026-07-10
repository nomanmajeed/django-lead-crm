from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_outbound_email_task(self, outbound_id: int):
    from email_engine.service import deliver_outbound_email

    try:
        return deliver_outbound_email(outbound_id).status
    except Exception as exc:  # noqa: BLE001 — retry transient provider failures
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_campaign_batch_task(self, campaign_id: int):
    from email_engine.campaigns import process_campaign_batch

    try:
        return process_campaign_batch(campaign_id)
    except Exception as exc:  # noqa: BLE001 — retry transient batch failures
        raise self.retry(exc=exc) from exc
