# CCA-009 — Local Docker deployment and isolated Python execution

## Status

**Implemented and locally verified — 2026-10-18.** After explicit user approval of trusted API socket access, the judge-enabled UI/API is running on project-specific host ports. The existing worker passed all 38 real qualification checks; actual API-to-worker benign AC/WA/TLE/RE/DQ/REVIEW cases, PDF/XLSX export and all 12 one-shot worker removals passed. Docker Desktop grouping and one port per web/API container are visually verified, with a real prerequisite-check worker retained stopped between jobs. A fixed-draft authoring smoke passed two actual isolated reference checks with cleanup; live models and execution of their output remain Not run. The earlier automatic approval rejection was resolved by the user's explicit socket authorization. See [release evidence](../verification.md). Explicitly requested by the user after CCA-008: start the application in Docker, add a user story for this capability, and retain Linux-container execution of submitted/reference code.

## User story

As a local teacher/operator, I want to start ContestCheck AI with Docker Compose and execute task tests in separate offline Linux judge containers, so I can use the application without installing its Python dependencies on the host.

## Goal

Provide project-owned Docker build/Compose files for Streamlit and FastAPI, safe local environment configuration and an explicit judge-enabled deployment using the existing qualified NsJail worker. Preserve the native setup and current application contracts.

## Dependencies

CCA-001–008, a local Linux-container Docker daemon/Compose, the existing reviewed worker profile and freshly qualified `contest-check-worker:cca003` image. Docker/WSL2 evidence applies only to the observed host; every separate worker must qualify again before accepting code.

## Acceptance criteria

- [x] One documented Compose workflow builds the locked Python application and starts healthy UI/API services with loopback-only published ports; restart/stop commands are provided.
- [x] Project-specific host ports default to 33080 (web) and 33081 (API), with loopback bindings, independent fixed internal ports and manual restarts only (`restart: "no"`, dependency restarts disabled). The UI explains disabled/unavailable judging before submission.
- [x] The same Compose project always shows web, API and the stopped judge-worker prerequisite-check service, even with judging disabled (latest user clarification, 2026-10-18). Each port belongs only to its serving container. Actual job workers group under that project while running and are removed afterward; the stopped service remains.
- [x] The teacher UI hides Streamlit developer controls (Deploy, Rerun, Clear cache and auto rerun) while retaining native System/Light/Dark themes, Print and browser-supported Record screen.
- [x] Runtime containers use a non-root account, bounded resources, read-only root and temporary scratch storage. No local credentials, runtime uploads or Git checkout are copied into the image.
- [x] Only API receives configured model settings/credentials from the root `.env`; web and judge workers receive no model keys. Startup/health/catalog/browser checks make no live or billable generation call.
- [x] Default Compose keeps code execution disabled; an explicit reviewed judge override grants the trusted API only the local daemon access required by the existing fixed Docker transport. This is Docker administration access and must be documented as such.
- [x] Submitted programs and optional reference checks execute only in fresh network-disabled Linux worker containers with NsJail, strict input/output/resource limits and real startup qualification. No Docker socket, API environment or host bind mounts reach the worker; no host/plain-container execution fallback is added.
- [x] Actual local verification covers health, model-catalog/UI connectivity, valid/invalid ZIP handling, real benign judge results and cleanup when judge mode is enabled. Missing/failed sandbox setup fails closed.
- [x] Exact commands, image/runtime IDs, safe observed results and Not run limitations are recorded in Release 0.2 verification; setup and architecture/status docs match the shipped deployment. No automatic commit/push.

## Out of scope

Public hosting, accounts, model downloads, automatic paid calls, Docker-in-Docker, persistent job/checkpoint databases, worker network servers, additional solution languages and changes to official verdict semantics.

## Verification guidance

Validate Compose without printing resolved secrets, build from the lockfile, inspect container isolation/credential boundaries, run a local browser smoke and fixed benign judge fixtures through the real API. Review the existing outer worker profile and run its full qualification before enabling execution. Keep untrusted-code execution out of CI and record observed evidence separately from mocked tests and older host-specific results.
