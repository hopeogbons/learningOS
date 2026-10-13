#!/usr/bin/env python3
"""Explicit opt-in live probes; redact report and keep human review separate."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
LANGUAGES = json.loads((ROOT / 'contracts/language-registry.json').read_text())['languages']
REQUIRED = ('LEARNING_OS_API_KEY', 'LLM_MODEL', 'STT_MODEL', 'TTS_MODEL', 'TTS_VOICE')
ANSWERS = {
 'en': ('The atomic number is the number of protons in the nucleus.', 'The atomic number is the number of neutrons.'),
 'zh-Hans': ('原子序数是原子核中的质子数。', '原子序数是中子数。'),
 'es': ('El número atómico es el número de protones del núcleo.', 'El número atómico es el número de neutrones.'),
 'ar': ('العدد الذري هو عدد البروتونات في النواة.', 'العدد الذري هو عدد النيوترونات.'),
 'pt': ('O número atômico é o número de prótons no núcleo.', 'O número atômico é o número de nêutrons.'),
 'fr': ('Le numéro atomique est le nombre de protons dans le noyau.', 'Le numéro atomique est le nombre de neutrons.'),
 'ja': ('原子番号は原子核内の陽子の数です。', '原子番号は中性子の数です。'),
 'ru': ('Атомный номер — это число протонов в ядре.', 'Атомный номер — это число нейтронов.'),
 'de': ('Die Ordnungszahl ist die Anzahl der Protonen im Kern.', 'Die Ordnungszahl ist die Anzahl der Neutronen.'),
 'id': ('Nomor atom adalah jumlah proton dalam inti atom.', 'Nomor atom adalah jumlah neutron.')}


def digest(value):
    data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def private_directory(value):
    """Raw review content can only be outside the repo or in its ignored runtime directory."""
    path = Path(value).resolve()
    if path == ROOT or ROOT in path.parents:
        if not (ROOT / '.runtime') in path.parents:
            raise ValueError('Private review artifacts must be outside checkout or under .runtime')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def synthetic_context(locale):
    raw = (ROOT / 'fixtures/chem_ch3.md').read_bytes()
    line = raw.decode().splitlines()[3]
    quote = "The atomic number equals the number of protons in an atom's nucleus."
    if quote not in line:
        raise ValueError('Synthetic source locator changed; review fixture before probing')
    return {'chunk_id': 'live-fixture-atomic-number', 'chunk_title': 'Atomic number',
        'source_revision_id': 'synthetic-sha256-' + digest(raw), 'study_locale': locale,
        'speech_locale': next(l['default_speech_locale'] for l in LANGUAGES if l['ui_locale'] == locale),
        'source_language': 'en', 'mode': 'review', 'demo_fixture': False,
        'question_focus': 'Ask only what atomic number represents; do not ask numerical examples or other concepts.',
        'concepts': [{'id': 'live-fixture-proton-count', 'text': quote, 'critical': True, 'citation_ids': ['live-fixture-line4']}],
        'citations': [{'id': 'live-fixture-line4', 'excerpt': quote, 'locator': {'line_start': 4, 'line_end': 4}}]}


def assessment_context(context, turn, answer, confidence, event_id, prior=()):
    return {**context, 'item_id': event_id + '-item', 'answer': answer, 'confidence': confidence,
        'question': turn['question'], 'expected_answer': turn['expected_answer'],
        'evidence_event_ids': [e['id'] for e in prior] + [event_id], 'prior_evidence': list(prior),
        'critical_concept_ids': ['live-fixture-proton-count'], 'demonstrated_concept_ids': [], 'coverage_ready': True}


class Probe:
    def __init__(self, report, private):
        self.report, self.private, self.count = report, private, 0

    def call(self, case_id, fn, check=lambda result: bool(result)):
        """Never emit exception messages, transcripts, prompts or returned source content."""
        self.count += 1
        start = time.monotonic()
        try:
            result = fn()
            passed = bool(check(result))
            record = {'case': case_id, 'status': 'programmatic_pass' if passed else 'failed',
                      'output_sha256': digest(result)}
        except Exception as exc:
            from app.llm import ProviderUnavailable, InvalidModelOutput
            record = {'case': case_id, 'status': 'blocked' if isinstance(exc, ProviderUnavailable) else 'failed',
                      'error_type': type(exc).__name__}
            result = None
        record['elapsed_ms'] = round((time.monotonic() - start) * 1000)
        self.report['checks'].append(record)
        return result

    def keep_private(self, name, data):
        target = self.private / name
        payload = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, indent=2).encode()
        # Never overwrite prior evidence; this directory is a fresh run identifier.
        with target.open('xb') as stream:
            stream.write(payload)
        target.chmod(0o600)


def text_probes(provider, probe):
    turns = {}
    for language in LANGUAGES:
        locale = language['ui_locale']
        context = synthetic_context(locale)
        turn = probe.call(locale + ':text:question', lambda: provider.generate('turn', context))
        if not turn:
            continue
        turns[locale] = turn
        private_cases = {'context': context, 'turn': turn, 'assessments': []}
        for label, answer, confidence, expected in [('correct', ANSWERS[locale][0], 5, 'correct'),
                ('incorrect', ANSWERS[locale][1], 5, 'incorrect'), ('low-confidence', ANSWERS[locale][0], 1, 'correct')]:
            event_id = 'synthetic-' + locale + '-' + label
            payload = assessment_context(context, turn, answer, confidence, event_id)
            result = probe.call(locale + ':text:' + label,
                lambda p=payload: provider.generate('assessment', p),
                lambda v, e=expected, c=confidence: v['correctness'] == e and (c != 1 or not v['title_complete']))
            private_cases['assessments'].append({'case': label, 'answer': answer, 'verdict': result})
        probe.keep_private(locale + '-text-review.json', private_cases)
    return turns


def vision_probes(provider, probe):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import io
    image = Image.new('RGB', (1500, 220), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((35, 40), 'ATOMIC NUMBER = PROTON COUNT', fill='black', font=ImageFont.load_default(size=44))
    draw.text((35, 115), 'A NEUTRAL ATOM HAS EQUAL ELECTRONS AND PROTONS', fill='black', font=ImageFont.load_default(size=32))
    buffer = io.BytesIO(); image.save(buffer, format='PNG'); clear = buffer.getvalue()
    blurred_image = image.filter(ImageFilter.GaussianBlur(radius=30))
    buffer = io.BytesIO(); blurred_image.save(buffer, format='PNG'); blurry = buffer.getvalue()
    probe.keep_private('synthetic-clear.png', clear); probe.keep_private('synthetic-blurry.png', blurry)
    result = probe.call('vision:clear', lambda: provider.vision(clear, 'image/png', 'en'),
        lambda text: 'atomic' in text.casefold() and 'proton' in text.casefold())
    if result is not None:
        probe.keep_private('vision-clear-private.json', {'text': result})
    from app.llm import InvalidModelOutput
    def retake():
        try:
            provider.vision(blurry, 'image/png', 'en')
        except InvalidModelOutput:
            return {'retake_required': True}
        return {'retake_required': False}
    probe.call('vision:blurry-needs-retake', retake, lambda r: r['retake_required'])


def read_manifest(path):
    manifest_path = Path(path).resolve()
    value = json.loads(manifest_path.read_text())
    if value.get('consent') != 'synthetic-or-explicitly-consented':
        raise ValueError('Speech fixture manifest requires explicit source consent attestation')
    languages = value.get('languages', {})
    for locale, rows in languages.items():
        if locale not in {l['default_speech_locale'] for l in LANGUAGES} or len(rows) != 3:
            raise ValueError('Each supplied language needs exactly three native audio turns')
        for row in rows:
            if not isinstance(row.get('expected_transcript'), str) or not row['expected_transcript'].strip():
                raise ValueError('Each turn needs an operator reference transcript')
            if row.get('expected_correctness') not in {'correct', 'incorrect', 'partial', 'uncertain'}:
                raise ValueError('Each turn needs operator expected conceptual correctness')
            if not isinstance(row.get('confidence'), int) or not 1 <= row['confidence'] <= 5:
                raise ValueError('Each turn needs confidence 1 through 5')
            row['_path'] = (manifest_path.parent / row['audio']).resolve()
            if not row['_path'].is_file():
                raise ValueError('Audio fixture missing')
    return languages


def speech_probes(provider, probe, manifest):
    from app.speech import AUDIO_TYPES, MAX_AUDIO_BYTES, audio_duration
    # The adapter's verified-language switch is scoped to this opted-in probe only.
    original = os.environ.get('VERIFIED_SPEECH_LOCALES')
    os.environ['VERIFIED_SPEECH_LOCALES'] = ','.join(manifest)
    try:
        for language in LANGUAGES:
            locale, speech_locale = language['ui_locale'], language['default_speech_locale']
            rows = manifest.get(speech_locale)
            if not rows:
                probe.report['checks'].append({'case': locale + ':speech', 'status': 'blocked', 'reason': 'three-native-audio-fixtures-missing'})
                continue
            context, prior = synthetic_context(locale), []
            private_turns = []
            for index, row in enumerate(rows):
                raw, mime = row['_path'].read_bytes(), row['mime']
                if mime not in AUDIO_TYPES or not raw or len(raw) > MAX_AUDIO_BYTES:
                    probe.report['checks'].append({'case': locale + ':speech:audio-' + str(index + 1), 'status': 'failed', 'reason': 'fixture-type-or-size'})
                    break
                try:
                    duration = audio_duration(raw, mime)
                except Exception:
                    probe.report['checks'].append({'case': locale + ':speech:audio-' + str(index + 1), 'status': 'failed', 'reason': 'fixture-duration-unreadable-or-over-60-seconds'})
                    break
                case = locale + ':speech:turn-' + str(index + 1)
                turn = probe.call(case + ':question', lambda: provider.generate('turn', context))
                if not turn:
                    break
                audio = probe.call(case + ':tts', lambda: provider.tts(turn['question'], speech_locale), lambda b: isinstance(b, bytes) and len(b) > 100)
                if audio:
                    probe.keep_private(locale + '-turn-' + str(index + 1) + '.mp3', audio)
                transcript = probe.call(case + ':stt', lambda: provider.stt(raw, mime, speech_locale),
                                        lambda r: isinstance(r.get('text'), str) and bool(r['text'].strip()))
                if not transcript:
                    break
                event_id = 'synthetic-voice-' + locale + '-' + str(index + 1)
                payload = assessment_context(context, turn, transcript['text'], row['confidence'], event_id, prior)
                verdict = probe.call(case + ':reviewer', lambda: provider.generate('assessment', payload),
                    lambda v: v['correctness'] == row['expected_correctness'] and (row['confidence'] >= 4 or not v['title_complete']))
                private_turns.append({'turn': turn, 'transcript': transcript['text'], 'operator_reference': row['expected_transcript'], 'verdict': verdict})
                probe.report['checks'].append({'case': case + ':fixture', 'status': 'metadata_recorded', 'source_sha256': digest(raw), 'duration_seconds': round(duration, 3)})
                if not verdict:
                    break
                prior.append({'id': event_id, 'concept_id': 'live-fixture-proton-count', 'correctness': verdict['correctness'],
                              'confidence': row['confidence'], 'guessing_signal': verdict['guessing_signal'], 'citation_ids': verdict['citation_ids']})
                context = {**context, 'targeted_followup': True, 'prior_attempts': [{'event_id': event_id,
                    'answer': transcript['text'], 'confidence': row['confidence'], 'correctness': verdict['correctness'],
                    'missing_parts': verdict['missing_parts'], 'feedback': verdict['feedback'], 'citation_ids': verdict['citation_ids'], 'voice': True}]}
                if verdict['title_complete'] and index < 2:
                    probe.report['checks'].append({'case': locale + ':speech:three-turn-fixture', 'status': 'failed',
                        'reason': 'title-completed-early-do-not-retest-demonstrated-concept'})
                    break
            probe.keep_private(locale + '-speech-review.json', private_turns)
    finally:
        if original is None:
            os.environ.pop('VERIFIED_SPEECH_LOCALES', None)
        else:
            os.environ['VERIFIED_SPEECH_LOCALES'] = original


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-provider-calls', action='store_true', help='Explicit opt-in to up to 162 actual billable provider calls; no automatic retries')
    parser.add_argument('--sections', default='text,vision,speech', help='Comma-separated text,vision,speech; all by default')
    parser.add_argument('--speech-manifest', type=Path, help='Private operator-provided three-turn audio fixtures per language')
    parser.add_argument('--private-review-dir', type=Path, help='Fresh directory outside Git or below .runtime for local human review')
    parser.add_argument('--report', type=Path, help='Optional fresh destination for redacted metadata; stdout always redacted')
    args = parser.parse_args(argv)
    sections = set(args.sections.split(','))
    if not sections or not sections <= {'text', 'vision', 'speech'}:
        parser.error('Sections must be text,vision,speech')
    if args.report and args.report.exists():
        parser.error('Report already exists; choose a fresh path')
    presence = {name: bool(os.getenv(name)) for name in REQUIRED}
    report = {'schema_version': 1, 'fixture_version': 'atomic-number-live-v1', 'generated_at': datetime.now(timezone.utc).isoformat(),
        'provider_calls_authorized': args.allow_provider_calls, 'provider_calls_attempted': 0, 'requirements': presence,
        'configured_models': {name: os.getenv(name) or None for name in ('LLM_MODEL', 'STT_MODEL', 'TTS_MODEL')},
        'checks': [], 'human_semantic_review': 'pending', 'native_transcript_review': 'pending',
        'audibility_and_browser_three_turn_review': 'pending', 'L03': 'blocked-until-proficient-review',
        'L04': 'blocked-until-native-transcript-audibility-and-browser-proof'}
    required = {'LEARNING_OS_API_KEY', 'LLM_MODEL'}
    if 'speech' in sections:
        required |= {'STT_MODEL', 'TTS_MODEL', 'TTS_VOICE'}
    missing = sorted(name for name in required if not presence[name])
    report['missing_requirements'] = missing
    for language in LANGUAGES:
        context = synthetic_context(language['ui_locale'])
        report['checks'].append({'case': language['ui_locale'] + ':fixture-preflight', 'status': 'programmatic_pass',
            'source_sha256': context['source_revision_id'].removeprefix('synthetic-sha256-')})
    if not args.allow_provider_calls:
        report['execution'] = 'preflight-only-no-external-calls'
        exit_code = 2 if missing else 0
    elif missing or os.getenv('APP_MODE') not in {'live', 'connected', 'production'}:
        report['execution'] = 'blocked-no-external-calls'
        if os.getenv('APP_MODE') not in {'live', 'connected', 'production'}:
            report['missing_requirements'].append('APP_MODE=live-or-connected-or-production')
        exit_code = 2
    else:
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        private = private_directory(args.private_review_dir or ROOT / '.runtime/live-verification' / run_id)
        from app.llm import get_provider
        provider = get_provider()
        if getattr(provider, 'name', None) != 'openai':
            parser.error('Live verification requires the actual server provider, never a fake')
        probe = Probe(report, private)
        report['execution'] = 'actual-provider-probes'
        if 'text' in sections:
            text_probes(provider, probe)
        if 'vision' in sections:
            vision_probes(provider, probe)
        if 'speech' in sections:
            if not args.speech_manifest:
                for language in LANGUAGES:
                    report['checks'].append({'case': language['ui_locale'] + ':speech', 'status': 'blocked', 'reason': 'three-native-audio-fixtures-missing'})
            else:
                speech_probes(provider, probe, read_manifest(args.speech_manifest))
        report['provider_calls_attempted'] = probe.count
        report['private_review_artifacts'] = 'kept-outside-tracked-files'
        exit_code = 1 if any(c['status'] in {'failed', 'blocked'} for c in report['checks']) else 0
    output = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x') as stream:
            stream.write(output)
    print(output, end='')
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
