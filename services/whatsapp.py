"""
WhatsApp service (future).

Planned approach:
- use Selenium WebDriver to automate WhatsApp Web
- authenticate once, persist session/cookies
- expose a small API for sending messages

This module is a stub in V1.
"""

from __future__ import annotations


class WhatsAppClient:
    """Placeholder for a future Selenium-backed WhatsApp client."""

    def send_message(self, *_: object, **__: object) -> None:
        raise NotImplementedError("WhatsApp messaging is not implemented in V1.")

