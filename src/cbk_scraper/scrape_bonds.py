"""Scrape Treasury Bonds page for PDF links (paginated table)."""

from __future__ import annotations

import logging
import time
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .config import load_config, get_paths

logger = logging.getLogger(__name__)

BONDS_URL = "https://www.centralbank.go.ke/bills-bonds/treasury-bonds/"


def _normalize_href(href: str, base: str) -> str:
    if not href or href.startswith("#"):
        return ""
    return urljoin(base, href).split("#")[0].split("?")[0]


def scrape_bonds(
    base_url: str | None = None,
    page_load_timeout_sec: float = 120,
    delay_between_pages_sec: float = 1.0,
    use_show_all: bool = True,
) -> list[str]:
    """
    Open the Treasury Bonds page and collect all PDF URLs from the results table.
    Uses either "Show All" if available or pagination (Next).
    """
    cfg = load_config()
    paths = get_paths(cfg)
    base = base_url or cfg.get("base_url", "https://www.centralbank.go.ke")
    timeout_ms = int(page_load_timeout_sec * 1000)
    seen: set[str] = set()
    all_urls: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            logger.info("Loading bonds page: %s", BONDS_URL)
            page.goto(BONDS_URL, wait_until="load", timeout=timeout_ms)
            time.sleep(max(delay_between_pages_sec, 3))

            if use_show_all:
                try:
                    sel = page.locator('select[name*="length"], select[aria-controls*="table"]').first
                    if sel.count() > 0:
                        sel.select_option(value="-1")
                        time.sleep(1.5)
                        logger.info("Selected 'All' entries for bonds table")
                except Exception as e:
                    logger.debug("Could not select All for bonds: %s", e)

            links = page.locator("table td.pdf_link a[href]")
            n = links.count()
            for i in range(n):
                a = links.nth(i)
                href = a.get_attribute("href") or ""
                url = _normalize_href(href, base)
                if url and url not in seen and (url.lower().endswith(".pdf") or ".pdf" in url.lower()):
                    seen.add(url)
                    all_urls.append(url)
            logger.info("Bonds: collected %d PDF URLs from table", len(all_urls))

            if len(all_urls) < 5:
                next_btn = page.locator(".dataTables_paginate a.paginate_button.next:not(.disabled)")
                while next_btn.count() > 0:
                    next_btn.first.click()
                    time.sleep(delay_between_pages_sec)
                    links = page.locator("table td.pdf_link a[href]")
                    for i in range(links.count()):
                        a = links.nth(i)
                        href = a.get_attribute("href") or ""
                        url = _normalize_href(href, base)
                        if url and url not in seen and (url.lower().endswith(".pdf") or ".pdf" in url.lower()):
                            seen.add(url)
                            all_urls.append(url)
                    next_btn = page.locator(".dataTables_paginate a.paginate_button.next:not(.disabled)")
        except PlaywrightTimeout as e:
            logger.warning("Bonds page timeout: %s", e)
        finally:
            browser.close()

    return all_urls
