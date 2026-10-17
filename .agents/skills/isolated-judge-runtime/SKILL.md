---
name: isolated-judge-runtime
description: Use for Linux sandbox verification, nsjail or reviewed equivalent, offline code execution, CPU/memory/process limits, input/output restrictions, and deterministic autograder verdict testing.
---

# Sandboxed code execution engineering

## When to load

Load **only** for approved judge-worker, isolation, execution, compilation, verdict or runtime security tasks. The active story sets the languages and acceptance tests.

## Technical practices

1. Student submissions are **untrusted executables**. Never invoke them directly via Streamlit, FastAPI, subprocess on the host, or a default Docker shell. A normal application container alone is not a verified secure sandbox.
2. Evaluate a vetted Linux sandbox such as [NsJail](https://github.com/google/nsjail) in a dedicated worker; document exact kernel/container prerequisites and third-party licenses. No Docker daemon socket in the worker; no privileged catch-all runtime.
3. Enforce separate PID/user/mount/network namespaces where supported; use read-only system mounts, dedicated scratch space, seccomp filtering, no capabilities, no secrets, no network egress, CPU/wall-time/memory/process/file-descriptor/disk/output limits. Apply isolation to compilation and execution.
4. Verify the real environment with harmless negative tests before enabling execution; **fail closed** if any critical restriction cannot be asserted. Log safe diagnostic metadata, not raw code.
5. Allow only explicitly named task input/output files. Validate entrypoints and imports within one participant directory, reject symlinks/path escape, never permit arbitrary host paths or shell command injection.
6. Record per-test outcome and timing. Compare output according to the manifest's explicit checker (initially exact normalized text); do not infer Big-O from a single timing measurement.
7. Distinguish archive rejection, objective policy violation/disqualification, sandbox failure and suspicion requiring human review. Do **not** claim reliable intent or plagiarism detection from static scanning or an LLM.
8. Never relax safety to make tests pass. Ask for explicit review if host/cgroups/seccomp support or sandbox licensing blocks implementation.

## Verification

Unit tests mock the runner; isolated integration checks verify no external network, no host filesystem escapes, bounded resource abuse, timeouts and file I/O using benign fixtures. Do not test malware or unknown third-party submissions. Record exact environment and limitations.
