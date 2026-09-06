"""ChatGPT/Grok-native DCM host API.

from dcm.chat import HostSession
session = HostSession.prepare(...)
"""

from dcm.chat.session import HostSession, doctor

__all__ = ["HostSession", "doctor"]
