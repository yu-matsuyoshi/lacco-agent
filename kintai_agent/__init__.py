"""
Kintai Agent - 工数管理エージェント

OA Lacco APPへの工数入力を自然言語化するAIエージェント
"""

__version__ = "0.1.0"

from .models import (
    Project,
    Category,
    WorkEntry,
    ProjectMatch,
    CalendarEvent,
    CalendarAnalysis,
    ValidationResult,
    CommandResult,
    ErrorResponse,
)
from .data_loader import DataLoader
from .agent import KintaiAgent
from .command_generator import CommandGenerator

__all__ = [
    "Project",
    "Category",
    "WorkEntry",
    "ProjectMatch",
    "CalendarEvent",
    "CalendarAnalysis",
    "ValidationResult",
    "CommandResult",
    "ErrorResponse",
    "DataLoader",
    "KintaiAgent",
    "CommandGenerator",
]
