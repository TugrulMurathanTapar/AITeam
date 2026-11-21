"""Automated unit and integration tests for AI Orchestrator."""

import sys
from pathlib import Path

# Add project root to sys.path before any local imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import json
import os
import tempfile
import unittest

import pytest

from core.api_handler import AIProvider, EffortLevel, SchemaType
from core.deliberation import DeliberationEngine, DeliberationResponse
from core.orchestrator import ChatMessage, Orchestrator
from core.security_guard import SecurityGuard
from skills.terminal import TerminalSkill
from ui.i18n import I18n, t




class TestAIOrchestrator(unittest.TestCase):
    """Test suite covering config safety, deliberation optimization, i18n, and persistence."""

    def test_settings_json_no_hardcoded_keys(self) -> None:
        """Ensure settings.json does not contain hardcoded sensitive API keys."""
        settings_path = Path("./config/settings.json").resolve()
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            providers = data.get("providers", [])
            for p in providers:
                key = p.get("api_key", "")
                self.assertEqual(key, "", f"Provider '{p.get('id')}' contains a hardcoded API key in settings.json!")

    def test_i18n_bilingual_support(self) -> None:
        """Verify i18n singleton switches language and translates correctly."""
        i18n = I18n()
        i18n.set_language("en")
        self.assertEqual(i18n.current_language, "en")
        self.assertEqual(t("app_title"), "AI Orchestrator")

        i18n.set_language("tr")
        self.assertEqual(i18n.current_language, "tr")
        self.assertEqual(t("app_title"), "AI Orkestratör")
        i18n.set_language("en")  # reset

    def test_deliberation_token_optimization(self) -> None:
        """Test message windowing and candidate content clipping in deliberation synthesis."""
        class MockClient:
            pass

        engine = DeliberationEngine(MockClient())

        # Generate 10 mock messages (> 6 window limit)
        messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"} for i in range(10)]
        
        # Long response to test clipping (> 1200 chars)
        long_content = "A" * 2500
        responses = [
            DeliberationResponse(provider_id="p1", model_name="Model-A", content=long_content, latency_ms=100.0)
        ]

        synthesis_prompt = engine._build_synthesis_prompt(messages, responses)
        
        # Verify message windowing (should keep last 6 messages)
        self.assertNotIn("Message 0", synthesis_prompt)
        self.assertIn("Message 9", synthesis_prompt)

        # Verify candidate clipping (should clip at 1200 chars + marker)
        self.assertIn("[... clipped for token efficiency ...]", synthesis_prompt)

    def test_default_security_policy_is_closed(self) -> None:
        """Desktop, file and mouse access should be off unless the user explicitly enables them."""
        guard = Orchestrator().security
        guard.reset_to_defaults()

        self.assertFalse(guard.policy.fs_read)
        self.assertFalse(guard.policy.fs_write)
        self.assertFalse(guard.policy.fs_delete)
        self.assertFalse(guard.policy.screen_capture)
        self.assertFalse(guard.policy.mouse_control)
        self.assertFalse(guard.policy.keyboard_control)

        allowed, _ = guard.check_permission("screen_capture")
        self.assertFalse(allowed)

        allowed, _ = guard.check_permission("file_read", "./README.md")
        self.assertFalse(allowed)

        allowed, _ = guard.check_permission("terminal")
        self.assertFalse(allowed)

    def test_terminal_skill_enforces_opt_in(self) -> None:
        """Direct calls to the terminal skill must be denied unless explicitly enabled."""
        guard = SecurityGuard()
        guard.reset_to_defaults()

        async def run_test() -> None:
            with self.assertRaises(PermissionError):
                await TerminalSkill(guard).execute({"command": "echo should-not-run"})

        asyncio.run(run_test())

    def test_file_io_creates_and_reads_files_inside_allowed_path(self) -> None:
        """Filesystem tools should create parent directories and honor opt-in scope."""
        from skills.file_io import FileIOSkill

        guard = SecurityGuard()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            allowed_root = root / "allowed"
            target = allowed_root / "example" / "hello.py"
            guard.update_policy(
                fs_read=True,
                fs_write=True,
                allowed_paths=[str(allowed_root)],
            )

            async def run_test() -> None:
                skill = FileIOSkill(guard)
                await skill.execute({
                    "action": "write",
                    "path": str(target),
                    "content": 'print("hello")',
                })
                read_result = await skill.execute({
                    "action": "read",
                    "path": str(target),
                })
                self.assertEqual(read_result["content"], 'print("hello")')

                with self.assertRaises(PermissionError):
                    await skill.execute({
                        "action": "write",
                        "path": str(root / "outside" / "blocked.py"),
                        "content": "blocked",
                    })

            try:
                asyncio.run(run_test())
            finally:
                guard.reset_to_defaults()

    def test_provider_urls_require_https_except_localhost(self) -> None:
        """Provider credentials must not be sent over plaintext remote HTTP."""
        secure = AIProvider(
            id="secure", name="Secure", base_url="https://api.example.com/v1",
            api_key="test", model_id="model",
        )
        local = AIProvider(
            id="local", name="Local", base_url="http://localhost:11434/v1",
            api_key="", model_id="model",
        )
        insecure = AIProvider(
            id="insecure", name="Insecure", base_url="http://api.example.com/v1",
            api_key="test", model_id="model",
        )

        from core.api_handler import APIClient

        APIClient._validate_provider_url(secure)
        APIClient._validate_provider_url(local)
        with self.assertRaises(ValueError):
            APIClient._validate_provider_url(insecure)

    def test_api_error_urls_redact_query_values(self) -> None:
        """Diagnostic URLs must never reveal Google API keys in query parameters."""
        from core.api_handler import APIClient

        self.assertEqual(
            APIClient._safe_url("https://example.com/models?key=secret&x=1"),
            "https://example.com/[path redacted]",
        )

    def test_legacy_settings_migrate_out_of_source_tree(self) -> None:
        """Legacy source-tree settings should move to user data and leave no duplicate."""
        import config

        original_config_dir = config.CONFIG_DIR
        original_data_dir = os.environ.get("AI_ORCHESTRATOR_DATA_DIR")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            legacy_config = temp_root / "source" / "config"
            legacy_config.mkdir(parents=True)
            legacy_file = legacy_config / "settings.json"
            legacy_file.write_text(
                json.dumps({"providers": [{"api_key": "migration-test"}]}),
                encoding="utf-8",
            )
            config.CONFIG_DIR = legacy_config
            os.environ["AI_ORCHESTRATOR_DATA_DIR"] = str(temp_root / "user-data")
            try:
                migrated = config.load_settings()
                self.assertEqual(migrated["providers"][0]["api_key"], "migration-test")
                self.assertFalse(legacy_file.exists())
                self.assertTrue(config.resolve_settings_path().is_relative_to(temp_root / "user-data"))
            finally:
                config.CONFIG_DIR = original_config_dir
                if original_data_dir is None:
                    os.environ.pop("AI_ORCHESTRATOR_DATA_DIR", None)
                else:
                    os.environ["AI_ORCHESTRATOR_DATA_DIR"] = original_data_dir

    def test_orchestrator_lazy_initialization(self) -> None:
        """Test orchestrator initialization and provider persistence without crashing."""
        async def run_test():
            orch = Orchestrator()
            await orch.load_settings()

            provider = AIProvider(
                id="test_provider",
                name="Test AI",
                base_url="https://api.openai.com/v1",
                api_key="",
                model_id="gpt-4o",
                schema_type=SchemaType.OPENAI,
                enabled=True,
            )
            orch.api_client.add_provider(provider)
            await orch.save_settings()

            retrieved = orch.api_client.get_provider("test_provider")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.name, "Test AI")

            # Cleanup test provider from settings
            orch.api_client.remove_provider("test_provider")
            await orch.save_settings()

        asyncio.run(run_test())

    def test_orchestrator_preserves_existing_api_key_on_reload(self) -> None:
        """A close/reopen cycle should never drop an already saved API key."""
        async def run_test():
            tmp_settings = Path(tempfile.mkdtemp()) / "settings.json"
            tmp_settings.write_text(
                json.dumps({
                    "providers": [{
                        "id": "gemini",
                        "name": "Gemini",
                        "base_url": "https://generativelanguage.googleapis.com/v1",
                        "api_key": "saved-key",
                        "model_id": "gemini-2.5-flash",
                        "schema_type": "google",
                        "enabled": True,
                        "effort_level": "medium",
                    }]
                }), encoding="utf-8")

            orch = Orchestrator(config_path=str(tmp_settings))
            orch.api_client.add_provider(AIProvider(
                id="gemini",
                name="Gemini",
                base_url="https://generativelanguage.googleapis.com/v1",
                api_key="",
                model_id="gemini-2.5-flash",
                schema_type=SchemaType.GOOGLE,
                enabled=True,
            ))

            await orch.save_settings()

            saved = json.loads(tmp_settings.read_text(encoding="utf-8"))
            self.assertEqual(saved["providers"][0]["api_key"], "saved-key")

        asyncio.run(run_test())

    def test_api_client_enforces_ten_active_provider_limit(self) -> None:
        from core.api_handler import APIClient

        client = APIClient()
        for index in range(10):
            client.add_provider(AIProvider(
                id=f"model_{index}",
                name=f"Model {index}",
                base_url="https://api.example.com/v1",
                api_key="test",
                model_id=f"model-{index}",
                enabled=True,
            ))

        assert len(client.get_active_providers()) == 10

        with pytest.raises(ValueError, match="10"):
            client.add_provider(AIProvider(
                id="model_10",
                name="Model 10",
                base_url="https://api.example.com/v1",
                api_key="test",
                model_id="model-10",
                enabled=True,
            ))

        assert client.get_provider("model_10") is None

    def test_orchestrator_builds_turkish_response_instruction(self) -> None:
        orchestrator = Orchestrator()
        I18n().set_language("tr")
        try:
            prompt = orchestrator._build_system_prompt()
            self.assertIn("Türkçe", prompt)
        finally:
            I18n().set_language("en")


