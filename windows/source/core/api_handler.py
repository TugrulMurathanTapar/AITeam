"""Multi-Provider AI API Handler for Cross-Platform Multi-AI Orchestrator.

Provides asynchronous HTTP client integration for multiple AI model providers,
including OpenAI, Anthropic, Google Gemini, and custom REST endpoints. Supports
connection pooling, streaming via Server-Sent Events (SSE), retry with exponential
backoff, effort level configuration, and health monitoring.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import random
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from urllib.parse import urlsplit, urlunsplit

import httpx

logger = logging.getLogger("orchestrator.api_handler")


class SchemaType(Enum):
    """Supported API schema and protocol types."""
    OPENAI = 'openai'           # Standard OpenAI-compatible REST API
    ANTHROPIC = 'anthropic'     # Anthropic Messages API
    GOOGLE = 'google'           # Google Gemini API
    CUSTOM = 'custom'           # Custom REST endpoint


class EffortLevel(Enum):
    """Reasoning effort or thinking budget levels."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    EXTENDED = 'extended_thinking'


@dataclass
class AIProvider:
    """Configuration record for an AI model provider."""
    id: str
    name: str
    base_url: str
    api_key: str
    model_id: str
    schema_type: SchemaType = SchemaType.OPENAI
    enabled: bool = True
    effort_level: EffortLevel = EffortLevel.MEDIUM
    max_tokens: int = 4096
    temperature: float = 0.7
    custom_headers: dict = field(default_factory=dict)
    custom_payload_template: dict | None = None  # For CUSTOM schema type


@dataclass
class HealthResult:
    """Outcome of a health check probe against an AI provider."""
    provider_id: str
    status: str  # 'ok', 'error', 'timeout'
    latency_ms: float
    status_code: int | None
    error_message: str | None = None
    model_info: str | None = None


class APIClientError(Exception):
    """Base exception for API client operations."""
    pass


class ProviderNotFoundError(APIClientError):
    """Raised when an operation references a non-existent provider."""
    pass


