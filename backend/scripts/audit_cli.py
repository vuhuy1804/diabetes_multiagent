"""Read local metadata-only audit without exposing records through public HTTP."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env', override=False)
from monitoring.audit_repository import AuditError, AuditRepository


def main() -> int:
    parser = argparse.ArgumentParser(description='Read/purge metadata-only SQLite audit')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('summary')
    recent = sub.add_parser('recent')
    recent.add_argument('--limit', type=int, default=10)
    purge = sub.add_parser('purge')
    purge.add_argument('--older-than-days', type=int, required=True)
    purge.add_argument('--yes', action='store_true', help='Confirm deletion of old audit metadata')
    args = parser.parse_args()
    if args.command == 'purge' and not args.yes:
        print('No deletion performed. Re-run with --yes to confirm.', file=sys.stderr)
        return 2
    try:
        repo = AuditRepository()
        if args.command == 'summary':
            output = repo.summary()
        elif args.command == 'recent':
            output = {'records': repo.recent(args.limit)}
        else:
            output = {'deleted': repo.purge_older_than(args.older_than_days)}
    except AuditError as exc:
        print('AUDIT ERROR: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