def test_memory_load_falls_back_when_configured_path_is_unreadable(monkeypatch, tmp_path) -> None:
    import memory.engine as memory_engine

    configured_path = tmp_path / "unavailable" / "memory.json"
    fallback_path = tmp_path / "user-data" / "memory" / "memory.json"
    fallback_path.parent.mkdir(parents=True)
    fallback_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(memory_engine, "_default_memory_path", lambda: fallback_path)
    monkeypatch.setattr(memory_engine, "HAS_AIOFILES", False)
    read_sync = memory_engine.MemoryEngine._read_sync

    def read_configured_or_fallback(path: Path) -> str:
        if path == configured_path:
            raise PermissionError("test permission failure")
        return read_sync(path)

    monkeypatch.setattr(
        memory_engine.MemoryEngine,
        "_read_sync",
        staticmethod(read_configured_or_fallback),
    )

    engine = memory_engine.MemoryEngine(str(configured_path))
    asyncio.run(engine.load())

    assert engine.path == fallback_path


def test_memory_save_falls_back_when_configured_path_is_unwritable(monkeypatch, tmp_path) -> None:
    import memory.engine as memory_engine

    configured_path = tmp_path / "unavailable" / "memory.json"
    fallback_path = tmp_path / "user-data" / "memory" / "memory.json"
    monkeypatch.setattr(memory_engine, "_default_memory_path", lambda: fallback_path)
    monkeypatch.setattr(memory_engine, "HAS_AIOFILES", False)
    write_sync = memory_engine.MemoryEngine._write_sync

    def write_configured_or_fallback(path: Path, content: str) -> None:
        if path.parent == configured_path.parent:
            raise PermissionError("test permission failure")
        write_sync(path, content)

    monkeypatch.setattr(
        memory_engine.MemoryEngine,
        "_write_sync",
        staticmethod(write_configured_or_fallback),
    )

    engine = memory_engine.MemoryEngine(str(configured_path))
    asyncio.run(engine.save())

    assert engine.path == fallback_path
    assert fallback_path.is_file()


