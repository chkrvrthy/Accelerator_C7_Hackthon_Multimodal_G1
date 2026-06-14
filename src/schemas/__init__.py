"""Schema package — re-exports the public Pydantic models.

Why this file exists:
    Every cross-module data shape lives in ``src/schemas/outputs.py``. Re-
    exporting them here means the rest of the code says
    ``from src.schemas import DesignReport`` instead of repeating the long
    submodule path. One import line, less typing, easier refactors.
"""

from .outputs import (
    AccessibilityReport,
    BrandConsistency,
    CompetitorRef,
    DesignReport,
    Finding,
    GraphState,
    MarketResearch,
    Recommendation,
    RetrievedRef,
    SearchResult,
    Severity,
    UXCritique,
    VisualAnalysis,
    WCAGFinding,
)

__all__ = [
    "AccessibilityReport",
    "BrandConsistency",
    "CompetitorRef",
    "DesignReport",
    "Finding",
    "GraphState",
    "MarketResearch",
    "Recommendation",
    "RetrievedRef",
    "SearchResult",
    "Severity",
    "UXCritique",
    "VisualAnalysis",
    "WCAGFinding",
]
