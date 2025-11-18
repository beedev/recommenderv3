"""
Centralized State Management Package

Provides state transition logic for S1→SN configurator flow.
All state-related functionality is consolidated here.
"""

from .state_manager import StateManager, get_state_manager

__all__ = [
    "StateManager",
    "get_state_manager",
]