def test_settings_replace_unwritable_memory_path(monkeypatch, tmp_path) -> None:
    import config

    settings_path = tmp_path / "user-data" / "config" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    stale_path = tmp_path / "other-user" / "memory.json"
    settings_path.write_text(json.dumps({"memory_path": str(stale_path)}), encoding="utf-8")
    monkeypatch.setattr(config, "resolve_settings_path", lambda: settings_path)
    monkeypatch.setattr(config, "resolve_user_data_dir", lambda: tmp_path / "user-data")

    original_mkdir = Path.mkdir

    def deny_stale_path(path: Path, *args, **kwargs) -> None:
        if path == stale_path.parent:
            raise PermissionError("test permission failure")
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", deny_stale_path)

    settings = config.load_settings()

    assert settings["memory_path"] == str(tmp_path / "user-data" / "memory" / "memory.json")
    assert json.loads(settings_path.read_text(encoding="utf-8"))["memory_path"] == settings["memory_path"]


def test_main_screen_receives_orchestrator_events(monkeypatch, tmp_path) -> None:
    from core.orchestrator import OrchestratorEvent
    from ui.app import OrchestratorApp

    monkeypatch.setenv("AI_ORCHESTRATOR_DATA_DIR", str(tmp_path / "user-data"))

    async def run_test() -> None:
        app = OrchestratorApp()
        async with app.run_test() as pilot:
            await pilot.pause(1)
            event = OrchestratorEvent(
                event_type="deliberation_start",
                data={"models": ["test-model"]},
            )
            await app.orchestrator._emit(event)
            panel = app.screen.query_one("#deliberation-panel")
            assert panel._events[-1] == ("deliberation_start", {"models": ["test-model"]})

    asyncio.run(run_test())


