"""Session-owned transient speech with durable tenant budgets and trusted text."""
from datetime import timedelta
import io
import json
import math
import os
import shutil
import subprocess
import tempfile
import wave
from typing import Literal
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from starlette.concurrency import run_in_threadpool
from .auth import get_learner
from .db import get_db, utcnow, as_utc
from .llm import get_provider, ProviderUnavailable, InvalidModelOutput
from .models import Learner, StudySession, SessionItem, ProgressEvent, Job
from .sessions import owned

router = APIRouter()
LOCALES = ['en','zh-Hans','es','ar','pt','fr','ja','ru','de','id']
VARIANTS = {'en':'en','en-US':'en','en-GB':'en','zh-Hans':'zh-Hans','zh-CN':'zh-Hans','es':'es','es-ES':'es','ar':'ar','ar-SA':'ar','pt':'pt','pt-BR':'pt','fr':'fr','fr-FR':'fr','ja':'ja','ja-JP':'ja','ru':'ru','ru-RU':'ru','de':'de','de-DE':'de','id':'id','id-ID':'id'}
MAX_AUDIO_BYTES = 5 * 1024 * 1024
MAX_AUDIO_SECONDS = 60
AUDIO_TYPES = {'audio/webm': '.webm', 'audio/wav': '.wav', 'audio/mpeg': '.mp3', 'audio/mp4': '.mp4', 'audio/ogg': '.ogg'}
DEMUXERS = {'audio/webm': 'matroska', 'audio/mpeg': 'mp3', 'audio/mp4': 'mov', 'audio/ogg': 'ogg'}


def locale_for(value):
    if value not in VARIANTS:
        raise HTTPException(422, 'speech_locale_unsupported')
    return VARIANTS[value]


def voice_count(db, session):
    events = db.scalars(select(ProgressEvent).where(ProgressEvent.learner_id == session.learner_id, ProgressEvent.session_id == session.id))
    return sum(bool(e.reviewer_json.get('voice')) for e in events)


def speech_turn(db, learner_id, session_id, item_id, transcribe=False):
    session = owned(db, StudySession, session_id, learner_id)
    item = owned(db, SessionItem, item_id, learner_id)
    if item.session_id != session.id or session.current_item_id != item.id:
        raise HTTPException(404, 'Not found')
    if session.status not in {'awaiting_answer', 'feedback'}:
        raise HTTPException(409, 'speech_turn_inactive')
    if transcribe and (session.status != 'awaiting_answer' or item.answer_state != 'pending'):
        raise HTTPException(409, 'speech_answer_already_submitted')
    count = voice_count(db, session)
    if transcribe and count >= 3:
        raise HTTPException(409, 'speech_turn_limit_typing_available')
    return session, item, count


def audio_duration(data: bytes, mime: str) -> float:
    """Validate actual container duration; never trust declarations or byte-size guesses."""
    try:
        if mime == 'audio/wav':
            with wave.open(io.BytesIO(data), 'rb') as recording:
                duration = recording.getnframes() / recording.getframerate()
        else:
            executable = shutil.which('ffprobe')
            if not executable:
                raise HTTPException(503, 'speech_duration_verifier_unavailable')
            with tempfile.NamedTemporaryFile(suffix=AUDIO_TYPES[mime]) as source:
                source.write(data); source.flush()
                result = subprocess.run([executable, '-v', 'error', '-protocol_whitelist', 'file,pipe',
                    '-f', DEMUXERS[mime], '-read_intervals', '%+61', '-show_entries',
                    'format=duration:stream=codec_type,duration:packet=pts_time,duration_time',
                    '-of', 'json', source.name], capture_output=True, timeout=8, check=True)
                metadata = json.loads(result.stdout)
            streams = metadata.get('streams', [])
            if not streams or any(s.get('codec_type') != 'audio' for s in streams):
                raise ValueError('not_audio_only')
            duration_value = metadata.get('format', {}).get('duration')
            if duration_value is None:
                durations = [float(s['duration']) for s in streams if s.get('duration') not in {None, 'N/A'}]
                if not durations:
                    packets = [p for p in metadata.get('packets', []) if p.get('pts_time') is not None]
                    if not packets:
                        raise ValueError('duration_unknown')
                    start = min(float(p['pts_time']) for p in packets)
                    end = max(float(p['pts_time']) + float(p.get('duration_time', 0)) for p in packets)
                    durations = [end - start]
                duration_value = max(durations)
            duration = float(duration_value)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('duration_invalid')
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, OSError, wave.Error, subprocess.SubprocessError):
        raise HTTPException(422, 'speech_audio_unreadable_or_duration_unknown') from None
    if duration > MAX_AUDIO_SECONDS:
        raise HTTPException(413, 'speech_audio_duration_limit')
    return duration


def reserve_budget(db, learner_id, session_id, item_id, operation, units):
    """Serialize each tenant's durable reservations before provider billing."""
    db.commit()
    db.execute(update(Learner).where(Learner.id == learner_id).values(id=Learner.id))
    now = utcnow()
    recent = list(db.scalars(select(Job).where(Job.learner_id == learner_id, Job.kind == 'speech.reservation', Job.created_at >= now - timedelta(days=1))))
    minute = sum(1 for j in recent if as_utc(j.created_at) >= now - timedelta(minutes=1))
    requests_per_minute = int(os.getenv('SPEECH_REQUESTS_PER_MINUTE', '12'))
    requests_per_day = int(os.getenv('SPEECH_REQUESTS_PER_DAY', '120'))
    limit_units = int(os.getenv('SPEECH_STT_SECONDS_PER_DAY', '3600')) if operation == 'stt' else int(os.getenv('SPEECH_TTS_CHARS_PER_DAY', '100000'))
    used_units = sum(j.payload.get('units', 0) for j in recent if j.payload.get('operation') == operation)
    if minute >= requests_per_minute or len(recent) >= requests_per_day or used_units + units > limit_units:
        db.rollback()
        raise HTTPException(429, 'speech_budget_exceeded')
    reservation = Job(learner_id=learner_id, kind='speech.reservation', entity_id=session_id, state='reserved', payload={'session_id': session_id, 'item_id': item_id, 'operation': operation, 'units': units})
    db.add(reservation); db.flush()
    reservation_id = reservation.id
    db.commit()
    return reservation_id


