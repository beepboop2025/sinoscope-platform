from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "dragonscope_collector",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "collector.tasks.forex",
        "collector.tasks.crypto",
        "collector.tasks.stocks",
        "collector.tasks.bonds",
        "collector.tasks.commodities",
        "collector.tasks.economic",
        "collector.tasks.news",
        "collector.tasks.defi",
        "collector.tasks.sentiment",
        "collector.tasks.research",
        "collector.tasks.china",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_soft_time_limit=120,
    task_time_limit=180,
)
