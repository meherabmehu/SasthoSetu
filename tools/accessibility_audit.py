"""WCAG/keyboard checks against the isolated review_server.py fixture only.

Install the pinned engine with npm ci --prefix tools/a11y --ignore-scripts.
Requires Playwright Chromium (or QA_CHROMIUM_PATH). No hosted site is contacted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = {"index.html", "login.html", "doctor-login.html", "staff-portal.html",
          "account-action.html", "verify.html", "offline.html"}
DOCTOR = {"doctor.html", "doctor-schedule.html"}


def run(base, engine, output):
    if urlparse(base).hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Use the disposable local review server, not a hosted service")
    engine = Path(engine)
    if not engine.is_file():
        raise FileNotFoundError("Install axe-core: npm ci --prefix tools/a11y --ignore-scripts")
    results = []
    pages = sorted(path.name for path in (ROOT / "frontend").glob("*.html"))
    with sync_playwright() as playwright:
        options = {"headless": True}
        if os.environ.get("QA_CHROMIUM_PATH"):
            options["executable_path"] = os.environ["QA_CHROMIUM_PATH"]
        browser = playwright.chromium.launch(**options)

        def capture(page, name, role, language, viewport, theme, state="initial"):
            page.add_script_tag(path=str(engine))
            findings = page.evaluate("""async () => {
              const report = await axe.run(document, {
                runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}
              });
              return {version: axe.version, violations: report.violations,
                      incomplete: report.incomplete, passes: report.passes.length};
            }""")
            results.append({"page": name, "role": role, "language": language,
                            "viewport": viewport, "theme": theme, "state": state, **findings})
            print(f"{theme}/{language}/{role}/{name}/{state}: " +
                  ", ".join(rule["id"] for rule in findings["violations"]), flush=True)
        for language, viewport, theme in [
            (language, viewport, theme) for theme in ["light", "dark"]
            for language, viewport in [("bn", {"width": 390, "height": 844}),
                                       ("en", {"width": 1440, "height": 900})]
        ]:
            for role in ["public", "patient", "doctor", "admin", "operator"]:
                targets = [name for name in pages if (
                    (role == "public" and name in PUBLIC)
                    or (role == "doctor" and name in DOCTOR)
                    or (role == "admin" and name in {"admin.html", "provider.html"})
                    or (role == "operator" and name == "provider.html")
                    or (role == "patient" and name not in PUBLIC | DOCTOR | {"admin.html", "provider.html"}))]
                context = browser.new_context(viewport=viewport, reduced_motion="reduce")
                # Deliberately test the offline font fallback; no external traffic.
                context.route("**/*", lambda route: route.continue_()
                              if route.request.url.startswith(base + "/") else route.abort())
                context.add_init_script("localStorage.setItem('sasthosetu.apiBase', " +
                    json.dumps(base + "/api/v1") + ");localStorage.setItem('sasthosetu.lang', " +
                    json.dumps(language) + ");localStorage.setItem('sasthosetu.theme', " +
                    json.dumps(theme) + ");")
                page = context.new_page()
                page.goto(base + "/index.html", wait_until="networkidle")
                if role != "public":
                    page.evaluate("""async role => {
                        const {api} = await import('./assets/js/api.js');
                        await api.login(role + '@qa.example', 'BrowserDemo123!');
                    }""", role)
                for name in targets:
                    suffix = {"doctor-profile.html": "?id=qa-doctor",
                              "hospital-detail.html": "?id=qa-hospital"}.get(name, "")
                    page.goto(base + "/" + name + suffix, wait_until="networkidle")
                    if urlparse(page.url).path != "/" + name:
                        raise AssertionError(f"Unexpected redirect for {role}: {name} -> {page.url}")
                    page.evaluate("theme => { document.documentElement.dataset.theme = theme; }", theme)
                    if page.locator('.skip-link').count():
                        page.keyboard.press('Tab')
                        assert page.locator('.skip-link').evaluate(
                            'el => el === document.activeElement'), f"Skip link not first: {name}"
                        page.keyboard.press('Enter')
                        assert page.evaluate("document.activeElement.id === 'main'"), f"Skip focus failed: {name}"
                    capture(page, name, role, language, viewport, theme)
                    if name == "login.html":
                        for door, tab, state in [("doorPatient", "tabRegister", "patient-register"),
                                                 ("doorDoctor", "dTabRegister", "doctor-register")]:
                            page.locator("#" + door).click()
                            page.locator("#" + tab).click()
                            capture(page, name, role, language, viewport, theme, state)
                    if name == "doctors.html":
                        page.locator('.bookBtn[data-doctor="qa-doctor"]:enabled').click()
                        page.locator('[role="dialog"]').wait_for()
                        capture(page, name, role, language, viewport, theme, "booking-dialog")
                        page.keyboard.press("Escape")
                    if name == "doctor.html":
                        page.locator('.openBtn[data-id="qa-appointment"]').click()
                        page.locator("#complaint").wait_for()
                        capture(page, name, role, language, viewport, theme, "consultation-dialog")
                        page.keyboard.press("Escape")
                context.close()
        browser.close()
    report = {"engine_sha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
              "scope": "Local synthetic fixtures; bn mobile/en desktop in light/dark CSS; fallback fonts; initial states, registration and clinical dialogs; skip-link keyboard focus",
              "limitations": "Automated checks do not establish WCAG conformance or replace manual assistive-technology review.",
              "configurations": results}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    violations = sum(len(result["violations"]) for result in results)
    print(f"{len(results)} page configurations; {violations} violations; report: {output}")
    return violations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=os.environ.get("QA_BASE_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--engine", type=Path, default=ROOT / "tools/a11y/node_modules/axe-core/axe.min.js")
    parser.add_argument("--output", type=Path, default=ROOT / ".tmp/accessibility-report.json")
    args = parser.parse_args()
    raise SystemExit(bool(run(args.base.rstrip("/"), args.engine, args.output)))
