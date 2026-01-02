"""Auditor Agent: Reviews and critiques the report draft."""

from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.schemas import ReviewCritique
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_prompt() -> str:
    """Load the auditor prompt from markdown file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "06_auditor.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


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
            model=Config.OPENAI_MODEL,
            temperature=0.2,
            api_key=Config.OPENAI_API_KEY
        )
        
        # Use with_structured_output instead of PydanticOutputParser to avoid template variable conflicts
        structured_llm = llm.with_structured_output(ReviewCritique, method="function_calling")
        
        # Prepare inputs
        research_plan_str = research_plan.model_dump_json(indent=2) if research_plan else "N/A"
        report_draft_str = report_draft.model_dump_json(indent=2) if report_draft else "N/A"
        analyst_output_str = analyst_output.model_dump_json(indent=2) if analyst_output else "N/A"
        
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
        
        return {
            "review_feedback": review_feedback
        }
        
    except Exception as e:
        logger.error(f"Error in Auditor agent: {e}")
        return {
            "review_feedback": ReviewCritique(
                approved=False,
                feedback=f"Error during review: {str(e)}",
                missing_data=[]
            )
        }

