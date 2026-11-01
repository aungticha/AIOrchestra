"""Claude Code statusLine adapter: quota only, no network and no transcript storage."""
import argparse
import json
import sys
import quota

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--workspace',required=True)
    args=parser.parse_args()
    try:
        raw=sys.stdin.read(1_000_001)
        if len(raw)>1_000_000: raise ValueError()
        result=quota.write_claude_snapshot(args.workspace,json.loads(raw))
        windows=result['windows']
        print('AIOrchestra | '+' | '.join(f"{w['label']}: {w['remainingPercent']:g}% left" for w in windows) if windows else 'AIOrchestra | quota not available')
    except (ValueError,OSError,TypeError):
        print('AIOrchestra | quota unavailable')
