"""Deterministic Home screenshots and hero-layout assertions.

All account/dashboard APIs are intercepted with synthetic fixture data; this
test never reads or changes a real learner account.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/evidence/ui-aesthetic-refinement"
OUT.mkdir(parents=True, exist_ok=True)
BASE = os.getenv("E2E_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
BROWSER = os.getenv("BROWSER_EXECUTABLE", "/usr/bin/chromium")

profile = {
    "id": "synthetic-aesthetic-learner",
    "display_name": "Alex Learner",
    "ui_locale": "en",
    "study_locale": "en",
    "speech_locale": "en-GB",
    "timezone": "Africa/Lagos",
    "is_demo": False,
    "mode": "fixture",
}
progress = {
    "scope_revision_id": "synthetic-scope",
    "completed_count": 2,
    "total_in_scope": 5,
    "percent": 40,
    "review_needed_count": 1,
}
dashboard = {
    "learner": profile,
    "collections_count": 1,
    "due_count": 2,
    "collections": [],
    "scope_progress": progress,
    "resume": None,
    "calibration": {
        "sample_count": 4,
        "confidence": 68,
        "accuracy": 62,
        "gap": 6,
        "brier_score": None,
        "window": "last-30-days",
    },
    "recent_materials": [],
    "connections": [],
    "mode": "fixture",
}


def fulfill_api(route, authenticated=True, locale="en"):
    path = urlsplit(route.request.url).path
    if not authenticated and path in {
        "/api/v1/me",
        "/api/v1/dashboard",
        "/api/v1/review/due",
    }:
        route.fulfill(
            status=401,
            content_type="application/json",
            body=json.dumps({"detail": "authentication_required"}),
        )
        return
    fixture_learner = {
        **profile,
        "ui_locale": locale,
        "study_locale": locale,
        "speech_locale": "ar-SA" if locale == "ar" else profile["speech_locale"],
    }
    if path == "/api/v1/me":
        payload = fixture_learner
    elif path == "/api/v1/dashboard":
        payload = {**dashboard, "learner": fixture_learner}
    elif path == "/api/v1/review/due":
        payload = {"items": []}
    else:
        payload = {"items": [], "total": 0, "next_cursor": None}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


results = []
errors = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=BROWSER, headless=True, args=["--no-sandbox"]
    )
    for width, height, filename in [
        (390, 844, "home-final-mobile-390.png"),
        (768, 1024, "home-final-tablet-768.png"),
        (991, 900, "home-final-mobile-991.png"),
        (992, 900, "home-final-desktop-992.png"),
        (1440, 1000, "home-final-desktop-1440.png"),
        (1920, 1080, "home-final-projector-1920.png"),
    ]:
        page = browser.new_page(viewport={"width": width, "height": height})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/api/v1/**", fulfill_api)
        response = page.goto(BASE, wait_until="networkidle")
        assert response and response.status == 200
        page.locator(".quick-tile").first.wait_for()
        page.evaluate("document.fonts.ready")

        visual = page.evaluate(
            """() => {
              const action = document.querySelector('.quick-tile--stacked');
              const actionStyle = getComputedStyle(action);
              const grid = getComputedStyle(document.querySelector('.quick-actions-grid'));
              const desktopHero = document.querySelector('.desktop-greeting');
              const topbar = document.querySelector('.app-main > .sticky-top');
              const heroRect = desktopHero?.getBoundingClientRect();
              const topbarRect = topbar?.getBoundingClientRect();
              const mobileHeroRect = document.querySelector('.hero')?.getBoundingClientRect();
              const introRect = document.querySelector('.home-introduction').getBoundingClientRect();
              const sidebar = document.querySelector('.sidebar');
              const sidebarRect = sidebar?.getBoundingClientRect();
              const activeHero = document.querySelector(innerWidth >= 992 ? '.desktop-greeting' : '.hero');
              const motifs = [...(activeHero?.querySelectorAll('.learning-motif') ?? [])]
                .filter(el => getComputedStyle(el).display !== 'none')
                .map(el => {
                  const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)];
                });
              const actionLabels = [...document.querySelectorAll('.quick-action-label')].map(el => el.textContent.trim());
              const actionColors = [...document.querySelectorAll('.quick-action-icon')].map(el => getComputedStyle(el).backgroundColor);
              return {
                viewport: {width: innerWidth, height: innerHeight},
                documentWidth: document.documentElement.scrollWidth,
                verticalWordmarkPresent: Boolean(document.querySelector('.viewport-wordmark-frame, .viewport-vertical-wordmark')),
                heroBackground: activeHero ? getComputedStyle(activeHero).backgroundColor : null,
                pageCanvas: getComputedStyle(document.body).backgroundColor,
                introVisible: Boolean(document.querySelector('.home-introduction')),
                introTopGap: innerWidth >= 992
                  ? introRect.top - topbarRect.bottom
                  : introRect.top - mobileHeroRect.bottom,
                footerTabs: [...document.querySelectorAll('.bottom-nav a')].map(a => a.textContent.trim()),
                pattern: {count: motifs.length, distinctX: new Set(motifs.map(p => p[0])).size, distinctY: new Set(motifs.map(p => p[1])).size},
                quickAction: {
                  flexDirection: actionStyle.flexDirection,
                  gridColumns: grid.gridTemplateColumns.split(' ').length,
                  labels: actionLabels,
                  colors: actionColors,
                },
                desktopHero: heroRect?.width && topbarRect ? {
                  leftInset: heroRect.left,
                  rightInset: innerWidth - heroRect.right,
                  topInset: heroRect.top,
                  sidebarTopGap: sidebarRect.top - heroRect.bottom,
                  sidebarLeft: sidebarRect.left,
                  sidebarWidth: sidebarRect.width,
                  topbarRowGap: topbarRect.top - sidebarRect.top,
                } : null,
              };
            }"""
        )
        assert visual["documentWidth"] == width, visual
        assert not visual["verticalWordmarkPresent"], visual
        assert visual["introVisible"], visual
        expected_intro_gap = 16 if width >= 992 else -28
        assert abs(visual["introTopGap"] - expected_intro_gap) <= 1, visual
        assert visual["footerTabs"] == ["Home", "Collections", "Study", "Review"], visual
        expected_motifs = 10 if width < 992 else 22
        assert visual["pattern"]["count"] == expected_motifs, visual
        assert visual["pattern"]["distinctX"] >= expected_motifs - 1, visual
        assert visual["pattern"]["distinctY"] >= expected_motifs - 1, visual
        assert visual["heroBackground"] == "rgb(176, 214, 205)", visual
        assert visual["pageCanvas"] == "rgb(243, 248, 246)", visual
        assert visual["quickAction"]["flexDirection"] == "column", visual
        expected_columns = 3 if width < 1400 else 6
        assert visual["quickAction"]["gridColumns"] == expected_columns, visual
        assert visual["quickAction"]["labels"] == [
            "Study", "Review", "Add Material", "Outline", "Voice", "Progress"
        ], visual
        assert visual["quickAction"]["colors"] == [
            "rgb(47, 123, 235)", "rgb(245, 158, 11)", "rgb(34, 177, 76)",
            "rgb(124, 92, 230)", "rgb(229, 68, 79)", "rgb(20, 184, 166)",
        ], visual
        if width >= 992:
            for inset in ("leftInset", "rightInset", "topInset", "sidebarTopGap"):
                assert abs(visual["desktopHero"][inset] - 24) <= 1, visual
            assert abs(visual["desktopHero"]["sidebarLeft"]) <= 1, visual
            assert abs(visual["desktopHero"]["sidebarWidth"] - 264) <= 1, visual
            assert abs(visual["desktopHero"]["topbarRowGap"]) <= 1, visual
        else:
            assert visual["desktopHero"] is None, visual
        page.screenshot(path=str(OUT / filename))
        results.append({"screenshot": filename, **visual})
        page.close()

    rtl_checks = []
    for width, height, filename in [
        (390, 844, "home-final-rtl-mobile-390.png"),
        (1440, 1000, "home-final-rtl-desktop-1440.png"),
    ]:
        context = browser.new_context(viewport={"width": width, "height": height})
        context.add_cookies([{"name": "learningos_locale", "value": "ar", "url": BASE}])
        rtl_page = context.new_page()
        rtl_page.on("pageerror", lambda error: errors.append(str(error)))
        rtl_page.route("**/api/v1/**", lambda route: fulfill_api(route, locale="ar"))
        response = rtl_page.goto(BASE, wait_until="networkidle")
        assert response and response.status == 200
        rtl_page.locator(".quick-tile").first.wait_for()
        rtl_visual = rtl_page.evaluate(
            """() => {
              const hero = document.querySelector(innerWidth >= 992 ? '.desktop-greeting' : '.hero');
              const heroRect = hero.getBoundingClientRect();
              const sidebar = document.querySelector('.sidebar');
              const sidebarRect = sidebar.getBoundingClientRect();
              return {
                width: innerWidth,
                documentWidth: document.documentElement.scrollWidth,
                lang: document.documentElement.lang,
                dir: document.documentElement.dir,
                introVisible: Boolean(document.querySelector('.home-introduction')),
                heroLeft: heroRect.left,
                heroRightInset: innerWidth - heroRect.right,
                sidebarLeft: sidebarRect.left,
                sidebarRight: sidebarRect.right,
                footerTabs: document.querySelectorAll('.bottom-nav a').length,
              };
            }"""
        )
        assert rtl_visual["documentWidth"] == width, rtl_visual
        assert rtl_visual["lang"] == "ar" and rtl_visual["dir"] == "rtl", rtl_visual
        assert rtl_visual["introVisible"] and rtl_visual["footerTabs"] == 4, rtl_visual
        if width >= 992:
            assert abs(rtl_visual["heroLeft"] - 24) <= 1, rtl_visual
            assert abs(rtl_visual["heroRightInset"] - 24) <= 1, rtl_visual
            assert abs(rtl_visual["sidebarLeft"] - (width - 264)) <= 1, rtl_visual
        rtl_page.screenshot(path=str(OUT / filename))
        rtl_checks.append({"screenshot": filename, **rtl_visual})
        context.close()

    auth_page = browser.new_page(viewport={"width": 390, "height": 844})
    auth_page.on("pageerror", lambda error: errors.append(str(error)))
    auth_paths = []
    def fulfill_auth_api(route):
        auth_paths.append(urlsplit(route.request.url).path)
        fulfill_api(route, authenticated=False)
    auth_page.route("**/api/v1/**", fulfill_auth_api)
    response = auth_page.goto(BASE, wait_until="networkidle")
    assert response and response.status == 200
    auth_page.get_by_role("heading", name="Make your materials work harder.").wait_for()
    info_card = auth_page.locator(".home-introduction")
    assert info_card.is_visible()
    assert info_card.get_by_role("link").count() == 0
    lower_signin = auth_page.locator("#review").get_by_role("link", name="Continue with Google")
    assert lower_signin.is_visible(), {
        "paths": auth_paths,
        "body": auth_page.locator("body").inner_text(),
    }
    auth_check = {
        "intro_remains_visible_signed_out": True,
        "intro_has_no_signin_action": True,
        "lower_due_review_signin_visible": True,
    }
    auth_page.close()
    browser.close()

assert not errors, errors
evidence = {
    "status": "passed",
    "command": os.getenv("EVIDENCE_COMMAND", "python3 tests/ui_aesthetic_capture.py"),
    "cwd": str(ROOT),
    "exit_code": 0,
    "target": BASE,
    "browser_executable": BROWSER,
    "fixture": "synthetic learner; all API responses intercepted",
    "checks": results,
    "rtl_checks": rtl_checks,
    "signed_out_home": auth_check,
    "page_errors": errors,
    "limitations": [
        "This focused run verifies Home at 390×844, 768×1024, 991×900, 992×900, 1440×1000 and 1920×1080; it does not replace full route/accessibility acceptance.",
        "No authentication, Drive, live speech or learner account was exercised.",
    ],
}
(OUT / "final-home-results.json").write_text(json.dumps(evidence, indent=2) + "\n")
print(json.dumps(evidence, indent=2))
