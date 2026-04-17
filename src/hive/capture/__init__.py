"""Capture adapters for ingesting AI sessions from various sources."""

from hive.capture.base import CaptureAdapter
from hive.capture.claude_code import ClaudeCodeAdapter
from hive.capture.git_hook import GitCommitHook

__all__ = ["CaptureAdapter", "ClaudeCodeAdapter", "GitCommitHook"]
