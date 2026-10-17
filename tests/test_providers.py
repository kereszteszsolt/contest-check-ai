# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
from dataclasses import replace

import httpx
import pytest
from pydantic import ValidationError

from contest_check.authoring_contracts import DraftRequest, TaskDraft
from contest_check.model_configuration import ProviderError, load_model_settings
from contest_check.providers import GenerationSession, ProviderTransport


def settings(provider="ollama", **overrides):
    return load_model_settings(
        {
            "OLLAMA_MODEL_1": "fixture:1",
            "OPENROUTER_MODEL_1": "test/fixture",
            "OPENROUTER_API_KEY": "not-a-real-key",
            **overrides,
        }
    )


def wire_response(provider, data, *, finish="stop"):
    content = data if isinstance(data, str) else json.dumps(data)
    if provider == "ollama":
        return {
            "model": "fixture:1",
            "message": {"role": "assistant", "content": content},
            "done": True,
            "done_reason": finish,
            "prompt_eval_count": 20,
            "eval_count": 100,
        }
    return {
        "id": "fixed-response",
        "object": "chat.completion",
        "created": 0,
        "system_fingerprint": None,
        "model": "test/fixture",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish,
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 100, "total_tokens": 120},
    }


@pytest.mark.parametrize("provider", ["ollama", "openrouter"])
def test_actual_langchain_sdk_roundtrip_is_bounded_and_explicit(provider, draft_data, monkeypatch):
    seen = []
    monkeypatch.setenv("OLLAMA_API_KEY", "PRIVATE_AMBIENT_KEY")

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json=wire_response(provider, draft_data))

    session = GenerationSession(settings(), f"{provider}:1")
    result = asyncio.run(
        session.generate("A simple addition exercise.", transport=httpx.MockTransport(handle))
    )
    assert result.draft == TaskDraft.model_validate(draft_data)
    assert result.calls_used == 1 and not result.executed and not result.approved
    assert len(seen) == 1
    request = seen[0]
    payload = json.loads(request.content)
    assert payload["stream"] is False
    assert "tools" not in payload or payload["tools"] == []
    assert "PRIVATE_AMBIENT_KEY" not in str(request.headers)
    if provider == "ollama":
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        assert "authorization" not in request.headers
        assert payload["options"]["num_predict"] == 4096
        assert payload["format"]["additionalProperties"] is False
    else:
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert payload["model"] == "test/fixture" and payload["max_tokens"] == 4096
        assert payload["provider"] == {"allow_fallbacks": False, "require_parameters": True}
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["tool_choice"] == "none" and payload["plugins"] == []


def test_catalog_hides_empty_duplicate_invalid_and_unconfigured_cloud_slots():
    config = load_model_settings(
        {
            "OLLAMA_MODEL_1": "fixture:1",
            "OLLAMA_MODEL_2": "fixture:1",
            "OLLAMA_MODEL_3": " ",
            "OPENROUTER_MODEL_1": "test/fixture",
        }
    )
    assert [model.slot for model in config.choices] == ["ollama:1"]
    assert config.issues == ("openrouter_key",)
    assert "key" in config.catalog().issues[0]
    assert (
        len(
            settings(
                OLLAMA_MODEL_2="fixture:2",
                OLLAMA_MODEL_3="fixture:3",
                OPENROUTER_MODEL_2="test/second",
                OPENROUTER_MODEL_3="test/third",
            ).choices
        )
        == 6
    )


@pytest.mark.parametrize(
    "name,value",
    [
        ("AI_MAX_CALLS_PER_GENERATION", "7"),
        ("AI_MAX_CALLS_PER_GENERATION", "0"),
        ("AI_REQUEST_TIMEOUT_SECONDS", "nan"),
        ("AI_REQUEST_TIMEOUT_SECONDS", "121"),
        ("AI_MAX_OUTPUT_TOKENS", "-1"),
        ("AI_MAX_OUTPUT_TOKENS", "8193"),
    ],
)
def test_bad_limits_disable_models(name, value):
    config = settings(**{name: value})
    assert config.choices == () and "invalid_limits" in config.issues