def test_direct_chat_uses_selected_active_provider(monkeypatch) -> None:
    async def run_test() -> None:
        orchestrator = Orchestrator()
        orchestrator._running = True
        orchestrator._settings = {"deliberation": {"enabled": False}}
        providers = [
            AIProvider(
                id=provider_id,
                name=provider_id,
                base_url="https://api.example.com/v1",
                api_key="test",
                model_id=provider_id,
                enabled=True,
            )
            for provider_id in ("first", "selected")
        ]
        for provider in providers:
            orchestrator.api_client.add_provider(provider)

        calls = []

        async def fake_chat_completion(provider, messages, system_prompt, tools=None):
            calls.append(provider.id)
            return {
                "content": "response",
                "tool_calls": [],
                "model": provider.model_id,
                "usage": {},
            }

        monkeypatch.setattr(orchestrator.api_client, "chat_completion", fake_chat_completion)
        response = await orchestrator.process_message("hello", provider_id="selected")

        assert response == "response"
        assert calls == ["selected"]

    asyncio.run(run_test())


def test_direct_chat_executes_model_requested_registered_tool(monkeypatch) -> None:
    from core.skill_manager import BaseSkill

    class EchoSkill(BaseSkill):
        @property
        def name(self) -> str:
            return "echo"

        @property
        def description(self) -> str:
            return "Return the submitted text."

        @property
        def required_permissions(self) -> list[str]:
            return ["terminal"]

        @property
        def parameters_schema(self) -> dict:
            return {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            }

        async def execute(self, params: dict) -> dict:
            return {"text": params["text"]}

    async def run_test() -> None:
        orchestrator = Orchestrator()
        orchestrator._running = True
        orchestrator._settings = {"deliberation": {"enabled": False}}
        provider = AIProvider(
            id="test",
            name="Test",
            base_url="https://api.example.com/v1",
            api_key="test",
            model_id="test-model",
            enabled=True,
        )
        orchestrator.api_client.add_provider(provider)
        orchestrator.skill_manager.register_skill(EchoSkill())
        orchestrator.security.reset_to_defaults()
        assert orchestrator._available_tool_schemas() == []
        orchestrator.security.update_policy(terminal_enabled=True)
        assert [schema["function"]["name"] for schema in orchestrator._available_tool_schemas()] == ["echo"]

        observed_messages = []
        observed_tools = []

        async def fake_chat_completion(provider, messages, system_prompt, tools=None):
            observed_messages.append(list(messages))
            observed_tools.extend(tools or [])
            if len(observed_messages) == 1:
                return {
                    "content": "",
                    "tool_calls": [{
                        "id": "call-1",
                        "name": "echo",
                        "arguments": {"text": "hello"},
                        "thought_signature": "gemini-thought-signature",
                    }],
                    "model": provider.model_id,
                    "usage": {},
                }
            return {
                "content": "The tool returned hello.",
                "tool_calls": [],
                "model": provider.model_id,
                "usage": {},
            }

        monkeypatch.setattr(orchestrator.api_client, "chat_completion", fake_chat_completion)
        response = await orchestrator.process_message("Use the echo tool.")

        assert response == "The tool returned hello."
        assert observed_tools
        assert all(item["function"]["name"] == "echo" for item in observed_tools)
        assert (
            observed_messages[1][1]["tool_calls"][0]["function"]["thought_signature"]
            == "gemini-thought-signature"
        )
        assert observed_messages[1][-1]["role"] == "tool"
        assert '"text": "hello"' in observed_messages[1][-1]["content"]

    asyncio.run(run_test())


