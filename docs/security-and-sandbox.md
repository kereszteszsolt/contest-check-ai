# Security and sandbox threat model

**This is the most critical part of ContestCheck AI.** Uploaded Python solutions, archives and AI-generated reference programs are **untrusted code**. They must never be run in Streamlit, FastAPI, or an unsandboxed host/Docker process.

## Design constraints (must fail closed)

1. Validate upload structure before extraction: reject unsafe paths, symlinks, nested archives, entry overflow, size/ratio overflow, unsupported extensions and malformed manifests.
2. The judge worker has **no internet egress** and no secrets (including OpenRouter tokens), no Docker daemon socket, no host home path, no persistent application volume and no unrelated credentials.
3. All executions — even compilation or AI-generated reference checks — use an actual hardened sandbox with isolated namespaces/filesystem, seccomp where supported, per-job scratch space, user isolation, limits and required log/cleanup behavior.
4. The runtime MUST refuse to execute if isolation prerequisites cannot be verified on the actual host. A `JUDGE_EXECUTION_ENABLED=true` flag is not sufficient evidence of safety. A default Docker container without a qualified sandbox is also insufficient.
5. Permit only prescribed file I/O in the sandbox, with hard limits on output bytes, disk consumption, memory, CPU and wall time, process count and file descriptors. Reset each test environment.
6. Prevent injection through filenames, tool arguments, file paths, logs, generated HTML, PDF metadata and XLSX formula cells.
7. Keep audit-friendly failure categories: invalid upload, proven policy violation, compiler/runtime error, time/memory limit, system failure and **suspected abuse needing human review**.

## Selected CCA-002 sandbox

[Google NsJail 3.5](https://github.com/google/nsjail/tree/402e2b4c13c79731c632c2add4c3884dd1afc25f), with its pinned Kafel submodule, is the selected CCA-002 backend. Both use Apache-2.0. The separate worker builds exact upstream source commits; its native dependencies retain their own licenses. Deployment/host requirements, the scoped outer Docker profile, inner default-kill policy, resource caps and qualification are detailed in [judge-worker.md](judge-worker.md). The recorded Docker Desktop/WSL2 environment passed real checks; this does not qualify a different host automatically.

No sandbox binary is vendored in the repository. If the pinned sandbox cannot qualify on a target environment, the worker refuses execution and returns structured system-error metadata. The default Docker profile failed closed on the recorded host; a worker-only profile was explicitly reviewed/approved for the actual integration tests. There is no privileged, unconfined, host-subprocess or plain-container fallback. The web/API judge route remains disabled until CCA-003.

## Security verification plan

Run **benign** negative/edge-case fixtures in the actual sandbox:

- Attempted read/write outside the permitted task workdir fails.
- No DNS or network connection is available from worker processes.
- CPU/wall-time, memory, file-count, output-byte and subprocess/fork caps are enforced.
- After timeout/error the process is terminated; no leaked workspaces or child processes remain.
- Symbolic link or path traversal cannot reach teacher/host files.
- The worker does not expose any public endpoint or leak credentials/environment variables.

Only after successful verification on a supported Linux host should the judge be enabled. Document kernel, runtime, exact test commands/results and residual limitations. No claims of absolute security.

## Cheating and disqualification

- **Objective policy violation:** a proven attempt to use prohibited interfaces/resources, an invalid forbidden file, or another explicitly documented disqualifying rule may produce `DQ` with rule/reason/evidence.
- **Suspicious code:** heuristic/static similarity, suspicious patterns and AI opinions are indicators for human review, **not conclusive cheating or automatic DQ**.
- **Sandbox failures:** infrastructure limitations receive `SYSTEM_ERROR` / blocked evaluation, never `DQ` against a student.

The teacher remains responsible for final disciplinary decisions. Do not use AI to identify a person or infer intent.

## Trusted and untrusted networks

For Release 0.1 the judge works offline and the application does not need any AI call. Release 0.2 may optionally call user-configured Ollama or OpenRouter from the **API/agent** component only; no other runtime web clients, web searches, GitHub access or arbitrary URL tools are allowed.
