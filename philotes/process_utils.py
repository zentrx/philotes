import ctypes
import sys
import os

def set_process_name(name: str):
    """
    Sets the Linux process title ('comm') via prctl(PR_SET_NAME) so the process
    is identified by tools like btop, htop, and ps as `name`.
    Also updates setproctitle if available.
    """
    # 1. Update Linux task comm via prctl (max 15 chars)
    PR_SET_NAME = 15
    try:
        libc = ctypes.CDLL("libc.so.6")
        name_bytes = name.encode("utf-8")[:15]
        libc.prctl(PR_SET_NAME, name_bytes, 0, 0, 0)
    except Exception as e:
        sys.stderr.write(f"[Philotes] Warning: failed to set prctl name: {e}\n")

    # 2. Try setproctitle for full ps commandline string
    try:
        import setproctitle
        setproctitle.setproctitle(name)
    except ImportError:
        pass