def test_security_settings_are_saved_from_settings_screen(monkeypatch, tmp_path) -> None:
    from textual.widgets import Input, Switch
    from ui.app import OrchestratorApp

    data_dir = tmp_path / "user-data"
    monkeypatch.setenv("AI_ORCHESTRATOR_DATA_DIR", str(data_dir))

    async def run_test() -> None:
        app = OrchestratorApp()
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause(1)
            await pilot.press("ctrl+s")
            await pilot.pause()
            screen = app.screen
            screen.query_one("#sw-fs_read", Switch).value = True
            screen.query_one("#sw-fs_write", Switch).value = True
            screen.query_one("#sw-terminal_enabled", Switch).value = True
            screen.query_one("#inp-paths", Input).value = str(tmp_path / "workspace")

            await screen._apply_security("en")

            settings_path = app.orchestrator.config_path
            saved = json.loads(settings_path.read_text(encoding="utf-8"))
            assert saved["security"]["fs_read"] is True
            assert saved["security"]["fs_write"] is True
            assert saved["security"]["terminal_enabled"] is True
            assert saved["security"]["allowed_paths"] == [str(tmp_path / "workspace")]

    asyncio.run(run_test())


def test_chat_history_and_providers_survive_permission_toggles(monkeypatch, tmp_path) -> None:
    config_dir = tmp_path / "user-data" / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "settings.json"
    memory_path = tmp_path / "user-data" / "memory" / "memory.json"
    settings = {
        "language": "en",
        "memory_path": str(memory_path),
        "providers": [{
            "id": "saved-provider",
            "name": "Saved AI",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-api-key",
            "model_id": "saved-model",
            "schema_type": "openai",
            "enabled": True,
        }],
        "security": {"terminal_enabled": False},
    }
    config_path.write_text(json.dumps(settings), encoding="utf-8")
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    async def run_test() -> None:
        first = Orchestrator(config_path=str(config_path))
        await first.initialize()
        first._chat_history = [
            ChatMessage(role="user", content="Keep this conversation."),
            ChatMessage(role="assistant", content="It will be saved."),
        ]
        await first._persist_chat_history()
        first.update_security_policy(terminal_enabled=True)
        await first.save_settings()
        first.update_security_policy(terminal_enabled=False)
        await first.save_settings()
        await first.api_client.shutdown()

        reopened = Orchestrator(config_path=str(config_path))
        await reopened.initialize()
        assert [message.content for message in reopened.get_chat_history()] == [
            "Keep this conversation.",
            "It will be saved.",
        ]
        saved_provider = reopened.api_client.get_provider("saved-provider")
        assert saved_provider is not None
        assert saved_provider.api_key == "test-api-key"
        assert saved_provider.model_id == "saved-model"
        assert not reopened.security.policy.terminal_enabled
        await reopened.api_client.shutdown()

        from ui.app import OrchestratorApp
        from ui.widgets.chat_panel import ChatPanel

        app = OrchestratorApp()
        async with app.run_test() as pilot:
            await pilot.pause(1)
            chat = app.screen.query_one("#chat-scroll", ChatPanel)
            assert len(chat.children) == 3

    asyncio.run(run_test())


def test_provider_http_errors_include_safe_provider_detail(monkeypatch) -> None:
    import httpx

    from core.api_handler import APIClient, ProviderRequestError

    client = APIClient()
    request = httpx.Request("POST", "https://example.com/v1/generate")
    response = httpx.Response(
        400,
        json={
            "error": {
                "message": "Invalid model request; rejected key secret-api-key",
                "status": "INVALID_ARGUMENT",
            },
        },
        request=request,
    )

    class FakeHTTPClient:
        async def request(self, method, url, **kwargs):
            return response

    async def get_client():
        return FakeHTTPClient()

    monkeypatch.setattr(client, "_get_client", get_client)

    async def run_test() -> None:
        with pytest.raises(ProviderRequestError) as error:
            await client._execute_with_retry(
                "POST",
                "https://example.com/v1/generate?key=url-secret",
                headers={"x-goog-api-key": "secret-api-key"},
            )

        assert error.value.status_code == 400
        assert "Invalid model request" in str(error.value)
        assert "[redacted]" in str(error.value)
        assert "secret-api-key" not in str(error.value)
        assert "url-secret" not in str(error.value)

    asyncio.run(run_test())


def test_google_tool_loop_preserves_thought_signature(monkeypatch) -> None:
    from core.api_handler import APIClient

    client = APIClient()
    responses = [
        {
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "file_io",
                            "args": {"action": "list_dir", "path": "./workspace"},
                        },
                        "thoughtSignature": "opaque-signature",
                    }],
                },
            }],
        },
        {
            "candidates": [{
                "content": {"parts": [{"text": "Done."}]},
            }],
        },
    ]
    payloads = []

    class Response:
        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    async def fake_request(method, url, **kwargs):
        payloads.append(kwargs["json"])
        return Response(responses.pop(0))

    monkeypatch.setattr(client, "_execute_with_retry", fake_request)
    provider = AIProvider(
        id="google",
        name="Google",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="test-key",
        model_id="gemini-test",
        schema_type=SchemaType.GOOGLE,
    )
    tool_schema = {
        "type": "function",
        "function": {
            "name": "file_io",
            "description": "Filesystem operations",
            "parameters": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {
                        "type": "string",
                        "default": "./workspace",
                        "additionalProperties": False,
                    },
                },
            },
        },
    }

    async def run_test() -> None:
        result = await client.chat_completion(
            provider,
            [{"role": "user", "content": "List workspace."}],
            tools=[tool_schema],
        )
        assert result["tool_calls"][0]["thought_signature"] == "opaque-signature"

        tool_messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": result["tool_calls"][0]["id"],
                    "function": {
                        "name": result["tool_calls"][0]["name"],
                        "arguments": json.dumps(result["tool_calls"][0]["arguments"]),
                        "thoughtSignature": result["tool_calls"][0]["thought_signature"],
                    },
                }],
            },
            {
                "role": "tool",
                "name": "file_io",
                "content": json.dumps({"success": True, "result": []}),
            },
        ]
        await client.chat_completion(
            provider,
            [{"role": "user", "content": "List workspace."}, *tool_messages],
            tools=[tool_schema],
        )

    asyncio.run(run_test())
    model_parts = payloads[1]["contents"][1]["parts"]
    assert model_parts[0]["thoughtSignature"] == "opaque-signature"
    assert "thoughtSignature" not in model_parts[0]["functionCall"]
    declaration_schema = payloads[0]["tools"][0]["functionDeclarations"][0]["parameters"]
    assert "$schema" not in declaration_schema
    assert "additionalProperties" not in declaration_schema
    assert "default" not in declaration_schema["properties"]["path"]


def test_google_serializer_migrates_legacy_nested_thought_signature(monkeypatch) -> None:
    from core.api_handler import APIClient

    client = APIClient()
    payloads = []

    class Response:
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

    async def fake_request(method, url, **kwargs):
        payloads.append(kwargs["json"])
        return Response()

    monkeypatch.setattr(client, "_execute_with_retry", fake_request)
    provider = AIProvider(
        id="google",
        name="Google",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="test-key",
        model_id="gemini-test",
        schema_type=SchemaType.GOOGLE,
    )

    asyncio.run(client.chat_completion(
        provider,
        [
            {"role": "user", "content": "continue"},
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "legacy",
                    "function": {
                        "name": "file_io",
                        "arguments": "{\"action\":\"list_dir\",\"path\":\"./workspace\"}",
                        "thoughtSignature": "legacy-signature",
                    },
                }],
            },
            {
                "role": "assistant",
                "function_call": {
                    "name": "file_io",
                    "args": {"action": "list_dir", "path": "./workspace"},
                    "thought_signature": "legacy-snake-signature",
                },
            },
        ],
    ))

    contents = payloads[0]["contents"]
    first_legacy_part = contents[1]["parts"][0]
    second_legacy_part = contents[2]["parts"][0]
    assert first_legacy_part["thoughtSignature"] == "legacy-signature"
    assert "thoughtSignature" not in first_legacy_part["functionCall"]
    assert second_legacy_part["thoughtSignature"] == "legacy-snake-signature"
    assert "thoughtSignature" not in second_legacy_part["functionCall"]


@pytest.mark.parametrize(
    ("schema_type", "response_body", "expected_payload_key", "expected_call"),
    [
        (
            SchemaType.OPENAI,
            {
                "choices": [{
                    "message": {
                        "content": "",
                        "tool_calls": [{
                            "id": "call-openai",
                            "function": {"name": "echo", "arguments": "{\"text\":\"hi\"}"},
                        }],
                    }
                }],
            },
            "tools",
            {"id": "call-openai", "name": "echo", "arguments": "{\"text\":\"hi\"}"},
        ),
        (
            SchemaType.ANTHROPIC,
            {
                "content": [{
                    "type": "tool_use",
                    "id": "call-anthropic",
                    "name": "echo",
                    "input": {"text": "hi"},
                }],
            },
            "tools",
            {"id": "call-anthropic", "name": "echo", "arguments": {"text": "hi"}},
        ),
        (
            SchemaType.GOOGLE,
            {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "functionCall": {
                                "name": "echo",
                                "args": {"text": "hi"},
                            },
                        }],
                    },
                }],
            },
            "tools",
            {"id": "google-0", "name": "echo", "arguments": {"text": "hi"}},
        ),
    ],
)
def test_provider_tool_calls_are_normalized(
    monkeypatch,
    schema_type,
    response_body,
    expected_payload_key,
    expected_call,
) -> None:
    from core.api_handler import APIClient

    client = APIClient()
    payloads = []

    class Response:
        def json(self):
            return response_body

    async def fake_request(method, url, **kwargs):
        payloads.append(kwargs["json"])
        return Response()

    monkeypatch.setattr(client, "_execute_with_retry", fake_request)
    provider = AIProvider(
        id="test",
        name="Test",
        base_url="https://api.example.com/v1",
        api_key="test-key",
        model_id="test-model",
        schema_type=schema_type,
    )
    tool_schema = {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo text",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
        },
    }

    result = asyncio.run(client.chat_completion(
        provider=provider,
        messages=[{"role": "user", "content": "hi"}],
        tools=[tool_schema],
    ))

    assert result["tool_calls"] == [expected_call]
    assert expected_payload_key in payloads[0]
    if schema_type == SchemaType.ANTHROPIC:
        assert payloads[0]["tools"][0]["input_schema"] == tool_schema["function"]["parameters"]
    elif schema_type == SchemaType.GOOGLE:
        assert payloads[0]["tools"][0]["functionDeclarations"][0]["name"] == "echo"


def test_chat_input_remains_visible_after_returning_from_settings(monkeypatch, tmp_path) -> None:
    from textual.widgets import Input
    from ui.app import OrchestratorApp

    monkeypatch.setenv("AI_ORCHESTRATOR_DATA_DIR", str(tmp_path / "user-data"))

    async def run_test() -> None:
        app = OrchestratorApp()
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause(1)
            await pilot.press("ctrl+s")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            assert type(app.screen).__name__ == "MainScreen"
            chat_input = app.screen.query_one("#chat-input", Input)
            assert chat_input.region.height > 0

    asyncio.run(run_test())


def test_chat_sidebar_switches_between_direct_and_deliberation(monkeypatch, tmp_path) -> None:
    from textual.widgets import Select, Switch
    from ui.app import OrchestratorApp

    monkeypatch.setenv("AI_ORCHESTRATOR_DATA_DIR", str(tmp_path / "user-data"))

    async def run_test() -> None:
        app = OrchestratorApp()
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause(1)
            orchestrator = app.orchestrator
            orchestrator.api_client._providers.clear()

            def add_provider(provider_id: str) -> None:
                orchestrator.api_client.add_provider(
                    AIProvider(
                        id=provider_id,
                        name=provider_id,
                        base_url="https://api.example.com/v1",
                        api_key="test",
                        model_id=provider_id,
                        enabled=True,
                    )
                )

            add_provider("first")
            orchestrator.deliberation_enabled = True
            app.screen.refresh_chat_state()
            await pilot.pause()

            toggle = app.screen.query_one("#deliberation-toggle", Switch)
            model_select = app.screen.query_one("#chat-model-select", Select)
            assert toggle.disabled
            assert not toggle.value
            assert model_select.region.height > 0
            assert model_select.value == "first"

            add_provider("second")
            app.screen.refresh_chat_state()
            await pilot.pause()
            assert not toggle.disabled
            assert toggle.value
            assert model_select.region.height == 0

            await pilot.click("#deliberation-toggle")
            await pilot.pause()
            assert not orchestrator.deliberation_enabled
            assert model_select.region.height > 0
            model_select.value = "second"
            assert model_select.value == "second"

            await pilot.press("ctrl+d")
            await pilot.pause()
            assert orchestrator.deliberation_enabled
            assert model_select.region.height == 0

    asyncio.run(run_test())


def test_chat_shows_elapsed_working_status_until_response_finishes(monkeypatch, tmp_path) -> None:
    from textual.widgets import Button, Input, Static
    from ui.app import OrchestratorApp

    monkeypatch.setenv("AI_ORCHESTRATOR_DATA_DIR", str(tmp_path / "user-data"))

    async def run_test() -> None:
        app = OrchestratorApp()
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause(1)
            screen = app.screen
            input_widget = screen.query_one("#chat-input", Input)
            send_button = screen.query_one("#send-btn", Button)
            status = screen.query_one("#chat-request-status", Static)
            input_widget.value = "Keep the interface responsive."
            started = asyncio.Event()
            release = asyncio.Event()

            async def delayed_response(message, provider_id=None):
                started.set()
                await release.wait()
                return "Response received."

            monkeypatch.setattr(app.orchestrator, "process_message", delayed_response)
            worker = app.run_worker(screen._send_message(), name="test-chat-response")
            await asyncio.wait_for(started.wait(), timeout=3)
            assert input_widget.disabled
            assert send_button.disabled
            assert status.display

            await asyncio.sleep(1.1)
            assert "1" in str(status.render())

            release.set()
            await worker.wait()
            assert not input_widget.disabled
            assert not send_button.disabled
            assert "Yanıt" in str(status.render()) or "Reply" in str(status.render())

    asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
