import logging
import time
from urllib.parse import quote

from lxml import etree

from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, save_data, safe_fetch

logger = logging.getLogger(__name__)

FINANCE_QUERIES = [
    "topic:finance topic:trading",
    "topic:cryptocurrency topic:trading-bot",
    "topic:quantitative-finance",
    "topic:stock-market topic:python",
    "topic:algorithmic-trading",
]

HF_SEARCHES = [
    "financial-sentiment",
    "stock-prediction",
    "finance-text-classification",
    "market-analysis",
    "trading",
]

ARXIV_QUERIES = [
    "algorithmic trading machine learning",
    "portfolio optimization deep learning",
    "financial sentiment analysis NLP",
    "cryptocurrency market prediction",
]

SEC_FORMS = "10-K,10-Q,8-K"


@celery_app.task(name="collector.tasks.research.fetch_github")
def fetch_github():
    all_repos = []
    seen_ids = set()

    for query in FINANCE_QUERIES:
        if not can_request("github"):
            break
        consume_token("github")
        try:
            resp = safe_fetch(
                f"https://api.github.com/search/repositories?q={quote(query)}&sort=stars&order=desc&per_page=30",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            data = resp.json()
            for r in data.get("items") or []:
                rid = r.get("id")
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                all_repos.append({
                    "id": rid,
                    "name": r.get("full_name", ""),
                    "description": (r.get("description") or "")[:200],
                    "stars": r.get("stargazers_count", 0),
                    "forks": r.get("forks_count", 0),
                    "language": r.get("language") or "",
                    "topics": (r.get("topics") or [])[:5],
                    "url": r.get("html_url", ""),
                    "updated": r.get("updated_at", ""),
                    "openIssues": r.get("open_issues_count", 0),
                    "license": (r.get("license") or {}).get("spdx_id", "") or "",
                })
        except Exception as e:
            logger.error(f"[GITHUB] Query '{query}' error: {e}")
        time.sleep(2)

    all_repos.sort(key=lambda r: r.get("stars", 0), reverse=True)
    top = all_repos[:50]
    if top:
        save_data("github_repos", top, ttl=3600)
        logger.info(f"[GITHUB] Updated: {len(top)} repos")
    else:
        logger.warning("[GITHUB] No repos fetched")


@celery_app.task(name="collector.tasks.research.fetch_huggingface")
def fetch_huggingface():
    all_models = []
    seen_ids = set()

    for search in HF_SEARCHES:
        if not can_request("huggingface"):
            break
        consume_token("huggingface")
        try:
            resp = safe_fetch(
                f"https://huggingface.co/api/models?search={quote(search)}&sort=downloads&direction=-1&limit=20"
            )
            data = resp.json()
            for m in data or []:
                mid = m.get("modelId", "")
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)
                all_models.append({
                    "id": mid,
                    "name": mid,
                    "pipeline": m.get("pipeline_tag") or "",
                    "downloads": m.get("downloads", 0),
                    "likes": m.get("likes", 0),
                    "tags": (m.get("tags") or [])[:8],
                    "lastModified": m.get("lastModified", ""),
                    "library": m.get("library_name") or "",
                    "isPrivate": m.get("private", False),
                })
        except Exception as e:
            logger.error(f"[HUGGINGFACE] Search '{search}' error: {e}")
        time.sleep(1)

    all_models.sort(key=lambda m: m.get("downloads", 0), reverse=True)
    top = all_models[:50]
    if top:
        save_data("huggingface_models", top, ttl=3600)
        logger.info(f"[HUGGINGFACE] Updated: {len(top)} models")
    else:
        logger.warning("[HUGGINGFACE] No models fetched")


@celery_app.task(name="collector.tasks.research.fetch_sec")
def fetch_sec():
    from datetime import datetime, timedelta

    if not can_request("sec"):
        return
    consume_token("sec")
    try:
        end = datetime.utcnow().strftime("%Y-%m-%d")
        start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        resp = safe_fetch(
            f"https://efts.sec.gov/LATEST/search-index?q={quote('quarterly earnings')}"
            f"&dateRange=custom&startdt={start}&enddt={end}&forms={SEC_FORMS}",
            headers={"User-Agent": "DragonScope research@example.com"},
        )
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        filings = []
        for h in hits[:30]:
            s = h.get("_source", {})
            filings.append({
                "id": h.get("_id", ""),
                "company": (s.get("display_names") or [""])[0] or s.get("entity_name", ""),
                "ticker": (s.get("tickers") or [""])[0],
                "form": s.get("form_type", ""),
                "filed": s.get("file_date", ""),
                "description": s.get("display_description") or s.get("file_description", ""),
                "url": f"https://www.sec.gov/Archives/{s.get('file_url', '')}" if s.get("file_url") else "",
            })
        if filings:
            save_data("sec_filings", filings, ttl=3600)
            logger.info(f"[SEC] Updated: {len(filings)} filings")
        else:
            logger.warning("[SEC] No filings found")
    except Exception as e:
        logger.error(f"[SEC] Error: {e}")


@celery_app.task(name="collector.tasks.research.fetch_arxiv")
def fetch_arxiv():
    all_papers = []
    seen_ids = set()

    for query in ARXIV_QUERIES:
        if not can_request("arxiv"):
            break
        consume_token("arxiv")
        try:
            search_q = quote(f"cat:q-fin* OR all:{query}")
            resp = safe_fetch(
                f"https://export.arxiv.org/api/query?search_query={search_q}"
                f"&start=0&max_results=20&sortBy=submittedDate&sortOrder=descending",
                timeout=20.0,
            )
            root = etree.fromstring(resp.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                arxiv_id = (entry.findtext("atom:id", "", ns) or "").strip()
                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)

                title = " ".join((entry.findtext("atom:title", "", ns) or "").split())
                summary = " ".join((entry.findtext("atom:summary", "", ns) or "").split())[:300]
                published = (entry.findtext("atom:published", "", ns) or "")[:10]
                authors = [
                    a.findtext("atom:name", "", ns)
                    for a in entry.findall("atom:author", ns)[:3]
                ]
                categories = [
                    c.get("term", "")
                    for c in entry.findall("atom:category", ns)[:3]
                ]
                pdf_url = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_url = link.get("href", "")
                        break

                all_papers.append({
                    "id": arxiv_id,
                    "title": title,
                    "summary": summary,
                    "authors": authors,
                    "categories": categories,
                    "published": published,
                    "pdfUrl": pdf_url,
                    "url": arxiv_id,
                })
        except Exception as e:
            logger.error(f"[ARXIV] Query '{query}' error: {e}")
        time.sleep(3.5)

    all_papers.sort(key=lambda p: p.get("published", ""), reverse=True)
    top = all_papers[:50]
    if top:
        save_data("arxiv_papers", top, ttl=3600)
        logger.info(f"[ARXIV] Updated: {len(top)} papers")
    else:
        logger.warning("[ARXIV] No papers fetched")
