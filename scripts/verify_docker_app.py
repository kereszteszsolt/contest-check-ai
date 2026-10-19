# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Operator-only checks against a running local Docker app; no model calls.

Uses only verify_judge_batch's fixed benign fixtures. Code is submitted only with
--reviewed-profile and is never executed in this script or on the host. Not CI.
"""

import argparse
import json
from pathlib import Path

import httpx
from verify_judge_batch import fixtures

from contest_check.results import BatchResult


def verify(api_port, web_port, reviewed, output):
    task, submissions = fixtures()
    files = {
        "task_zip": ("task.zip", task, "application/zip"),
        "submissions_zip": ("submissions.zip", submissions, "application/zip"),
    }
    evidence = {"model_calls": "Not run", "fixture_source": "fixed benign CCA-003 cases"}
    with httpx.Client(
        base_url=f"http://127.0.0.1:{api_port}", trust_env=False, timeout=180
    ) as client:
        health = client.get("/health")
        health.raise_for_status()
        evidence["health"] = health.json()
        ui = client.get(f"http://127.0.0.1:{web_port}/_stcore/health")
        assert ui.status_code == 200 and ui.text == "ok"
        catalog = client.get("/api/authoring/models")
        catalog.raise_for_status()
        evidence["catalog"] = {
            "models": len(catalog.json()["models"]),
            "issues": len(catalog.json()["issues"]),
            "no_store": catalog.headers.get("cache-control") == "no-store",
        }
        valid = client.post("/api/validate", files=files)
        valid.raise_for_status()
        assert valid.json()["task_id"] == "cca003-fixture"
        evidence["validation"] = valid.json()
        bad = client.post(
            "/api/validate",
            files=files
            | {
                "submissions_zip": ("invalid.zip", b"not a ZIP", "application/zip"),
            },
        )
        assert bad.status_code == 400 and bad.json()["code"] == "invalid_zip"
        evidence["invalid_archive_rejected"] = True
        if health.json()["execution_enabled"]:
            if not reviewed:
                raise RuntimeError(
                    "Judge is enabled. Explicit --reviewed-profile is required to submit fixtures."
                )
            judged = client.post("/api/judge", files=files)
            judged.raise_for_status()
            batch = BatchResult.model_validate(judged.json())
            assert batch.status == "completed" and batch.test_ids == ["b", "a", "empty"]
            for participant, verdict in zip(
                batch.participants[:4], ["AC", "WA", "TLE", "RE"], strict=True
            ):
                assert [test.verdict for test in participant.tests] == [verdict] * 3
            assert (
                batch.participants[0].status == "REVIEW" and batch.participants[0].passed_tests == 3
            )
            assert batch.participants[4].status == "DQ" and batch.participants[4].not_run_tests == 3
            evidence["judge"] = batch.model_dump(mode="json")
            output.mkdir(parents=True, exist_ok=True)
            for kind in ("pdf", "xlsx"):
                report = client.post(f"/api/reports/{kind}", json=batch.model_dump(mode="json"))
                report.raise_for_status()
                assert report.content.startswith(b"%PDF-" if kind == "pdf" else b"PK\x03\x04")
                (output / f"results.{kind}").write_bytes(report.content)
            evidence["reports"] = ["pdf", "xlsx"]
        else:
            disabled = client.post("/api/judge", files=files)
            assert disabled.status_code == 503 and disabled.json()["code"] == "execution_disabled"
            evidence["judge"] = "Disabled: real API-to-worker execution Not run"
            evidence["reports"] = "Not run: no actual judge batch"
    output.mkdir(parents=True, exist_ok=True)
    (output / "app-smoke.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        json.dumps(
            {
                "health": evidence["health"],
                "catalog": evidence["catalog"],
                "valid_and_invalid_uploads": True,
                "real_judge": reviewed and isinstance(evidence["judge"], dict),
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=33081)
    parser.add_argument("--web-port", type=int, default=33080)
    parser.add_argument("--reviewed-profile", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(".runtime/cca009-verification"))
    arguments = parser.parse_args()
    if not all(1 <= port <= 65535 for port in (arguments.api_port, arguments.web_port)):
        parser.error("Ports must be between 1 and 65535.")
    verify(arguments.api_port, arguments.web_port, arguments.reviewed_profile, arguments.output)


if __name__ == "__main__":
    main()
