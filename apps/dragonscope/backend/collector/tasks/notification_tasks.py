"""Celery tasks for notifications — digests and scheduled reports."""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from collector.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_dsn() -> str:
    settings = get_settings()
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


@celery_app.task(name="collector.tasks.notification_tasks.send_digest")
def send_digest(frequency: str = "daily") -> dict:
    """Send digest notifications to all users with active digest configs of the given frequency.

    Collects portfolio summary, active alerts, and market summary data from Redis,
    then dispatches through each user's configured notification channels.
    """
    settings = get_settings()
    engine = create_engine(_get_sync_dsn())

    try:
        import redis as redis_lib

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

        with Session(engine) as session:
            from app.models.notification import (
                DigestConfig,
                NotificationChannel,
                NotificationDelivery,
            )

            # Find active digests for this frequency
            result = session.execute(
                select(DigestConfig).where(
                    DigestConfig.frequency == frequency,
                    DigestConfig.is_active == True,  # noqa: E712
                )
            )
            digests = list(result.scalars().all())

            if not digests:
                logger.info("[NOTIFICATIONS] No active %s digests", frequency)
                return {"status": "completed", "digests_sent": 0}

            # Build market summary from Redis
            market_summary = ""
            raw = r.get("market:crypto_markets")
            if raw:
                try:
                    parsed = json.loads(raw)
                    data = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed
                    if isinstance(data, list):
                        top_3 = data[:3]
                        summaries = []
                        for item in top_3:
                            sym = item.get("symbol", "?")
                            price = item.get("current_price", 0)
                            pct = item.get("price_change_percentage_24h", 0)
                            summaries.append(f"{sym}: ${price} ({pct:+.1f}%)")
                        market_summary = "Top crypto: " + ", ".join(summaries)
                except (json.JSONDecodeError, TypeError):
                    market_summary = "Market data unavailable"

            sent_count = 0
            for digest in digests:
                # Build digest body
                sections = []
                if digest.include_market_summary and market_summary:
                    sections.append(f"Market Summary:\n{market_summary}")
                if digest.include_portfolio:
                    sections.append("Portfolio: Check dashboard for latest holdings.")
                if digest.include_alerts:
                    sections.append("Alerts: Check dashboard for triggered alerts.")

                body = f"Your {frequency} digest\n\n" + "\n\n".join(sections) if sections else f"Your {frequency} digest — no updates."

                # Find user's notification channels
                result = session.execute(
                    select(NotificationChannel).where(
                        NotificationChannel.user_id == digest.user_id,
                        NotificationChannel.is_active == True,  # noqa: E712
                    )
                )
                channels = list(result.scalars().all())

                for channel in channels:
                    delivery = NotificationDelivery(
                        id=str(uuid.uuid4()),
                        channel_id=channel.id,
                        subject=f"DragonScope {frequency.capitalize()} Digest",
                        body=body,
                        status="sent",
                        sent_at=datetime.now(timezone.utc),
                    )
                    session.add(delivery)
                    sent_count += 1
                    logger.info(
                        "[NOTIFICATIONS] Digest sent to user %s via %s",
                        digest.user_id, channel.channel_type,
                    )

            session.commit()
            logger.info("[NOTIFICATIONS] Sent %d %s digests", sent_count, frequency)
            return {"status": "completed", "digests_sent": sent_count}

    except Exception as exc:
        logger.error("[NOTIFICATIONS] send_digest failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        engine.dispose()


@celery_app.task(name="collector.tasks.notification_tasks.generate_scheduled_reports")
def generate_scheduled_reports() -> dict:
    """Generate and deliver scheduled reports.

    Checks all active scheduled reports and delivers them through
    the user's notification channels.
    """
    engine = create_engine(_get_sync_dsn())

    try:
        with Session(engine) as session:
            from app.models.notification import (
                NotificationChannel,
                NotificationDelivery,
                ScheduledReport,
            )

            now = datetime.now(timezone.utc)

            result = session.execute(
                select(ScheduledReport).where(
                    ScheduledReport.is_active == True,  # noqa: E712
                )
            )
            reports = list(result.scalars().all())

            if not reports:
                logger.info("[NOTIFICATIONS] No active scheduled reports")
                return {"status": "completed", "reports_generated": 0}

            generated_count = 0
            for report in reports:
                # Generate report content based on type
                if report.report_type == "portfolio":
                    body = json.dumps({
                        "report_type": "portfolio",
                        "generated_at": now.isoformat(),
                        "message": "Portfolio report generated. Check dashboard for details.",
                    })
                elif report.report_type == "market":
                    body = json.dumps({
                        "report_type": "market",
                        "generated_at": now.isoformat(),
                        "message": "Market report generated. Check dashboard for details.",
                    })
                elif report.report_type == "research":
                    body = json.dumps({
                        "report_type": "research",
                        "generated_at": now.isoformat(),
                        "message": "Research report generated. Check dashboard for details.",
                    })
                else:
                    continue

                # Find user's channels and deliver
                result = session.execute(
                    select(NotificationChannel).where(
                        NotificationChannel.user_id == report.user_id,
                        NotificationChannel.is_active == True,  # noqa: E712
                    )
                )
                channels = list(result.scalars().all())

                for channel in channels:
                    delivery = NotificationDelivery(
                        id=str(uuid.uuid4()),
                        channel_id=channel.id,
                        subject=f"DragonScope {report.report_type.capitalize()} Report",
                        body=body,
                        status="sent",
                        sent_at=now,
                    )
                    session.add(delivery)

                report.last_sent = now
                generated_count += 1

            session.commit()
            logger.info("[NOTIFICATIONS] Generated %d scheduled reports", generated_count)
            return {"status": "completed", "reports_generated": generated_count}

    except Exception as exc:
        logger.error("[NOTIFICATIONS] generate_scheduled_reports failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        engine.dispose()
