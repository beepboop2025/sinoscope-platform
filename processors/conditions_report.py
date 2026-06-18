"""China economic conditions report generator.

Reads the latest CBB index (Redis key `cbb:latest` or recent
`ConditionsIndexSnapshot` rows), builds a neutral briefing prompt, calls an
LLM via the project's free-llm router / Anthropic / Ollama fallback chain, and
writes the report to `data/cbb/reports/<date>.md` plus `latest.md`.

A lightweight metadata record is stored by reusing the existing `DailyDigest`
table; the canonical report content lives on disk so the API can serve it
without depending on Postgres.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from core.base_processor import BaseProcessor

logger = logging.getLogger(__name__)

_REPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "cbb" / "reports"
_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


class ConditionsReportGenerator(BaseProcessor):
    name = "conditions_report"
    batch_size = 50

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.llm_model = self.config.get("llm_model", "claude-sonnet-4-6")
        self.ollama_model = self.config.get("ollama_model", "llama3")
        self.send_telegram = self.config.get("send_telegram", False)

    def process_one(self, article: dict) -> dict:
        return {"status": "use_run"}

    def run(self) -> dict:
        """Generate today's China economic conditions report."""
        from api.database import SessionLocal
        from storage.models import DailyDigest

        db = SessionLocal()
        try:
            today = datetime.now(timezone.utc).date()

            # 1. Load latest index data.
            index_data = self._load_latest_index(db)
            if not index_data:
                return {"status": "no_data", "date": str(today)}

            sectors = index_data.get("sectors", [])
            generated_at = index_data.get("generated_at")

            # 2. Build prompt and generate report.
            prompt = self._build_prompt(sectors, generated_at)
            report = self._generate_report(prompt, sectors, generated_at)

            # 3. Write report files.
            report_path, latest_path = self._write_report(report, today)

            # 4. Store lightweight metadata record.
            digest = DailyDigest(
                date=today,
                summary=report,
                top_themes=[{"sector": s.get("sector"), "D": s.get("D")} for s in sectors],
                sentiment_summary={
                    "sectors": len(sectors),
                    "generated_at": generated_at,
                    "report_path": str(report_path),
                },
                key_data_releases=[
                    {
                        "sector": s.get("sector"),
                        "D": s.get("D"),
                        "momentum": s.get("momentum"),
                        "confidence": s.get("confidence"),
                    }
                    for s in sectors
                ],
                new_circulars=[],
            )
            db.add(digest)
            db.commit()

            if self.send_telegram:
                self._send_telegram(report)

            return {
                "status": "success",
                "date": str(today),
                "sectors": len(sectors),
                "report_path": str(report_path),
                "report_length": len(report),
            }
        except Exception as e:
            logger.error(f"[ConditionsReport] Failed: {e}")
            try:
                db.rollback()
            except Exception:
                pass
            return {"status": "error", "error": str(e)}
        finally:
            db.close()

    def _load_latest_index(self, db) -> dict:
        """Read `cbb:latest` from Redis or fall back to recent DB snapshots."""
        try:
            import redis

            r = redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                decode_responses=True,
            )
            raw = r.get("cbb:latest")
            r.close()
            if raw:
                data = json.loads(raw)
                if data and data.get("sectors"):
                    return data
        except Exception as e:
            logger.warning(f"[ConditionsReport] Redis read failed: {e}")

        # Fallback: query recent ConditionsIndexSnapshot rows.
        try:
            from storage.models import ConditionsIndexSnapshot

            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            rows = (
                db.query(ConditionsIndexSnapshot)
                .filter(ConditionsIndexSnapshot.generated_at >= cutoff)
                .order_by(ConditionsIndexSnapshot.generated_at.desc())
                .all()
            )
            if not rows:
                return {}

            # Keep the newest row per sector.
            seen = {}
            for row in rows:
                if row.sector not in seen:
                    seen[row.sector] = row

            sectors = []
            generated_at = None
            for row in seen.values():
                ts = row.generated_at.isoformat() if row.generated_at else None
                if generated_at is None and ts:
                    generated_at = ts
                sectors.append({
                    "sector": row.sector,
                    "region": row.region,
                    "period": row.period,
                    "D": float(row.diffusion) if row.diffusion is not None else 0.0,
                    "SD": float(row.sentiment) if row.sentiment is not None else 0.0,
                    "AS": float(row.anchor) if row.anchor is not None else 0.0,
                    "momentum": float(row.momentum) if row.momentum is not None else 0.0,
                    "mirror_gap": (
                        float(row.mirror_gap) if row.mirror_gap is not None else None
                    ),
                    "confidence": row.confidence or "low",
                    "n_mentions": int(row.n_mentions) if row.n_mentions is not None else 0,
                    "inputs": row.inputs or {},
                })

            return {"sectors": sectors, "generated_at": generated_at}
        except Exception as e:
            logger.warning(f"[ConditionsReport] DB fallback failed: {e}")
            return {}

    def _build_prompt(self, sectors: list[dict], generated_at: str | None) -> str:
        """Build a neutral LLM prompt from sector index data."""
        lines = [
            "You are an economic analyst writing a neutral, data-focused briefing on current "
            "conditions in the Chinese economy.",
            "",
            f"Index generated at: {generated_at or 'unknown'}",
            f"Sectors covered: {len(sectors)}",
            "",
            "For each sector below, comment on:",
            "- Current diffusion (D): negative = weaker, positive = stronger.",
            "- Momentum vs the previous month.",
            "- Confidence level (low / med / high) and why.",
            "",
            "Then identify the biggest movers (largest absolute change in D or momentum).",
            "",
            "Finally, include a short 'Cross-source triangulation' section. "
            "Compare the official/trade anchor and the mirror-gap where available. "
            "Frame any divergence as a data-quality / nowcasting commentary rather than "
            "accusation. Note when independent or commercial indicators align or depart "
            "from the headline direction.",
            "",
            "Use plain Markdown. Keep the tone neutral, concise, and focused on the numbers.",
            "",
            "--- Sector data ---",
        ]

        for s in sectors:
            inputs = s.get("inputs", {}) or {}
            anchor_source = inputs.get("anchor_source") or "none"
            reported = inputs.get("reported_value")
            mirror = inputs.get("mirror_value")
            lines.append(
                f"\nSector: {s.get('sector')} | Region: {s.get('region', 'unknown')} | "
                f"Period: {s.get('period', 'unknown')}"
            )
            lines.append(
                f"- Diffusion D={s.get('D', 0):.2f}, "
                f"sentiment SD={s.get('SD', 0):.2f}, "
                f"anchor AS={s.get('AS', 0):.2f}, "
                f"momentum={s.get('momentum', 0):.2f}"
            )
            lines.append(
                f"- Confidence={s.get('confidence', 'low')}, "
                f"mentions={s.get('n_mentions', 0)}"
            )
            if s.get("mirror_gap") is not None:
                lines.append(f"- Mirror gap={s.get('mirror_gap'):.2f}%")
            lines.append(f"- Anchor source={anchor_source}")
            if reported is not None:
                lines.append(f"- Reported trade value={reported}")
            if mirror is not None:
                lines.append(f"- Mirror trade value={mirror}")

        return "\n".join(lines)

    def _generate_report(
        self, prompt: str, sectors: list[dict], generated_at: str | None
    ) -> str:
        """Try LLM providers in order; fall back to a rule-based stub."""
        # 1. free_llm_router (async).
        try:
            from free_llm_router import FreeLLMRouter

            router = FreeLLMRouter()
            result = asyncio.run(
                router.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    task_type="briefing",
                    temperature=0.3,
                    max_tokens=2048,
                )
            )
            text = result.get("text", "").strip()
            if text:
                return text
        except Exception as e:
            logger.warning(f"[ConditionsReport] FreeLLMRouter failed: {e}")

        # 2. Anthropic Claude.
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic

                client = anthropic.Anthropic(api_key=api_key)
                message = client.messages.create(
                    model=self.llm_model,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = message.content[0].text.strip()
                if text:
                    return text
            except Exception as e:
                logger.warning(f"[ConditionsReport] Claude API failed: {e}")

        # 3. Ollama local fallback.
        try:
            resp = httpx.post(
                f"{_OLLAMA_URL}/api/generate",
                json={"model": self.ollama_model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                if text:
                    return text
        except Exception as e:
            logger.warning(f"[ConditionsReport] Ollama failed: {e}")

        # 4. Rule-based stub.
        return self._rule_based_report(sectors, generated_at)

    def _rule_based_report(
        self, sectors: list[dict], generated_at: str | None
    ) -> str:
        """Minimal deterministic report when no LLM is available."""
        now = datetime.now(timezone.utc)
        lines = [
            f"# China Economic Conditions Briefing — {now.date().isoformat()}",
            "",
            f"_Index generated at: {generated_at or 'unknown'}_",
            "",
            "## Sector conditions",
        ]

        def _arrow(momentum: float) -> str:
            if momentum > 0.5:
                return "▲ improving"
            if momentum < -0.5:
                return "▼ weakening"
            return "▬ stable"

        for s in sorted(sectors, key=lambda x: abs(x.get("momentum", 0)), reverse=True):
            sector = s.get("sector", "unknown")
            d = s.get("D", 0.0)
            momentum = s.get("momentum", 0.0)
            conf = s.get("confidence", "low")
            gap = s.get("mirror_gap")
            lines.append(
                f"- **{sector}**: D={d:.2f}, momentum={momentum:.2f} {_arrow(momentum)}, "
                f"confidence={conf}"
            )
            if gap is not None:
                lines.append(f"  - Mirror gap: {gap:.2f}%")

        if sectors:
            movers = sorted(sectors, key=lambda x: abs(x.get("momentum", 0)), reverse=True)[:3]
            lines.extend(["", "## Biggest movers"])
            for s in movers:
                lines.append(
                    f"- **{s.get('sector')}**: momentum {s.get('momentum', 0):.2f} "
                    f"(D {s.get('D', 0):.2f})"
                )

        lines.extend(
            [
                "",
                "## Cross-source triangulation",
                "- Compare official/trade anchors with mirror-gap and high-frequency indicators.",
                "- Large mirror gaps may reflect reporting lags, valuation effects, or "
                "transshipment; treat them as nowcasting uncertainty, not proof of revision.",
                "- Where confidence is low, rely on the direction of high-frequency commercial "
                "series and sentiment diffusion rather than point estimates.",
                "",
                "_Report generated by rule-based fallback (no LLM available)._",
            ]
        )
        return "\n".join(lines)

    def _write_report(self, report: str, today) -> tuple[Path, Path]:
        """Write dated report and update latest symlink/file."""
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        date_str = today.isoformat()
        report_path = _REPORT_DIR / f"{date_str}.md"
        latest_path = _REPORT_DIR / "latest.md"
        report_path.write_text(report, encoding="utf-8")
        latest_path.write_text(report, encoding="utf-8")
        return report_path, latest_path

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
        for ch in (
            "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+",
            "-", "=", "|", "{", "}", ".", "!",
        ):
            text = text.replace(ch, f"\\{ch}")
        return text

    def _send_telegram(self, report: str):
        """Send report via Telegram bot (best-effort)."""
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_ALERT_CHAT_ID")
        if not bot_token or not chat_id:
            return

        try:
            escaped = self._escape_markdown(report[:3500])
            httpx.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": f"📊 *China Conditions Report*\n\n{escaped}",
                    "parse_mode": "MarkdownV2",
                },
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"[ConditionsReport] Telegram send failed: {e}")


if __name__ == "__main__":
    # Stand-alone sanity run: generate a report from sample index data.
    sample = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sectors": [
            {
                "sector": "electronics_machinery",
                "region": "coastal_export",
                "period": "2024-05",
                "D": 18.5,
                "SD": 12.0,
                "AS": 22.0,
                "momentum": 4.2,
                "mirror_gap": -8.3,
                "confidence": "high",
                "n_mentions": 42,
                "inputs": {
                    "reported_value": 120_000_000_000.0,
                    "mirror_value": 110_000_000_000.0,
                    "anchor_growth": 0.12,
                    "anchor_source": "trade",
                },
            },
            {
                "sector": "property_construction",
                "region": "national",
                "period": "2024-05",
                "D": -22.1,
                "SD": -18.5,
                "AS": -25.0,
                "momentum": -6.7,
                "mirror_gap": None,
                "confidence": "med",
                "n_mentions": 18,
                "inputs": {"anchor_source": "cn_hf:bdi"},
            },
        ],
    }

    gen = ConditionsReportGenerator()
    prompt = gen._build_prompt(sample["sectors"], sample["generated_at"])
    report = gen._generate_report(prompt, sample["sectors"], sample["generated_at"])
    paths = gen._write_report(report, datetime.now(timezone.utc).date())
    print(report)
    print(f"\n--- wrote: {paths[0]} and {paths[1]} ---")
