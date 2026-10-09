"""Preserve a UTF-8 transcript and create stable line/turn evidence locators."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def prepare(text, title='', started_at=None):
    turns = [{'id': f'T{i:04d}', 'text': line} for i, line in enumerate(text.splitlines(), 1)]
    return {'title': title, 'started_at': started_at,
            'sha256': hashlib.sha256(text.encode()).hexdigest(),
            'transcript': text, 'turns': turns}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('transcript', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--title', default='')
    p.add_argument('--started-at')
    args = p.parse_args()
    source = prepare(args.transcript.read_bytes().decode('utf-8'), args.title, args.started_at)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, body in [('source.json', json.dumps(source, indent=2, ensure_ascii=False)),
                       ('transcript.md', '\n'.join(f"[{t['id']}] {t['text']}" for t in source['turns']))]:
        fd = os.open(args.out / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(body)
    print(f"Prepared {len(source['turns'])} turns; source hash {source['sha256']}")
