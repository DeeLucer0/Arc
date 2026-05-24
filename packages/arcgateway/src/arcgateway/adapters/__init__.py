"""Platform adapter package.

Platform-specific adapters (Telegram, Slack, Discord, etc.) are implemented
in T1.7. This package exports the base Protocol, reconnect state, and the
in-process adapter shim.

Usage::

    from arcgateway.adapters.base import BasePlatformAdapter
    from arcgateway.adapters._reconnect import FailedAdapter
"""

from arcgateway.adapters._reconnect import FailedAdapter
from arcgateway.adapters.base import BasePlatformAdapter
from arcgateway.adapters.in_process import DeltaStream, PythonAdapter

__all__ = ["BasePlatformAdapter", "DeltaStream", "FailedAdapter", "PythonAdapter"]
