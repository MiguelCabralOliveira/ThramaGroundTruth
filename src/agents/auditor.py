"""Auditor Agent: Reviews and critiques the report draft."""

from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.schemas import ReviewCritique
from src.config import Config
from src.utils.logger import get_logger, save_agent_io
from src.utils.toon_serializer import pydantic_to_toon

logger = get_logger(__name__)


def load_prompt() -> str:
    """Load the auditor prompt and global instructions."""
    base_path = Path(__file__).parent.parent / "prompts"
    
    # Load global instructions
    global_path = base_path / "global_instructions.md"
    global_instr = ""
    if global_path.exists():
        with open(global_path, "r", encoding="utf-8") as f:
            global_instr = f.read() + "\n\n"
            
    # Load auditor prompt
    prompt_path = base_path / "06_auditor.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return global_instr + f.read()


def agent_node(state: AgentGraphState) -> dict:
    """
    Auditor agent node: Review and critique the report draft.
    
    Args:
        state: Current graph state
        
    Returns:
        State update dictionary with review_feedback
    """
    logger.info("Auditor Agent: Starting report review")
    
    try:
        research_plan = state.get("research_plan")
        report_draft = state.get("report_draft")
        qualitative_research = state.get("qualitative_research", "")
        analyst_output = state.get("analyst_output")
        pdf_documents = state.get("pdf_documents", [])
        
        if not report_draft:
            logger.error("No report draft to review")
            return {
                "review_feedback": ReviewCritique(
                    approved=False,
                    feedback="No report draft available for review.",
                    missing_data=["Report draft"]
                )
            }
        
        # Load prompt
        prompt_template = load_prompt()
        
        # Initialize LLM with structured output
        llm = ChatOpenAI(
            model=Config.AGENT_MODELS["auditor"],
            temperature=0.2,
            api_key=Config.OPENAI_API_KEY
        )
        
        # Use with_structured_output instead of PydanticOutputParser to avoid template variable conflicts
        structured_llm = llm.with_structured_output(ReviewCritique, method="function_calling")
        
        # Prepare inputs (using TOON for token efficiency)
        research_plan_str = pydantic_to_toon(research_plan) if research_plan else "N/A"
        report_draft_str = pydantic_to_toon(report_draft) if report_draft else "N/A"
        analyst_output_str = pydantic_to_toon(analyst_output) if analyst_output else "N/A"
        
        # Truncate PDF documents for reference (don't send full content)
        pdf_summary = f"{len(pdf_documents)} documents available for reference"
        if pdf_documents:
            pdf_summary += f" (first document preview: {pdf_documents[0][:500]}...)"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
            ("human", """Research Plan:
{research_plan}

Report Draft:
{report_draft}

Qualitative Research:
{qualitative_research}

Quantitative Analysis:
{analyst_output}

Source Documents:
{pdf_documents}

Please review the report and provide your critique as specified in your instructions.""")
        ])
        
        chain = prompt | structured_llm
        
        logger.info("Reviewing report draft...")
        review_feedback = chain.invoke({
            "research_plan": research_plan_str,
            "report_draft": report_draft_str,
            "qualitative_research": qualitative_research[:2000] if qualitative_research else "N/A",  # Truncate for context
            "analyst_output": analyst_output_str,
            "pdf_documents": pdf_summary
        })
        
        status = "APPROVED" if review_feedback.approved else "REJECTED"
        logger.info(f"Report review complete: {status}")
        if not review_feedback.approved:
            logger.info(f"Feedback: {review_feedback.feedback[:200]}...")
            logger.info(f"Missing data: {review_feedback.missing_data}")
        
        result = {
            "review_feedback": review_feedback
        }
        
        save_agent_io("Auditor", state, review_feedback.model_dump())
        return result
        
    except Exception as e:
        logger.error(f"Error in Auditor agent: {e}")
        return {
            "review_feedback": ReviewCritique(
                approved=False,
                feedback=f"Error during review: {str(e)}",
                missing_data=[]
            )
        }

