"""Bounded synthetic developer receipt, not an application Reviewer hook."""
from datetime import datetime, timezone
import json, sys
from pathlib import Path

def main():
    raw = sys.stdin.read(65537)
    if len(raw) > 65536:
        raise ValueError('Hook payload exceeds safe metadata limit')
    payload = json.loads(raw or '{}')
    event = payload.get('hook_event_name', 'unknown')
    if event not in {'Stop', 'SessionEnd'}:
        event = 'unknown'
    root = Path(__file__).resolve().parents[1]
    out = root / 'docs' / 'evidence' / 'codex-hook-receipts.jsonl'
    out.parent.mkdir(parents=True, exist_ok=True)
    # Never copy arbitrary payload, transcript, cwd or provider tokens.
    record = {'event': event, 'at': datetime.now(timezone.utc).isoformat(),
              'kind': 'developer_lifecycle_receipt', 'app_session_finished': False}
    with out.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record) + '\n')
    print(json.dumps({'ok': True}))

if __name__ == '__main__':
    main()
