# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys

from contest_check.judge.contracts import (
    MAX_REQUEST_BYTES,
    RuntimeResult,
    VerificationReport,
    parse_request,
)
from contest_check.judge.environment import outer_checks
from contest_check.judge.verification import QualifiedWorker


def main() -> None:
    parser = argparse.ArgumentParser(description="Internal one-shot offline judge worker")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--check", action="store_true", help="Inspect prerequisites; execute no code"
    )
    action.add_argument(
        "--verify", action="store_true", help="Run only built-in trusted sandbox probes"
    )
    action.add_argument(
        "--run", action="store_true", help="Verify, then handle one bounded JSON request"
    )
    arguments = parser.parse_args()
    try:
        if arguments.check:
            report = VerificationReport(checks=outer_checks())
            print(report.model_dump_json())
            raise SystemExit(0 if all(check.passed for check in report.checks) else 78)
        request = None
        if arguments.run:
            try:
                request = parse_request(sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1))
            except (ValueError, RecursionError):
                print(
                    RuntimeResult(
                        status="system_error", diagnostic="invalid_request"
                    ).model_dump_json()
                )
                raise SystemExit(65) from None
        worker = QualifiedWorker()
        report = worker.verify()
        if arguments.verify:
            print(report.model_dump_json())
            raise SystemExit(0 if report.execution_ready else 78)
        result = worker.run(request)
        print(result.model_dump_json())
        raise SystemExit(78 if result.status == "system_error" else 0)
    except Exception:
        # The process boundary returns fixed metadata even for unexpected internal
        # errors. Never print exception messages/tracebacks containing job data.
        print(
            RuntimeResult(status="system_error", diagnostic="sandbox_unavailable").model_dump_json()
        )
        raise SystemExit(78) from None


if __name__ == "__main__":
    main()
