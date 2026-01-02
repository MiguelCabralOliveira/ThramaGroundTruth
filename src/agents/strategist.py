"""Strategist Agent: Converts user request to structured research plan."""

import os
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.schemas import ResearchPlan
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_prompt() -> str:
    """Load the strategist prompt from markdown file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "01_strategist.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def agent_node(state: AgentGraphState) -> dict:
    """
    Strategist agent node: Convert user request to ResearchPlan.
    
    Args:
        state: Current graph state
        
    Returns:
        State update dictionary with research_plan
    """
    logger.info("Strategist Agent: Starting research plan generation")
    
    try:
        # Load prompt
        prompt_template = load_prompt()
        
        # Initialize LLM with structured output
        llm = ChatOpenAI(
            model=Config.OPENAI_MODEL,
            temperature=0.3,
            api_key=Config.OPENAI_API_KEY
        )
        
        # Use with_structured_output instead of PydanticOutputParser to avoid template variable conflicts
        structured_llm = llm.with_structured_output(ResearchPlan)
        
        # Create chat prompt (no need for format instructions with with_structured_output)
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
            ("human", "User Request: {user_request}")
        ])
        
        # Create chain
        chain = prompt | structured_llm
        
        # Invoke chain
        logger.info(f"Processing user request: {state['user_request']}")
        research_plan = chain.invoke({"user_request": state["user_request"]})
        
        logger.info(f"Research plan generated: {research_plan.target_sector} in {research_plan.geography}")
        
        return {
            "research_plan": research_plan
        }
        
    except Exception as e:
        logger.error(f"Error in Strategist agent: {e}")
        # Return empty research plan on error
        return {
            "research_plan": None
        }

