"""
データモデル定義

工数管理エージェントで使用するデータクラスを定義
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class Project:
    """案件マスタ"""
    id: int
    name: str


@dataclass
class Category:
    """区分マスタ"""
    id: int
    name: str


@dataclass
class WorkEntry:
    """工数エントリ"""
    date: str  # YYYY/MM/DD
    project_id: int
    project_name: str
    category_id: int
    category_name: str
    percentage: int
    confidence: str  # "high" | "medium" | "low"
    reason: Optional[str] = None


@dataclass
class ProjectMatch:
    """案件マッチ結果"""
    project_id: int
    project_name: str
    confidence: str  # "high" | "medium" | "low"
    method: str  # "exact_match" | "partial_match" | "llm_select" | "llm_search"


@dataclass
class CalendarEvent:
    """カレンダーイベント"""
    title: str
    start: datetime
    end: datetime
    duration_hours: float


@dataclass
class CalendarAnalysis:
    """カレンダー分析結果"""
    entries: List[WorkEntry]
    total_percentage: int
    unaccounted_hours: float
    unaccounted_percentage: int


@dataclass
class ValidationResult:
    """検証結果"""
    valid: bool
    total_percentage: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class CommandResult:
    """コマンド生成結果"""
    success: bool
    commands: List[str]
    explanation: str
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    entries: List[WorkEntry] = field(default_factory=list)
    calendar_analysis: Optional[CalendarAnalysis] = None


@dataclass
class ErrorResponse:
    """エラーレスポンス"""
    success: bool = False
    error_type: str = ""  # "input_error" | "data_error" | "api_error" | "validation_error"
    error_message: str = ""
    suggestions: List[str] = field(default_factory=list)
    details: Optional[Dict[str, Any]] = None
