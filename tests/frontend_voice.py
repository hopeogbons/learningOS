"""Synthetic browser acceptance for the two-way Voice Study turn loop.

API responses are intercepted here. This proves the UI/session path, not real
microphone quality, translation quality or audible provider output.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(os.getenv("VOICE_EVIDENCE_PATH", ROOT / "docs/evidence/frontend/voice.json"))
EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
BASE = os.getenv("E2E_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
BROWSER = os.getenv("BROWSER_EXECUTABLE", "/usr/bin/chromium")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=BROWSER, headless=True, args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    transcripts = []
    speech_requests = []
    answer_requests = []
    fixture = {"answered": False}
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script(
        """
        Object.defineProperty(window, 'webkitSpeechRecognition', {value:undefined, configurable:true});
        Object.defineProperty(window, 'SpeechRecognition', {value:undefined, configurable:true});
        Object.defineProperty(navigator, 'mediaDevices', {value:{getUserMedia:async()=>({getTracks:()=>[{stop:()=>{}}]})}, configurable:true});
        class FixtureRecorder {
          constructor(){this.state='inactive';this.mimeType='audio/webm';}
          static isTypeSupported(){return true;}
          start(){this.state='recording';}
          stop(){this.state='inactive';setTimeout(()=>{this.ondataavailable?.({data:new Blob(['fixture'],{type:'audio/webm'})});this.onstop?.();},10);}
        }
        window.MediaRecorder=FixtureRecorder;
        window.speechSynthesis.getVoices=()=>[];
        """
    )

    learner = {
        "id": "synthetic-voice-learner",
        "display_name": "Alex Learner",
        "ui_locale": "en",
        "study_locale": "en",
        "speech_locale": "en-GB",
        "timezone": "Africa/Lagos",
        "is_demo": True,
        "mode": "demo",
    }
    progress = {
        "scope_revision_id": "voice-scope",
        "completed_count": 0,
        "total_in_scope": 1,
        "percent": 0,
        "review_needed_count": 0,
    }
    collection = {
        "id": "voice-collection",
        "name": "Synthetic voice Collection",
        "note": "Fixture only",
        "icon_key": "book",
        "color_key": "teal",
        "storage_mode": "local",
        "folder_mode": "app-managed",
        "provisioning_state": "local-only",
        "drive_folder_id": None,
        "position": 0,
        "version": 1,
        "archived": False,
        "created_at": "2026-10-14T12:00:00Z",
        "last_sync": None,
        "last_sync_at": None,
        "material_count": 1,
        "active_scope": {
            "id": "voice-scope",
            "revision_number": 1,
            "created_at": "2026-10-14T12:00:00Z",
            "chunk_ids": ["voice-title"],
        },
        "progress": progress,
    }
    dashboard = {
        "learner": learner,
        "collections_count": 1,
        "due_count": 0,
        "collections": [collection],
        "scope_progress": [{"collection_id": collection["id"], **progress}],
        "resume": None,
        "calibration": {
            "sample_count": 0,
            "confidence": 0,
            "accuracy": 0,
            "gap": 0,
            "brier_score": None,
            "window": "last-30-days",
        },
        "recent_materials": [],
        "connections": [],
        "mode": "demo",
        "demo_notice": "Offline demo — sample material",
    }

    def public_turn():
        if not fixture["answered"]:
            return {
                "session_id": "voice-fixture",
                "item_id": "voice-item",
                "version": 1,
                "status": "awaiting_answer",
                "question": "Explain a neutral atom.",
                "teaching": "Atoms contain protons and electrons.",
                "citation_ids": [],
                "voice_turn_count": 0,
            }
        return {
            "session_id": "voice-fixture",
            "item_id": "voice-item",
            "version": 2,
            "status": "feedback",
            "question": "Explain a neutral atom.",
            "teaching": "Atoms contain protons and electrons.",
            "citation_ids": [],
            "voice_turn_count": 1,
            "feedback": {
                "item_id": "voice-item",
                "correctness": "correct",
                "confidence": 4,
                "missing_parts": [],
                "guessing_signal": "unsupported",
                "feedback": "A neutral atom has equal numbers of protons and electrons.",
                "title_complete": False,
                "rationale": "Synthetic voice acceptance fixture.",
                "evidence_event_ids": [],
                "citation_ids": [],
                "critical_coverage": {
                    "critical_ids": [],
                    "demonstrated_ids": [],
                    "complete": False,
                    "evidence_event_ids": [],
                },
                "demo": True,
                "provider_version": "fixture-v1",
                "prompt_version": "reviewer-fixture",
                "voice": True,
            },
        }

    def api_fixture(route):
        path = urlsplit(route.request.url).path
        method = route.request.method
        if path == "/api/v1/me":
            data = learner
        elif path == "/api/v1/dashboard":
            data = dashboard
        elif path == "/api/v1/collections":
            data = {"items": [collection], "total": 1, "next_cursor": None}
        elif path == "/api/v1/review/due":
            data = {"items": [], "total": 0}
        elif path == "/api/v1/connections":
            data = []
        elif path == "/api/v1/sessions/voice-fixture/next":
            data = public_turn()
        elif path == "/api/v1/sessions/voice-fixture/speech/transcribe":
            transcripts.append(method)
            data = {
                "text": "A neutral atom has equal protons and electrons.",
                "locale": "en-GB",
                "verified": True,
                "session_id": "voice-fixture",
                "item_id": "voice-item",
                "language": "en-GB",
                "raw_audio_retained": False,
                "editable": True,
                "voice_turn_count": 0,
            }
        elif path == "/api/v1/sessions/voice-fixture/speech/synthesize":
            speech_requests.append(json.loads(route.request.post_data or "{}"))
            route.fulfill(
                status=503,
                json={"error": {"code": "speech_unavailable", "message": "fixture fallback"}},
            )
            return
        elif path == "/api/v1/sessions/voice-fixture/answer":
            answer_requests.append(json.loads(route.request.post_data or "{}"))
            fixture["answered"] = True
            route.fulfill(status=202, json={"id": "assessment-job", "status": "queued"})
            return
        else:
            data = {"items": [], "total": 0, "next_cursor": None}
        route.fulfill(status=200, json=data)

    page.route("**/api/v1/**", api_fixture)
    page.goto(BASE + "/study?mode=voice")
    page.get_by_text("Hear the tutor's cited teaching", exact=False).wait_for()

    page.goto(BASE + "/study?session=voice-fixture&mode=voice")
    page.get_by_role("button", name="Listen: Check your understanding").wait_for()
    for _ in range(20):
        if any(item.get("message_id") == "question" for item in speech_requests):
            break
        page.wait_for_timeout(100)
    assert any(item.get("message_id") == "question" for item in speech_requests), speech_requests
    page.get_by_role("button", name="Listen: Teach").click()
    page.get_by_role("button", name="Record an answer", exact=True).click()
    page.get_by_role("button", name="Stop recording", exact=True).wait_for()
    page.goto(BASE + "/collections")
    assert not transcripts, "Leaving while recording must cancel without submitting the audio"

    fixture["answered"] = False
    page.goto(BASE + "/study?session=voice-fixture&mode=voice")
    page.get_by_role("button", name="Record an answer", exact=True).click()
    page.get_by_role("button", name="Stop recording", exact=True).click()
    answer_box = page.get_by_label("Your answer", exact=True)
    answer_box.wait_for()
    answer_box.fill("Edited spoken answer: equal protons and electrons.")
    assert len(transcripts) == 1
    page.locator('input[name="confidence"][value="4"]').check(force=True)
    transcript_before_submit = answer_box.input_value()
    page.get_by_role("button", name="Check answer", exact=True).click()
    page.get_by_text("A neutral atom has equal numbers of protons and electrons.", exact=True).wait_for()
    page.get_by_role("button", name="Listen: Reviewer feedback").wait_for()
    for _ in range(25):
        if any(item.get("message_id") == "feedback" for item in speech_requests):
            break
        page.wait_for_timeout(100)

    spoken_ids = [item.get("message_id") for item in speech_requests]
    assert answer_requests and answer_requests[0]["voice"] is True
    assert {"question", "teaching", "feedback"} <= set(spoken_ids), spoken_ids
    assert "Selected-language speech is unavailable" in page.locator("body").inner_text()
    assert not errors, errors

    result = {
        "status": "passed",
        "command": os.getenv("EVIDENCE_COMMAND", "python3 tests/frontend_voice.py"),
        "cwd": str(ROOT),
        "exit_code": 0,
        "fixture": "synthetic session; STT/TTS responses intercepted",
        "checks": [
            "Voice mode explains the tutor/learner audio loop before session start",
            "Tutor question is spoken and teaching can be replayed",
            "Recording is cancelled on navigation without submitting audio",
            "Transcribed answer remains editable and requires confidence",
            "Voice response uses the ordinary answer endpoint with voice=true",
            "Reviewer feedback is spoken after a voice answer with replay available",
            "Unavailable speech preserves visible text and typing fallback",
        ],
        "voice_answer_posts": len(answer_requests),
        "voice_flag": answer_requests[0]["voice"],
        "editable_transcript_before_submit": transcript_before_submit,
        "speech_message_ids": spoken_ids,
        "live_speech_verified": False,
        "page_errors": errors,
        "limitations": ["No real microphone capture, transcription quality or audible provider output was exercised."],
    }
    EVIDENCE.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    browser.close()
