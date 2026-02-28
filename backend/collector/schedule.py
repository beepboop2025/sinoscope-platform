from celery.schedules import crontab

from collector.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # Every 60 seconds
    "fetch-forex": {
        "task": "collector.tasks.forex.fetch_forex",
        "schedule": 60.0,
    },
    "fetch-crypto-markets": {
        "task": "collector.tasks.crypto.fetch_crypto_markets",
        "schedule": 60.0,
    },
    # Every 2 minutes
    "fetch-crypto-global": {
        "task": "collector.tasks.crypto.fetch_crypto_global",
        "schedule": 120.0,
    },
    # Every 5 minutes
    "fetch-fear-greed": {
        "task": "collector.tasks.sentiment.fetch_fear_greed",
        "schedule": 300.0,
    },
    "fetch-economic": {
        "task": "collector.tasks.economic.fetch_economic",
        "schedule": 300.0,
    },
    "fetch-cny-rates": {
        "task": "collector.tasks.china.fetch_cny_rates",
        "schedule": 300.0,
    },
    # Every 10 minutes
    "fetch-bonds": {
        "task": "collector.tasks.bonds.fetch_bonds",
        "schedule": 600.0,
    },
    "fetch-commodities": {
        "task": "collector.tasks.commodities.fetch_commodities",
        "schedule": 600.0,
    },
    # Every 15 minutes
    "fetch-defi": {
        "task": "collector.tasks.defi.fetch_defi",
        "schedule": 900.0,
    },
    # Every 30 minutes
    "fetch-news": {
        "task": "collector.tasks.news.fetch_news",
        "schedule": 1800.0,
    },
    "fetch-reddit": {
        "task": "collector.tasks.sentiment.fetch_reddit",
        "schedule": 1800.0,
    },
    # Every 60 minutes
    "fetch-stocks": {
        "task": "collector.tasks.stocks.fetch_stocks",
        "schedule": crontab(minute=0),
    },
    "fetch-github": {
        "task": "collector.tasks.research.fetch_github",
        "schedule": crontab(minute=0),
    },
    "fetch-huggingface": {
        "task": "collector.tasks.research.fetch_huggingface",
        "schedule": crontab(minute=0),
    },
    "fetch-sec": {
        "task": "collector.tasks.research.fetch_sec",
        "schedule": crontab(minute=0),
    },
    "fetch-arxiv": {
        "task": "collector.tasks.research.fetch_arxiv",
        "schedule": crontab(minute=0),
    },
    # Every 6 hours
    "fetch-worldbank": {
        "task": "collector.tasks.china.fetch_worldbank",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "fetch-forex-timeseries": {
        "task": "collector.tasks.forex.fetch_forex_timeseries",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "fetch-crypto-trending": {
        "task": "collector.tasks.crypto.fetch_trending_coins",
        "schedule": crontab(minute=0, hour="*/6"),
    },
}
