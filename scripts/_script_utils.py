"""Shared entry-point helper for all ADD scripts. v2.0.1 P2-4 fix.

Eliminates 8 copies of the same try/except pattern. All scripts call:
    run_script(main)

Replaces:
    try:
        sys.exit(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(2)
"""

import sys
import json
import traceback


def run_script(main_fn):
    """Run main() with consistent error handling. All scripts use this."""
    try:
        sys.exit(main_fn())
    except Exception as e:
        traceback.print_exc()
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(2)
