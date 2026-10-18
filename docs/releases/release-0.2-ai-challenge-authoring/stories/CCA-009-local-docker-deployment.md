# CCA-009 — Local Docker deployment and isolated Python execution

## Status

**In progress — default Docker UI/API is running; optional integrated judge startup is awaiting explicit API socket permission after automatic approval rejection.** The worker passed all 38 real qualification checks and the optional API image builds, but integrated code execution is Not run. See [release evidence](../verification.md). Explicitly requested by the user after CCA-008: start the application in Docker, add a user story for this capability, and retain Linux-container execution of submitted/reference code.

## User story

As a local teacher/operator, I want to start ContestCheck AI with Docker Compose and execute task tests in separate offline Linux judge containers, so I can use the application without installing its Python dependencies on the host.

## Goal

Provide project-owned Docker build/Compose files for Streamlit and FastAPI, safe local environment configuration and an explicit judge-enabled deployment using the existing qualified NsJail worker. Preserve the native setup and current application contracts.

## Dependencies

CCA-001–008, a local Linux-container Docker daemon/Compose, the existing reviewed worker profile and freshly qualified `contest-check-worker:cca003` image. Docker/WSL2 evidence applies only to the observed host; every separate worker must qualify again before accepting code.

## Acceptance criteria

- [x] One documented Compose workflow builds the locked Python application and starts healthy UI/API services with loopback-only published ports; restart/stop commands are provided.
- [x] Runtime containers use a non-root account, bounded resources, read-only root and temporary scratch storage. No local credentials, runtime uploads or Git checkout are copied into the image.
- [x] Only API receives configured model settings/credentials from the root `.env`; web and judge workers receive no model keys. Startup/health/catalog/browser checks make no live or billable generation call.
- [ ] Default Compose keeps code execution disabled; an explicit reviewed judge override grants the trusted API only the local daemon access required by the existing fixed Docker transport. This is Docker administration access and must be documented as such.
- [ ] Submitted programs and optional reference checks execute only in fresh network-disabled Linux worker containers with NsJail, strict input/output/resource limits and real startup qualification. No Docker socket, API environment or host bind mounts reach the worker; no host/plain-container execution fallback is added.
- [ ] Actual local verification covers health, model-catalog/UI connectivity, valid/invalid ZIP handling, real benign judge results and cleanup when judge mode is enabled. Missing/failed sandbox setup fails closed.
- [x] Exact commands, image/runtime IDs, safe observed results and Not run limitations are recorded in Release 0.2 verification; setup and architecture/status docs match the shipped deployment. No automatic commit/push.

## Out of scope

Public hosting, accounts, model downloads, automatic paid calls, Docker-in-Docker, persistent job/checkpoint databases, worker network servers, additional solution languages and changes to official verdict semantics.

## Verification guidance

Validate Compose without printing resolved secrets, build from the lockfile, inspect container isolation/credential boundaries, run a local browser smoke and fixed benign judge fixtures through the real API. Review the existing outer worker profile and run its full qualification before enabling execution. Keep untrusted-code execution out of CI and record observed evidence separately from mocked tests and older host-specific results.
