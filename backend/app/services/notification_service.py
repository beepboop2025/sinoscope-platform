"""Notification service — send via channel, template rendering, mock dispatchers."""

import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import NotificationChannel, NotificationDelivery, NotificationTemplate

logger = logging.getLogger(__name__)


class NotificationService:
    """Handles notification dispatch across multiple channel types.

    All dispatchers are mock implementations that log what WOULD be sent,
    allowing full integration testing without external service dependencies.
    """

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    @staticmethod
    async def send(
        session: AsyncSession,
        channel_id: str,
        subject: str,
        body: str,
    ) -> NotificationDelivery:
        """Send a notification through the specified channel.

        Returns the persisted delivery record with status "sent" or "failed".
        """
        result = await session.execute(
            select(NotificationChannel).where(NotificationChannel.id == channel_id)
        )
        channel = result.scalar_one_or_none()
        if channel is None:
            raise ValueError(f"Channel {channel_id} not found")

        delivery = NotificationDelivery(
            channel_id=channel_id,
            subject=subject,
            body=body,
            status="pending",
        )
        session.add(delivery)
        await session.flush()

        try:
            config = json.loads(channel.config_json) if channel.config_json else {}
        except (json.JSONDecodeError, TypeError):
            config = {}

        try:
            dispatcher = {
                "email": NotificationService._dispatch_email,
                "telegram": NotificationService._dispatch_telegram,
                "discord": NotificationService._dispatch_discord,
                "webhook": NotificationService._dispatch_webhook,
                "sms": NotificationService._dispatch_sms,
            }.get(channel.channel_type)

            if dispatcher is None:
                raise ValueError(f"Unknown channel type: {channel.channel_type}")

            dispatcher(config, subject, body)
            delivery.status = "sent"
            delivery.sent_at = datetime.now(timezone.utc)
            logger.info(
                "Notification sent: channel=%s type=%s subject=%s",
                channel_id, channel.channel_type, subject,
            )
        except Exception as exc:
            delivery.status = "failed"
            delivery.error_message = str(exc)
            logger.error("Notification failed: channel=%s error=%s", channel_id, exc)

        await session.flush()
        return delivery

    @staticmethod
    async def send_with_template(
        session: AsyncSession,
        channel_id: str,
        template_id: str,
        variables: dict[str, str],
    ) -> NotificationDelivery:
        """Send a notification using a template with variable substitution."""
        result = await session.execute(
            select(NotificationTemplate).where(NotificationTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise ValueError(f"Template {template_id} not found")

        rendered_subject = NotificationService._render_template(template.subject, variables)
        rendered_body = NotificationService._render_template(template.body_template, variables)

        delivery = await NotificationService.send(
            session, channel_id, rendered_subject, rendered_body,
        )
        delivery.template_id = template_id
        await session.flush()
        return delivery

    # ------------------------------------------------------------------
    # Template rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _render_template(template_body: str, variables: dict[str, str]) -> str:
        """Replace {{variable}} placeholders with values from the variables dict."""
        def replacer(match: re.Match) -> str:
            key = match.group(1).strip()
            return str(variables.get(key, match.group(0)))

        return re.sub(r"\{\{(\s*\w+\s*)\}\}", replacer, template_body)

    # ------------------------------------------------------------------
    # Mock dispatchers — log what WOULD be sent
    # ------------------------------------------------------------------

    @staticmethod
    def _dispatch_email(config: dict, subject: str, body: str) -> None:
        to_address = config.get("to", config.get("email", "unknown@example.com"))
        logger.info(
            "[MOCK EMAIL] To: %s | Subject: %s | Body length: %d",
            to_address, subject, len(body),
        )

    @staticmethod
    def _dispatch_telegram(config: dict, subject: str, body: str) -> None:
        chat_id = config.get("chat_id", "unknown")
        message = f"*{subject}*\n{body}"
        logger.info(
            "[MOCK TELEGRAM] Chat: %s | Message length: %d",
            chat_id, len(message),
        )

    @staticmethod
    def _dispatch_discord(config: dict, subject: str, body: str) -> None:
        webhook_url = config.get("webhook_url", "unknown")
        logger.info(
            "[MOCK DISCORD] Webhook: %s | Subject: %s | Body length: %d",
            webhook_url, subject, len(body),
        )

    @staticmethod
    def _dispatch_webhook(config: dict, subject: str, body: str) -> None:
        url = config.get("url", "unknown")
        payload = {"subject": subject, "body": body}
        logger.info(
            "[MOCK WEBHOOK] URL: %s | Payload: %s",
            url, json.dumps(payload)[:200],
        )

    @staticmethod
    def _dispatch_sms(config: dict, subject: str, body: str) -> None:
        phone = config.get("phone", config.get("to", "unknown"))
        message = f"{subject}: {body}"
        logger.info(
            "[MOCK SMS] Phone: %s | Message length: %d",
            phone, len(message),
        )
