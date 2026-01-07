"""Strategist Agent: Converts user request to structured research plan."""

import os
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.schemas import ResearchPlan
from src.config import Config
from src.utils.logger import get_logger, save_agent_io

logger = get_logger(__name__)


def load_prompt() -> str:
    """Load the strategist prompt and global instructions."""
    base_path = Path(__file__).parent.parent / "prompts"
    
    # Load global instructions
    global_path = base_path / "global_instructions.md"
    global_instr = ""
    if global_path.exists():
        with open(global_path, "r", encoding="utf-8") as f:
            global_instr = f.read() + "\n\n"
            
    # Load strategist prompt
    prompt_path = base_path / "01_strategist.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return global_instr + f.read()


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
            model=Config.AGENT_MODELS["strategist"],
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
        
        # Get current date
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Invoke chain
        request_to_process = state.get("enhanced_request") or state.get("user_request")
        log_preview = request_to_process[:100] + "..." if len(request_to_process) > 100 else request_to_process
        logger.info(f"Processing request: {log_preview}")
        research_plan = chain.invoke({
            "user_request": request_to_process,
            "current_date": current_date
        })
        
        logger.info(f"Research plan generated: {research_plan.target_sector} in {research_plan.geography}")
        
        result = {
            "research_plan": research_plan
        }
        
        save_agent_io("Strategist", state, research_plan.model_dump())
        return result
        
    except Exception as e:
        logger.error(f"Error in Strategist agent: {e}")
        # Return empty research plan on error
        return {
            "research_plan": None
        }

