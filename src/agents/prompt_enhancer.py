"""Prompt Enhancer Agent: Refines user requests for better research outcomes."""

from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_prompt() -> str:
    """Load the prompt enhancer prompt from markdown file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "00_prompt_enhancer.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def agent_node(state: AgentGraphState) -> dict:
    """
    Prompt Enhancer agent node: Refine user request.
    
    Args:
        state: Current graph state
        
    Returns:
        State update dictionary with enhanced_request
    """
    logger.info("Prompt Enhancer Agent: Refining user request")
    
    try:
        user_request = state.get("user_request")
        
        # Load prompt
        prompt_template = load_prompt()
        
        # Initialize LLM
        llm = ChatOpenAI(
            model=Config.AGENT_MODELS["prompt_enhancer"],
            temperature=0.3,
            api_key=Config.OPENAI_API_KEY
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
            ("human", "User Request: {user_request}")
        ])
        
        # Create chain
        chain = prompt | llm
        
        # Get current date
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"Enhancing request: {user_request}")
        response = chain.invoke({
            "user_request": user_request,
            "current_date": current_date
        })
        
        enhanced_request = response.content
        logger.info(f"Enhanced request: {enhanced_request}")
        
        return {
            "enhanced_request": enhanced_request
        }
        
    except Exception as e:
        logger.error(f"Error in Prompt Enhancer agent: {e}")
        # Fallback to original request if enhancement fails
        return {
            "enhanced_request": state.get("user_request")
        }
