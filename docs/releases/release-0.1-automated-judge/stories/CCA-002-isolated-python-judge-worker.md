# CCA-002 — Isolated Python judge worker

## Status

**Implemented and locally verified (2026-10-17).** The separately deployed NsJail worker passed actual Docker/WSL2 sandbox checks and controlled protocol cases. See [verification.md](../verification.md) and [worker deployment](../../../judge-worker.md) for exact pins, approved profile, evidence and host-specific limitations. Browser/API judging remains disabled until CCA-003.

## User story

As a teacher, I want untrusted Python submissions executed only in an isolated, resource-limited environment, so student code cannot freely access the network or host files.

## Goal

Implement a separately deployed offline judge worker and validate a hardened Linux sandbox backend, with **no unsafe fallback**.

## Dependencies

CCA-001 archive schemas and [security threat model](../../../security-and-sandbox.md); supported Linux host/kernel/container features and reviewed sandbox runtime licensing.

## Acceptance criteria

- [x] Review and document a concrete sandbox backend (e.g. NsJail) with pinned installation/version, actual Linux host requirements, licensing and supported Docker integration. Do not vendor a sandbox binary blindly.
- [x] Worker is internal-only, has no public endpoint, outbound internet, Docker socket, application secrets or unrestricted host mounts; its own code cannot be invoked from the browser with arbitrary command arguments.
- [x] Compilation/execution (Python MVP: execution only) occurs in a newly isolated jail per submission/test, with explicit file allowlists, process/user/mount/network isolation and enforced CPU, wall-time, memory, file/output/process limits.
- [x] Each test invocation starts a fresh `task.limits.time_seconds` budget, including after a timeout. Temporary source/input/output/configuration files are automatically removed before returning to the caller and starting the next test; a cleanup failure blocks further execution.
- [x] The worker supplies manifest-named `.in` file(s), runs allowlisted `main.py` and captures only the expected `.out` file(s), without shell-string interpolation or arbitrary path access.
- [x] Runtime returns structured success/timeout/resource/crash/system-error metadata without leaking host file paths, secrets or raw source in logs.
- [x] **Fail closed:** if sandbox prerequisites or security checks fail, the judge refuses all submissions; there is no `subprocess`/plain Docker shell fallback.
- [x] Benign sandbox integration tests on the actual intended host demonstrate no network access, no filesystem escape, limits, termination and cleanup, with exact environment/evidence recorded.

## Out of scope

C/C++/Free Pascal compilation, scoring, malware inspection guarantees, automatic intent/plagiarism detection, distributed execution and public submissions.

## Verification guidance

Unit tests mock the worker. Hardened sandbox integration must use benign controlled fixtures and record host/kernel/settings. **Block this story** if isolation cannot be validated; do not mark `Implemented` due to green mocks alone.
