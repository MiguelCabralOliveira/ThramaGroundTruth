"""LangGraph orchestration for the GroundTruth agent workflow."""

from typing import Literal, Optional, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.state import AgentGraphState
from src.agents.strategist import agent_node as strategist_node
from src.agents.scout import agent_node as scout_node
from src.agents.researcher import agent_node as researcher_node
from src.agents.analyst import agent_node as analyst_node
from src.agents.writer import agent_node as writer_node
from src.agents.auditor import agent_node as auditor_node
from src.utils.logger import get_logger

logger = get_logger(__name__)


def should_continue(state: AgentGraphState) -> Literal["writer", "end"]:
    """
    Conditional edge function: determine if report should be revised or finished.
    
    Args:
        state: Current graph state
        
    Returns:
        "writer" if report needs revision, "end" if approved
    """
    review_feedback = state.get("review_feedback")
    revision_count = state.get("revision_count", 0)
    
    # Limit revisions to prevent infinite loops
    max_revisions = 3
    if revision_count >= max_revisions:
        logger.warning(f"Maximum revisions ({max_revisions}) reached. Ending workflow.")
        return "end"
    
    if not review_feedback:
        logger.warning("No review feedback found, ending workflow")
        return "end"
    
    if review_feedback.approved:
        logger.info("Report approved! Ending workflow.")
        return "end"
    else:
        logger.info(f"Report rejected (revision {revision_count + 1}/{max_revisions}). Sending back to writer for revision.")
        return "writer"


def create_graph(checkpointer: Optional[MemorySaver] = None) -> Any:
    """
    Create and compile the LangGraph workflow.
    
    Args:
        checkpointer: Optional checkpointer for state persistence (required for LangGraph Studio)
    
    Returns:
        Compiled LangGraph
    """
    logger.info("Creating agent graph...")
    
    # Create StateGraph
    workflow = StateGraph(AgentGraphState)
    
    # Add nodes
    workflow.add_node("strategist", strategist_node)
    workflow.add_node("scout", scout_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("auditor", auditor_node)
    
    # Set entry point
    workflow.set_entry_point("strategist")
    
    # Define edges
    workflow.add_edge("strategist", "scout")
    workflow.add_edge("scout", "researcher")
    workflow.add_edge("scout", "analyst")  # Parallel execution
    workflow.add_edge("researcher", "writer")
    workflow.add_edge("analyst", "writer")
    workflow.add_edge("writer", "auditor")
    
    # Conditional edge after auditor
    workflow.add_conditional_edges(
        "auditor",
        should_continue,
        {
            "writer": "writer",
            "end": END
        }
    )
    
    # Compile graph with optional checkpointer
    # Checkpointer is required for LangGraph Studio
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    graph = workflow.compile(checkpointer=checkpointer)
    
    logger.info("Graph compiled successfully")
    return graph


# Export the graph creation function
__all__ = ["create_graph"]

