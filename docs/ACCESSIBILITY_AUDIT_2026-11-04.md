# Accessibility verification — 2026-11-04

The local synthetic demo was checked with Playwright/Edge and axe-core 4.14.0.
The final scan covered **140 page configurations with zero reported automated
violations**. It used WCAG 2 A/AA, 2.1 A/AA, 2.2 AA and best-practice rules.

Coverage combines 30 HTML pages, patient/doctor/admin/operator roles, selected
registration and booking/consultation dialogs, Bengali mobile (390×844) and
English desktop (1440×900), and light/dark CSS. External requests are blocked;
system-font fallback is deliberately tested. Synthetic fixtures provide a
doctor, available slot, appointment, hospital/ward and laboratory.

Changes made:

- Give the mobile brand link an accessible name and include visible language
  text in the language switch's name.
- Repair skipped heading levels in populated lists and retain a heading on
  hospital error states, while preserving card title sizes.
- Improve link, role chooser, staff footer and dark-theme conversation contrast.
  Keep destructive/completion button contrast across both themes.
- Make skip links move keyboard focus to main content; use roving focus and
  arrow/Home/End keys on tabs; close mobile navigation with Escape.
- Trap Tab/Shift+Tab in booking and consultation dialogs, support Escape and
  restore focus to the launching control. Clean up listeners on every close.
- Name the remove-medicine button. Refresh the clinician queue after closing
  a workspace and preserve meaningful focus after the refresh.
- Advance the service-worker shell version so returning clients receive fixes.

Keyboard smoke checks passed for both login tab groups, the mobile menu,
booking/consultation boundaries, Escape, cancellation and restored focus.
Existing browser journeys also cover encrypted offline storage and account
isolation; their output is recorded separately from axe results.

## Reproduce locally

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
npm ci --prefix tools/a11y --ignore-scripts
python tools/review_server.py
# In another terminal:
python tools/browser_smoke.py
python tools/keyboard_smoke.py
python tools/accessibility_audit.py
```

Use `QA_CHROMIUM_PATH` for an installed Chromium browser. The audit and keyboard
tools reject hosted targets. Detailed output is `.tmp/accessibility-report.json`;
CI uploads it together with the browser screenshot. The dependency lockfile
records the exact npm tarball and integrity digest.

## Limits and manual follow-up

Automated success does not establish WCAG conformance. Axe marked contrast checks
as incomplete in 136 configurations and visible-label/name checks in 132;
these are retained in the JSON for manual review, not counted as passes.
Screen-reader navigation/pronunciation, real phone zoom/reflow, actual downloaded
fonts, user testing, every error/loading state and all assistive technologies
still need human evaluation. The viewport/language combinations above are a
sample, not a cross-product of every browser, width and language.

This is an engineering audit of disposable fixtures. It is not the independent
accessibility/security review or clinical validation required for production.
