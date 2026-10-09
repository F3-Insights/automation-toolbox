"""Check action evidence references; semantic correctness still requires source review."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys


def known_references(directory):
    refs = set()
    names = {'contact': 'contact', 'contacts': 'contact', 'company': 'company',
             'companies': 'company', 'project': 'project', 'projects': 'project',
             'task': 'task', 'tasks': 'task', 'domain': 'domain', 'domains': 'domain',
             'goal': 'goal', 'goals': 'goal', 'note': 'note', 'notes': 'note'}
    def visit(value, kind=None):
        if isinstance(value, list):
            for item in value:
                visit(item, kind)
        elif isinstance(value, dict):
            if value.get('_ref'):
                refs.add(value['_ref'])
            if kind and value.get('id'):
                refs.add(f"portal://{kind}/{value['id']}")
            for key, item in value.items():
                child_kind = names.get(key)
                if key == 'items':
                    child_kind = value.get('entity_type')
                visit(item, child_kind)
    for path in Path(directory).glob('*.json'):
        receipt = json.loads(path.read_text())
        visit(receipt.get('result', {}))
    return refs


def check(source, actions, known_refs=None):
    errors = []
    if hashlib.sha256(source['transcript'].encode()).hexdigest() != source['sha256']:
        errors.append('Source hash mismatch')
    expected = [{'id': f'T{i:04d}', 'text': line} for i, line in enumerate(source['transcript'].splitlines(), 1)]
    if source['turns'] != expected:
        errors.append('Source turn map does not match transcript')
    turns = {t['id']: ' '.join(t['text'].split()) for t in source['turns']}
    seen = set()
    for item in actions:
        key = item.get('id')
        if not key or key in seen:
            errors.append(f'{key}: missing or duplicate action ID')
        seen.add(key)
        if item.get('status') not in ('accepted', 'requested', 'proposed'):
            errors.append(f'{key}: invalid status')
        if not item.get('actor') or not item.get('action'):
            errors.append(f'{key}: actor/action missing')
        if not item.get('evidence'):
            errors.append(f'{key}: no evidence')
        for evidence in item.get('evidence') or []:
            quote = ' '.join(str(evidence.get('quote') or '').split())
            turn = evidence.get('turn')
            if not quote or turn not in turns or quote not in turns[turn]:
                errors.append(f'{key}: quote not found at {turn}')
        if known_refs is not None:
            for field in ('actor_ref', 'project_ref', 'domain_ref', 'existing_task_ref'):
                ref = item.get(field)
                if ref and ref not in known_refs:
                    errors.append(f'{key}: {field} not found in Portal receipts')
        if item.get('due_date'):
            try:
                date.fromisoformat(item['due_date'])
            except (ValueError, TypeError):
                errors.append(f'{key}: invalid ISO date')
    return errors


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('actions', type=Path)
    p.add_argument('--context-dir', type=Path)
    args = p.parse_args()
    errors = check(json.loads(args.source.read_text()), json.loads(args.actions.read_text()),
                   known_references(args.context_dir) if args.context_dir else None)
    print(json.dumps({'evidence_checks_passed': not errors, 'errors': errors,
                      'semantic_review_required': True}, indent=2))
    sys.exit(bool(errors))
