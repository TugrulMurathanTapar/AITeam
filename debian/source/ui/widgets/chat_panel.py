"""Chat panel widget for rendering message streams and bubbles."""

from __future__ import annotations

from typing import Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual.containers import ScrollableContainer
from textual.widgets import Static

from ui.i18n import t


class ChatPanel(ScrollableContainer):
    """Scrollable chat message stream with styled message bubbles."""

    DEFAULT_CSS = """
    ChatPanel {
        height: 1fr;
        scrollbar-gutter: stable;
        padding: 1;
    }
    .chat-msg-user {
        margin: 1 0 1 4;
        align-horizontal: right;
    }
    .chat-msg-assistant {
        margin: 1 4 1 0;
        align-horizontal: left;
    }
    .chat-msg-error {
        margin: 1 2;
    }
    """

    def __init__(self, *children, **kwargs):
        super().__init__(*children, **kwargs)
        self._welcome_message: Static | None = None

    def add_message(
        self,
        role: str,
        content: str,
        model_name: Optional[str] = None,
    ) -> None:
        """Add a styled message bubble to the chat stream.

        Args:
            role: 'user', 'assistant', 'error', or 'system'.
            content: Text or Markdown message content.
            model_name: Optional badge name for the responding model.
        """
        css_class = "chat-msg-assistant"

        if role == "user":
            user_title = t("role_user")
            renderable = Panel(
                Text(content, style="bright_white"),
                title=f"👤 {user_title}",
                border_style="bright_magenta",
                expand=False,
            )
            css_class = "chat-msg-user"
        elif role == "assistant":
            title = model_name or t("role_assistant")
            renderable = Panel(
                Markdown(content),
                title=f"🤖 {title}",
                border_style="bright_cyan",
                expand=True,
            )
            css_class = "chat-msg-assistant"
        elif role == "error":
            error_title = t("error") if t("error") != "error" else "Error"
            renderable = Panel(
                Text(content, style="bold red"),
                title=f"⚠ {error_title}",
                border_style="red",
                expand=True,
            )
            css_class = "chat-msg-error"
        else:
            # System / Info
            renderable = Panel(
                Text(content, style="italic yellow"),
                title=f"ℹ {t('role_system')}",
                border_style="yellow",
                expand=True,
            )
            css_class = "chat-msg-system"

        msg_widget = Static(renderable, classes=css_class)
        self.mount(msg_widget)
        if role == "system" and self._welcome_message is None:
            self._welcome_message = msg_widget
        self.scroll_end(animate=False)

    def update_welcome_message(self, content: str) -> None:
        """Refresh the localized welcome message without clearing chat history."""
        if self._welcome_message is None or not self._welcome_message.is_attached:
            return
        self._welcome_message.update(
            Panel(
                Text(content, style="italic yellow"),
                title=f"ℹ {t('role_system')}",
                border_style="yellow",
                expand=True,
            )
        )

    def clear_messages(self) -> None:
        """Remove all messages from the chat stream."""
        self._welcome_message = None
        self.remove_children()