class ProviderRequestError(APIClientError):
    """Raised when an API request fails after retries."""
    def __init__(self, message: str, status_code: int | None = None, response_text: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class APIClient:
    """Async multi-provider AI client with connection pooling, retries, and streaming."""

    MAX_ACTIVE_PROVIDERS = 10

    def __init__(self) -> None:
        """Initialize the APIClient with empty provider registry and inactive HTTP client."""
        self._providers: dict[str, AIProvider] = {}
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _tool_call_fields(call: dict[str, Any]) -> dict[str, Any]:
        """Normalize provider-neutral and OpenAI-shaped tool-call messages."""
        function = (
            call.get("function")
            or call.get("function_call")
            or call.get("functionCall")
        )
        if not isinstance(function, dict):
            function = call
        raw_arguments = function.get("arguments", call.get("arguments", {}))
        if isinstance(raw_arguments, str):
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                arguments = {}
        else:
            arguments = raw_arguments

        result = {
            "id": call.get("id", ""),
            "name": function.get("name", call.get("name", "")),
            "arguments": arguments if isinstance(arguments, dict) else {},
        }
        thought_signature = (
            function.get("thought_signature")
            or function.get("thoughtSignature")
            or call.get("thought_signature")
            or call.get("thoughtSignature")
        )
        if thought_signature:
            result["thought_signature"] = thought_signature
        return result

    @staticmethod
    def _google_schema(schema: Any) -> Any:
        """Remove JSON Schema fields unsupported by Gemini function declarations."""
        unsupported_fields = {"$schema", "additionalProperties", "default"}
        if isinstance(schema, dict):
            return {
                key: APIClient._google_schema(value)
                for key, value in schema.items()
                if key not in unsupported_fields
            }
        if isinstance(schema, list):
            return [APIClient._google_schema(item) for item in schema]
        return schema

    @staticmethod
    def _safe_error_detail(response: httpx.Response, headers: Any) -> str:
        """Extract a provider error message without exposing request credentials."""
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            return ""

        error = data.get("error", {}) if isinstance(data, dict) else {}
        detail = error.get("message", "") if isinstance(error, dict) else ""
        if not isinstance(detail, str):
            return ""

        for key, value in (headers.items() if isinstance(headers, dict) else []):
            if value and any(token in str(key).lower() for token in ("key", "token", "authorization")):
                detail = detail.replace(str(value), "[redacted]")
        detail = detail.replace("\r", " ").replace("\n", " ").strip()
        return detail[:1000]

    @staticmethod
    def _safe_url(url: str) -> str:
        """Return a URL suitable for diagnostics without credentials or query values."""
        try:
            parsed = urlsplit(url)
            host = parsed.hostname or "invalid-host"
            if parsed.port:
                host = f"{host}:{parsed.port}"
            return urlunsplit((parsed.scheme, host, "/[path redacted]", "", ""))
        except ValueError:
            return "[invalid URL]"

    @staticmethod
    def _validate_provider_url(provider: AIProvider) -> None:
        """Require HTTPS except for explicitly local development endpoints."""
        try:
            parsed = urlsplit(provider.base_url)
            hostname = (parsed.hostname or "").lower()
            local_http = parsed.scheme == "http" and hostname in {"localhost", "127.0.0.1", "::1"}
            if parsed.scheme != "https" and not local_http:
                raise ValueError("Provider URL must use HTTPS (HTTP is allowed only for localhost).")
            if not hostname or parsed.username or parsed.password:
                raise ValueError("Provider URL must contain a host and must not embed credentials.")
        except ValueError as exc:
            if "Provider URL" in str(exc):
                raise
            raise ValueError("Provider URL is invalid.") from exc

    async def __aenter__(self) -> APIClient:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit with cleanup."""
        await self.shutdown()

    async def initialize(self) -> None:
        """Create httpx.AsyncClient with connection pooling and standard limits."""
        async with self._lock:
            if self._client is None or self._client.is_closed:
                limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
                timeout = httpx.Timeout(60.0, connect=10.0)
                self._client = httpx.AsyncClient(limits=limits, timeout=timeout)
                logger.info("APIClient HTTP session initialized with 60s timeout.")

    async def shutdown(self) -> None:
        """Close httpx.AsyncClient and release resources."""
        async with self._lock:
            if self._client is not None and not self._client.is_closed:
                await self._client.aclose()
                self._client = None
                logger.info("APIClient HTTP session closed.")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get the active httpx client or initialize one if not present."""
        if self._client is None or self._client.is_closed:
            await self.initialize()
        assert self._client is not None
        return self._client

    # -------------------------------------------------------------------------
    # Provider Management
    # -------------------------------------------------------------------------

    def add_provider(self, provider: AIProvider) -> None:
        """Register a new AI provider or replace an existing one by ID.

        Args:
            provider: AIProvider instance to register.
        """
        existing = self._providers.get(provider.id)
        if provider.enabled:
            already_active = bool(existing and existing.enabled)
            active_count = len(self.get_active_providers())
            if not already_active and active_count >= self.MAX_ACTIVE_PROVIDERS:
                raise ValueError(
                    f"En fazla {self.MAX_ACTIVE_PROVIDERS} model aynı anda aktif olabilir."
                )
        self._providers[provider.id] = provider
        logger.debug(f"Registered provider: {provider.id} ({provider.name})")

    def remove_provider(self, provider_id: str) -> None:
        """Remove a provider by ID from the registry.

        Args:
            provider_id: Unique identifier of provider to remove.
        """
        if provider_id in self._providers:
            del self._providers[provider_id]
            logger.debug(f"Removed provider: {provider_id}")

    def get_provider(self, provider_id: str) -> AIProvider | None:
        """Retrieve a provider configuration by ID.

        Args:
            provider_id: Unique identifier of the provider.

        Returns:
            AIProvider instance or None if not found.
        """
        return self._providers.get(provider_id)

    def list_providers(self) -> list[AIProvider]:
        """List all registered providers.

        Returns:
            List of AIProvider instances.
        """
        return list(self._providers.values())

    def get_active_providers(self) -> list[AIProvider]:
        """Get all enabled providers.

        Returns:
            List of AIProvider instances where enabled=True.
        """
        return [p for p in self._providers.values() if p.enabled]

    def toggle_provider(self, provider_id: str, enabled: bool) -> None:
        """Enable or disable a registered provider.

        Args:
            provider_id: Unique identifier of the provider.
            enabled: Boolean flag to enable (True) or disable (False).

        Raises:
            ProviderNotFoundError: If provider ID is not registered.
            ValueError: If enabling would exceed the active-provider limit.
        """
        provider = self._providers.get(provider_id)
        if not provider:
            raise ProviderNotFoundError(f"Provider '{provider_id}' not found.")
        if enabled and not provider.enabled:
            active_count = len(self.get_active_providers())
            if active_count >= self.MAX_ACTIVE_PROVIDERS:
                raise ValueError(
                    f"En fazla {self.MAX_ACTIVE_PROVIDERS} model aynı anda aktif olabilir."
                )
        provider.enabled = enabled
        logger.debug(f"Set provider '{provider_id}' enabled={enabled}")

    def update_effort(self, provider_id: str, level: EffortLevel) -> None:
        """Update the reasoning effort level for a provider.

        Args:
            provider_id: Unique identifier of the provider.
            level: Desired EffortLevel enum value.

        Raises:
            ProviderNotFoundError: If provider ID is not registered.
        """
        provider = self._providers.get(provider_id)
        if not provider:
            raise ProviderNotFoundError(f"Provider '{provider_id}' not found.")
        provider.effort_level = level
        logger.debug(f"Updated provider '{provider_id}' effort_level={level.value}")

    # -------------------------------------------------------------------------
    # HTTP Request Execution with Exponential Backoff Retries
    # -------------------------------------------------------------------------

    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs: Any
    ) -> httpx.Response:
        """Execute an HTTP request with exponential backoff retry logic.

        Retries on network errors, timeouts, and 429/5xx status codes.
        Non-retryable client errors (400, 401, 403, 404, etc.) are raised immediately.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL.
            max_retries: Maximum number of retry attempts (default 3).
            **kwargs: Extra parameters passed to httpx.request.

        Returns:
            httpx.Response on success.

        Raises:
            ProviderRequestError: If retries are exhausted or a non-retryable error occurs.
        """
        client = await self._get_client()
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
                # If retryable status code, trigger exception for retry logic
                if response.status_code in (429, 500, 502, 503, 504):
                    response.raise_for_status()
                # If other 4xx or 5xx, raise immediately without retry
                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as exc:
                last_exception = exc
                status = exc.response.status_code
                if status not in (429, 500, 502, 503, 504) or attempt == max_retries:
                    safe_url = self._safe_url(url)
                    err_msg = f"HTTP {status} from {safe_url}"
                    detail = self._safe_error_detail(
                        exc.response,
                        kwargs.get("headers", {}),
                    )
                    if detail:
                        err_msg = f"{err_msg}: {detail}"
                    logger.error("%s", err_msg)
                    raise ProviderRequestError(
                        err_msg,
                        status_code=status,
                        response_text=detail or None,
                    ) from None

                # Parse retry delay with jitter
                delay = 0.5 * (2 ** attempt) + random.uniform(0.05, 0.25)
                retry_after = exc.response.headers.get("retry-after")
                if retry_after:
                    try:
                        delay = min(float(retry_after), 10.0)
                    except ValueError:
                        pass

                logger.warning(
                    f"HTTP {status} requesting {self._safe_url(url)}. Retrying attempt {attempt + 1}/{max_retries} in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exception = exc
                if attempt == max_retries:
                    err_msg = f"Network or timeout error contacting {self._safe_url(url)}"
                    logger.error(err_msg)
                    raise ProviderRequestError(err_msg) from None

                delay = 0.5 * (2 ** attempt) + random.uniform(0.05, 0.25)
                logger.warning(
                    f"Connection issue with {self._safe_url(url)} ({type(exc).__name__}). Retrying attempt {attempt + 1}/{max_retries} in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)

        if last_exception:
            raise ProviderRequestError(f"Request failed after {max_retries} retries: {last_exception}")
            raise ProviderRequestError(f"Request failed unexpectedly on {self._safe_url(url)}")

    # -------------------------------------------------------------------------
    # Chat Completion (Non-Streaming)
    # -------------------------------------------------------------------------

    async def chat_completion(
        self,
        provider: AIProvider,
        messages: list[dict],
        system_prompt: str = '',
        stream: bool = False,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """Execute chat completion and route to appropriate schema handler.

        Args:
            provider: Target AIProvider configuration.
            messages: List of chat messages (e.g. [{"role": "user", "content": "..."}]).
            system_prompt: Optional system instructions.
            stream: Boolean flag (if True, completes non-streaming or sets stream flag).
            tools: Optional tool definitions list.

        Returns:
            Standardized response dictionary:
            {
                'content': str,
                'usage': {'prompt_tokens': int, 'completion_tokens': int, 'total_tokens': int},
                'model': str
            }

        Raises:
            ValueError: If provider is disabled or schema type is invalid.
            ProviderRequestError: If request fails.
        """
        if not provider.enabled:
            raise ValueError(f"Provider '{provider.id}' ({provider.name}) is disabled.")
        self._validate_provider_url(provider)

        if provider.schema_type == SchemaType.OPENAI:
            return await self._openai_request(provider, messages, system_prompt, stream, tools, max_tokens)
        elif provider.schema_type == SchemaType.ANTHROPIC:
            return await self._anthropic_request(provider, messages, system_prompt, stream, tools, max_tokens)
        elif provider.schema_type == SchemaType.GOOGLE:
            return await self._google_request(provider, messages, system_prompt, stream, tools, max_tokens)
        elif provider.schema_type == SchemaType.CUSTOM:
            return await self._custom_request(provider, messages, system_prompt, stream, tools, max_tokens)
        else:
            raise ValueError(f"Unsupported schema type: {provider.schema_type}")

    # -------------------------------------------------------------------------
    # Schema Implementations (Requests)
    # -------------------------------------------------------------------------

    async def _openai_request(
        self,
        provider: AIProvider,
        messages: list[dict],
        system_prompt: str,
        stream: bool,
        tools: list[dict] | None,
        max_tokens: int | None = None,
    ) -> dict:
        """Handle request for standard OpenAI-compatible endpoints."""
        url = f"{provider.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        headers.update(provider.custom_headers)

        formatted_messages = []
        if system_prompt:
            # Check if first message is already system
            has_system = messages and messages[0].get("role") in ("system", "developer")
            if not has_system:
                # For o1/o3 reasoning models, role can be developer or system
                is_reasoning = any(provider.model_id.lower().startswith(p) for p in ("o1", "o3", "o4"))
                role = "developer" if is_reasoning else "system"
                formatted_messages.append({"role": role, "content": system_prompt})

        formatted_messages.extend(messages)

        payload: dict[str, Any] = {
            "model": provider.model_id,
            "messages": formatted_messages,
            "stream": stream
        }

        # Handle effort level & reasoning models (o1, o3, etc.)
        is_reasoning_model = any(provider.model_id.lower().startswith(p) for p in ("o1", "o3", "o4"))
        effective_max_tokens = max_tokens if max_tokens is not None else provider.max_tokens
        if is_reasoning_model:
            payload["max_completion_tokens"] = effective_max_tokens
            effort_map = {
                EffortLevel.LOW: "low",
                EffortLevel.MEDIUM: "medium",
                EffortLevel.HIGH: "high",
                EffortLevel.EXTENDED: "high"
            }
            payload["reasoning_effort"] = effort_map.get(provider.effort_level, "medium")
            # Note: o1/o3 APIs reject temperature != 1
        else:
            payload["max_tokens"] = effective_max_tokens
            payload["temperature"] = provider.temperature

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = await self._execute_with_retry("POST", url, headers=headers, json=payload)
        data = response.json()

        choices = data.get("choices", [])
        content = ""
        tool_calls: list[dict[str, Any]] = []
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content") or ""
            tool_calls = [
                {
                    "id": item.get("id", ""),
                    "name": item.get("function", {}).get("name", ""),
                    "arguments": item.get("function", {}).get("arguments", "{}"),
                }
                for item in message.get("tool_calls", [])
            ]

        raw_usage = data.get("usage", {})
        usage = {
            "prompt_tokens": raw_usage.get("prompt_tokens", 0),
            "completion_tokens": raw_usage.get("completion_tokens", 0),
            "total_tokens": raw_usage.get("total_tokens", 0)
        }

        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": usage,
            "model": data.get("model", provider.model_id)
        }

    async def _anthropic_request(
        self,
        provider: AIProvider,
        messages: list[dict],
        system_prompt: str,
        stream: bool,
        tools: list[dict] | None,
        max_tokens: int | None = None,
    ) -> dict:
        """Handle request for Anthropic Messages API."""
        url = f"{provider.base_url.rstrip('/')}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": provider.api_key,
            "anthropic-version": "2023-06-01"
        }
        headers.update(provider.custom_headers)

        system_parts = []
        if system_prompt:
            system_parts.append(system_prompt.strip())

        filtered_messages: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("system", "developer"):
                if content:
                    system_parts.append(str(content).strip())
            elif role == "tool":
                try:
                    result = json.loads(str(content))
                except (TypeError, ValueError):
                    result = str(content)
                filtered_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": result if isinstance(result, str) else json.dumps(result, ensure_ascii=False),
                    }],
                })
            elif role == "assistant" and msg.get("tool_calls"):
                blocks: list[dict[str, Any]] = []
                if content:
                    blocks.append({"type": "text", "text": str(content)})
                for call in msg["tool_calls"]:
                    normalized_call = self._tool_call_fields(call)
                    blocks.append({
                        "type": "tool_use",
                        "id": normalized_call["id"],
                        "name": normalized_call["name"],
                        "input": normalized_call["arguments"],
                    })
                filtered_messages.append({"role": "assistant", "content": blocks})
            else:
                norm_role = "assistant" if role == "assistant" else "user"
                filtered_messages.append({"role": norm_role, "content": str(content)})

        # Merge consecutive identical roles to comply with Anthropic requirements
        merged_messages: list[dict[str, Any]] = []
        for m in filtered_messages:
            if merged_messages and merged_messages[-1]["role"] == m["role"]:
                previous_content = merged_messages[-1]["content"]
                if isinstance(previous_content, list) and isinstance(m["content"], list):
                    previous_content.extend(m["content"])
                elif isinstance(previous_content, str) and isinstance(m["content"], str):
                    merged_messages[-1]["content"] += "\n\n" + m["content"]
                else:
                    merged_messages[-1]["content"] = (
                        previous_content if isinstance(previous_content, list) else [{"type": "text", "text": previous_content}]
                    ) + (m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}])
            else:
                merged_messages.append(dict(m))

        if not merged_messages:
            merged_messages = [{"role": "user", "content": "Hello"}]
        elif merged_messages[0]["role"] != "user":
            merged_messages.insert(0, {"role": "user", "content": "Begin."})

        effective_max_tokens = max_tokens if max_tokens is not None else provider.max_tokens
        payload: dict[str, Any] = {
            "model": provider.model_id,
            "messages": merged_messages,
            "max_tokens": effective_max_tokens,
            "stream": stream
        }

        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        # Handle Anthropic extended thinking block
        if provider.effort_level in (EffortLevel.HIGH, EffortLevel.EXTENDED):
            budget = 16384 if provider.effort_level == EffortLevel.EXTENDED else 8192
            budget = min(budget, max(1024, effective_max_tokens - 1024))
            if effective_max_tokens <= budget:
                payload["max_tokens"] = budget + 1024
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": budget
            }
            # Anthropic requires temperature 1.0 when thinking is enabled
            payload["temperature"] = 1.0
        else:
            payload["temperature"] = provider.temperature

        if tools:
            payload["tools"] = [
                {
                    "name": item["function"]["name"],
                    "description": item["function"]["description"],
                    "input_schema": item["function"]["parameters"],
                }
                for item in tools
            ]

        response = await self._execute_with_retry("POST", url, headers=headers, json=payload)
        data = response.json()

        # Parse content text blocks
        content_blocks = data.get("content", [])
        text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        content = "".join(text_parts)
        tool_calls = [
            {
                "id": block.get("id", ""),
                "name": block.get("name", ""),
                "arguments": block.get("input", {}),
            }
            for block in content_blocks
            if block.get("type") == "tool_use"
        ]

        raw_usage = data.get("usage", {})
        prompt_tokens = raw_usage.get("input_tokens", 0)
        completion_tokens = raw_usage.get("output_tokens", 0)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }

        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": usage,
            "model": data.get("model", provider.model_id)
        }

    async def _google_request(
        self,
        provider: AIProvider,
        messages: list[dict],
        system_prompt: str,
        stream: bool,
        tools: list[dict] | None,
        max_tokens: int | None = None,
    ) -> dict:
        """Handle request for Google Gemini generateContent API."""
        url = f"{provider.base_url.rstrip('/')}/models/{provider.model_id}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": provider.api_key
        }
        headers.update(provider.custom_headers)

        contents: list[dict[str, Any]] = []
        sys_parts = []
        if system_prompt:
            sys_parts.append(system_prompt.strip())

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("system", "developer"):
                if content:
                    sys_parts.append(str(content).strip())
            elif role == "tool":
                try:
                    result = json.loads(str(content))
                except (TypeError, ValueError):
                    result = {"result": str(content)}
                contents.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.get("name", ""),
                            "response": result if isinstance(result, dict) else {"result": result},
                        }
                    }],
                })
            elif role == "assistant" and msg.get("tool_calls"):
                parts = [{"text": str(content)}] if content else []
                calls = msg["tool_calls"]
                if not calls and msg.get("function_call"):
                    calls = [msg["function_call"]]
                for call in calls:
                    normalized_call = self._tool_call_fields(call)
                    function_call = {
                        "name": normalized_call["name"],
                        "args": normalized_call["arguments"],
                    }
                    part = {"functionCall": function_call}
                    thought_signature = normalized_call.get("thought_signature")
                    if thought_signature:
                        part["thoughtSignature"] = thought_signature
                    parts.append(part)
                contents.append({"role": "model", "parts": parts})
            elif role == "assistant" and msg.get("function_call"):
                normalized_call = self._tool_call_fields(msg["function_call"])
                part = {
                    "functionCall": {
                        "name": normalized_call["name"],
                        "args": normalized_call["arguments"],
                    }
                }
                if normalized_call.get("thought_signature"):
                    part["thoughtSignature"] = normalized_call["thought_signature"]
                contents.append({"role": "model", "parts": [part]})
            else:
                gemini_role = "model" if role == "assistant" else "user"
                if contents and contents[-1]["role"] == gemini_role:
                    contents[-1]["parts"].append({"text": str(content)})
                else:
                    contents.append({
                        "role": gemini_role,
                        "parts": [{"text": str(content)}]
                    })

        generation_config: dict[str, Any] = {
            "temperature": provider.temperature,
            "maxOutputTokens": provider.max_tokens
        }

        # Effort level mapping for Gemini
        if provider.effort_level == EffortLevel.EXTENDED:
            generation_config["thinkingConfig"] = {"thinkingBudget": 8192}
        elif provider.effort_level == EffortLevel.HIGH:
            generation_config["thinkingConfig"] = {"thinkingBudget": 4096}
        elif provider.effort_level == EffortLevel.LOW:
            generation_config["thinkingConfig"] = {"thinkingBudget": 1024}

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config
        }

        if sys_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(sys_parts)}]
            }

        if tools:
            payload["tools"] = [{
                "functionDeclarations": [
                    {
                        "name": item["function"]["name"],
                        "description": item["function"]["description"],
                        "parameters": self._google_schema(
                            item["function"]["parameters"]
                        ),
                    }
                    for item in tools
                ]
            }]

        response = await self._execute_with_retry("POST", url, headers=headers, json=payload)
        data = response.json()

        candidates = data.get("candidates", [])
        content = ""
        tool_calls: list[dict[str, Any]] = []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts if "text" in p)
            tool_calls = [
                {
                    "id": f"google-{index}",
                    "name": part["functionCall"].get("name", ""),
                    "arguments": part["functionCall"].get("args", {}),
                    **(
                        {
                            "thought_signature": part.get("thoughtSignature")
                            or part.get("thought_signature")
                        }
                        if part.get("thoughtSignature") or part.get("thought_signature")
                        else {}
                    ),
                }
                for index, part in enumerate(parts)
                if "functionCall" in part
            ]

        meta = data.get("usageMetadata", {})
        prompt_tokens = meta.get("promptTokenCount", 0)
        completion_tokens = meta.get("candidatesTokenCount", 0)
        total_tokens = meta.get("totalTokenCount", prompt_tokens + completion_tokens)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        }

        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": usage,
            "model": data.get("modelVersion", provider.model_id)
        }

    async def _custom_request(
        self,
        provider: AIProvider,
        messages: list[dict],
        system_prompt: str,
        stream: bool,
        tools: list[dict] | None,
        max_tokens: int | None = None,
    ) -> dict:
        """Handle request for custom REST endpoints using template interpolation."""
        url = provider.base_url
        headers = {
            "Content-Type": "application/json"
        }
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        headers.update(provider.custom_headers)

        effective_max_tokens = max_tokens if max_tokens is not None else provider.max_tokens
        context: dict[str, Any] = {
            "model": provider.model_id,
            "messages": messages,
            "system_prompt": system_prompt,
            "stream": stream,
            "temperature": provider.temperature,
            "max_tokens": effective_max_tokens,
            "effort_level": provider.effort_level.value,
            "tools": tools or []
        }

        if provider.custom_payload_template:
            payload = self._interpolate_template(provider.custom_payload_template, context)
        else:
            # Fallback to standard OpenAI format
            payload = {
                "model": provider.model_id,
                "messages": [{"role": "system", "content": system_prompt}] + messages if system_prompt else messages,
                "temperature": provider.temperature,
                "max_tokens": provider.max_tokens,
                "stream": stream
            }
            if tools:
                payload["tools"] = tools

        response = await self._execute_with_retry("POST", url, headers=headers, json=payload)
        data = response.json()

        content = ""
        tool_calls: list[dict[str, Any]] = []
        # Inspect common response fields
        if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
            choice = data["choices"][0]
            if "message" in choice:
                message = choice["message"]
                content = message.get("content", "")
                tool_calls = [
                    {
                        "id": item.get("id", ""),
                        "name": item.get("function", {}).get("name", ""),
                        "arguments": item.get("function", {}).get("arguments", "{}"),
                    }
                    for item in message.get("tool_calls", [])
                ]
            elif "text" in choice:
                content = choice.get("text", "")
        elif "content" in data:
            content = str(data["content"])
        elif "response" in data:
            content = str(data["response"])
        elif "text" in data:
            content = str(data["text"])
        elif "output" in data:
            content = str(data["output"])

        raw_usage = data.get("usage", {})
        usage = {
            "prompt_tokens": raw_usage.get("prompt_tokens", 0),
            "completion_tokens": raw_usage.get("completion_tokens", 0),
            "total_tokens": raw_usage.get("total_tokens", 0)
        }

        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": usage,
            "model": data.get("model", provider.model_id)
        }

    @staticmethod
    def _interpolate_template(template: Any, context: dict[str, Any]) -> Any:
        """Recursively interpolate placeholders into payload template."""
        if isinstance(template, str):
            if template in ("{messages}", "{tools}"):
                return context.get(template[1:-1], template)
            result = template
            for k, v in context.items():
                if isinstance(v, (str, int, float, bool)):
                    result = result.replace(f"{{{k}}}", str(v))
            return result
        elif isinstance(template, dict):
            return {k: APIClient._interpolate_template(v, context) for k, v in template.items()}
        elif isinstance(template, list):
            return [APIClient._interpolate_template(elem, context) for elem in template]
        return template

    # -------------------------------------------------------------------------
    # Streaming SSE Chat Completion
    # -------------------------------------------------------------------------

    async def chat_completion_stream(
        self,
        provider: AIProvider,
        messages: list[dict],
        system_prompt: str = '',
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """SSE streaming for real-time token output.

        Yields individual tokens/chunks as they arrive from the provider.

        Args:
            provider: Target AIProvider configuration.
            messages: List of chat messages.
            system_prompt: Optional system prompt.

        Yields:
            Token strings in real time.

        Raises:
            ValueError: If provider is disabled or schema type is invalid.
            ProviderRequestError: If stream initialization or transfer fails.
        """
        if not provider.enabled:
            raise ValueError(f"Provider '{provider.id}' ({provider.name}) is disabled.")
        self._validate_provider_url(provider)

        if provider.schema_type == SchemaType.OPENAI:
            async for chunk in self._stream_openai(provider, messages, system_prompt):
                yield chunk
        elif provider.schema_type == SchemaType.ANTHROPIC:
            async for chunk in self._stream_anthropic(provider, messages, system_prompt):
                yield chunk
        elif provider.schema_type == SchemaType.GOOGLE:
            async for chunk in self._stream_google(provider, messages, system_prompt):
                yield chunk
        elif provider.schema_type == SchemaType.CUSTOM:
            async for chunk in self._stream_custom(provider, messages, system_prompt):
                yield chunk
        else:
            raise ValueError(f"Unsupported schema type for streaming: {provider.schema_type}")

    async def _stream_openai(
        self,
        provider: AIProvider,
        messages: list[dict],
        system_prompt: str
    ) -> AsyncIterator[str]:
        """Handle OpenAI SSE stream parsing data: [DONE] and data: {...}."""
        client = await self._get_client()
        url = f"{provider.base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        headers.update(provider.custom_headers)

        formatted_messages = []
        if system_prompt:
            has_system = messages and messages[0].get("role") in ("system", "developer")
            if not has_system:
                is_reasoning = any(provider.model_id.lower().startswith(p) for p in ("o1", "o3", "o4"))
                role = "developer" if is_reasoning else "system"
                formatted_messages.append({"role": role, "content": system_prompt})
        formatted_messages.extend(messages)

        payload: dict[str, Any] = {
            "model": provider.model_id,
            "messages": formatted_messages,
            "stream": True
        }

        is_reasoning_model = any(provider.model_id.lower().startswith(p) for p in ("o1", "o3", "o4"))
        if is_reasoning_model:
            payload["max_completion_tokens"] = provider.max_tokens
            effort_map = {
                EffortLevel.LOW: "low",
                EffortLevel.MEDIUM: "medium",
                EffortLevel.HIGH: "high",
                EffortLevel.EXTENDED: "high"
            }
            payload["reasoning_effort"] = effort_map.get(provider.effort_level, "medium")
        else:
            payload["max_tokens"] = provider.max_tokens
            payload["temperature"] = provider.temperature

        async with client.stream("POST", url, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                except json.JSONDecodeError:
                    continue

    async def _stream_anthropic(
        self,
        provider: AIProvider,
        messages: list[dict],
        system_prompt: str
    ) -> AsyncIterator[str]:
        """Handle Anthropic Messages SSE streaming."""
        client = await self._get_client()
        url = f"{provider.base_url.rstrip('/')}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": provider.api_key,
            "anthropic-version": "2023-06-01"
        }
        headers.update(provider.custom_headers)

        system_parts = []
        if system_prompt:
            system_parts.append(system_prompt.strip())

        filtered_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("system", "developer"):
                if content:
                    system_parts.append(str(content).strip())
            else:
                norm_role = "assistant" if role == "assistant" else "user"
                filtered_messages.append({"role": norm_role, "content": str(content)})

        merged_messages: list[dict[str, Any]] = []
        for m in filtered_messages:
            if merged_messages and merged_messages[-1]["role"] == m["role"]:
                merged_messages[-1]["content"] += "\n\n" + m["content"]
            else:
                merged_messages.append(dict(m))

        if not merged_messages:
            merged_messages = [{"role": "user", "content": "Hello"}]
        elif merged_messages[0]["role"] != "user":
            merged_messages.insert(0, {"role": "user", "content": "Begin."})

        payload: dict[str, Any] = {
            "model": provider.model_id,
            "messages": merged_messages,
            "max_tokens": provider.max_tokens,
            "stream": True
        }

        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        if provider.effort_level in (EffortLevel.HIGH, EffortLevel.EXTENDED):
            budget = 16384 if provider.effort_level == EffortLevel.EXTENDED else 8192
            budget = min(budget, max(1024, provider.max_tokens - 1024))
            if provider.max_tokens <= budget:
                payload["max_tokens"] = budget + 1024
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
            payload["temperature"] = 1.0
        else:
            payload["temperature"] = provider.temperature

        async with client.stream("POST", url, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                try:
                    event = json.loads(data_str)
                    event_type = event.get("type")
                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield text
                    elif event_type == "message_stop":
                        break
                except json.JSONDecodeError:
                    continue

    async def _stream_google(
        self,
        provider: AIProvider,
        messages: list[dict],
        system_prompt: str
    ) -> AsyncIterator[str]:
        """Handle Google Gemini streamGenerateContent with alt=sse."""
        client = await self._get_client()
        url = f"{provider.base_url.rstrip('/')}/models/{provider.model_id}:streamGenerateContent"
        params = {"alt": "sse"}
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": provider.api_key
        }
        headers.update(provider.custom_headers)

        contents: list[dict[str, Any]] = []
        sys_parts = []
        if system_prompt:
            sys_parts.append(system_prompt.strip())

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("system", "developer"):
                if content:
                    sys_parts.append(str(content).strip())
            else:
                gemini_role = "model" if role == "assistant" else "user"
                if contents and contents[-1]["role"] == gemini_role:
                    contents[-1]["parts"].append({"text": str(content)})
                else:
                    contents.append({"role": gemini_role, "parts": [{"text": str(content)}]})

        generation_config: dict[str, Any] = {
            "temperature": provider.temperature,
            "maxOutputTokens": provider.max_tokens
        }
        if provider.effort_level == EffortLevel.EXTENDED:
            generation_config["thinkingConfig"] = {"thinkingBudget": 8192}
        elif provider.effort_level == EffortLevel.HIGH:
            generation_config["thinkingConfig"] = {"thinkingBudget": 4096}
        elif provider.effort_level == EffortLevel.LOW:
            generation_config["thinkingConfig"] = {"thinkingBudget": 1024}

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config
        }
        if sys_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(sys_parts)}]}

        async with client.stream("POST", url, headers=headers, params=params, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                try:
                    chunk = json.loads(data_str)
                    candidates = chunk.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            text = part.get("text")
                            if text:
                                yield text
                except json.JSONDecodeError:
                    continue

    async def _stream_custom(
        self,
        provider: AIProvider,
        messages: list[dict],
        system_prompt: str
    ) -> AsyncIterator[str]:
        """Handle custom REST endpoint streaming."""
        client = await self._get_client()
        url = provider.base_url
        headers = {"Content-Type": "application/json"}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        headers.update(provider.custom_headers)

        context: dict[str, Any] = {
            "model": provider.model_id,
            "messages": messages,
            "system_prompt": system_prompt,
            "stream": True,
            "temperature": provider.temperature,
            "max_tokens": provider.max_tokens,
            "effort_level": provider.effort_level.value
        }

        if provider.custom_payload_template:
            payload = self._interpolate_template(provider.custom_payload_template, context)
        else:
            payload = {
                "model": provider.model_id,
                "messages": [{"role": "system", "content": system_prompt}] + messages if system_prompt else messages,
                "temperature": provider.temperature,
                "max_tokens": provider.max_tokens,
                "stream": True
            }

        async with client.stream("POST", url, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        if "choices" in chunk and chunk["choices"]:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content") or chunk["choices"][0].get("text")
                            if content:
                                yield content
                        elif "content" in chunk:
                            yield str(chunk["content"])
                        elif "text" in chunk:
                            yield str(chunk["text"])
                    except json.JSONDecodeError:
                        yield data_str
                else:
                    yield line

    # -------------------------------------------------------------------------
    # Health Testing
    # -------------------------------------------------------------------------

    async def health_check(self, provider: AIProvider) -> HealthResult:
        """Send a minimal request to verify connectivity and measure latency.

        Probes provider endpoints and records response latency, status, and metadata.

        Args:
            provider: AIProvider to test.

        Returns:
            HealthResult with status ('ok', 'error', 'timeout'), latency_ms, and details.
        """
        client = await self._get_client()
        start_time = time.perf_counter()

        try:
            self._validate_provider_url(provider)
            if provider.schema_type == SchemaType.OPENAI:
                # Try GET /models first
                models_url = f"{provider.base_url.rstrip('/')}/models"
                headers = {"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
                headers.update(provider.custom_headers)

                try:
                    resp = await client.get(models_url, headers=headers, timeout=10.0)
                    if resp.status_code == 200:
                        latency_ms = (time.perf_counter() - start_time) * 1000
                        data = resp.json()
                        models_list = data.get("data", [])
                        count = len(models_list) if isinstance(models_list, list) else "unknown"
                        return HealthResult(
                            provider_id=provider.id,
                            status="ok",
                            latency_ms=round(latency_ms, 2),
                            status_code=resp.status_code,
                            model_info=f"Active, {count} models available"
                        )
                except (httpx.RequestError, httpx.HTTPStatusError):
                    pass  # Fall through to lightweight chat test

                # Lightweight chat completion probe
                chat_url = f"{provider.base_url.rstrip('/')}/chat/completions"
                test_payload = {
                    "model": provider.model_id,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1
                }
                resp = await client.post(chat_url, headers=headers, json=test_payload, timeout=15.0)
                resp.raise_for_status()
                latency_ms = (time.perf_counter() - start_time) * 1000
                return HealthResult(
                    provider_id=provider.id,
                    status="ok",
                    latency_ms=round(latency_ms, 2),
                    status_code=resp.status_code,
                    model_info=f"Model: {provider.model_id}"
                )

            elif provider.schema_type == SchemaType.ANTHROPIC:
                headers = {
                    "x-api-key": provider.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                headers.update(provider.custom_headers)
                url = f"{provider.base_url.rstrip('/')}/messages"
                test_payload = {
                    "model": provider.model_id,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1
                }
                resp = await client.post(url, headers=headers, json=test_payload, timeout=15.0)
                resp.raise_for_status()
                latency_ms = (time.perf_counter() - start_time) * 1000
                return HealthResult(
                    provider_id=provider.id,
                    status="ok",
                    latency_ms=round(latency_ms, 2),
                    status_code=resp.status_code,
                    model_info=f"Model: {provider.model_id}"
                )

            elif provider.schema_type == SchemaType.GOOGLE:
                url = f"{provider.base_url.rstrip('/')}/models"
                headers = {"x-goog-api-key": provider.api_key}
                headers.update(provider.custom_headers)

                resp = await client.get(url, headers=headers, timeout=15.0)
                resp.raise_for_status()
                latency_ms = (time.perf_counter() - start_time) * 1000
                data = resp.json()
                models_list = data.get("models", [])
                count = len(models_list) if isinstance(models_list, list) else "unknown"
                return HealthResult(
                    provider_id=provider.id,
                    status="ok",
                    latency_ms=round(latency_ms, 2),
                    status_code=resp.status_code,
                    model_info=f"Active, {count} models available"
                )

            elif provider.schema_type == SchemaType.CUSTOM:
                headers = {}
                if provider.api_key:
                    headers["Authorization"] = f"Bearer {provider.api_key}"
                headers.update(provider.custom_headers)
                resp = await client.get(provider.base_url, headers=headers, timeout=15.0)
                latency_ms = (time.perf_counter() - start_time) * 1000
                status_str = "ok" if resp.status_code < 400 else "error"
                return HealthResult(
                    provider_id=provider.id,
                    status=status_str,
                    latency_ms=round(latency_ms, 2),
                    status_code=resp.status_code,
                    error_message=None if status_str == "ok" else f"HTTP {resp.status_code}",
                    model_info=f"Custom: {provider.model_id}"
                )

            return HealthResult(
                provider_id=provider.id,
                status="error",
                latency_ms=0.0,
                status_code=None,
                error_message=f"Unknown schema type: {provider.schema_type}"
            )

        except httpx.TimeoutException:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return HealthResult(
                provider_id=provider.id,
                status="timeout",
                latency_ms=round(latency_ms, 2),
                status_code=None,
                error_message="Connection timed out"
            )
        except httpx.HTTPStatusError as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return HealthResult(
                provider_id=provider.id,
                status="error",
                latency_ms=round(latency_ms, 2),
                status_code=exc.response.status_code,
                error_message=f"HTTP {exc.response.status_code}"
            )
        except ValueError as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return HealthResult(
                provider_id=provider.id,
                status="error",
                latency_ms=round(latency_ms, 2),
                status_code=None,
                error_message=str(exc)
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return HealthResult(
                provider_id=provider.id,
                status="error",
                latency_ms=round(latency_ms, 2),
                status_code=None,
                error_message=f"Request failed: {type(exc).__name__}"
            )

    async def health_check_all(self) -> list[HealthResult]:
        """Perform concurrent health checks of all registered providers.

        Returns:
            List of HealthResult instances for all registered providers.
        """
        if not self._providers:
            return []
        tasks = [self.health_check(provider) for provider in self._providers.values()]
        return await asyncio.gather(*tasks)

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def providers_to_dict(self) -> list[dict]:
        """Serialize all registered providers to a list of dictionaries.

        Returns:
            List of dictionaries representing providers.
        """
        result = []
        for p in self._providers.values():
            result.append({
                "id": p.id,
                "name": p.name,
                "base_url": p.base_url,
                "api_key": p.api_key,
                "model_id": p.model_id,
                "schema_type": p.schema_type.value,
                "enabled": p.enabled,
                "effort_level": p.effort_level.value,
                "max_tokens": p.max_tokens,
                "temperature": p.temperature,
                "custom_headers": p.custom_headers,
                "custom_payload_template": p.custom_payload_template
            })
        return result

    def providers_from_dict(self, data: list[dict]) -> None:
        """Populate registered providers from a list of dictionaries.

        Args:
            data: List of dictionary representations of providers.
        """
        self._providers.clear()
        active_count = 0
        for item in data:
            schema_raw = item.get("schema_type", "openai")
            effort_raw = item.get("effort_level", "medium")

            try:
                schema_type = SchemaType(schema_raw)
            except ValueError:
                schema_type = SchemaType.OPENAI

            try:
                effort_level = EffortLevel(effort_raw)
            except ValueError:
                effort_level = EffortLevel.MEDIUM

            enabled = bool(item.get("enabled", True))
            if enabled:
                if active_count >= self.MAX_ACTIVE_PROVIDERS:
                    enabled = False
                else:
                    active_count += 1

            provider = AIProvider(
                id=item["id"],
                name=item["name"],
                base_url=item["base_url"],
                api_key=item.get("api_key", ""),
                model_id=item["model_id"],
                schema_type=schema_type,
                enabled=enabled,
                effort_level=effort_level,
                max_tokens=item.get("max_tokens", 4096),
                temperature=float(item.get("temperature", 0.7)),
                custom_headers=item.get("custom_headers", {}),
                custom_payload_template=item.get("custom_payload_template")
            )
            self._providers[provider.id] = provider
        logger.debug(f"Loaded {len(self._providers)} providers from dictionary data.")
