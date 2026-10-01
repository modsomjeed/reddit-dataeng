"""Capture README screenshots of the running stack with headless Chromium (run by `make screenshots`).

Runs inside the Playwright Docker image and reaches the services through host.docker.internal.
Credentials come from the environment (the local .env and the Airflow dev login), never from the repo.
"""

import logging
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

HOST = os.environ.get("SCREENSHOT_HOST", "host.docker.internal")
OUT = Path(__file__).resolve().parent.parent / "docs" / "images"
VIEWPORT = {"width": 1440, "height": 900}

log = logging.getLogger("screenshots")


def save(page: Page, name: str, full_page: bool = False) -> None:
    path = OUT / name
    page.screenshot(path=str(path), full_page=full_page)
    log.info("saved %s", path.relative_to(OUT.parent.parent))


def dashboard(page: Page) -> None:
    page.goto(f"http://{HOST}:8501/", wait_until="networkidle")
    page.get_by_text("Compare tools over time").wait_for(timeout=60_000)
    # Vega charts render after the page settles
    page.wait_for_timeout(4_000)
    save(page, "dashboard-overview.png")
    # Streamlit scrolls inside its own container, so grow the viewport to the content height
    height = page.evaluate("document.querySelector('[data-testid=\"stMain\"]').scrollHeight")
    page.set_viewport_size({"width": VIEWPORT["width"], "height": height})
    page.wait_for_timeout(3_000)
    save(page, "dashboard-full.png")


def airflow(page: Page) -> None:
    base = f"http://{HOST}:{os.environ.get('AIRFLOW_PORT', '8082')}"
    page.goto(f"{base}/auth/login/", wait_until="networkidle")
    page.fill("#username", os.environ.get("AIRFLOW_USER", "airflow"))
    page.fill("#password", os.environ.get("AIRFLOW_PASSWORD", "airflow"))
    page.click("input[type=submit]")
    page.wait_for_url(lambda url: "login" not in url)
    page.wait_for_load_state("networkidle")
    for dag in ("reddit_ingest", "reddit_dbt"):
        page.goto(f"{base}/dags/{dag}", wait_until="networkidle")
        page.wait_for_timeout(3_000)
        save(page, f"airflow-{dag}.png")


def rustfs(page: Page) -> None:
    port = os.environ.get("RUSTFS_CONSOLE_PORT", "9001")
    page.goto(f"http://{HOST}:{port}/rustfs/console/", wait_until="networkidle")
    inputs = page.locator("input")
    if inputs.count() >= 2:
        inputs.nth(0).fill(os.environ["RUSTFS_ACCESS_KEY"])
        inputs.nth(1).fill(os.environ["RUSTFS_SECRET_KEY"])
        page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle")
    # let the "Login Success" toast fade out
    page.wait_for_timeout(6_000)
    save(page, "rustfs-console.png")


def mailpit(page: Page) -> None:
    # run `make alert-test` and `make digest-test` first so the inbox has one of each
    for name, subject in (("mailpit-alert.png", "failed"), ("mailpit-digest.png", "digest")):
        page.goto(f"http://{HOST}:{os.environ.get('MAILPIT_PORT', '8025')}/", wait_until="networkidle")
        page.locator(".message", has_text=subject).first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2_000)
        save(page, name)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        shots = (dashboard, airflow, rustfs, mailpit)
        # optional names on the command line pick a subset, e.g. `python scripts/screenshots.py mailpit`
        wanted = set(sys.argv[1:])
        for shoot in (s for s in shots if not wanted or s.__name__ in wanted):
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
            try:
                shoot(page)
            except Exception:
                log.exception("could not capture %s", shoot.__name__)
            finally:
                page.close()
        browser.close()


if __name__ == "__main__":
    main()
