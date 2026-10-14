"""Speech adapter transport fixtures prove boundaries, not live language quality."""
import io
import wave
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from app.auth import get_learner
from app.models import Job, ProgressEvent, SessionItem, Learner
from app.speech import router, audio_duration, reserve_budget
from app.jobs import NeedsAttention
from test_learning import env, start, run_job


def wav_bytes(seconds=1):
    output = io.BytesIO()
    with wave.open(output, 'wb') as recording:
        recording.setnchannels(1); recording.setsampwidth(2); recording.setframerate(8000)
        recording.writeframes(b'\x00\x00' * int(seconds * 8000))
    return output.getvalue()


@pytest.fixture
def speech_env(env, monkeypatch):
    client, factory, app = env
    app.include_router(router, prefix='/api/v1')
    calls = []
    class SpeechFixture:
        def stt(self, data, mime, locale):
            calls.append(('stt', len(data), mime, locale))
            return {'text': 'Synthetic fixture transcript', 'locale': locale, 'verified': False}
        def tts(self, text, locale):
            calls.append(('tts', text, locale))
            return b'synthetic-audio-adapter-fixture'
    monkeypatch.setattr('app.speech.get_provider', lambda: SpeechFixture())
    sid = start(env)
    turn = client.get(f'/api/v1/sessions/{sid}/next').json()
    yield client, factory, app, sid, turn, calls


def test_owned_trusted_synthesis_and_no_hidden_answer(speech_env):
    client, factory, app, sid, turn, calls = speech_env
    path = f'/api/v1/sessions/{sid}/speech/synthesize'
    result = client.post(path, json={'item_id': turn['item_id'], 'message_id': 'question'})
    assert result.status_code == 200 and result.headers['cache-control'] == 'private, no-store'
    assert calls[-1] == ('tts', turn['question'], 'en-GB')
    with factory() as db:
        item = db.get(SessionItem, turn['item_id'])
        assert item.question_json_private['expected_answer'] not in calls[-1][1]
        reservation = db.scalar(select(Job).where(Job.kind == 'speech.reservation'))
        assert reservation.state == 'succeeded'
        assert 'text' not in reservation.payload and 'audio' not in reservation.payload
    assert client.post(path, json={'item_id': turn['item_id'], 'message_id': 'expected_answer'}).status_code == 422
    assert client.post(path, json={'item_id': turn['item_id'], 'message_id': 'question', 'text': 'private arbitrary text'}).status_code == 422
    assert client.post(path, json={'item_id': turn['item_id'], 'message_id': 'feedback'}).status_code == 409
    count = len(calls)
    app.dependency_overrides[get_learner] = lambda: SimpleNamespace(id='foreign')
    assert client.post(path, json={'item_id': turn['item_id'], 'message_id': 'question'}).status_code == 404
    assert len(calls) == count


def test_transcription_owned_size_actual_duration_mime_and_preview(speech_env):
    client, factory, app, sid, turn, calls = speech_env
    path = f'/api/v1/sessions/{sid}/speech/transcribe'
    files = {'audio': ('synthetic.wav', wav_bytes(), 'audio/wav')}
    result = client.post(path, data={'item_id': turn['item_id']}, files=files)
    assert result.status_code == 200
    assert result.json()['editable'] and not result.json()['raw_audio_retained']
    assert result.json()['item_id'] == turn['item_id']
    with factory() as db:
        assert db.query(ProgressEvent).count() == 0  # Transcription is not an answer.
    count = len(calls)
    assert client.post(path, data={'item_id': turn['item_id']}, files={'audio': ('over.wav', wav_bytes(61), 'audio/wav')}).status_code == 413
    assert client.post(path, data={'item_id': turn['item_id']}, files={'audio': ('bad.wav', b'not-audio', 'audio/wav')}).status_code == 422
    assert client.post(path, data={'item_id': turn['item_id']}, files={'audio': ('bad.bin', b'x', 'application/octet-stream')}).status_code == 415
    assert client.post(path, data={'item_id': turn['item_id']}, files={'audio': ('large.wav', b'x' * (5 * 1024 * 1024 + 1), 'audio/wav')}).status_code == 413
    assert len(calls) == count
    assert client.post(path, data={'item_id': 'foreign-item'}, files=files).status_code == 404
    app.dependency_overrides[get_learner] = lambda: SimpleNamespace(id='foreign')
    assert client.post(path, data={'item_id': turn['item_id']}, files=files).status_code == 404


