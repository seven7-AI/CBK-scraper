"""Scrape Treasury Bills page for 91-, 182-, and 364-day PDF links."""

from __future__ import annotations

import logging
import time
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .config import load_config

logger = logging.getLogger(__name__)

BILLS_URL = "https://www.centralbank.go.ke/bills-bonds/treasury-bills/"

BILLS_TABLES = [
    ("table_2", "91-day"),
    ("table_3", "182-day"),
    ("table_4", "364-day"),
]


def _normalize_href(href: str, base: str) -> str:
    if not href or href.startswith("#"):
        return ""
    return urljoin(base, href).split("#")[0].split("?")[0]


def _collect_links_from_table(page, table_id: str, base_url: str) -> list[str]:
    sel = page.locator(f"#{table_id} tbody td.pdf_link a[href]")
    urls: list[str] = []
    for i in range(sel.count()):
        a = sel.nth(i)
        href = a.get_attribute("href") or ""
        url = _normalize_href(href, base_url)
        if url and (url.lower().endswith(".pdf") or ".pdf" in url.lower()):
            urls.append(url)
    return urls


def scrape_bills(
    base_url: str | None = None,
    page_load_timeout_sec: float = 120,
    delay_between_pages_sec: float = 1.0,
    use_show_all: bool = True,
) -> list[str]:
    """
    Open the Treasury Bills page and collect all PDF URLs from the 91-, 182-,
    and 364-day tables. Returns a deduplicated list.
    """
    cfg = load_config()
    base = base_url or cfg.get("base_url", "https://www.centralbank.go.ke")
    timeout_ms = int(page_load_timeout_sec * 1000)
    seen: set[str] = set()
    all_urls: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            logger.info("Loading bills page: %s", BILLS_URL)
            page.goto(BILLS_URL, wait_until="load", timeout=timeout_ms)
            time.sleep(max(delay_between_pages_sec, 3))

            for table_id, label in BILLS_TABLES:
                if use_show_all:
                    try:
                        length_sel = page.locator(
                            f'select[name="{table_id}_length"], select[aria-controls="{table_id}"]'
                        ).first
                        if length_sel.count() > 0:
                            length_sel.select_option(value="-1")
                            time.sleep(1.2)
                            logger.info("Selected 'All' for %s table", label)
                    except Exception as e:
                        logger.debug("Could not select All for %s: %s", label, e)

                urls = _collect_links_from_table(page, table_id, base)
                for u in urls:
                    if u not in seen:
                        seen.add(u)
                        all_urls.append(u)
                logger.info("Bills %s: collected %d links (total unique %d)", label, len(urls), len(all_urls))

                if len(urls) < 20:
                    next_btn = page.locator(f"#{table_id}_paginate a.paginate_button.next:not(.disabled)")
                    while next_btn.count() > 0:
                        next_btn.first.click()
                        time.sleep(delay_between_pages_sec)
                        urls = _collect_links_from_table(page, table_id, base)
                        for u in urls:
                            if u not in seen:
                                seen.add(u)
                                all_urls.append(u)
                        next_btn = page.locator(f"#{table_id}_paginate a.paginate_button.next:not(.disabled)")
        except PlaywrightTimeout as e:
            logger.warning("Bills page timeout: %s", e)
        finally:
            browser.close()

    return all_urls