@pytest.mark.parametrize(
    "provider,value",
    [
        ("OLLAMA", "file:///tmp/test"),
        ("OLLAMA", "http://user:secret@localhost:11434"),
        ("OLLAMA", "http://localhost:11434?other=1"),
        ("OLLAMA", "http://localhost:0"),
        ("OPENROUTER", "https://unconfigured.example/api/v1"),
    ],
)
def test_invalid_endpoints_disable_only_that_provider(provider, value):
    config = settings(**{f"{provider}_BASE_URL": value})
    assert all(choice.provider != provider.lower() for choice in config.choices)
    assert f"{provider.lower()}_url" in config.issues


@pytest.mark.parametrize(
    "provider,value",
    [
        ("OLLAMA", "fixture:cloud"),
        ("OLLAMA", "bad\nmodel"),
        ("OPENROUTER", "openrouter/auto"),
        ("OPENROUTER", "test/model:online"),
        ("OPENROUTER", "not-a-provider-model"),
    ],
)
def test_dynamic_routes_and_invalid_model_ids_are_hidden(provider, value):
    config = settings(**{f"{provider}_MODEL_1": value})
    assert all(choice.provider != provider.lower() for choice in config.choices)


def test_unknown_selection_never_constructs_a_client():
    with pytest.raises(ProviderError, match="arbitrary"):
        GenerationSession(settings(), "https://unknown.example/model")
    assert "not-a-real-key" not in repr(settings())
    assert "not-a-real-key" not in settings().catalog().model_dump_json()


@pytest.mark.parametrize("provider", ["ollama", "openrouter"])
@pytest.mark.parametrize(
    "status,code",
    [(401, "credentials"), (429, "rate_limit"), (503, "provider_error"), (302, "provider_error")],
)
def test_errors_never_retry_redirect_fallback_or_leak(provider, status, code, caplog):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(
            status, headers={"location": "https://other.example"}, content=b"PRIVATE_BODY"
        )

    session = GenerationSession(settings(), f"{provider}:1")
    with pytest.raises(ProviderError) as caught:
        asyncio.run(
            session.generate("PRIVATE_TEACHER_INSTRUCTIONS", transport=httpx.MockTransport(handle))
        )
    assert caught.value.code == code
    assert len(seen) == 1 and session.budget.used == 1
    assert "PRIVATE" not in str(caught.value) + caplog.text


@pytest.mark.parametrize("provider", ["ollama", "openrouter"])
@pytest.mark.parametrize(
    "variant", ["json", "field", "duplicate", "truncated", "unfinished", "size"]
)
def test_untrusted_outputs_are_refused_without_repair(provider, variant, draft_data):
    data = draft_data
    if variant == "json":
        data = "```json\n{}\n```"
    if variant == "field":
        data = {**draft_data, "approved": True}
    if variant == "duplicate":
        data = '{"title":"first","title":"second"}'
    if variant == "size":
        data = "x" * (256 * 1024 + 1)
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(
            200,
            json=wire_response(
                provider,
                data,
                finish={"truncated": "length", "unfinished": None}.get(variant, "stop"),
            ),
        )

    with pytest.raises(ProviderError) as caught:
        asyncio.run(
            GenerationSession(settings(), f"{provider}:1").generate(
                "Draft exercise", transport=httpx.MockTransport(handle)
            )
        )
    assert caught.value.code == ("output_size" if variant == "size" else "invalid_output")
    assert len(seen) == 1


@pytest.mark.parametrize("provider", ["ollama", "openrouter"])
def test_absolute_timeout_cancels_the_selected_call(provider):
    seen = []

    async def handle(request):
        seen.append(request)
        await asyncio.sleep(1)
        raise AssertionError("must be cancelled")

    config = replace(settings(), timeout_seconds=0.02)
    session = GenerationSession(config, f"{provider}:1")
    with pytest.raises(ProviderError) as caught:
        asyncio.run(session.generate("Draft exercise", transport=httpx.MockTransport(handle)))
    assert caught.value.code == "timeout" and len(seen) == 1 and session.budget.used == 1


