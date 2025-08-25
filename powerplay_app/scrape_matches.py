# file: powerplay_app/fetch_results_playwright.py
"""Playwright-based network capture for league match data.

Opens the league schedule page in Chromium, listens to responses whose URL
contains ``"api/matches"``, parses their JSON payloads, and returns a list of
match dictionaries. All console output remains **Czech** for operators.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import sync_playwright


# --- Public API ------------------------------------------------------------

def fetch_results_playwright(
    season: str = "2025-2026",
    *,
    url: str = "https://nocnihokejovaliga.cz/schedule",
    headless: bool = False,
    wait_ms: int = 7000,
    log: bool = True,
) -> list[dict[str, Any]]:
    """Fetch match results by observing network responses via Playwright.

    Navigates to the schedule page and collects data from any response URL
    containing ``"api/matches"``. Handles either a top-level list or an object
    with a ``"matches"`` key.

    Args:
        season: Season label used only for logging/compatibility.
        url: Page URL to visit (defaults to the league schedule).
        headless: Whether to run Chromium headlessly. ``False`` by default.
        wait_ms: Milliseconds to wait after navigation for API calls to finish.
        log: If ``True``, print Czech diagnostic messages.

    Returns:
        List of match dictionaries (may be empty if nothing was captured).

    Notes:
        ``season`` is not used to filter the page; it is retained for backwards
        compatibility and logging semantics.
    """

    if log:
        print("🔍 Spouštím Playwright…")

    matches: list[dict[str, Any]] = []

    def handle_response(response: Any) -> None:
        """Capture and parse responses resembling the matches endpoint.

        Defensive by design: any parsing/network errors are logged (if enabled)
        and ignored so that a single bad response does not abort the run.
        """
        try:
            resp_url = getattr(response, "url", "")
            if log:
                print("📡 Odpověď:", resp_url)
            if "api/matches" not in resp_url:
                return

            try:
                data = response.json()
            except Exception as e:  # network/JSON decoding issues
                if log:
                    print("❌ Chyba při dekódování JSON:", e)
                return

            if log:
                print("📦 Obsah odpovědi:", data)

            if isinstance(data, list):
                if log:
                    print(f"✅ Načteno {len(data)} zápasů")
                matches.extend(data)  # type: ignore[arg-type]
            elif isinstance(data, dict) and "matches" in data:
                rows = data.get("matches") or []
                if log:
                    print(f"✅ Načteno {len(rows)} zápasů")
                if isinstance(rows, list):
                    matches.extend(rows)  # type: ignore[arg-type]
                else:
                    if log:
                        print("⚠️ Neočekávaný formát: 'matches' není seznam")
            else:
                if log:
                    print("⚠️ Neočekávaný formát odpovědi")
        except Exception as e:
            if log:
                print("⚠️ Chyba ve zpracování odpovědi:", e)

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            page.on("response", handle_response)

            # Navigate and allow time for XHR/fetch calls to happen.
            page.goto(url)
            page.wait_for_timeout(wait_ms)
        finally:
            if browser is not None:
                browser.close()

    if log:
        print(f"📊 Celkem načteno: {len(matches)} zápasů")

    return matches
