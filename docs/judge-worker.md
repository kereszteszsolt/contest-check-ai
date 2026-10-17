# CCA-002 — isolated one-shot Python worker

CCA-002 supplies a separate, offline worker image and a typed stdin/stdout protocol. CCA-003 now connects it to the explicitly configured local API and performs verdict comparison outside the worker; see [judging.md](judging.md). The current image tag is `contest-check-worker:cca003`. Actual host-specific evidence is recorded in [Release 0.1 verification](releases/release-0.1-automated-judge/verification.md). There is no network worker endpoint, background queue or account system. Streamlit judging/results remain CCA-004 work.

## Pinned backend and supported host

| Component | Pin |
| --- | --- |
| NsJail 3.5 | `402e2b4c13c79731c632c2add4c3884dd1afc25f` |
| Kafel submodule | `b4241da9f3d17e786387280fc6e4965634fdf45b` |
| CPython | `3.12.13` |
| Official base image | `python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2` |

The Dockerfile builds upstream NsJail from the exact commit, checks its Kafel revision and retains both licenses. No downloaded sandbox binary is vendored. Worker Python dependencies are exported with hashes from the `worker` dependency group in `uv.lock`; FastAPI, Streamlit and model clients are not installed as worker dependencies. Debian native-package versions are recorded in the release evidence; apt repository resolution is not a claim of a bit-for-bit reproducible image. Record the image ID after every build and requalify it.

The supported target is **Linux x86-64**, cgroup v2 with observable CPU/memory/pids limits and swap disabled, unprivileged user/PID/mount/network/IPC/UTS/cgroup namespaces, seccomp-BPF, no-new-privileges, and the modern mount API used by NsJail 3.5 (`--experimental_mnt new`, kernel >= 6.3 as required by upstream). The upstream experimental mount implementation is part of the deployment review. There is no legacy/host/plain-container fallback. Windows-native or different kernels/architectures are not qualified by the recorded run.

The recorded Docker Desktop default syscall profile blocks namespace setup. The narrowly scoped [worker profile review](worker-security-review.md) and explicit Compose override are required on that host. Do not enable `--privileged`, add SYS_ADMIN, use `seccomp=unconfined`, mount a Docker socket or write host cgroups to make a failed qualification green.

## Build and qualify

From the repository root:

```bash
docker compose -f deploy/worker/compose.yaml build judge-worker
docker compose -f deploy/worker/compose.yaml run --rm --no-deps judge-worker --check
```

`--check` inspects only outer prerequisites and integrity. Even when it exits 0, its `execution_ready` remains false: it does not run the security probes. Without the reviewed override, `--verify` exits 78 on the recorded host and refuses execution.

After reviewing the concrete [security profile](worker-security-review.md) for the deployment:

```bash
docker compose -f deploy/worker/compose.yaml -f deploy/worker/compose.reviewed.yaml \
  run --rm --no-deps judge-worker --verify
uv run --frozen python scripts/verify_worker_deployment.py --reviewed-profile
```

The second command is an operator-only integration suite. It inspects actual Docker settings, verifies the default profile fails closed and the reviewed profile qualifies, then submits six fixed benign examples. It accepts no external source files. All examples execute only inside NsJail; each worker requalifies before its example. The script removes only its own named test containers. Do not run this suite automatically in CI.

Qualification checks real namespace identities, PID 1 and UID/GID 65534 in the jail, zero capabilities, no-new-privileges and layered seccomp, actual read-only root/work mounts and writable output mount, hard limits, restricted environment/descriptors, missing worker/host paths, denied network/DNS/Unix/Netlink/fork/namespace/symlink/ptrace calls, memory/output/wall/CPU/file-descriptor caps, sibling imports, termination/reaping and scratch cleanup. All checks must pass. The qualification exists only in that supervisor process and is tied to runtime hashes; neither a saved JSON report nor `JUDGE_EXECUTION_ENABLED=true` enables execution.

## One request, one fresh jail

The worker handles exactly one JSON object from stdin with `--run`, verifies the sandbox in that process, creates a new private test workspace/jail, emits one JSON result, and exits. A caller must already have applied CCA-001 ZIP validation; the worker independently validates every protocol field and never takes a ZIP or host path.

```bash
docker compose -f deploy/worker/compose.yaml -f deploy/worker/compose.reviewed.yaml \
  run --rm -T --no-deps judge-worker --run < job.json
```

| Request field | Contract |
| --- | --- |
| `protocol` | Version `1` (default) |
| `participant_id` | Same canonical opaque numeric ID contract as CCA-001 |
| `task` | Complete typed [task manifest](archive-contracts.md), including bounds and declared test IDs |
| `test_id` | One ID already declared by `task.tests` |
| `source_files` | Object mapping 1–30 ASCII `.py` basenames to strict base64 contents; exactly one `main.py`, no case collisions, max 1 MiB decoded per file |
| `input_base64` | Only the selected test input; strict base64, max 1 MiB decoded |

Unknown fields, duplicate JSON keys, unsafe names and oversized data are rejected; the entire JSON request is capped at 44 MiB before parsing. No command, interpreter option, URL, environment variable, workdir, path, reference source or expected-output field is accepted. Expected teacher answers never enter the worker protocol.

The jail receives only a minimal read-only CPython/stdlib/native-library tree, the fixed trusted bootstrap, one participant's source files, and one input at `task.input_filename`. `/proc` is read-only and belongs to the new PID namespace. The only writable file is the pre-created `task.output_filename`. A private noexec tmpfs holds bounded temporary files; sources/input are read-only and the work directory cannot be used to create arbitrary files. The supervisor reads only that expected output using `O_NOFOLLOW`, validates its type/size and removes the workspace. No input/expected-output package or neighboring participant directory is mounted into a jail.

