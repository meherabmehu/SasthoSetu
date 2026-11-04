"""Keyboard navigation checks using only tools/review_server.py's synthetic users."""
import json
import os
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE_URL", "http://127.0.0.1:8765").rstrip("/")


def run():
    if urlparse(BASE).hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Run against the local disposable fixture only")
    with sync_playwright() as playwright:
        options = {"headless": True}
        if os.environ.get("QA_CHROMIUM_PATH"):
            options["executable_path"] = os.environ["QA_CHROMIUM_PATH"]
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        context.add_init_script("localStorage.setItem('sasthosetu.apiBase', " + json.dumps(BASE + "/api/v1") + ");")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE + "/login.html")
        for door, first, second, panel in [("doorPatient", "tabLogin", "tabRegister", "registerPanel"),
                                           ("doorDoctor", "dTabLogin", "dTabRegister", "dRegisterPanel")]:
            page.locator("#" + door).click()
            page.locator("#" + first).focus()
            page.keyboard.press("ArrowRight")
            assert page.locator("#" + second).get_attribute("aria-selected") == "true"
            assert page.locator("#" + panel).is_visible()
            assert page.locator("#" + first).get_attribute("tabindex") == "-1"
            page.keyboard.press("Home")
            assert page.locator("#" + first).get_attribute("aria-selected") == "true"
        page.locator("#navToggle").click()
        assert page.locator("#navToggle").get_attribute("aria-expanded") == "true"
        page.keyboard.press("Escape")
        assert page.locator("#navToggle").get_attribute("aria-expanded") == "false"
        assert page.locator("#navToggle").evaluate("el => el === document.activeElement")

        def sign_in(role):
            page.goto(BASE + "/index.html")
            page.evaluate("""async role => {
              const {api} = await import('./assets/js/api.js');
              await api.login(role + '@qa.example', 'BrowserDemo123!');
            }""", role)

        def check_dialog(initial, first, last, opener):
            page.locator('[role="dialog"]').wait_for()
            page.wait_for_function("id => document.activeElement.id === id", arg=initial)
            page.locator("#" + last).focus()
            page.keyboard.press("Tab")
            assert page.evaluate("id => document.activeElement.id === id", first)
            page.keyboard.press("Shift+Tab")
            assert page.evaluate("id => document.activeElement.id === id", last)
            page.keyboard.press("Escape")
            page.locator('[role="dialog"]').wait_for(state="detached")
            page.wait_for_function("selector => document.activeElement.matches(selector)", arg=opener)

        sign_in("patient")
        page.goto(BASE + "/doctors.html")
        page.locator('.bookBtn[data-doctor="qa-doctor"]:enabled').click()
        check_dialog("bReason", "bDate", "cancelBtn", '.bookBtn[data-doctor="qa-doctor"]')
        # A second close via a button must also remove the keyboard listener.
        page.locator('.bookBtn[data-doctor="qa-doctor"]').click()
        page.locator("#cancelBtn").click()
        assert page.locator('.bookBtn[data-doctor="qa-doctor"]').evaluate("el => el === document.activeElement")
        sign_in("doctor")
        page.goto(BASE + "/doctor.html")
        page.locator('.openBtn[data-id="qa-appointment"]').click()
        check_dialog("complaint", "closeBtn", "closeConsultBtn", '.openBtn[data-id="qa-appointment"]')
        assert not errors, repr(errors)
        browser.close()
    print("Keyboard checks passed: patient/doctor tabs, mobile menu, booking and consultation focus traps, Escape and restored focus.")


if __name__ == "__main__":
    run()
