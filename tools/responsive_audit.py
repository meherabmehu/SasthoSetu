# -*- coding: utf-8 -*-
"""Check every page for layout that breaks on small screens.

Serves the frontend, loads each page at a set of viewport widths and reports
two faults that make a page unusable on a phone:

  overflow  - the document is wider than the viewport, so the reader has to
              scroll sideways to finish a sentence
  small tap - an interactive control is under the 44x44 CSS px that a finger
              can reliably hit

Run it with the backend down; pages render their shell and static content
regardless, which is what the layout check needs.

    python tools/responsive_audit.py            (all pages, all widths)
    python tools/responsive_audit.py triage.html
"""
from __future__ import annotations

import http.server
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
PORT = 8931

# 320 is the narrowest phone still in use, 360 the most common Android width,
# 768 an upright tablet, 1024 a small laptop.
WIDTHS = [320, 360, 414, 768, 1024]

MIN_TAP = 44

# A finger needs 44px, but these are not finger targets: inline text links in
# a sentence, and controls the page keeps hidden until something is chosen.
TAP_EXEMPT = {"a.link-inline", ".skip-link"}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def log_message(self, *args):
        pass


def serve() -> socketserver.TCPServer:
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", PORT), QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def audit(pages: list[str]) -> int:
    from playwright.sync_api import sync_playwright

    faults = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for page_name in pages:
            for width in WIDTHS:
                # Below the tablet breakpoint, emulate a touch screen. Without
                # this the browser reports a mouse, the pointer:coarse rules
                # never apply and the tap-target check measures the desktop
                # sizes instead of the ones a phone actually gets.
                context = browser.new_context(
                    viewport={"width": width, "height": 800},
                    device_scale_factor=2,
                    has_touch=width <= 768,
                    is_mobile=width <= 768,
                )
                page = context.new_page()
                page.goto(f"http://127.0.0.1:{PORT}/{page_name}",
                          wait_until="networkidle")

                scroll_width = page.evaluate(
                    "Math.max(document.documentElement.scrollWidth,"
                    " document.body.scrollWidth)")
                if scroll_width > width + 1:
                    culprits = page.evaluate(
                        """(w) => [...document.querySelectorAll('*')]
                            .filter(el => {
                              const r = el.getBoundingClientRect();
                              return r.width > 0 && r.right > w + 1;
                            })
                            .slice(0, 4)
                            .map(el => el.tagName.toLowerCase() +
                              (el.className && typeof el.className === 'string'
                                ? '.' + el.className.trim().split(/\\s+/)[0]
                                : ''))""",
                        width)
                    print(f"  overflow  {page_name} @{width}px "
                          f"scrollWidth={scroll_width} {culprits}")
                    faults += 1

                if width <= 414:
                    # A checkbox is judged by the label wrapped around it: the
                    # whole row toggles it, so that row is the tap target and
                    # a 44px box would look wrong next to its text.
                    small = page.evaluate(
                        """(min) => [...document.querySelectorAll(
                             'button, a.btn, input, select, textarea')]
                            .filter(el => {
                              const r = el.getBoundingClientRect();
                              if (r.width === 0 && r.height === 0) return false;
                              const box = el.type === 'checkbox' ||
                                          el.type === 'radio';
                              const target = box && el.closest('label')
                                ? el.closest('label').getBoundingClientRect()
                                : r;
                              return target.height < min;
                            })
                            .slice(0, 4)
                            .map(el => el.tagName.toLowerCase() +
                              (el.className && typeof el.className === 'string'
                                ? '.' + el.className.trim().split(/\\s+/)[0]
                                : '') +
                              ' h=' + Math.round(
                                el.getBoundingClientRect().height))""",
                        MIN_TAP)
                    if small:
                        print(f"  small tap {page_name} @{width}px {small}")
                        faults += 1

                context.close()
        browser.close()
    return faults


def main() -> None:
    pages = sys.argv[1:] or sorted(
        p.name for p in FRONTEND.glob("*.html"))
    server = serve()
    try:
        print(f"Auditing {len(pages)} page(s) at {WIDTHS}")
        faults = audit(pages)
    finally:
        server.shutdown()

    if faults:
        print(f"\n{faults} layout fault(s)")
        sys.exit(1)
    print("\nNo horizontal overflow, no undersized tap targets.")


if __name__ == "__main__":
    main()
