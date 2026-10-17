# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Trusted entrypoint inside the jail; the kernel sandbox is the security boundary."""

import os
import resource
import runpy
import signal
import sys


def main() -> None:
    output_limit = int(sys.argv[1])
    if not 1 <= output_limit <= 1_048_576:
        raise SystemExit(255)
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_limit, output_limit))
    # PID 1 ignores many default signal dispositions; use an explicit handler.
    # The kernel byte limit remains effective even if contestant code changes it.
    signal.signal(signal.SIGXFSZ, lambda *_: os._exit(71))
    sys.path.insert(0, "/work")
    sys.argv = ["main.py"]
    try:
        runpy.run_path("/work/main.py", run_name="__main__")
    except MemoryError:
        # A hint only: a contestant can choose this exit code too. Never a DQ.
        raise SystemExit(70) from None


if __name__ == "__main__":
    main()