def finalize_budget(db, learner_id, reservation_id, succeeded):
    row = owned(db, Job, reservation_id, learner_id)
    row.state = 'succeeded' if succeeded else 'failed'
    row.retryable = False
    row.error_code = None if succeeded else 'speech_unavailable'
    row.result = {'completed': succeeded, 'raw_audio_retained': False}
    db.commit()


def trusted_text(item, message_id):
    if message_id == 'teaching':
        text = item.teaching
    elif message_id == 'question':
        text = item.public_question
    else:
        if item.answer_state != 'answered':
            raise HTTPException(409, 'speech_feedback_not_available')
        text = item.feedback_json.get('feedback', '')
    if not text:
        raise HTTPException(409, 'speech_message_not_available')
    if len(text) > 4000:
        raise HTTPException(413, 'speech_message_size')
    return text


class SpeechLanguageDTO(BaseModel):
    locale: str
    stt: str
    tts: str
    verified: bool
    fallback: Literal['typing']


class SpeechCapabilitiesDTO(BaseModel):
    provider: str
    raw_audio_retained: Literal[False]
    languages: list[SpeechLanguageDTO]
    max_audio_bytes: int
    max_audio_seconds: int
    max_voice_turns: int
    live_gate: str


@router.get('/speech/capabilities', response_model=SpeechCapabilitiesDTO)
def capabilities(learner=Depends(get_learner)):
    configured = bool(os.getenv('LEARNING_OS_API_KEY') and os.getenv('LLM_MODEL') and os.getenv('STT_MODEL') and os.getenv('TTS_MODEL') and os.getenv('TTS_VOICE'))
    return {'provider': 'openai-configured-unverified' if configured else 'unavailable', 'raw_audio_retained': False, 'languages': [{'locale': locale, 'stt': 'configured-unverified' if configured else 'unavailable', 'tts': 'configured-unverified' if configured else 'unavailable', 'verified': False, 'fallback': 'typing'} for locale in LOCALES], 'max_audio_bytes': MAX_AUDIO_BYTES, 'max_audio_seconds': MAX_AUDIO_SECONDS, 'max_voice_turns': 3, 'live_gate': 'L04-blocked-until-real-three-turn-proof'}


class TranscriptDTO(BaseModel):
    text: str
    locale: str
    verified: bool
    session_id: str
    item_id: str
    language: str
    raw_audio_retained: Literal[False]
    editable: Literal[True]
    voice_turn_count: int


@router.post('/sessions/{session_id}/speech/transcribe', response_model=TranscriptDTO)
async def transcribe(session_id: str, item_id: str = Form(...), audio: UploadFile = File(...), db=Depends(get_db), learner=Depends(get_learner)):
    session, item, count = speech_turn(db, learner.id, session_id, item_id, transcribe=True)
    locale = learner.speech_locale
    locale_for(locale)
    mime = (audio.content_type or '').split(';')[0].strip().lower()
    if mime not in AUDIO_TYPES:
        await audio.close()
        raise HTTPException(415, 'speech_audio_type')
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    await audio.close()
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, 'speech_audio_size')
    duration = await run_in_threadpool(audio_duration, data, mime)
    reservation = await run_in_threadpool(reserve_budget, db, learner.id, session.id, item.id, 'stt', duration)
    learner_id = learner.id
    try:
        result = await run_in_threadpool(lambda: get_provider().stt(data, mime, locale))
    except (ProviderUnavailable, InvalidModelOutput):
        await run_in_threadpool(finalize_budget, db, learner_id, reservation, False)
        raise HTTPException(503, {'code': 'speech_unavailable', 'fallback': 'typing'}) from None
    finally:
        data = b''
    await run_in_threadpool(finalize_budget, db, learner_id, reservation, True)
    return {**result, 'session_id': session_id, 'item_id': item_id, 'language': locale, 'raw_audio_retained': False, 'editable': True, 'voice_turn_count': count}


class SpeechInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_id: str
    message_id: Literal['teaching', 'question', 'feedback']


@router.post('/sessions/{session_id}/speech/synthesize', response_class=Response,
             responses={200: {'content': {'audio/mpeg': {'schema': {'type': 'string', 'format': 'binary'}}}}})
def synthesize(session_id: str, body: SpeechInput, db=Depends(get_db), learner=Depends(get_learner)):
    session, item, count = speech_turn(db, learner.id, session_id, body.item_id)
    locale = learner.speech_locale
    locale_for(locale)
    if locale_for(locale) != locale_for(item.generation_locale):
        raise HTTPException(409, 'speech_language_mismatch_typing_available')
    text = trusted_text(item, body.message_id)
    reservation = reserve_budget(db, learner.id, session.id, item.id, 'tts', len(text))
    learner_id = learner.id
    try:
        data = get_provider().tts(text, locale)
    except (ProviderUnavailable, InvalidModelOutput):
        finalize_budget(db, learner_id, reservation, False)
        raise HTTPException(503, {'code': 'speech_unavailable', 'fallback': 'typing'}) from None
    finalize_budget(db, learner_id, reservation, True)
    return Response(data, media_type='audio/mpeg', headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff', 'X-Voice-Turn-Count': str(count)})
