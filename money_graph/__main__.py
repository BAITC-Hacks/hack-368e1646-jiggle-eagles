import argparse
from pathlib import Path
import sys

from .pipeline import ValidationError, run
from .server import make_server


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate Parquet, calculate Money Graph hypotheses and export results locally.')
    parser.add_argument('--data', type=Path, default=Path('data/private/money-graph/input'))
    parser.add_argument('--out', type=Path, default=Path('data/private/money-graph/output'))
    parser.add_argument('--serve', action='store_true', help='After reproduction, serve the local dashboard until Ctrl+C.')
    parser.add_argument('--upload-only', action='store_true', help='With --serve, start without inputs and upload in the dashboard.')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be 1–65535')
    if args.upload_only and not args.serve:
        parser.error('--upload-only requires --serve')
    result = None
    if not args.upload_only:
        try:
            result, manifest = run(args.data, args.out)
        except (ValidationError, OSError, ValueError) as error:
            print(f'Money Graph failed: {error}', file=sys.stderr)
            return 1
        print(f"Validated {len(result.nodes)} nodes, {result.graph.number_of_edges()} directed connections; "
              f"{len(result.clusters)} communities, {len(result.top)} ranked accounts. "
              f"Exports: {args.out.resolve()} ({manifest['elapsed_seconds']:.3f}s)", flush=True)
    if args.serve:
        try:
            with make_server(result, args.out, args.port) as server:
                print(f'Dashboard: http://127.0.0.1:{args.port} — hypotheses for review. Ctrl+C to stop.', flush=True)
                server.serve_forever()
        except KeyboardInterrupt:
            pass
        except OSError as error:
            print(f'Dashboard could not start: {error}', file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