@pytest.mark.parametrize("provider", ["ollama", "openrouter"])
def test_shared_session_budget_counts_all_attempts(provider, draft_data):
    session = GenerationSession(settings(AI_MAX_CALLS_PER_GENERATION="2"), f"{provider}:1")
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json=wire_response(provider, draft_data))

    async def run():
        for _ in range(2):
            await session.generate("Draft exercise", transport=httpx.MockTransport(handle))
        with pytest.raises(ProviderError) as caught:
            await session.generate("Draft exercise", transport=httpx.MockTransport(handle))
        assert caught.value.code == "call_budget"

    asyncio.run(run())
    assert len(seen) == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("instructions", " "),
        ("instructions", "x" * 8001),
        ("model_slot", "openrouter:4"),
        ("model", "unconfigured"),
        ("submissions_zip", "PRIVATE"),
    ],
)
def test_generation_request_has_no_upload_url_key_or_arbitrary_model_fields(field, value):
    with pytest.raises(ValidationError):
        DraftRequest.model_validate(
            {"model_slot": "ollama:1", "instructions": "Exercise", field: value}
        )


def test_draft_reuses_manifest_bounds_and_rejects_duplicate_private_tests(draft_data):
    TaskDraft.model_validate(draft_data)
    for change in (
        {"output_filename": "input.txt"},
        {"private_tests": draft_data["private_tests"] * 2},
        {"limits": {"time_seconds": 60, "memory_mb": 128, "output_bytes": 1024}},
    ):
        with pytest.raises(ValidationError):
            TaskDraft.model_validate({**draft_data, **change})


def test_guard_refuses_other_origins_before_transport_or_budget():
    from contest_check.providers import CallBudget

    budget = CallBudget(1)
    guard = ProviderTransport("http://127.0.0.1:11434/api/chat", settings().choices[0], budget)

    async def run():
        try:
            with pytest.raises(ProviderError):
                await guard.handle_async_request(
                    httpx.Request("POST", "https://unconfigured.example/api/chat")
                )
        finally:
            await guard.aclose()

    asyncio.run(run())
    assert budget.used == 0


@pytest.mark.parametrize("provider", ["ollama", "openrouter"])
def test_inherited_tracing_is_disabled(provider, draft_data, monkeypatch):
    import langsmith

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("OPENROUTER_DEBUG", "true")

    def forbidden(*args, **kwargs):
        pytest.fail("Tracing must not transmit prompts or outputs")

    monkeypatch.setattr(langsmith.Client, "create_run", forbidden)
    monkeypatch.setattr(langsmith.Client, "update_run", forbidden)
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json=wire_response(provider, draft_data))
    )
    asyncio.run(
        GenerationSession(settings(), f"{provider}:1").generate("Exercise", transport=transport)
    )


@pytest.mark.parametrize("provider", ["ollama", "openrouter"])
@pytest.mark.parametrize(
    "failure,code", [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "provider_error")]
)
def test_transport_failures_are_classified_without_retry(provider, failure, code):
    seen = []

    def handle(request):
        seen.append(request)
        raise failure("PRIVATE_CONNECTION_DETAILS", request=request)

    with pytest.raises(ProviderError) as caught:
        asyncio.run(
            GenerationSession(settings(), f"{provider}:1").generate(
                "Exercise", transport=httpx.MockTransport(handle)
            )
        )
    assert caught.value.code == code and len(seen) == 1
    assert "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize("provider", ["ollama", "openrouter"])
@pytest.mark.parametrize("failure", ["size", "encoded", "invalid_json"])
def test_response_stream_is_bounded_closed_and_rejected_before_sdk_parsing(provider, failure):
    class Stream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            for _ in range(5 if failure == "size" else 1):
                yield b"x" * 65536

        async def aclose(self):
            self.closed = True

    stream = Stream()

    def handle(request):
        return httpx.Response(
            200, headers={"Content-Encoding": "gzip"} if failure == "encoded" else {}, stream=stream
        )

    with pytest.raises(ProviderError) as caught:
        asyncio.run(
            GenerationSession(settings(), f"{provider}:1").generate(
                "Exercise", transport=httpx.MockTransport(handle)
            )
        )
    assert caught.value.code == ("invalid_output" if failure == "invalid_json" else "output_size")
    assert stream.closed
