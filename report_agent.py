"""Report local agent lifecycle events without requiring a running HTTP server."""
import argparse
import json
from pathlib import Path
import sys
import uuid
import live_agents


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',default=str(Path(__file__).resolve().parent/'workspace'))
    parser.add_argument('--engine',choices=['Codex','Claude'],required=True)
    parser.add_argument('--team',required=True)
    parser.add_argument('--agent',required=True)
    parser.add_argument('--project',required=True,help='Absolute path of the project being worked on')
    parser.add_argument('--session',help='Reuse the session returned by selected for later events')
    parser.add_argument('--event',choices=sorted(live_agents.EVENTS),required=True)
    parser.add_argument('--skill')
    parser.add_argument('--summary',default='',help='Task title / concise description')
    parser.add_argument('--result',default='',help='Completed work / result for human review')
    args=parser.parse_args(argv)
    if not args.session and args.event!='selected': parser.error('--session is required after selected')
    payload=vars(args).copy()
    payload['session']=args.session or uuid.uuid4().hex
    try:
        result=live_agents.report(args.workspace,payload)
    except (ValueError,OSError,live_agents.sqlite3.Error) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=True),file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