CPython runs with `-I -S -B`; the bootstrap adds only `/work` for sibling module imports and sets the exact hard output-byte limit. Kernel namespaces, mount permissions, seccomp and hard resource limits are the boundary. Python-level checks or static source inspection are not used as sandboxing.

## Limits and metadata

| Boundary | Enforcement |
| --- | --- |
| Whole worker | Non-root 1000:1000, no capabilities, read-only root, no-new-privileges, network `none`, no ports/host binds/secrets/socket, 384 MiB memory/no additional swap, one CPU, 16 outer processes, private 96 MiB tmpfs |
| One solution | Fresh user/mount/network/PID/IPC/UTS/cgroup namespaces; UID/GID 65534; no capabilities; default-kill inner syscall allowlist; fork/clone/threads denied |
| Memory | Hard per-process RLIMIT_AS from manifest, max 256 MiB; one jailed process; outer cgroup bounds the supervisor as well |
| Time | Monotonic supervisor deadline from manifest, max 3 seconds; counts jail startup; hard CPU limit rounded up to whole seconds; independent NsJail wall backup |
| Timeout cleanup | TERM to NsJail for kill/reap, then bounded KILL escalation; NsJail child has parent-death SIGKILL; verify cgroup process count returns to baseline |
| Files | 32 descriptors, NPROC=1 plus denied process syscalls, no core/locked memory, only one writable output file with exact hard byte cap <=1 MiB |

Set `task.limits.time_seconds` in the task manifest, for example `0.5` for a half-second limit (accepted range: greater than zero, at most 3 seconds). The full budget starts again for every program/test invocation; previous tests and timeouts never consume the next test's budget. A timeout stops the running program before its result is returned.

Every invocation creates its own temporary directory. After success, crash, resource failure or timeout, the supervisor automatically deletes the source/input copies, output, jail configuration and any nested temporary data before returning. The next invocation begins with a new directory and an empty output file. Only the bounded structured result leaves the worker; generated test files are not retained. If termination/reaping or directory cleanup fails, the worker returns `system_error` and revokes its qualification. The CCA-003 coordinator additionally removes the container before proceeding and stops the entire batch if cleanup is uncertain.

Observed elapsed time includes NsJail startup and termination; it is not a benchmark of the algorithm alone. Timeout reporting can include the bounded termination/reaping grace after the program deadline. Very low teacher memory/time limits may prevent Python startup and are returned as failure metadata.

Result `status` is `success`, `timeout`, `resource`, `crash` or `system_error`, with a fixed `diagnostic`, measured `elapsed_seconds` (null when unavailable), optional exit/signal metadata, `output_size_bytes` and `output_written`. The latter distinguishes an untouched pre-created file from an intentionally empty written/truncated file; epoch mtime initialization and denied timestamp-setting syscalls are verified by three additional startup probes. The current image passes 38 qualification checks. `output_base64` is returned only on successful execution. `success` means execution and capture succeeded; CCA-003 performs comparison and official verdicts outside the worker.

Exit codes 70/71 produce `memory_or_exit`/`output_or_exit` hints; a program can deliberately choose those codes. NsJail's 128+signal encoding also overlaps deliberate program exits. These fields are runtime hints, never proof of intent or grounds for DQ. Raw student stdout/stderr and NsJail logs are discarded, and exceptions return fixed metadata without paths, environment values or source. The expected output remains untrusted result data; encoding it is not sanitizing it for a future browser/report.

Normal success/error/timeout cleanup is verified. A host crash or unkillable kernel task is not an absolute cleanup guarantee; the dedicated container tmpfs is discarded when the container is removed. Unexpected cleanup failure revokes readiness and yields `system_error`.

## Licensing and distribution

ContestCheck's own source remains Apache-2.0. The image contains separate third-party components under their respective licenses:

- [NsJail 3.5](https://github.com/google/nsjail/tree/402e2b4c13c79731c632c2add4c3884dd1afc25f) and [Kafel](https://github.com/google/kafel/tree/b4241da9f3d17e786387280fc6e4965634fdf45b): Apache-2.0; unmodified upstream source, compiled during build. License copies are retained under `/usr/share/doc/cca-nsjail/` and `/usr/share/doc/cca-kafel/`.
- CPython: PSF licensing and bundled notices from the official pinned image. Worker Pydantic dependencies retain their MIT notices.
- Dynamically linked Debian libnl/libnl-route: LGPL-2.1 with component notices; protobuf: BSD and component notices; GCC runtime: GPL with its runtime-library exception and bundled notices; glibc and the remaining base packages retain their original licenses. The package copyright files and `/usr/share/common-licenses` are retained. A package copyright file can describe build tools/source components not all present in the runtime binary.

No upstream code is relicensed as ContestCheck source. Publishing an image requires preserving the relevant notices and satisfying the corresponding source/relinking obligations for its distributed components; a dependency-name list alone is not a substitute. This story builds locally and publishes no image. The component review does not assert that every possible future base image or bundled dependency is legally/security audited.

## Evidence boundary

The historical [CCA-002 Docker evidence](releases/release-0.1-automated-judge/evidence/cca002-docker-verification.json) records that image's actual ID, two qualification outcomes, inspected container settings and six controlled runtime results. The current [CCA-003 batch evidence](releases/release-0.1-automated-judge/evidence/cca003-batch-verification.json) records the updated image, 38-check qualification and API-driven results. Host/kernel, exact commands, corrected failures and checks not run are in [verification.md](releases/release-0.1-automated-judge/verification.md). Re-run qualification on every worker start and after any image/profile/host change. This is host-specific evidence, not a guarantee against every kernel exploit or malicious program.
