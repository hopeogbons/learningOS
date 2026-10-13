"""Comparable unfocused synthetic Home captures; original baselines stay intact."""
import json
import os
from pathlib import Path

import httpx
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("E2E_BASE_URL", "http://127.0.0.1:3000")
OUT = ROOT / "docs/evidence/browser"
with httpx.Client(base_url=BASE) as client:
    assert client.get("/api/v1/health").json()["mode"] == "demo"
    client.patch("/api/v1/me", json={"ui_locale": "en"}).raise_for_status()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"])
    for width, height in [(390, 844), (768, 1024), (1440, 1000)]:
        page = browser.new_page(viewport={"width": width, "height": height})
        response = page.goto(BASE, wait_until="networkidle")
        assert response.status == 200
        page.locator(".quick-tile").first.wait_for()
        page.screenshot(path=str(OUT / f"visual-home-{width}.png"), full_page=True)
        page.close()
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.add_cookies([{"name": "learningos_locale", "value": "ar", "url": BASE}])
    with httpx.Client(base_url=BASE) as client:
        client.patch("/api/v1/me", json={"ui_locale": "ar"}).raise_for_status()
    page = context.new_page()
    page.goto(BASE, wait_until="networkidle")
    assert page.locator("html").get_attribute("dir") == "rtl"
    assert round(page.locator(".sidebar").bounding_box()["width"]) == 264
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.screenshot(path=str(OUT / "locale-ar-1440.png"), full_page=True)
    browser.close()
with httpx.Client(base_url=BASE) as client:
    client.patch("/api/v1/me", json={"ui_locale": "en"}).raise_for_status()

results = []
for name, baseline, actual, box, masks in [
    ("desktop-sidebar", "desktop.png", "visual-home-1440.png", (0, 0, 264, 900), []),
    ("mobile-topbar", "mobile.png", "visual-home-390.png", (0, 0, 390, 70), [(330, 15, 375, 62)]),
]:
    a = Image.open(ROOT / "reference/screenshots" / baseline).convert("RGB").crop(box)
    b = Image.open(OUT / actual).convert("RGB").crop(box)
    difference = ImageChops.difference(a, b)
    pixels = difference.load()
    count = changed = 0
    for y in range(difference.height):
        for x in range(difference.width):
            if any(left <= x < right and top <= y < bottom for left, top, right, bottom in masks):
                continue
            count += 1
            changed += max(pixels[x, y]) > 51
    result = {"region": name, "baseline": f"reference/screenshots/{baseline}", "actual": f"docs/evidence/browser/{actual}", "capture_state": "unfocused, closed drawer, English, matching baseline viewport", "box": box, "excluded_rectangles": masks, "exclusion_reason": "dynamic notification badge only" if masks else "none", "threshold_max_rgb_delta": 51, "pixels": count, "changed_pixels": changed, "percent_changed": round(changed / count * 100, 4), "one_percent_target_passed": changed / count <= .01}
    (ROOT / f"docs/evidence/visual-diff-{name}.json").write_text(json.dumps(result, indent=2))
    results.append(result)
print(json.dumps(results, indent=2))
