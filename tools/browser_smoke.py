"""Browser checks against tools/review_server.py, never the hosted application.

python tools/review_server.py  # terminal 1
python tools/browser_smoke.py # terminal 2; install Playwright's Chromium first
"""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE_URL", "http://127.0.0.1:8765")


def run():
    with sync_playwright() as playwright:
        options = {"headless": True}
        if os.environ.get("QA_CHROMIUM_PATH"):
            options["executable_path"] = os.environ["QA_CHROMIUM_PATH"]
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        import json
        context.add_init_script("localStorage.setItem('sasthosetu.apiBase', " +
                                json.dumps(BASE + "/api/v1") + ");")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE + "/login.html")
        page.locator("#loginEmail").fill("patient@qa.example")
        page.locator("#loginPassword").fill("BrowserDemo123!")
        page.locator("#loginBtn").click()
        page.wait_for_url(lambda url: "login.html" not in str(url))

        def sign_in(name):
            page.goto(BASE + "/index.html")
            page.evaluate("""async name => {
              const {api} = await import('./assets/js/api.js');
              await api.login(name + '@qa.example', 'BrowserDemo123!');
            }""", name)

        page.goto(BASE + "/account.html")
        page.locator("#careAccess button[data-doctor]").wait_for()
        consent_button = page.locator("#careAccess button[data-doctor]").first
        if consent_button.get_attribute("data-granted") == "true":
            consent_button.click()
            page.wait_for_function("document.querySelector('#careAccess button')?.dataset.granted === 'false'")
        consent_button.click()
        page.wait_for_function("document.querySelector('#careAccess button')?.dataset.granted === 'true'")
        page.locator("#verifyEmail").click()
        page.wait_for_function("document.getElementById('verifyStatus').textContent.length > 0")

        page.goto(BASE + "/labs.html")
        page.locator("button[data-id='qa-cbc']").wait_for()
        page.locator("button[data-id='qa-cbc']").click()
        page.wait_for_url("**/records.html")
        page.locator("#labsTab").click()
        page.get_by_text("Complete Blood Count", exact=True).first.wait_for()
        page.locator("button[data-consent]").first.click()
        page.locator("button[data-pay-lab]").first.click()
        page.locator("#labPaymentSimulator button[data-status='COMPLETED']").click()
        page.wait_for_function("document.getElementById('labPaymentSimulator').textContent === 'DEMO: COMPLETED'")

        sign_in("operator")
        page.goto(BASE + "/provider.html")
        page.locator("#provider option[value='qa-lab']").wait_for(state="attached")
        page.locator("#provider").select_option("qa-lab")
        page.locator("button[data-result]").first.wait_for()
        page.locator("button[data-result]").first.click()
        page.locator("#summary").fill("QA result: normal blood count")
        page.locator("#resultForm button").click()
        page.get_by_text("QA result: normal blood count", exact=True).first.wait_for()

        sign_in("patient")
        page.goto(BASE + "/records.html")
        page.locator("#labsTab").click()
        page.get_by_text("QA result: normal blood count", exact=True).first.wait_for()
        # No private API responses may enter the worker's unscoped cache.
        page.evaluate("navigator.serviceWorker.ready")
        count = page.evaluate("""async () => {
          let count = 0;
          for (const name of await caches.keys()) {
            for (const req of await (await caches.open(name)).keys()) {
              if (new URL(req.url).pathname.includes('/api/v1/')) count++;
            }
          }
          return count;
        }""")
        assert count == 0, "Private responses leaked to the worker cache"
        page.evaluate("""async () => {
          const {queue, session} = await import('./assets/js/api.js');
          await queue.add({ path: '/users/me', method: 'PATCH', body: {full_name: 'secret-marker'} }, session.token);
        }""")
        raw_storage = page.evaluate("JSON.stringify({...localStorage})")
        assert "secret-marker" not in raw_storage, "Queue is stored as plaintext"
        context.set_offline(True)
        page.evaluate("""async () => {
          const {api} = await import('./assets/js/api.js'); await api.logout();
        }""")
        context.set_offline(False)
        sign_in("other")
        identity = page.evaluate("""async () => {
          const {api, queue, flushQueue} = await import('./assets/js/api.js');
          await flushQueue(); return {me: await api.get('/auth/me'), size: queue.size};
        }""")
        assert identity["size"] == 0
        assert identity["me"]["full_name"] != "secret-marker", "Previous account's write replayed"

        # A failed identity lookup must not leave a usable token paired with
        # the preceding account's locally cached profile.
        rejected = page.evaluate("""async () => {
          const {api, session} = await import('./assets/js/api.js');
          const originalFetch = window.fetch;
          window.fetch = (url, ...args) => String(url).endsWith('/auth/me')
            ? Promise.reject(new TypeError('Simulated identity network failure'))
            : originalFetch(url, ...args);
          try { await api.login('patient@qa.example', 'BrowserDemo123!'); return false; }
          catch { return !session.token && !session.user; }
          finally { window.fetch = originalFetch; }
        }""")
        assert rejected, "Failed login identity lookup retained a prior identity"

        sign_in("doctor")
        for path in ["doctor.html", "doctor-schedule.html", "consultations.html"]:
            page.goto(BASE + "/" + path)
            page.locator("main").wait_for()
        sign_in("admin")
        page.goto(BASE + "/admin.html")
        page.locator("#loadOutbox").click()
        page.locator("#outbox a").first.wait_for()
        verify_link = page.locator("#outbox a").first.get_attribute("href")
        page.goto(BASE + "/" + verify_link)
        page.locator("#submit").click()
        page.wait_for_function("document.getElementById('result').textContent === 'Email verified.'")
        for path in ["labs.html", "provider.html", "account-action.html"]:
            page.goto(BASE + "/" + path)
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            assert not overflow, f"Mobile horizontal overflow: {path}"
        # Translation toggle remains usable on a desktop viewport too.
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(BASE + "/account.html")
        page.locator("#langBtn").click()
        page.locator("#profileName").wait_for()
        Path(".tmp").mkdir(exist_ok=True)
        page.screenshot(path=".tmp/browser-smoke.png", full_page=True)
        assert not errors, "Browser script errors: " + repr(errors)
        browser.close()
    print("Browser checks passed: login, consent, labs, operator report, email verification, "
          "encrypted queue, cross-account isolation, portals, mobile layout and language toggle.")


if __name__ == "__main__":
    run()
