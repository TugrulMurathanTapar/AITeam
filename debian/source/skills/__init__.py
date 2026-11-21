"""
Skills module for Multi-AI Orchestrator.

Exports the BaseSkill interface along with all production skills:
TerminalSkill, FileIOSkill, WebSearchSkill, and CodeAnalysisSkill.
"""

from core.skill_manager import BaseSkill
from skills.code_analysis import CodeAnalysisSkill
from skills.file_io import FileIOSkill
from skills.terminal import TerminalSkill
from skills.web_search import WebSearchSkill

__all__ = [
    "BaseSkill",
    "TerminalSkill",
    "FileIOSkill",
    "WebSearchSkill",
    "CodeAnalysisSkill",
]
