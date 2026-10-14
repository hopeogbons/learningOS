import re
from urllib.parse import urlsplit, parse_qs
from .base import ExtractedSection, SourceError, SourceSnapshot
from ..ingest_limits import MAX_CAPTION_SEGMENTS, MAX_CAPTION_TEXT_BYTES


def video_id(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.hostname in {'youtu.be', 'www.youtu.be'}: value = parsed.path.strip('/')
    elif parsed.hostname in {'youtube.com','www.youtube.com','m.youtube.com'}: value = parse_qs(parsed.query).get('v', [''])[0]
    else: raise SourceError('invalid_video', 'Use a supported YouTube watch URL.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', value): raise SourceError('invalid_video', 'The video ID is invalid.')
    return value


def extract_captions(url: str, authorized_caption_reader=None) -> SourceSnapshot:
    identifier = video_id(url)
    if authorized_caption_reader is None:
        raise SourceError('captions_unavailable', 'Authorized captions are not configured. Paste a permitted transcript as text; no video is copied or watched.')
    captions = authorized_caption_reader(identifier)
    if not captions: raise SourceError('no_captions', 'This video has no permitted captions available.')
    if len(captions)>MAX_CAPTION_SEGMENTS:raise SourceError('captions_segment_limit',f'Limit transcripts to {MAX_CAPTION_SEGMENTS} caption segments.')
    if sum(len(str(item.get('text','')).encode('utf-8')) for item in captions)>MAX_CAPTION_TEXT_BYTES:
        raise SourceError('captions_size_limit','The permitted transcript exceeds the 2 MiB text limit.')
    canonical = f'https://www.youtube.com/watch?v={identifier}'
    sections = []
    for index, caption in enumerate(captions,1):
        start, end, text = float(caption['start']), float(caption['end']), str(caption['text']).strip()
        if start < 0 or end <= start or not text: raise SourceError('invalid_captions', 'Caption timestamps or text are invalid.')
        sections.append(ExtractedSection(f'Caption {index}', text, 'captions', {'video_id': identifier, 'url': canonical, 'start_seconds': start, 'end_seconds': end, 'language': caption.get('language','und')}))
    return SourceSnapshot(sections, canonical)
