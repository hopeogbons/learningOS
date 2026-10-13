"""Public-page fetches pin validated DNS addresses and revalidate every redirect."""
import http.client
import ipaddress
import socket
import ssl
import time
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit, urljoin
from .base import ExtractedSection, SourceError, SourceSnapshot

MAX_BYTES = 2 * 1024 * 1024


def validate_url_syntax(url: str):
    """Accept a pending public-hostname record without performing network I/O."""
    try:
        parsed=urlsplit(url)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None,80,443}:raise ValueError()
        if len(url)>4096 or any(ord(c)<33 for c in url) or '\\' in url:raise ValueError()
        host=parsed.hostname.encode('idna').decode('ascii').lower().rstrip('.')
        try:ipaddress.ip_address(host)
        except ValueError:pass
        else:raise ValueError()
        if len(host)>253 or '.' not in host or not re.fullmatch(r'[a-z0-9.-]+',host):raise ValueError()
        if re.fullmatch(r'[0-9a-fx.]+',host) or host.split('.')[-1].isdigit():raise ValueError()
        if host=='localhost' or host.endswith(('.localhost','.local','.internal','.invalid','.test','.example','.onion','.localdomain')):raise ValueError()
        if any(not label or len(label)>63 or label.startswith('-') or label.endswith('-') for label in host.split('.')):raise ValueError()
        return parsed
    except (ValueError,UnicodeError) as exc:
        raise SourceError('unsafe_url','Use a public HTTP(S) hostname without credentials or reserved/private destinations.') from exc


def validate_url(url: str):
    parsed=validate_url_syntax(url)
    host=parsed.hostname.encode('idna').decode('ascii')
    try:
        addresses=sorted({entry[4][0] for entry in socket.getaddrinfo(host,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM)})
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):raise ValueError()
    except OSError as exc:
        raise SourceError('web_dns_unavailable','Public-source DNS is temporarily unavailable.',True) from exc
    except ValueError as exc:
        raise SourceError('unsafe_url','The source resolves to a private or reserved network destination.') from exc
    return parsed,addresses


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, address, port, secure):
        super().__init__(host, port=port, timeout=10)
        self.address, self.secure = address, secure
    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)
        if self.secure:
            self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip = 0; self.buffer = []; self.paragraphs = []; self.title = ''; self.in_title = False
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript', 'svg'}: self.skip += 1
        if tag == 'title': self.in_title = True
        if tag in {'p','h1','h2','h3','h4','li','pre','article','section','div'}: self.flush()
    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'svg'}: self.skip = max(0, self.skip-1)
        if tag == 'title': self.in_title = False
        if tag in {'p','h1','h2','h3','h4','li','pre','article','section','div'}: self.flush()
    def handle_data(self, data):
        if self.in_title: self.title += data
        elif not self.skip: self.buffer.append(data)
    def flush(self):
        value = ' '.join(' '.join(self.buffer).split()); self.buffer = []
        if value: self.paragraphs.append(value)


def fetch_public_page(url: str) -> SourceSnapshot:
    for _ in range(6):
        parsed, addresses = validate_url(url)
        connection = PinnedHTTPConnection(parsed.hostname, addresses[0], parsed.port or (443 if parsed.scheme == 'https' else 80), parsed.scheme == 'https')
        try:
            path = urlunsplit(('', '', parsed.path or '/', parsed.query, ''))
            connection.request('GET', path, headers={'Host': parsed.netloc, 'User-Agent': 'LearningOS/1.0 public-study-snapshot', 'Accept': 'text/html,text/plain', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in {301,302,303,307,308}:
                location = response.getheader('Location')
                if not location: raise SourceError('bad_redirect', 'The source returned an invalid redirect.')
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise SourceError('public_source_unavailable', f'The public page is unavailable (HTTP {response.status}).', response.status >= 500)
            mime = response.getheader('Content-Type', '').split(';')[0].lower()
            if mime not in {'text/html','text/plain','application/xhtml+xml'}:
                raise SourceError('unsupported_web_type', 'Only public HTML or plain-text pages are supported.')
            if response.getheader('Content-Encoding', 'identity') != 'identity':
                raise SourceError('unsupported_encoding', 'The page must support uncompressed public text.')
            parts=[]; total=0; started=time.monotonic()
            while True:
                chunk=response.read1(min(65536,MAX_BYTES+1-total))
                if not chunk:break
                parts.append(chunk);total+=len(chunk)
                if total>MAX_BYTES:raise SourceError('web_too_large','The public page exceeds 2 MB.')
                if time.monotonic()-started>20:raise SourceError('web_timeout','The public page exceeded its time budget.',True)
            body=b''.join(parts)
        except SourceError:
            raise
        except (OSError, http.client.HTTPException) as exc:
            raise SourceError('web_network', 'The public source could not be fetched.', True) from exc
        finally:
            connection.close()
        charset = 'utf-8'
        content_type = response.getheader('Content-Type', '')
        if 'charset=' in content_type: charset = content_type.split('charset=')[-1].split(';')[0].strip(' \"')
        try: text = body.decode(charset)
        except (LookupError, UnicodeDecodeError): text = body.decode('utf-8', errors='replace')
        parser = PageParser(); parser.feed(text); parser.flush()
        paragraphs = parser.paragraphs if mime != 'text/plain' else [p.strip() for p in text.split('\n\n') if p.strip()]
        canonical = urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', '', ''))
        snapshot_at = datetime.now(timezone.utc).isoformat()
        sections = [ExtractedSection(parser.title.strip()[:160] or 'Public page', p, 'web', {'url': canonical, 'snapshot_at': snapshot_at, 'paragraph': index}) for index,p in enumerate(paragraphs, 1)]
        if not sections: raise SourceError('empty_web', 'No public study text was found.')
        return SourceSnapshot(sections, canonical, metadata={'snapshot_at': snapshot_at})
    raise SourceError('redirect_limit', 'The URL redirects too many times.')
