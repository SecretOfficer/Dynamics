"""
runner.py – Executes user-submitted Python code in a subprocess.
Returns stdout, stderr, and return code.
"""

import subprocess
import sys
import tempfile
import os


def run_user_code(code: str, timeout: int = 60) -> dict:
    """
    Writes user code to a temp file and executes it in a subprocess.

    Uses the SYSTEM temp directory to avoid triggering Flask's
    debug auto-reloader (which watches the gui/ directory).

    Returns:
        dict with keys: stdout, stderr, returncode
    """
    # Write code to the SYSTEM temp dir (outside Flask's watch scope)
    fd, tmp_path = tempfile.mkstemp(suffix='.py', prefix='strategy_')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(code)

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(__file__)  # run from gui/ directory
        )
        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            'stdout': '',
            'stderr': f'ERROR: Script timed out after {timeout} seconds.',
            'returncode': -1,
        }
    except Exception as e:
        return {
            'stdout': '',
            'stderr': f'ERROR: {str(e)}',
            'returncode': -1,
        }
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
