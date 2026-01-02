"""State definition for the LangGraph agent workflow."""

from typing import List, Optional, TypedDict
from src.schemas import AnalystOutput, ReportDraft, ResearchPlan, ReviewCritique


class AgentGraphState(TypedDict):
    """State structure for the GroundTruth agent graph."""
    
    user_request: str
    research_plan: Optional[ResearchPlan]
    pdf_documents: List[str]  # Parsed text content from PDFs
    source_documents: List[dict]  # RAG chunks with metadata: {text, source_url, source_title}
    analyst_output: Optional[AnalystOutput]
    qualitative_research: str
    report_draft: Optional[ReportDraft]
    review_feedback: Optional[ReviewCritique]
    revision_count: int