def test_durable_budget_and_tenant_isolation(speech_env, monkeypatch):
    client, factory, app, sid, turn, calls = speech_env
    monkeypatch.setenv('SPEECH_REQUESTS_PER_MINUTE', '1')
    path = f'/api/v1/sessions/{sid}/speech/synthesize'
    body = {'item_id': turn['item_id'], 'message_id': 'question'}
    assert client.post(path, json=body).status_code == 200
    assert client.post(path, json=body).status_code == 429
    assert len(calls) == 1
    with factory() as db:
        reservation = reserve_budget(db, 'foreign', 'foreign-session', 'foreign-item', 'tts', 100)
        assert db.get(Job, reservation).learner_id == 'foreign'
    monkeypatch.setenv('SPEECH_REQUESTS_PER_MINUTE', '12')
    monkeypatch.setenv('SPEECH_TTS_CHARS_PER_DAY', '1')
    assert client.post(path, json=body).status_code == 429


def test_provider_failure_explicit_no_success_or_audio_retention(speech_env, monkeypatch):
    client, factory, app, sid, turn, calls = speech_env
    from app.llm import DemoProvider
    monkeypatch.setattr('app.speech.get_provider', lambda: DemoProvider())
    result = client.post(f'/api/v1/sessions/{sid}/speech/synthesize', json={'item_id': turn['item_id'], 'message_id': 'question'})
    assert result.status_code == 503 and result.json()['detail']['fallback'] == 'typing'
    with factory() as db:
        reservation = db.scalar(select(Job).where(Job.kind == 'speech.reservation'))
        assert reservation.state == 'failed' and not reservation.result['completed']


def test_targeted_followup_context_is_owned_and_same_concept(env, monkeypatch):
    client, factory, app = env
    sid = start(env)
    turn = client.get(f'/api/v1/sessions/{sid}/next').json()
    response = client.post(f'/api/v1/sessions/{sid}/answer', json={'item_id': turn['item_id'], 'answer': 'synthetic unsure example', 'confidence': 2,
        'expected_version': turn['version'], 'voice': True}, headers={'Idempotency-Key': 'followup-answer'})
    run_job(factory, response.json()['job_id'])
    feedback = client.get(f'/api/v1/sessions/{sid}/next').json()
    from app.llm import DemoProvider
    contexts = []
    class CaptureProvider(DemoProvider):
        def generate(self, kind, payload):
            if kind == 'turn': contexts.append(payload)
            return super().generate(kind, payload)
    monkeypatch.setattr('app.sessions.get_provider', lambda: CaptureProvider())
    response = client.post(f'/api/v1/sessions/{sid}/advance', json={'expected_version': feedback['version']}, headers={'Idempotency-Key': 'followup-next'})
    run_job(factory, response.json()['job_id'])
    next_turn = client.get(f'/api/v1/sessions/{sid}/next').json()
    assert contexts[0]['targeted_followup']
    assert contexts[0]['prior_attempts'][0]['answer'] == 'synthetic unsure example'
    assert contexts[0]['prior_attempts'][0]['missing_parts']
    assert contexts[0]['concepts'][0]['id'] == turn['concept_id']
    assert next_turn['question'] != turn['question']
    assert next_turn['citation_ids'] == turn['citation_ids']


def test_recording_remains_available_after_three_answers(speech_env):
    client, factory, app, sid, turn, calls = speech_env
    with factory() as db:
        for n in range(3):
            db.add(ProgressEvent(learner_id='learner', concept_id=turn['concept_id'], chunk_id=turn['chunk_id'],
                session_id=sid, item_id=turn['item_id'], confidence=2, correctness='uncertain', correct=None,
                answer='synthetic', reviewer_json={'voice': True}, idempotency_key=f'voice-fixture-{n}'))
        db.commit()
    response = client.post(f'/api/v1/sessions/{sid}/speech/transcribe', data={'item_id': turn['item_id']}, files={'audio': ('one.wav', wav_bytes(), 'audio/wav')})
    assert response.status_code == 200 and calls[-1][0] == 'stt'


