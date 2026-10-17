# Story-driven Codex workflow

## Minimal implementation procedure

1. Main session selects **one `CCA-*` story** in dependency order, reads `AGENTS.md`, its release README, the story and focused documentation, and asks for explicit implementation approval.
2. Main session or one optional **sole-writer** agent implements only that story; do not write from two agents concurrently. Load the one relevant technical skill, never all skills preemptively.
3. Run the narrowest unit/static tests first, then the required API/UI checks and **verified sandbox integration** where necessary. Live OpenRouter is never assumed or auto-billed.
4. Record actual test commands, observed results, environment, blockers and `Not run` in that release's `verification.md`. Failed security gates block completion.
5. Check the diff and propose a message, request **separate user approval for git commit**. Only store the real hash after a successful commit. Pushing/releasing likewise requires approval.
6. Ask before advancing to another story. Never implement future ideas solely because they are mentioned in docs.

## Story template

Every planned story includes **Status**, **User story**, **Goal**, **Dependencies**, **Acceptance criteria** as unchecked measurable checkboxes, **Out of scope**, and **Verification guidance**. Keep business criteria in the story; agents and skills give technology practices only.

## Source and license

Follow [AGENTS.md](../AGENTS.md) for the two-line SPDX header on **hand-written application source**. Do not add it to generic configuration, generated files, dependency locks, Markdown or vendor files.

## Safety gate

Unknown code must never be run to speed up verification. If no supported hardened sandbox exists, mark the story **Blocked/Not run** and ask the user. No unapproved privileged worker, network access, Docker socket mount or execution in the API process.
