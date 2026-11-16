from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


PAGE_URL = (Path(__file__).resolve().parents[2] / "apps" / "tour_booking" / "index.html").as_uri()


@pytest.mark.integration
def test_tour_page_layout_and_static_form_behavior():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        navigations = []
        page.on("framenavigated", lambda frame: navigations.append(frame.url) if frame == page.main_frame else None)
        page.goto(PAGE_URL)

        assert page.locator('[data-testid="booking-form"]').count() == 1
        assert page.locator('[data-testid="book-now-btn"]').count() == 1
        panel_selectors = [
            '[data-testid="tour-summary-card"]',
            '[data-testid="brochure-card"]',
            '[data-testid="support-card"]',
        ]
        assert [page.locator(selector).get_attribute("data-testid") for selector in panel_selectors] == [
            "tour-summary-card", "brochure-card", "support-card"
        ]
        assert [page.locator(selector + " h2").inner_text() for selector in panel_selectors] == [
            "Tour Summary", "Download Brochure", "Support"
        ]
        desktop_top = [page.locator(selector).bounding_box()["y"] for selector in panel_selectors]
        assert desktop_top == sorted(desktop_top)

        button = page.locator('[data-testid="download-brochure-btn"]')
        assert button.is_enabled()
        assert page.get_by_text("(Demo file generated in-browser)").is_visible()
        assert page.locator('[data-testid="brochure-error"]').is_hidden()

        initial_url = page.url
        page.locator('[data-testid="book-now-btn"]').click()
        assert page.url == initial_url
        assert navigations == [initial_url]

        page.set_viewport_size({"width": 390, "height": 844})
        mobile_top = [page.locator(selector).bounding_box()["y"] for selector in panel_selectors]
        assert mobile_top == sorted(mobile_top)
        browser.close()


@pytest.mark.integration
def test_brochure_download_metadata_filename_and_delayed_revocation():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.add_init_script("""
          (() => {
            const createUrl = URL.createObjectURL.bind(URL);
            const revokeUrl = URL.revokeObjectURL.bind(URL);
            const anchorClick = HTMLAnchorElement.prototype.click;
            window.__brochureProbe = {};
            URL.createObjectURL = (blob) => {
              window.__brochureProbe.mime = blob.type;
              return createUrl(blob);
            };
            URL.revokeObjectURL = (url) => {
              window.__brochureProbe.revokedAt = performance.now();
              window.__brochureProbe.revokedUrl = url;
              return revokeUrl(url);
            };
            HTMLAnchorElement.prototype.click = function () {
              window.__brochureProbe.clickedAt = performance.now();
              window.__brochureProbe.filename = this.download;
              return anchorClick.call(this);
            };
          })();
        """)
        page.goto(PAGE_URL)
        popups = []
        page.on("popup", lambda popup: popups.append(popup))
        with page.expect_download() as download_info:
            page.locator('[data-testid="download-brochure-btn"]').click()
        download = download_info.value
        assert download.suggested_filename == "tour-brochure.pdf"
        page.wait_for_function("window.__brochureProbe.revokedAt !== undefined")
        probe = page.evaluate("window.__brochureProbe")
        assert probe["mime"] == "application/pdf"
        assert probe["filename"] == "tour-brochure.pdf"
        assert probe["revokedUrl"].startswith("blob:")
        assert probe["revokedAt"] - probe["clickedAt"] >= 90
        assert popups == []
        browser.close()


@pytest.mark.integration
def test_simulated_error_clears_before_retry_and_preserves_helper_text():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.add_init_script("""
          const originalGet = URLSearchParams.prototype.get;
          window.__errorWasPresentAtGeneration = null;
          URLSearchParams.prototype.get = function (name) {
            if (name === 'simulate_error') {
              window.__errorWasPresentAtGeneration =
                Boolean(document.querySelector('[data-testid="brochure-error"]').textContent);
            }
            return originalGet.call(this, name);
          };
        """)
        page.goto(PAGE_URL + "?simulate_error=true")
        button = page.locator('[data-testid="download-brochure-btn"]')
        error = page.locator('[data-testid="brochure-error"]')
        button.click()
        assert error.is_visible()
        assert error.get_attribute("role") == "alert"
        assert error.inner_text() == "Unable to generate brochure (demo)"
        assert page.get_by_text("(Demo file generated in-browser)").is_visible()

        button.click()
        assert page.evaluate("window.__errorWasPresentAtGeneration") is False
        assert error.is_visible()
        assert error.inner_text() == "Unable to generate brochure (demo)"
        browser.close()
