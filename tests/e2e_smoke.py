"""Real browser/API acceptance for a running, synthetic offline demo.

Run with API, worker and frontend running. Live Drive/model/voice proof is not
inferred from these checks. Failures preserve nonzero exit status and evidence.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("E2E_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
EVIDENCE = ROOT / "docs" / "evidence" / "browser"
REGISTRY = json.loads((ROOT / "contracts" / "language-registry.json").read_text())["languages"]
CREATED_COLLECTIONS = []


def wait_job(client, job_id, timeout=40):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        r = client.get(f"/api/v1/jobs/{job_id}"); r.raise_for_status()
        body = r.json()
        if body["state"] == "succeeded":
            return body
        if body["state"] in {"failed", "needs-attention"}:
            raise AssertionError(f"Job did not succeed: {body['error_code']}")
        time.sleep(.2)
    raise AssertionError("Durable worker job timed out")


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = []
    with httpx.Client(base_url=BASE, timeout=40) as client:
        health = client.get("/api/v1/health"); health.raise_for_status()
        assert health.json()["mode"] == "demo", "Run this synthetic check in demo mode only"
        ready = client.get("/api/v1/ready"); ready.raise_for_status()
        client.patch("/api/v1/me", json={"ui_locale": "en", "study_locale": "en", "speech_locale": "en-GB"}).raise_for_status()
        profile = client.get("/api/v1/me").json()
        snapshot = client.get("/api/v1/dashboard"); snapshot.raise_for_status()
        assert snapshot.json()["learner"]["id"] == profile["id"]
        locale_rows = client.get("/api/v1/languages").json()["items"]
        assert [x.get("locale", x.get("ui_locale")) for x in locale_rows] == [x["ui_locale"] for x in REGISTRY]
        results.append({"check": "database-backed health/readiness/dashboard/locale registry", "status": "passed"})

        # HTTP upload -> durable worker -> source-grounded outline -> frozen scope.
        label = "Browser acceptance " + uuid.uuid4().hex[:8]
        made = client.post("/api/v1/collections", json={"name": label, "storage_mode": "local"})
        made.raise_for_status(); collection = made.json(); cid = collection["id"]
        CREATED_COLLECTIONS.append(cid)
        note = b"# Original browser fixture\n\n## Atomic number\nThe atomic number equals the number of protons in an atom's nucleus.\n\n## Neutrality\nA neutral atom has equal numbers of protons and electrons.\n"
        upload = client.post(f"/api/v1/collections/{cid}/materials", files={"file": ("browser-original.md", note, "text/markdown")}, headers={"Idempotency-Key": uuid.uuid4().hex})
        upload.raise_for_status(); receipt = upload.json()
        wait_job(client, receipt["job_id"])
        outline = client.get(f"/api/v1/collections/{cid}/outline").json()
        chunks = [c for m in outline["materials"] for c in m["chunks"]]
        assert len(chunks) == 2, "Actual Markdown headings must become titled sections"
        assert all(c["citation_ids"] for c in chunks)
        cite = client.get("/api/v1/citations/" + chunks[0]["citation_ids"][0]); cite.raise_for_status()
        assert cite.json()["excerpt"] in note.decode(), "Citations resolve to uploaded original"
        scoped = client.post(f"/api/v1/collections/{cid}/scope", json={"chunk_ids": [chunks[0]["id"]], "expected_version": outline["version"]})
        scoped.raise_for_status()
        fresh = client.get(f"/api/v1/collections/{cid}").json()
        scope = fresh["active_scope"]
        assert fresh["progress"]["total_in_scope"] == 1 and fresh["progress"]["completed_count"] == 0
        invalid = client.post(f"/api/v1/collections/{cid}/scope", json={"chunk_ids": [chunks[0]["id"], chunks[0]["id"]], "expected_version": fresh["version"]})
        assert invalid.status_code in {400, 422}, "Duplicate scope titles must be rejected"
        results.append({"check": "real multipart upload, worker extraction, original citations, scope denominator/duplicate guard", "status": "passed"})

        # Start one cited turn; public API has no answer/rubric leakage.
        start = client.post("/api/v1/sessions", json={"collection_id": cid, "scope_revision_id": scope["id"], "mode": "study"}, headers={"Idempotency-Key": uuid.uuid4().hex})
        start.raise_for_status(); session = start.json(); sid = session["id"]
        wait_job(client, session["job_id"])
        turn = client.get(f"/api/v1/sessions/{sid}/next").json()
        assert turn["question"] and turn["citation_ids"]
        assert not {"expected_answer", "rubric", "question_json_private"} & set(turn)
        replay_get = client.get(f"/api/v1/sessions/{sid}/next").json()
        assert replay_get["item_id"] == turn["item_id"], "GET next never consumes/generates a second turn"
        answer = {"item_id": turn["item_id"], "answer": "Atomic number equals the proton count.", "confidence": 4, "expected_version": turn["version"]}
        key = uuid.uuid4().hex
        first = client.post(f"/api/v1/sessions/{sid}/answer", json=answer, headers={"Idempotency-Key": key})
        first.raise_for_status(); wait_job(client, first.json()["job_id"])
        replay = client.post(f"/api/v1/sessions/{sid}/answer", json=answer, headers={"Idempotency-Key": key})
        replay.raise_for_status(); assert replay.json()["job_id"] == first.json()["job_id"]
        history = client.get(f"/api/v1/collections/{cid}/history").json()
        assert history["total"] == 1, "Replayed answer must not duplicate history"
        current = client.get(f"/api/v1/sessions/{sid}").json()
        end = client.post(f"/api/v1/sessions/{sid}/finish", json={"expected_version": current["version"]}, headers={"Idempotency-Key": uuid.uuid4().hex})
        end.raise_for_status()
        if end.json().get("job_id"):
            wait_job(client, end.json()["job_id"])
        summary = client.get(f"/api/v1/sessions/{sid}/summary"); summary.raise_for_status()
        assert summary.status_code == 200, "Finish triggers automatic persisted summary"
        results.append({"check": "cited turn, hidden answers, repeat-safe answer, automatic summary", "status": "passed"})

        with sync_playwright() as p:
            chromium = os.getenv("CHROMIUM_PATH", "/usr/bin/chromium")
            options = {"executable_path": chromium} if Path(chromium).is_file() else {}
            browser = p.chromium.launch(**options, headless=True, args=["--no-sandbox"])
            for width, height in [(360, 800), (390, 844), (768, 1024), (991, 900), (992, 900), (1440, 1000)]:
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
                response = page.goto(BASE, wait_until="networkidle")
                assert response.status == 200
                page.locator(".quick-tile").first.wait_for()
                assert page.locator(".quick-tile").count() == 6
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), f"Overflow at {width}"
                if width >= 992:
                    assert round(page.locator(".sidebar").bounding_box()["width"]) == 264
                else:
                    assert page.locator(".bottom-nav").is_visible()
                    page.get_by_role("button", name="Open menu", exact=True).click()
                    assert page.locator(".offcanvas.show").is_visible()
                    for _ in range(12):
                        page.keyboard.press("Tab")
                        assert page.evaluate("document.querySelector('.offcanvas.show').contains(document.activeElement)"), "Drawer must trap keyboard focus"
                    page.keyboard.press("Escape")
                    assert page.locator(".offcanvas.show").count() == 0
                    expect(page.get_by_role("button", name="Open menu", exact=True)).to_be_focused()
                page.screenshot(path=str(EVIDENCE / f"home-{width}.png"), full_page=True)
                assert not errors, errors
                results.append({"check": f"Home {width}px layout/drawer/static chrome", "status": "passed"})
                page.close()

            for width in [390, 1440]:
                page = browser.new_page(viewport={"width": width, "height": 1000 if width == 1440 else 844})
                errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
                for route in ["/collections", f"/collections/{cid}/outline", "/outline", "/add-material", "/study", "/study?mode=voice", "/review", "/progress", "/connections", "/profile", "/search", "/notifications"]:
                    response = page.goto(BASE + route, wait_until="networkidle")
                    assert response.status == 200, route
                    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), (route, width)
                    suffix = "" if width == 390 else "-1440"
                    page.screenshot(path=str(EVIDENCE / (route.replace("/", "_").replace("?", "_").replace("=", "_") + suffix + ".png")), full_page=True)
                assert not errors, errors
                page.close()
            results.append({"check": "all functional routes render on mobile/desktop without overflow or page errors", "status": "passed"})

            # Exercise real form controls, not just the corresponding HTTP API.
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(BASE + f"/add-material?collection={cid}", wait_until="networkidle")
            expect(page.locator("select.form-select:not(.form-select-sm)").first).to_have_value(cid)
            ui_note = b"# UI fixture\n\n## Isotope\nIsotopes have equal proton counts and different neutron counts.\n\n## Ion\nAn ion has unequal proton and electron counts.\n\n## Mass number\nMass number equals the sum of protons and neutrons.\n"
            page.locator('input[type="file"]').set_input_files({"name": "ui-original.md", "mimeType": "text/markdown", "buffer": ui_note})
            page.locator('#upload-panel select[name="source_language"]').select_option("en")
            network = page.context.new_cdp_session(page)
            network.send("Network.enable")
            network.send("Network.emulateNetworkConditions", {"offline": False, "latency": 300, "downloadThroughput": 125000, "uploadThroughput": 125000})
            accepted_but_lost = []
            def lose_first_receipt(route):
                response = route.fetch()
                assert response.status in {200, 201, 202}
                accepted_but_lost.append(response.json())
                route.abort("failed")
            page.route(f"**/api/v1/collections/{cid}/materials", lose_first_receipt, times=1)
            page.get_by_role("button", name="Add to Collection", exact=True).click()
            expect(page.get_by_role("alert").filter(has_text="Something went wrong")).to_be_visible()
            with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith(f"/collections/{cid}/materials")) as intake:
                page.get_by_role("button", name="Add to Collection", exact=True).click()
            assert intake.value.status in {200, 201, 202}
            ui_receipt = intake.value.json()
            assert ui_receipt["job_id"] == accepted_but_lost[0]["job_id"], "Retry after a lost receipt must reuse the same intake"
            network.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
            wait_job(client, ui_receipt["job_id"])
            assert client.get(f"/api/v1/materials/{ui_receipt['material_id']}").json()["source_language"] == "en"
            expect(page.get_by_role("status").filter(has_text="Material received")).to_be_visible()
            language_row = page.locator(".event-row").filter(has_text="ui-original.md")
            expect(language_row.locator('select[name="source_language"]')).to_have_value("en")
            # Test an explicit correction from unknown back to the actual source language.
            for source_language in ["und", "en"]:
                language_row.locator('select[name="source_language"]').select_option(source_language)
                with page.expect_response(lambda r: r.request.method == "PATCH" and r.url.endswith("/source-language")) as correction:
                    language_row.get_by_role("button", name="Save", exact=True).click()
                assert correction.value.status == 200
                assert correction.value.json()["revision_id"] == ui_receipt["revision_id"]
            results.append({"check": "UI source-language intake and correction preserve original revision identity", "status": "passed"})
            page.screenshot(path=str(EVIDENCE / "ui-upload-receipt.png"), full_page=True)

            page.goto(BASE + f"/collections/{cid}/outline", wait_until="networkidle")
            expect(page.locator('.outline-row input[type="checkbox"]')).to_have_count(5)
            for checkbox in page.locator('.outline-row input[type="checkbox"]').all():
                checkbox.check()
            original_material = next(m for m in client.get(f"/api/v1/collections/{cid}/outline").json()["materials"] if m["id"] == receipt["material_id"])
            original_order = original_material["chunks"]
            assert len(original_order) == 2
            page.get_by_role("button", name=f"Move down: {original_order[0]['title']}", exact=True).focus()
            page.keyboard.press("Enter")
            page.get_by_role("button", name="Save order", exact=True).click()
            expect(page.get_by_role("button", name="Save order", exact=True)).to_have_count(0)
            page.reload(wait_until="networkidle")
            expect(page.locator('.outline-row bdi').first).to_have_text(original_order[1]["title"])
            persisted_material = next(m for m in client.get(f"/api/v1/collections/{cid}/outline").json()["materials"] if m["id"] == receipt["material_id"])
            assert [chunk["id"] for chunk in persisted_material["chunks"]] == [original_order[1]["id"], original_order[0]["id"]], "Keyboard reorder must persist source IDs, including hierarchical heading labels"
            for checkbox in page.locator('.outline-row input[type="checkbox"]').all():
                checkbox.check()
            page.get_by_role("button", name="Go — save scope and study", exact=True).click()
            page.wait_for_url("**/study?**")
            current_collection = client.get(f"/api/v1/collections/{cid}").json()
            assert current_collection["progress"]["total_in_scope"] == 5, current_collection["progress"]
            assert client.get(f"/api/v1/sessions/{sid}").json()["scope_revision_id"] == scope["id"], "Earlier session must keep its original scope revision"
            page.screenshot(path=str(EVIDENCE / "ui-study-five-title-scope.png"), full_page=True)
            results.append({"check": "UI file upload at 1Mbps/300ms, lost-receipt retry dedup, extraction, keyboard reorder/reload, five-title Go, earlier session pinned", "status": "passed"})

            page.goto(BASE + f"/add-material?collection={cid}", wait_until="networkidle")
            page.get_by_role("tab", name="Paste link", exact=True).click()
            page.locator('input[name="url"]').fill("https://example.com/learning-os-browser-fixture")
            with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith(f"/collections/{cid}/link")) as link:
                page.get_by_role("button", name="Add to Collection", exact=True).click()
            assert link.value.status in {200, 201, 202}
            link_receipt = link.value.json()
            assert link_receipt["material_id"] and link_receipt["storage_state"] == "local-only", "Local link intake must not claim a Drive receipt"
            results.append({"check": "UI link submission persists local descriptor; external retrieval remains separately unverified", "status": "passed"})

            before = client.get(f"/api/v1/collections/{cid}").json()["progress"]
            page.goto(BASE + "/profile", wait_until="networkidle")
            page.get_by_label("Study language").select_option("fr")
            page.get_by_label("Speech language").select_option("ar-SA")
            page.get_by_label("Interface language").select_option("es")
            page.wait_for_function("document.documentElement.lang === 'es'")
            # Saving uses the actual translated control after the UI switch.
            page.locator('form button.btn-primary').first.click()
            expect(page.locator('p[role="status"]').first).to_be_visible()
            page.reload(wait_until="networkidle")
            expect(page.locator("html")).to_have_attribute("lang", "es")
            persisted = client.get("/api/v1/me").json()
            assert (persisted["ui_locale"], persisted["study_locale"], persisted["speech_locale"]) == ("es", "fr", "ar-SA")
            assert client.get(f"/api/v1/collections/{cid}").json()["progress"] == before
            results.append({"check": "independent UI/study/speech preferences save/reload without changing progress", "status": "passed"})
            client.patch("/api/v1/me", json={"ui_locale": "en", "study_locale": "en", "speech_locale": "en-GB"}).raise_for_status()
            page.close()

            # A 200%-zoom equivalent CSS viewport and increased text size.
            page = browser.new_page(viewport={"width": 720, "height": 500})
            page.goto(BASE, wait_until="networkidle")
            page.evaluate("document.documentElement.style.fontSize = '200%'")
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), "200% text zoom overflow"
            page.screenshot(path=str(EVIDENCE / "home-text-zoom-200.png"), full_page=True)
            page.close()
            results.append({"check": "200% text resize and half-sized desktop viewport reflow", "status": "passed"})

            for language in REGISTRY:
                client.patch("/api/v1/me", json={"ui_locale": language["ui_locale"]}).raise_for_status()
                context = browser.new_context(viewport={"width": 390, "height": 844})
                context.add_cookies([{"name": "learningos_locale", "value": language["ui_locale"], "url": BASE}])
                page = context.new_page(); errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(BASE, wait_until="networkidle")
                page.locator(".quick-tile").first.wait_for()
                assert page.locator("html").get_attribute("lang") == language["ui_locale"]
                assert page.locator("html").get_attribute("dir") == language["direction"]
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), language["ui_locale"]
                page.screenshot(path=str(EVIDENCE / f"locale-{language['ui_locale']}.png"), full_page=True)
                assert not errors, errors
                context.close()
            results.append({"check": "all ten locale home render/RTL/script layout (not live learning/speech proof)", "status": "passed"})
            browser.close()
        client.patch("/api/v1/me", json={"ui_locale": "en"}).raise_for_status()
        latest = client.get(f"/api/v1/collections/{cid}").json()
        client.delete(f"/api/v1/collections/{cid}", params={"expected_version": latest["version"]}).raise_for_status()

    (EVIDENCE / "results.json").write_text(json.dumps({"base": BASE, "mode": "demo", "results": results, "live_source_and_speech": "unrun; actual credentials/consent/microphone required"}, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    try:
        main()
    finally:
        # Own synthetic fixtures only, even when a later browser assertion fails.
        with httpx.Client(base_url=BASE, timeout=40) as client:
            client.patch("/api/v1/me", json={"ui_locale": "en", "study_locale": "en", "speech_locale": "en-GB"})
            for cid in CREATED_COLLECTIONS:
                response = client.get(f"/api/v1/collections/{cid}")
                if response.status_code == 200:
                    client.delete(f"/api/v1/collections/{cid}", params={"expected_version": response.json()["version"]}).raise_for_status()
