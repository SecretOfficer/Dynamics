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

    Returns:
        dict with keys: stdout, stderr, returncode
    """
    # Write code to a temp file
    tmp_dir = os.path.join(os.path.dirname(__file__), '.tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    tmp_path = os.path.join(tmp_dir, 'user_script.py')
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write(code)

    try:
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
        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass
