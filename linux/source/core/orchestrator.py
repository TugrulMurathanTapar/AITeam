"""Main Orchestrator Controller for Multi-AI Orchestrator.

Integrates the multi-provider API client, security guard, skill manager,
portable memory engine, and deliberation engine into a unified asynchronous
coordination hub with real-time UI event streaming.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging
import os
from pathlib import Path
import time
import traceback
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
import uuid


class RequestStatus(str, Enum):
    IDLE = "idle"
    SENDING = "sending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"


@dataclass
class RequestErrorReport:
    """Detailed error object containing taxonomy, diagnostic step, and remediation."""

    error_type: str
    error_code: str
    short_description: str
    possible_causes: str
    suggested_fix: str
    last_step: str
    last_successful_step: str
    timeout_seconds: float
    stacktrace: str
    request_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "error_code": self.error_code,
            "short_description": self.short_description,
            "possible_causes": self.possible_causes,
            "suggested_fix": self.suggested_fix,
            "last_step": self.last_step,
            "last_successful_step": self.last_successful_step,
            "timeout_seconds": self.timeout_seconds,
            "stacktrace": self.stacktrace,
            "request_id": self.request_id,
        }

    def format_ui_card(self) -> str:
        return (
            f"❌ **{self.short_description}** [{self.error_code}]\n"
            f"• **Hata Tipi / Type:** {self.error_type}\n"
            f"• **Bekleme / Timeout:** {self.timeout_seconds:.0f}s\n"
            f"• **Son Adım / Last Step:** {self.last_step}\n"
            f"• **Son Başarılı Adım / Last Success:** {self.last_successful_step}\n"
            f"• **Olası Sebep / Possible Cause:** {self.possible_causes}\n"
            f"• **Çözüm / Suggested Fix:** {self.suggested_fix}"
        )


def classify_error(
    exc: Exception,
    last_step: str,
    last_successful_step: str,
    timeout: float,
    request_id: str,
) -> RequestErrorReport:
    tb = traceback.format_exc()
    exc_str = str(exc)
    exc_name = type(exc).__name__

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timeout" in exc_str.lower():
        return RequestErrorReport(
            error_type="TimeoutError",
            error_code="ERR_TIMEOUT",
            short_description="İşlem bekleme süresini aştı (Timeout)",
            possible_causes="provider timeout / network delay / request hang / loop block.",
            suggested_fix="Ağ bağlantısını, provider API yanıt süresini veya timeout süresini kontrol edin.",
            last_step=last_step,
            last_successful_step=last_successful_step,
            timeout_seconds=timeout,
            stacktrace=tb,
            request_id=request_id,
        )
    elif "json" in exc_str.lower() or "decode" in exc_str.lower() or "parse" in exc_str.lower():
        return RequestErrorReport(
            error_type="JSONParseError",
            error_code="ERR_JSON_PARSE",
            short_description="API yanıtı geçerli JSON formatında değil",
            possible_causes="Provider geçersiz veya bozuk yanıt döndü / proxy yetkilendirme hatası.",
            suggested_fix="Provider ayarlarını ve API uç noktasını doğrulayın.",
            last_step=last_step,
            last_successful_step=last_successful_step,
            timeout_seconds=timeout,
            stacktrace=tb,
            request_id=request_id,
        )
    elif "permission" in exc_str.lower() or "access denied" in exc_str.lower() or "forbidden" in exc_str.lower():
        return RequestErrorReport(
            error_type="PermissionError",
            error_code="ERR_PERMISSION_DENIED",
            short_description="İzin engeli veya yetkisiz erişim",
            possible_causes="API anahtarı geçersiz, yetkisiz dosya/komut işlemi veya SecurityGuard engeli.",
            suggested_fix="API anahtarını ve güvenlik politikası izinlerini kontrol edin.",
            last_step=last_step,
            last_successful_step=last_successful_step,
            timeout_seconds=timeout,
            stacktrace=tb,
            request_id=request_id,
        )
    elif "connection" in exc_str.lower() or "network" in exc_str.lower() or "unreachable" in exc_str.lower() or "dns" in exc_str.lower():
        return RequestErrorReport(
            error_type="NetworkError",
            error_code="ERR_NETWORK_DISCONNECTED",
            short_description="Ağ bağlantı hatası",
            possible_causes="İnternet bağlantısı kesildi / DNS çözümlenemedi / SSL el sıkışma hatası.",
            suggested_fix="İnternet bağlantınızı ve firewall/proxy ayarlarınızı kontrol edin.",
            last_step=last_step,
            last_successful_step=last_successful_step,
            timeout_seconds=timeout,
            stacktrace=tb,
            request_id=request_id,
        )
    else:
        return RequestErrorReport(
            error_type=exc_name,
            error_code=f"ERR_{exc_name.upper()}",
            short_description=f"İşlem sırasında hata oluştu: {exc_str}",
            possible_causes="API istemcisi hatası, beklenmeyen model yanıtı veya iç mantık hatası.",
            suggested_fix="Logları inceleyin veya isteği tekrar deneyin.",
            last_step=last_step,
            last_successful_step=last_successful_step,
            timeout_seconds=timeout,
            stacktrace=tb,
            request_id=request_id,
        )

from config import load_api_schemas, load_settings, resolve_settings_path
from core.api_handler import (
    AIProvider,
    APIClient,
    EffortLevel,
    HealthResult,
    SchemaType,
)
from core.crypto_engine import CryptoEngine
from core.deliberation import (
    DeliberationEngine,
    DeliberationResponse,
    DeliberationResult,
)
from core.security_guard import SecurityGuard, SecurityPolicy
from core.skill_manager import BaseSkill, SkillManager
from memory.engine import MemoryEngine
from memory.schema import CoreMemory, MemoryEntry, MemoryStore, SubMemory
from ui.i18n import I18n

logger = logging.getLogger("orchestrator.core")


@dataclass
class ChatMessage:
    """Represents a single chat message in the conversation history.

    Attributes:
        role: Message role ('user', 'assistant', 'system', 'deliberation').
        content: Text content of the message.
        model_name: Optional name of the AI model that produced the message.
        timestamp: Creation timestamp for chronological tracking.
        metadata: Extra contextual information (e.g., token usage, latency).
    """

    role: str
    content: str
    model_name: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert chat message into a serializable dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "model_name": self.model_name,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatMessage:
        """Construct a ChatMessage from a dictionary representation."""
        ts = data.get("timestamp")
        if isinstance(ts, str):
            try:
                parsed_ts = datetime.fromisoformat(ts)
            except ValueError:
                parsed_ts = datetime.now()
        elif isinstance(ts, datetime):
            parsed_ts = ts
        else:
            parsed_ts = datetime.now()

        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            model_name=data.get("model_name"),
            timestamp=parsed_ts,
            metadata=data.get("metadata", {}),
        )


@dataclass
class OrchestratorEvent:
    """Structured event emitted by the orchestrator for UI and subscriber consumption.

    Standard event types:
        - 'message': New ChatMessage added to conversation history.
        - 'stream_token': Individual token emitted during real-time generation.
        - 'stream_end': Generation streaming finalized.
        - 'deliberation_start': Multi-AI deliberation initiated.
        - 'deliberation_response': An individual candidate model responded.
        - 'deliberation_synthesis': Judge model synthesis initiated.
        - 'deliberation_end': Deliberation session concluded with consensus.
        - 'error': Runtime or communication error occurred.
        - 'status_change': System operational status modified.
        - 'skill_execution': Tool/skill execution initiated or completed.

    Attributes:
        event_type: String identifier of the event category.
        data: Contextual payload dictionary.
        timestamp: Time the event was produced.
    """

    event_type: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert event into a serializable dictionary."""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class Orchestrator:
    """Primary asynchronous controller wiring together all Multi-AI subsystems.

    Coordinates API client connection pools, security policies, dynamic skills,
    portable persistent memory, and multi-AI deliberation debates.
    """

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize the Orchestrator with default subsystems.

        Args:
            config_path: Optional explicit path for the settings configuration JSON.
                When omitted, the portable per-user config location is used.
        """
        if config_path is None:
            config_path = str(resolve_settings_path())
        self.config_path: Path = Path(config_path).expanduser().resolve()
        self.chat_history_path: Path = self.config_path.parent / "chat_history.json"
        self.api_client: APIClient = APIClient()
        self.security: SecurityGuard = SecurityGuard()
        self.skill_manager: SkillManager = SkillManager(self.security)
        self.memory: MemoryEngine = MemoryEngine()
        self.deliberation: DeliberationEngine = DeliberationEngine(self.api_client)

        # Wire deliberation engine events directly into the orchestrator event bus
        self.deliberation.set_event_callback(self._on_deliberation_event)

        self._settings: dict[str, Any] = {}
        self._chat_history: list[ChatMessage] = []
        self._event_handlers: list[Callable[..., Any]] = []
        self._running: bool = False

        # Status Lifecycle & Watchdog tracking
        self.status: RequestStatus = RequestStatus.IDLE
        self.last_error_report: Optional[RequestErrorReport] = None
        self.last_step: str = "idle"
        self.last_successful_step: str = "initialized"
        self.current_request_id: Optional[str] = None
        self.request_timeout: float = 30.0

    @property
    def is_running(self) -> bool:
        """Check if the orchestrator has completed initialization and is active."""
        return self._running

    @property
    def settings(self) -> dict[str, Any]:
        """Get the current loaded settings dictionary."""
        return self._settings

    @property
    def security_guard(self) -> SecurityGuard:
        """Backward-compatible alias for the active security policy gate."""
        return self.security

    @property
    def memory_engine(self) -> MemoryEngine:
        """Backward-compatible alias for the active memory engine."""
        return self.memory

    @property
    def deliberation_enabled(self) -> bool:
        """Get deliberation enabled status."""
        return self._settings.get("deliberation", {}).get("enabled", True)

    @deliberation_enabled.setter
    def deliberation_enabled(self, value: bool) -> None:
        """Set deliberation enabled status."""
        self._settings.setdefault("deliberation", {})["enabled"] = bool(value)

    @property
    def show_raw_debate(self) -> bool:
        """Get show_raw_debate status."""
        return self._settings.get("deliberation", {}).get("show_raw_debate", False)

    @show_raw_debate.setter
    def show_raw_debate(self, value: bool) -> None:
        """Set show_raw_debate status."""
        self._settings.setdefault("deliberation", {})["show_raw_debate"] = bool(value)

    @property
    def judge_model(self) -> Optional[str]:
        """Get judge model provider ID."""
        return self.deliberation._judge_provider_id

    @judge_model.setter
    def judge_model(self, value: Optional[str]) -> None:
        """Set judge model provider ID."""
        self.deliberation.set_judge(value)
        self._settings.setdefault("deliberation", {})["judge_model"] = value

    @property
    def memory_path(self) -> Path:
        """Get configured memory path."""
        return self.memory.path

    @memory_path.setter
    def memory_path(self, value: str | Path) -> None:
        """Set memory path and update settings."""
        p = Path(value).expanduser().resolve()
        self.memory.path = p
        self._settings["memory_path"] = str(p)

    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------

    async def initialize(self) -> None:
        """Execute system boot sequence: config, security, APIs, memory, skills.

        Steps:
            1. Load settings.json configuration.
            2. Apply security policy parameters.
            3. Initialize API client HTTP connection pooling.
            4. Load encrypted credentials and registered providers.
            5. Load memory store from configured path.
            6. Discover and register dynamic skills.
            7. Set operational running flag and emit status.
        """
        logger.info("Initializing Multi-AI Orchestrator...")

        # 1. Load settings
        await self.load_settings()
        await self._load_chat_history()

        # 2. Apply security policy from loaded settings
        sec_config = self._settings.get("security", {})
        if sec_config and isinstance(sec_config, dict):
            self.security.update_policy(**sec_config)
            logger.info("Security policy synchronized from settings.")

        # Configure deliberation engine from settings
        delib_config = self._settings.get("deliberation", {})
        if delib_config and isinstance(delib_config, dict):
            if "parallel_timeout" in delib_config:
                self.deliberation.set_timeout(float(delib_config["parallel_timeout"]))
            if "judge_model" in delib_config:
                self.deliberation.set_judge(delib_config.get("judge_model"))

        # Synchronize UI language preference
        language = self._settings.get("language")
        if language:
            I18n().set_language(language)

        # 3. Initialize API client connection pool
        await self.api_client.initialize()

        # 4. Load API credentials and providers
        await self._load_credentials_and_providers()

        # 5. Load persistent memory store
        memory_path = Path(self._settings.get("memory_path", "./memory/memory.json"))
        if not memory_path.is_absolute():
            memory_path = Path(__file__).resolve().parent.parent / memory_path
        await self.memory.load(memory_path)
        logger.info("Memory store loaded from %s", self.memory.path)

        # 6. Discover and register agent skills
        skills_dir = Path(self._settings.get("skills_dir", "./skills/"))
        if not skills_dir.is_absolute():
            skills_dir = Path(__file__).resolve().parent.parent / skills_dir
        loaded_skills = self.skill_manager.discover_and_load(skills_dir)
        logger.info("Discovered and registered %d skills from %s", loaded_skills, skills_dir)

        # 7. Set running flag and emit ready status
        self._running = True
        await self._emit(
            OrchestratorEvent(
                event_type="status_change",
                data={"status": "ready", "running": True},
            )
        )
        logger.info("Multi-AI Orchestrator successfully initialized.")

    async def shutdown(self) -> None:
        """Gracefully terminate orchestrator: save memory, flush settings, close APIs."""
        logger.info("Shutting down Multi-AI Orchestrator...")

        try:
            # 1. Save persistent memory
            await self.memory.save()
            logger.info("Persistent memory saved.")
        except Exception as exc:
            logger.error("Error saving memory during shutdown: %s", exc)

        try:
            # 2. Save settings
            await self.save_settings()
            logger.info("Application settings saved.")
        except Exception as exc:
            logger.error("Error saving settings during shutdown: %s", exc)

        try:
            # 3. Close API client connections
            await self.api_client.shutdown()
            logger.info("API client connections closed.")
        except Exception as exc:
            logger.error("Error terminating API client: %s", exc)

        self._running = False
        await self._emit(
            OrchestratorEvent(
                event_type="status_change",
                data={"status": "stopped", "running": False},
            )
        )
        logger.info("Multi-AI Orchestrator shutdown complete.")

    async def _load_credentials_and_providers(self) -> None:
        """Load provider configurations from settings, files, or environment variables."""
        loaded_from_config = False

        # Check for provider configurations embedded in settings.json
        if "providers" in self._settings and isinstance(self._settings["providers"], list):
            self.api_client.providers_from_dict(self._settings["providers"])
            if self.api_client.list_providers():
                logger.info(
                    "Loaded %d providers directly from settings.json",
                    len(self.api_client.list_providers()),
                )
                loaded_from_config = True

        # Check for external providers.json configuration
        project_root = Path(__file__).resolve().parent.parent
        providers_file = (project_root / "config" / "providers.json").resolve()
        if not loaded_from_config and providers_file.exists() and providers_file.is_file():
            try:
                loop = asyncio.get_running_loop()
                raw_text = await loop.run_in_executor(None, providers_file.read_text, "utf-8")
                providers_data = json.loads(raw_text)
                if isinstance(providers_data, list):
                    self.api_client.providers_from_dict(providers_data)
                    logger.info("Loaded %d providers from %s", len(providers_data), providers_file)
                    loaded_from_config = True
            except Exception as exc:
                logger.error("Failed to load providers from %s: %s", providers_file, exc)

        # Check for encrypted credentials file (e.g., config/credentials.enc)
        credentials_file = Path(self._settings.get("credentials_path", "./config/credentials.enc"))
        if not credentials_file.is_absolute():
            credentials_file = project_root / credentials_file
        credentials_file = credentials_file.resolve()
        sync_pass = (
            os.environ.get("ORCHESTRATOR_SYNC_PASSWORD")
            or os.environ.get("ORCHESTRATOR_KEY")
            or self._settings.get("credentials_password")
        )

        if credentials_file.exists() and credentials_file.is_file() and sync_pass:
            try:
                loop = asyncio.get_running_loop()
                enc_token = await loop.run_in_executor(
                    None, credentials_file.read_text, "utf-8"
                )
                token_data = CryptoEngine.parse_sync_token(enc_token.strip(), sync_pass)
                if "api_configs" in token_data and isinstance(token_data["api_configs"], list):
                    self.api_client.providers_from_dict(token_data["api_configs"])
                    logger.info(
                        "Loaded %d encrypted providers from %s",
                        len(token_data["api_configs"]),
                        credentials_file,
                    )
                    loaded_from_config = True
            except Exception as exc:
                logger.warning("Could not decrypt credentials file %s: %s", credentials_file, exc)

        # Auto-configure standard providers from environment variables if none registered
        if not self.api_client.list_providers():
            self._discover_environment_providers()

    def _discover_environment_providers(self) -> None:
        """Inspect environment variables and register default providers if available."""
        schemas = {}
        try:
            schemas_data = load_api_schemas()
            schemas = schemas_data.get("schemas", {})
        except Exception:
            pass

        # 1. OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key and not self.api_client.get_provider("openai"):
            openai_cfg = schemas.get("openai", {})
            self.api_client.add_provider(
                AIProvider(
                    id="openai",
                    name="OpenAI GPT-4o-mini",
                    base_url=openai_cfg.get("base_url", "https://api.openai.com/v1"),
                    api_key=openai_key,
                    model_id=openai_cfg.get("default_model", "gpt-4o-mini"),
                    schema_type=SchemaType.OPENAI,
                    enabled=True,
                )
            )

        # 2. Anthropic
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key and not self.api_client.get_provider("anthropic"):
            anthropic_cfg = schemas.get("anthropic", {})
            self.api_client.add_provider(
                AIProvider(
                    id="anthropic",
                    name="Anthropic Claude Sonnet",
                    base_url=anthropic_cfg.get("base_url", "https://api.anthropic.com/v1"),
                    api_key=anthropic_key,
                    model_id=anthropic_cfg.get("default_model", "claude-sonnet-4-20250514"),
                    schema_type=SchemaType.ANTHROPIC,
                    enabled=True,
                )
            )

        # 3. Google Gemini
        google_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if google_key and not self.api_client.get_provider("google"):
            google_cfg = schemas.get("google", {})
            self.api_client.add_provider(
                AIProvider(
                    id="google",
                    name="Google Gemini Flash",
                    base_url=google_cfg.get(
                        "base_url", "https://generativelanguage.googleapis.com/v1beta"
                    ),
                    api_key=google_key,
                    model_id=google_cfg.get("default_model", "gemini-2.5-flash"),
                    schema_type=SchemaType.GOOGLE,
                    enabled=True,
                )
            )

        # 4. Groq
        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key and not self.api_client.get_provider("groq"):
            groq_cfg = schemas.get("groq", {})
            self.api_client.add_provider(
                AIProvider(
                    id="groq",
                    name="Groq LLaMA 3.3",
                    base_url=groq_cfg.get("base_url", "https://api.groq.com/openai/v1"),
                    api_key=groq_key,
                    model_id=groq_cfg.get("default_model", "llama-3.3-70b-versatile"),
                    schema_type=SchemaType.OPENAI,
                    enabled=True,
                )
            )

    # -------------------------------------------------------------------------
    # Event System
    # -------------------------------------------------------------------------

    def on_event(self, handler: Callable[..., Any]) -> None:
        """Register an event listener callback for real-time UI notifications.

        Args:
            handler: Callable taking a single `OrchestratorEvent` parameter.
        """
        if handler not in self._event_handlers:
            self._event_handlers.append(handler)

    def add_event_listener(self, handler: Callable[..., Any]) -> None:
        """Backward-compatible alias for on_event."""
        self.on_event(handler)

    def remove_event_handler(self, handler: Callable[..., Any]) -> None:
        """Unregister an event listener callback.

        Args:
            handler: Previously registered handler.
        """
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)

    def remove_event_listener(self, handler: Callable[..., Any]) -> None:
        """Backward-compatible alias for remove_event_handler."""
        self.remove_event_handler(handler)

    async def _emit(self, event: OrchestratorEvent) -> None:
        """Emit an event asynchronously to all registered listeners.

        Args:
            event: OrchestratorEvent instance to dispatch.
        """
        for handler in list(self._event_handlers):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as exc:
                logger.error("Error in orchestrator event handler %r: %s", handler, exc)

    async def _on_deliberation_event(self, event_type: str, data: dict) -> None:
        """Bridge events emitted by DeliberationEngine into the orchestrator event bus.

        Args:
            event_type: Deliberation event type string.
            data: Deliberation event payload dictionary.
        """
        await self._emit(OrchestratorEvent(event_type=event_type, data=data))

    # -------------------------------------------------------------------------
    # Message Processing & Deliberation Pipeline
    # -------------------------------------------------------------------------

    async def process_message(
        self,
        user_input: str,
        provider_id: str | None = None,
    ) -> str:
        """Process a user message and generate a comprehensive assistant response.

        Execution steps:
            1. Append user ChatMessage to history and emit event.
            2. Build system prompt injecting core and scoped memories.
            3. Retrieve active AI providers.
            4. If deliberation is enabled and multiple models are active:
                   -> Delegate to DeliberationEngine (parallel query + synthesis).
               Else (single model or deliberation disabled):
                   -> Direct completion with the selected or primary provider.
            5. Append assistant ChatMessage to history and emit event.
            6. Return final response content.

        Args:
            user_input: Raw query string from the user.
            provider_id: Optional active provider to use for direct responses.

        Returns:
            Final textual response from the assistant or deliberation synthesis.
        """
        if not self._running:
            await self.initialize()

        # 1. Record user message
        user_msg = ChatMessage(
            role="user",
            content=user_input,
            timestamp=datetime.now(),
        )
        self._chat_history.append(user_msg)
        await self._persist_chat_history()
        await self._emit(OrchestratorEvent(event_type="message", data=user_msg.to_dict()))

        # 2. Build system prompt and payload
        system_prompt = self._build_system_prompt()
        messages = self._build_messages_payload()
        active_providers = self.api_client.get_active_providers()

        # Handle scenario with zero active providers
        if not active_providers:
            fallback_err = I18n().t("no_models")
            if not fallback_err or fallback_err == "no_models":
                fallback_err = (
                    "No active AI providers are configured. Please enable at least "
                    "one provider in settings or provide an API key."
                )

            err_chat_msg = ChatMessage(
                role="assistant",
                content=fallback_err,
                model_name=None,
                timestamp=datetime.now(),
                metadata={"error": True},
            )
            self._chat_history.append(err_chat_msg)
            await self._persist_chat_history()
            await self._emit(OrchestratorEvent(event_type="error", data={"error": fallback_err}))
            await self._emit(OrchestratorEvent(event_type="message", data=err_chat_msg.to_dict()))
            return fallback_err

        # Check deliberation settings
        delib_settings = self._settings.get("deliberation", {})
        deliberation_enabled = delib_settings.get("enabled", True)

        # 4. Route execution
        if deliberation_enabled and len(active_providers) > 1:
            # Multi-model Deliberation mode
            delib_result: DeliberationResult = await self.deliberation.deliberate(
                messages=messages,
                system_prompt=system_prompt,
                providers=active_providers,
            )
            response_text = delib_result.synthesis
            model_name = delib_result.judge_model
            metadata = {
                "deliberation": True,
                "judge_model": delib_result.judge_model,
                "total_time_ms": delib_result.total_time_ms,
                "consensus_achieved": delib_result.consensus_achieved,
                "responses": [
                    {
                        "provider_id": r.provider_id,
                        "model_name": r.model_name,
                        "latency_ms": r.latency_ms,
                        "token_usage": r.token_usage,
                        "error": r.error,
                        "preview": r.content[:150] if r.content else "",
                    }
                    for r in delib_result.responses
                ],
            }
        else:
            # Single model direct completion mode
            provider = active_providers[0]
            if provider_id is not None:
                provider = next(
                    (item for item in active_providers if item.id == provider_id),
                    None,
                )
                if provider is None:
                    raise ValueError(
                        f"Selected provider '{provider_id}' is not active."
                    )
            try:
                tool_schemas = self._available_tool_schemas()
                if tool_schemas:
                    tool_names = ", ".join(
                        item["function"]["name"] for item in tool_schemas
                    )
                    system_prompt = "\n\n".join(filter(None, [
                        system_prompt,
                        "You may use only these application tools when needed: "
                        f"{tool_names}. Use a tool instead of claiming you cannot "
                        "perform an enabled operation. If the user asks you to create, "
                        "read, write, modify, or delete a file or run a command, you MUST "
                        "call the matching tool; do not provide shell commands as a "
                        "substitute or claim the action is complete without a successful "
                        "tool result. If a tool reports a permission or path error, explain "
                        "that error and ask for an allowed path or permission. Use file_io "
                        "for file and folder operations instead of terminal commands. Never "
                        "claim access to screen, mouse, keyboard, or other desktop controls "
                        "unless a matching tool is listed.",
                    ]))
                else:
                    system_prompt = "\n\n".join(filter(None, [
                        system_prompt,
                        "No application tools are currently available in this chat. "
                        "Do not claim to access or control the user's computer.",
                    ]))

                response_text = await self._complete_with_tools(
                    provider=provider,
                    messages=messages,
                    system_prompt=system_prompt,
                    tools=tool_schemas,
                )
                model_name = provider.name
                metadata = {
                    "deliberation": False,
                    "provider_id": provider.id,
                }
            except Exception as exc:
                logger.error("Chat completion failed on provider %s: %s", provider.name, exc)
                response_text = f"API Error ({provider.name}): {exc}"
                model_name = provider.name
                metadata = {
                    "deliberation": False,
                    "provider_id": provider.id,
                    "error": str(exc),
                }
                await self._emit(
                    OrchestratorEvent(
                        event_type="error",
                        data={"error": str(exc), "provider": provider.name},
                    )
                )

        # 5. Append assistant message to chat history
        assistant_msg = ChatMessage(
            role="assistant",
            content=response_text,
            model_name=model_name,
            timestamp=datetime.now(),
            metadata=metadata,
        )
        self._chat_history.append(assistant_msg)
        await self._persist_chat_history()
        await self._emit(OrchestratorEvent(event_type="message", data=assistant_msg.to_dict()))

        # 6. Return response text
        return response_text

    def _available_tool_schemas(self) -> list[dict[str, Any]]:
        """Return registered tools whose required permissions are enabled."""
        schemas: list[dict[str, Any]] = []
        for skill in self.skill_manager.skills.values():
            if all(
                self.security.check_permission(permission)[0]
                for permission in skill.required_permissions
            ):
                schemas.append(skill.to_tool_schema())
        return schemas

    async def _complete_with_tools(
        self,
        provider: AIProvider,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> str:
        """Run a bounded model/tool loop for direct responses."""
        max_rounds = 6
        max_tool_calls = 12
        tool_call_count = 0

        for _ in range(max_rounds):
            result = await self.api_client.chat_completion(
                provider=provider,
                messages=messages,
                system_prompt=system_prompt,
                tools=tools or None,
            )
            tool_calls = result.get("tool_calls", [])
            if not tool_calls:
                return result.get("content", "")

            if tool_call_count + len(tool_calls) > max_tool_calls:
                raise RuntimeError("The model exceeded the maximum number of tool calls.")

            normalized_calls = []
            for index, call in enumerate(tool_calls):
                normalized_calls.append({
                    "id": call.get("id") or f"tool-{tool_call_count + index}",
                    "type": "function",
                    "function": {
                        "name": call.get("name", ""),
                        "arguments": (
                            call.get("arguments", "{}")
                            if isinstance(call.get("arguments", "{}"), str)
                            else json.dumps(call.get("arguments", {}), ensure_ascii=False)
                        ),
                        **(
                            {"thought_signature": call["thought_signature"]}
                            if call.get("thought_signature")
                            else {}
                        ),
                    },
                })
            messages.append({
                "role": "assistant",
                "content": result.get("content", ""),
                "tool_calls": normalized_calls,
            })

            for call in normalized_calls:
                function = call["function"]
                try:
                    params = json.loads(function["arguments"])
                    if not isinstance(params, dict):
                        raise ValueError("Tool arguments must be a JSON object.")
                    await self._emit(
                        OrchestratorEvent(
                            event_type="tool_start",
                            data={"tool_name": function["name"]},
                        )
                    )
                    tool_result = await self.execute_tool(function["name"], params)
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    tool_result = {
                        "success": False,
                        "result": None,
                        "error": f"Invalid tool call: {exc}",
                    }
                finally:
                    await self._emit(
                        OrchestratorEvent(
                            event_type="tool_end",
                            data={"tool_name": function["name"]},
                        )
                    )
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": function["name"],
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                })
            tool_call_count += len(normalized_calls)

        raise RuntimeError("The model did not finish after the maximum tool-call rounds.")

    async def process_message_stream(self, user_input: str) -> AsyncIterator[str]:
        """Stream real-time tokens for a user message as they arrive from the model.

        For single model execution, streams tokens directly from the provider.
        For multi-model deliberation, parallel queries are executed and the judge
        model's synthesis tokens are streamed back.

        Args:
            user_input: Raw query string from the user.

        Yields:
            Token chunks as they are generated.
        """
        if not self._running:
            await self.initialize()

        # 1. Record user message
        user_msg = ChatMessage(
            role="user",
            content=user_input,
            timestamp=datetime.now(),
        )
        self._chat_history.append(user_msg)
        await self._persist_chat_history()
        await self._emit(OrchestratorEvent(event_type="message", data=user_msg.to_dict()))

        system_prompt = self._build_system_prompt()
        messages = self._build_messages_payload()
        active_providers = self.api_client.get_active_providers()

        if not active_providers:
            fallback_err = I18n().t("no_models")
            if not fallback_err or fallback_err == "no_models":
                fallback_err = (
                    "No active AI providers are configured. Please enable at least "
                    "one provider in settings or provide an API key."
                )

            err_chat_msg = ChatMessage(
                role="assistant",
                content=fallback_err,
                model_name=None,
                timestamp=datetime.now(),
                metadata={"error": True},
            )
            self._chat_history.append(err_chat_msg)
            await self._persist_chat_history()
            await self._emit(OrchestratorEvent(event_type="error", data={"error": fallback_err}))
            await self._emit(OrchestratorEvent(event_type="message", data=err_chat_msg.to_dict()))
            yield fallback_err
            return

        delib_settings = self._settings.get("deliberation", {})
        deliberation_enabled = delib_settings.get("enabled", True)

        accumulated_chunks: list[str] = []

        if deliberation_enabled and len(active_providers) > 1:
            judge = self.deliberation._get_judge(active_providers)
            model_name = judge.name

            async for token in self.deliberation.deliberate_stream(
                messages=messages,
                system_prompt=system_prompt,
                providers=active_providers,
            ):
                accumulated_chunks.append(token)
                await self._emit(
                    OrchestratorEvent(
                        event_type="stream_token",
                        data={"token": token, "model": model_name},
                    )
                )
                yield token

            metadata = {"deliberation": True, "judge_model": model_name}
        else:
            provider = active_providers[0]
            model_name = provider.name
            try:
                async for token in self.api_client.chat_completion_stream(
                    provider=provider,
                    messages=messages,
                    system_prompt=system_prompt,
                ):
                    accumulated_chunks.append(token)
                    await self._emit(
                        OrchestratorEvent(
                            event_type="stream_token",
                            data={"token": token, "model": model_name},
                        )
                    )
                    yield token
                metadata = {"deliberation": False, "provider_id": provider.id}
            except Exception as exc:
                logger.error("Streaming error on provider %s: %s", provider.name, exc)
                err_text = f"\n[Streaming error ({provider.name}): {exc}]"
                accumulated_chunks.append(err_text)
                await self._emit(
                    OrchestratorEvent(
                        event_type="error",
                        data={"error": str(exc), "provider": provider.name},
                    )
                )
                yield err_text
                metadata = {"deliberation": False, "error": str(exc)}

        full_content = "".join(accumulated_chunks)
        await self._emit(
            OrchestratorEvent(
                event_type="stream_end",
                data={"model": model_name, "total_chars": len(full_content)},
            )
        )

        assistant_msg = ChatMessage(
            role="assistant",
            content=full_content,
            model_name=model_name,
            timestamp=datetime.now(),
            metadata=metadata,
        )
        self._chat_history.append(assistant_msg)
        await self._persist_chat_history()
        await self._emit(OrchestratorEvent(event_type="message", data=assistant_msg.to_dict()))

    def _build_system_prompt(self) -> str:
        """Combine memory context injection with custom base system instructions.

        Returns:
            Concatenated system prompt instructions string.
        """
        memory_context = self.memory.get_context_injection()
        custom_system = self._settings.get("system_prompt", "").strip()

        components: list[str] = []
        if custom_system:
            components.append(custom_system)
        if memory_context and memory_context.strip():
            components.append(memory_context.strip())

        # The UI language is a response-language preference, not merely a label.
        # Always pass an explicit instruction to providers because their defaults
        # can otherwise fall back to English even when the user selected Turkish.
        response_language = I18n().current_language
        if response_language == "tr":
            components.append(
                "Yanıtlarını tutarlı biçimde Türkçe ver. Teknik terimler, ürün/kitaplık adları ve kod kelimeleri gerektiğinde İngilizce kalabilir."
            )
        else:
            components.append(
                "Respond in the language of the user's message. If the language is undetermined, respond in English."
            )

        return "\n\n".join(components)

    def _build_messages_payload(self) -> list[dict]:
        """Convert internal ChatMessage history to API-compatible messages schema.

        Extracts only 'user' and 'assistant' roles, skipping deliberation internal markers.

        Returns:
            List of message dictionaries with 'role' and 'content' keys.
        """
        payload: list[dict] = []
        for msg in self._chat_history:
            if msg.role in ("user", "assistant"):
                payload.append({"role": msg.role, "content": msg.content})
        return payload

    # -------------------------------------------------------------------------
    # Tool & Skill Execution
    # -------------------------------------------------------------------------

    async def execute_tool(self, tool_name: str, params: dict) -> dict:
        """Execute an autonomous skill tool through the secured execution pipeline.

        Verifies tool registration, checks security policies via SkillManager,
        dispatches execution, and emits an audit event.

        Args:
            tool_name: Unique registered name of the skill.
            params: Dictionary of arguments required by the skill.

        Returns:
            Execution result dictionary: {'success': bool, 'result': Any, 'error': str | None}.
        """
        if tool_name not in self.skill_manager.skills:
            error_result = {
                "success": False,
                "result": None,
                "error": f"Tool '{tool_name}' not found.",
            }
            await self._emit(
                OrchestratorEvent(
                    event_type="skill_execution",
                    data={"tool_name": tool_name, "params": params, "result": error_result},
                )
            )
            return error_result

        result = await self.skill_manager.execute_skill(tool_name, params)
        await self._emit(
            OrchestratorEvent(
                event_type="skill_execution",
                data={"tool_name": tool_name, "params": params, "result": result},
            )
        )
        return result

    # -------------------------------------------------------------------------
    # Settings Management
    # -------------------------------------------------------------------------

    async def save_settings(self) -> None:
        """Persist current application configuration to disk atomically.

        This preserves previously saved provider secrets when the same provider is
        reloaded without an explicit key change, so toggling the app on/off does not
        silently wipe API credentials or other user-entered settings.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        existing_settings: dict[str, Any] = {}
        if self.config_path.exists() and self.config_path.is_file():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    existing_settings = json.load(f)
            except (json.JSONDecodeError, OSError):
                existing_settings = {}

        merged_settings = dict(existing_settings if isinstance(existing_settings, dict) else {})

        # Reflect active state into settings dictionary
        merged_settings["memory_path"] = str(self.memory.path)

        policy = self.security.policy
        merged_settings["security"] = {
            "sudo_enabled": policy.sudo_enabled,
            "fs_read": policy.fs_read,
            "fs_write": policy.fs_write,
            "fs_delete": policy.fs_delete,
            "screen_capture": policy.screen_capture,
            "mouse_control": policy.mouse_control,
            "keyboard_control": policy.keyboard_control,
            "allowed_paths": policy.allowed_paths,
            "gui_automation": policy.gui_automation,
            "terminal_enabled": policy.terminal_enabled,
        }

        delib_cfg = merged_settings.setdefault("deliberation", {})
        delib_cfg["parallel_timeout"] = self.deliberation._timeout
        delib_cfg["judge_model"] = self.deliberation._judge_provider_id
        delib_cfg["enabled"] = self.deliberation_enabled
        delib_cfg["show_raw_debate"] = self.show_raw_debate
        merged_settings["language"] = I18n().current_language

        raw_providers = self.api_client.providers_to_dict()
        previous_providers = {
            str(item.get("id")): item
            for item in existing_settings.get("providers", [])
            if isinstance(item, dict) and item.get("id") is not None
        }

        merged_providers: list[dict[str, Any]] = []
        for provider in raw_providers:
            provider_id = str(provider.get("id"))
            prior = previous_providers.get(provider_id, {})
            if isinstance(prior, dict):
                for key in ("api_key", "base_url", "model_id", "name", "schema_type", "effort_level"):
                    current_value = provider.get(key)
                    prior_value = prior.get(key)
                    if current_value in (None, "") and prior_value not in (None, ""):
                        provider[key] = prior_value
            merged_providers.append(provider)

        merged_settings["providers"] = merged_providers
        self._settings = merged_settings

        content = json.dumps(merged_settings, indent=2, ensure_ascii=False)
        temp_file = self.config_path.with_suffix(".tmp")
        loop = asyncio.get_running_loop()

        def _write_file() -> None:
            with open(temp_file, "w", encoding="utf-8") as f:
                if os.name != "nt":
                    os.chmod(temp_file, 0o600)
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            temp_file.replace(self.config_path)

        await loop.run_in_executor(None, _write_file)
        logger.debug("Settings successfully saved to %s", self.config_path)

    async def load_settings(self) -> None:
        """Load settings from the configured JSON file path, falling back to defaults."""
        if self.config_path.exists() and self.config_path.is_file():
            loop = asyncio.get_running_loop()

            def _read_file() -> dict:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)

            try:
                self._settings = await loop.run_in_executor(None, _read_file)
            except Exception as exc:
                logger.error("Failed to parse settings file %s: %s", self.config_path, exc)
                self._settings = load_settings()
        else:
            try:
                self._settings = load_settings()
            except Exception as exc:
                logger.warning("Default settings could not be loaded: %s", exc)
                self._settings = {}

    def update_security_policy(self, **kwargs: Any) -> None:
        """Update security guard permission parameters and synchronize settings.

        Args:
            **kwargs: Policy arguments matching SecurityPolicy attributes.
        """
        self.security.update_policy(**kwargs)
        if "security" not in self._settings:
            self._settings["security"] = {}
        self._settings["security"].update(kwargs)

    # -------------------------------------------------------------------------
    # Provider Management (Delegates to APIClient)
    # -------------------------------------------------------------------------

    def add_provider(self, provider: AIProvider) -> None:
        """Register a new AIProvider configuration.

        Args:
            provider: AIProvider instance to register.
        """
        self.api_client.add_provider(provider)

    def remove_provider(self, provider_id: str) -> None:
        """Remove a provider by ID from the active registry.

        Args:
            provider_id: Unique identifier string of the provider.
        """
        self.api_client.remove_provider(provider_id)

    def toggle_provider(self, provider_id: str, enabled: bool) -> None:
        """Enable or disable a registered provider.

        Args:
            provider_id: Unique identifier string of the provider.
            enabled: True to enable, False to disable.
        """
        self.api_client.toggle_provider(provider_id, enabled)

    async def health_check_all(self) -> list[HealthResult]:
        """Execute concurrent health check probes across all registered providers.

        Returns:
            List of HealthResult records detailing latency and endpoint reachability.
        """
        return await self.api_client.health_check_all()

    # -------------------------------------------------------------------------
    # Memory Management
    # -------------------------------------------------------------------------

    def get_memory(self) -> MemoryEngine:
        """Retrieve the primary MemoryEngine instance.

        Returns:
            MemoryEngine managing core and sub-memories.
        """
        return self.memory

    # -------------------------------------------------------------------------
    # Synchronization & Portability Tokens
    # -------------------------------------------------------------------------

    def generate_sync_token(self, password: str) -> str:
        """Bundle memory data and API configurations into an encrypted sync token.

        Uses AES-256-GCM with PBKDF2 key derivation for cross-platform portability.

        Args:
            password: Passphrase used to derive encryption key.

        Returns:
            Base64-encoded encrypted synchronization token.
        """
        memory_data = self.memory.export_data()
        api_configs = self.api_client.providers_to_dict()
        return CryptoEngine.generate_sync_token(memory_data, api_configs, password)

    def import_sync_token(self, token: str, password: str) -> None:
        """Import and decrypt data from an encrypted synchronization token.

        Restores both the memory store and API provider registry.

        Args:
            token: Base64-encoded sync token.
            password: Decryption passphrase.
        """
        data = CryptoEngine.parse_sync_token(token, password)

        if "memory" in data and isinstance(data["memory"], dict):
            self.memory.store = MemoryStore.model_validate(data["memory"])
            logger.info("Imported memory store from sync token.")

        if "api_configs" in data and isinstance(data["api_configs"], list):
            self.api_client.providers_from_dict(data["api_configs"])
            logger.info("Imported %d providers from sync token.", len(data["api_configs"]))

    # -------------------------------------------------------------------------
    # Chat History Operations
    # -------------------------------------------------------------------------

    def get_chat_history(self) -> list[ChatMessage]:
        """Retrieve a copy of the entire current conversation history.

        Returns:
            List of ChatMessage objects in chronological order.
        """
        return list(self._chat_history)

    def clear_chat_history(self) -> None:
        """Clear persisted and in-memory conversation history."""
        self._write_chat_history_sync(self.chat_history_path, [])
        self._chat_history.clear()
        logger.debug("Chat history cleared.")

    async def _load_chat_history(self) -> None:
        """Load the user's private conversation history without overwriting bad data."""
        if not self.chat_history_path.is_file():
            return

        loop = asyncio.get_running_loop()

        def _read_file() -> Any:
            with open(self.chat_history_path, "r", encoding="utf-8") as file:
                return json.load(file)

        try:
            history = await loop.run_in_executor(None, _read_file)
        except (OSError, json.JSONDecodeError) as exc:
            logger.exception("Could not load chat history from %s", self.chat_history_path)
            raise RuntimeError(
                f"Could not load saved chat history: {self.chat_history_path}"
            ) from exc

        if not isinstance(history, list) or not all(isinstance(item, dict) for item in history):
            raise ValueError(f"Invalid chat history format in {self.chat_history_path}")

        self._chat_history = [ChatMessage.from_dict(item) for item in history]

    async def _persist_chat_history(self) -> None:
        """Atomically save a snapshot of the conversation to the private data directory."""
        serialized = [message.to_dict() for message in self._chat_history]
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                self._write_chat_history_sync,
                self.chat_history_path,
                serialized,
            )
        except OSError:
            logger.exception("Could not save chat history to %s", self.chat_history_path)
            raise

    @staticmethod
    def _write_chat_history_sync(path: Path, history: list[dict[str, Any]]) -> None:
        """Write private chat history atomically so interruptions cannot truncate it."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        serialized = json.dumps(history, ensure_ascii=False, indent=2)
        try:
            with open(temp_path, "w", encoding="utf-8") as file:
                if os.name != "nt":
                    os.chmod(temp_path, 0o600)
                file.write(serialized)
                file.flush()
                os.fsync(file.fileno())
            temp_path.replace(path)
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