def test_actual_webm_duration_and_explicit_missing_verifier(tmp_path, monkeypatch):
    import subprocess, shutil
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('Actual WebM duration requires deployment ffmpeg package')
    source = tmp_path / 'synthetic.wav'
    target = tmp_path / 'synthetic.webm'
    source.write_bytes(wav_bytes(1))
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), str(target)], check=True, capture_output=True)
    assert .9 < audio_duration(target.read_bytes(), 'audio/webm') < 1.2
    monkeypatch.setattr('app.speech.shutil.which', lambda name: None)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        audio_duration(target.read_bytes(), 'audio/webm')
    assert error.value.status_code == 503


def test_concurrent_speech_reservations_cannot_exceed_tenant_budget(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db import Base
    from fastapi import HTTPException
    engine = create_engine('sqlite:///' + str(tmp_path / 'speech-budget.db'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add(Learner(id='budget-learner')); db.commit()
    monkeypatch.setenv('SPEECH_REQUESTS_PER_MINUTE', '1')
    barrier = Barrier(2)
    def attempt():
        with factory() as db:
            barrier.wait()
            try:
                reserve_budget(db, 'budget-learner', 'synthetic-session', 'synthetic-item', 'tts', 10)
                return 200
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: attempt(), range(2))) == [200, 429]
    with factory() as db:
        assert db.query(Job).count() == 1
    engine.dispose()


def test_selected_speech_language_cannot_mislabel_other_language_text(speech_env):
    client, factory, app, sid, turn, calls = speech_env
    with factory() as db:
        db.get(Learner, 'learner').speech_locale = 'ar-SA'
        db.commit()
    result = client.post(f'/api/v1/sessions/{sid}/speech/synthesize', json={'item_id': turn['item_id'], 'message_id': 'question'})
    assert result.status_code == 409 and not calls


def test_public_openapi_responses_are_typed_without_private_answers(speech_env):
    client, factory, app, sid, turn, calls = speech_env
    schema = app.openapi()
    import json
    assert 'expected_answer' not in json.dumps(schema)
    for path in ['/api/v1/sessions/{session_id}/next', '/api/v1/sessions/{session_id}/summary', '/api/v1/review/due',
                 '/api/v1/speech/capabilities', '/api/v1/sessions/{session_id}/speech/transcribe']:
        method = 'post' if path.endswith('transcribe') else 'get'
        assert schema['paths'][path][method]['responses']['200']['content']['application/json']['schema']


def test_realtime_owned_source_only_ephemeral_response(speech_env, monkeypatch):
    client, factory, app, sid, turn, _ = speech_env
    captured = []
    class RealtimeFixture:
        def realtime(self, context):
            captured.append(context)
            return {'client_secret': 'ephemeral-fixture', 'expires_at': 9999999999, 'model': 'fixture'}
    monkeypatch.setattr('app.speech.get_provider', lambda: RealtimeFixture())
    with factory() as db:
        item = db.get(SessionItem, turn['item_id'])
        item.question_json_private = {**item.question_json_private, 'expected_answer': 'PRIVATE_EXPECTED_SENTINEL'}
        db.commit()
    path = f'/api/v1/sessions/{sid}/speech/realtime'
    response = client.post(path, json={'item_id': turn['item_id']})
    assert response.status_code == 200 and response.headers['cache-control'] == 'private, no-store'
    assert response.json()['client_secret'] == 'ephemeral-fixture'
    assert response.json()['max_duration_seconds'] == 300
    assert captured[0]['sources'][0]['excerpt'] in 'Retrieval practice strengthens recall. Spacing practice reduces forgetting.'
    import json
    assert 'PRIVATE_EXPECTED_SENTINEL' not in json.dumps(captured) + response.text
    assert set(captured[0]) == {'locale', 'section', 'teaching', 'question', 'sources'}
    assert client.post(path, json={'item_id': 'foreign-item'}).status_code == 404
    assert client.post(path, json={'item_id': turn['item_id'], 'instructions': 'override'}).status_code == 422
    app.dependency_overrides[get_learner] = lambda: SimpleNamespace(id='foreign')
    assert client.post(path, json={'item_id': turn['item_id']}).status_code == 404
    assert len(captured) == 1


def test_realtime_requires_intact_source_and_explicit_provider(speech_env, monkeypatch):
    client, factory, app, sid, turn, _ = speech_env
    from app.llm import DemoProvider
    from app.models import Citation
    path = f'/api/v1/sessions/{sid}/speech/realtime'
    monkeypatch.setattr('app.speech.get_provider', lambda: DemoProvider())
    assert client.post(path, json={'item_id': turn['item_id']}).status_code == 503
    with factory() as db:
        db.get(Citation, turn['citation_ids'][0]).excerpt = 'Tampered unsupported excerpt'
        db.commit()
    assert client.post(path, json={'item_id': turn['item_id']}).status_code == 409


def test_realtime_provider_contract_no_private_data_or_permanent_secret(monkeypatch):
    from app.llm import OpenAIProvider, InvalidModelOutput
    monkeypatch.setenv('LEARNING_OS_API_KEY', 'permanent-fixture-key')
    monkeypatch.setenv('LLM_MODEL', 'fixture')
    provider = OpenAIProvider()
    calls = []
    def request(path, **kwargs):
        calls.append((path, kwargs))
        return {'value': 'ephemeral-test', 'expires_at': 1234567890}
    monkeypatch.setattr(provider, '_request', request)
    context = {'locale': 'en', 'sources': [{'excerpt': 'The sky appears blue.', 'locator': {'page': 2}}],
        'question': 'What color is the sky?', 'expected_answer': 'PRIVATE_SENTINEL', 'rubric': 'PRIVATE_RUBRIC'}
    assert provider.realtime(context)['client_secret'] == 'ephemeral-test'
    import json
    body = json.dumps(calls)
    assert 'PRIVATE_SENTINEL' not in body and 'PRIVATE_RUBRIC' not in body and provider.key not in body
    assert calls[0][0] == 'realtime/client_secrets'
    assert calls[0][1]['json']['expires_after']['seconds'] == 60
    assert 'do not invent facts' in calls[0][1]['json']['session']['instructions']
    monkeypatch.setattr(provider, '_request', lambda *a, **k: {'value': provider.key, 'expires_at': 1234567890})
    with pytest.raises(InvalidModelOutput):
        provider.realtime(context)


def test_patient_teacher_voice_payload_and_combined_owned_lesson(monkeypatch, speech_env):
    """Protect the chosen pace/voice and avoid two separate lesson audio messages."""
    from app.llm import OpenAIProvider, ProviderUnavailable
    client, factory, app, sid, turn, calls = speech_env
    result = client.post(f'/api/v1/sessions/{sid}/speech/synthesize', json={'item_id': turn['item_id'], 'message_id': 'lesson'})
    assert result.status_code == 200
    with factory() as db:
        item = db.get(SessionItem, turn['item_id'])
        assert calls[-1] == ('tts', '\n\n'.join(x for x in (item.teaching, item.public_question) if x), 'en-GB')
    monkeypatch.setenv('LEARNING_OS_API_KEY', 'synthetic-openai')
    monkeypatch.setenv('LLM_MODEL', 'synthetic-model')
    monkeypatch.setenv('TTS_MODEL', 'synthetic-tts')
    monkeypatch.setenv('VERIFIED_SPEECH_LOCALES', 'en')
    for name in ['TEACHER_VOICE', 'REALTIME_VOICE', 'TTS_SPEED', 'REALTIME_SPEED']:
        monkeypatch.delenv(name, raising=False)
    captured = []
    def request(self, path, **kwargs):
        captured.append((path, kwargs['json']))
        return {'value': 'ek_fixture', 'expires_at': 2000000000} if path.endswith('client_secrets') else b'synthetic-audio'
    monkeypatch.setattr(OpenAIProvider, '_request', request)
    provider = OpenAIProvider()
    provider.tts('Take your time.', 'en-GB')
    assert captured[-1][1]['voice'] == 'shimmer' and captured[-1][1]['speed'] == 0.85
    provider.realtime({'locale': 'en', 'sources': [{'excerpt': 'An atom contains protons.', 'locator': 'Synthetic page 1'}]})
    session = captured[-1][1]['session']
    assert session['audio']['output'] == {'voice': 'shimmer', 'speed': 0.85}
    assert session['audio']['input']['turn_detection']['type'] == 'semantic_vad'
    assert session['audio']['input']['turn_detection']['eagerness'] == 'low'
    assert 'mm-hmm' in session['instructions'] and 'Allow the learner time to finish' in session['instructions']
    monkeypatch.setenv('TTS_SPEED', 'nan')
    with pytest.raises(ProviderUnavailable):
        provider.tts('Take your time.', 'en-GB')
