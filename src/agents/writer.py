"""Writer Agent: Generates the final report draft."""

from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.schemas import ReportDraft
from src.config import Config
from src.tools.database import VectorDatabase
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_prompt() -> str:
    """Load the writer prompt from markdown file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "05_writer.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def format_source_references(source_documents: list) -> str:
    """Format source documents as a numbered reference list for citations."""
    if not source_documents:
        return ""
    
    references = ["## Available Source References\n"]
    references.append("**CRITICAL**: You MUST cite sources using the format [N • Source Type] for every claim, statistic, or data point.\n")
    references.append("Format: [N • Source Type] where N is the number below and Source Type is the type shown.\n\n")
    
    for i, doc in enumerate(source_documents, 1):
        metadata = doc.get("metadata", {})
        
        # Extract source name - try multiple fields
        source_name = (
            metadata.get("source_title") or 
            metadata.get("source") or 
            metadata.get("title") or 
            "Unknown Source"
        )
        
        # Extract source type - try multiple fields and normalize
        source_type = (
            metadata.get("source_type") or 
            metadata.get("type") or 
            "Document"
        )
        
        # Normalize source type to common formats
        type_mapping = {
            "market_report": "Market Report",
            "expert_call": "Expert Call",
            "analyst_research": "Analyst Research",
            "transcript": "Transcript",
            "ars": "ARS",
            "document": "Document"
        }
        source_type = type_mapping.get(source_type.lower(), source_type.title())
        
        # Clean up source name - extract filename without path
        if "/" in source_name:
            source_name = source_name.split("/")[-1]
        if "\\" in source_name:
            source_name = source_name.split("\\")[-1]
        # Remove file extension if present
        if source_name.endswith(".pdf"):
            source_name = source_name[:-4]
        
        # Get text preview
        text_preview = doc.get("text", metadata.get("text", ""))[:200]
        
        references.append(f"[{i}] {source_name} • {source_type}")
        if text_preview:
            references.append(f"    Preview: {text_preview}...")
        references.append("")  # Empty line between sources
    
    return "\n".join(references)


def agent_node(state: AgentGraphState) -> dict:
    """
    Writer agent node: Generate comprehensive report draft.
    
    Args:
        state: Current graph state
        
    Returns:
        State update dictionary with report_draft
    """
    logger.info("Writer Agent: Starting report generation")
    
    try:
        research_plan = state.get("research_plan")
        qualitative_research = state.get("qualitative_research", "")
        analyst_output = state.get("analyst_output")
        source_documents = state.get("source_documents", [])
        revision_count = state.get("revision_count", 0)
        review_feedback = state.get("review_feedback")
        
        # Check if this is a revision (has feedback from auditor)
        is_revision = review_feedback is not None
        if is_revision:
            revision_count += 1
            logger.info(f"Revision {revision_count}: Incorporating feedback")
        
        # Load prompt
        prompt_template = load_prompt()
        
        # Initialize LLM with structured output
        llm = ChatOpenAI(
            model=Config.OPENAI_MODEL,
            temperature=0.4,
            api_key=Config.OPENAI_API_KEY
        )
        
        # Use with_structured_output instead of PydanticOutputParser to avoid template variable conflicts
        structured_llm = llm.with_structured_output(ReportDraft)
        
        # Prepare inputs
        research_plan_str = research_plan.model_dump_json(indent=2) if research_plan else "N/A"
        analyst_output_str = analyst_output.model_dump_json(indent=2) if analyst_output else "N/A"
        
        # If source_documents is empty or insufficient, query Pinecone directly
        if not source_documents or len(source_documents) < 3:
            logger.info("Source documents empty or insufficient, querying Pinecone for additional sources")
            try:
                vector_db = VectorDatabase()
                if vector_db.index and research_plan:
                    # Build comprehensive search queries
                    search_queries = [
                        f"{research_plan.target_sector} {research_plan.geography} market overview",
                        f"{research_plan.target_sector} investment yields returns",
                        f"{research_plan.target_sector} supply demand trends",
                        f"{research_plan.target_sector} risks regulations",
                        f"{research_plan.target_sector} market analysis"
                    ]
                    
                    additional_sources = []
                    for query in search_queries:
                        results = vector_db.search_similar(query, top_k=2)
                        for result in results:
                            # Check if not already in source_documents
                            if not any(
                                r.get("id") == result.get("id") or 
                                r.get("metadata", {}).get("source") == result.get("metadata", {}).get("source")
                                for r in source_documents
                            ):
                                additional_sources.append(result)
                    
                    if additional_sources:
                        source_documents.extend(additional_sources)
                        logger.info(f"Added {len(additional_sources)} additional sources from Pinecone")
            except Exception as e:
                logger.warning(f"Failed to query Pinecone for additional sources: {e}")
        
        # Format source documents as numbered reference list
        source_references = format_source_references(source_documents)
        logger.info(f"Formatted {len(source_documents)} source documents for citations")
        
        # Add feedback if this is a revision
        feedback_context = ""
        if is_revision and review_feedback:
            feedback_context = f"\n\nPrevious Review Feedback (Revision {revision_count}):\n{review_feedback.feedback}\nMissing Data: {', '.join(review_feedback.missing_data) if review_feedback.missing_data else 'None'}"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
            ("human", """Research Plan:
{research_plan}

Qualitative Research:
{qualitative_research}

Quantitative Analysis:
{analyst_output}

{source_references}
{feedback_context}

**CRITICAL INSTRUCTIONS FOR CITATIONS:**
1. You MUST include inline citations using the format [N • Source Type] for EVERY key claim, statistic, or data point
2. Use the numbered references provided above - each source has a number [N] and a Source Type
3. Place citations immediately after the relevant statement
4. Multiple citations for the same claim: [1 • Market Report] [3 • Expert Call]
5. Examples of what to cite:
   - All numerical data and statistics
   - Market trends and forecasts
   - Regulatory information
   - Investment yields and returns
   - Supply/demand figures
   - Risk factors and assessments

Please write the comprehensive market intelligence report as specified in your instructions. Remember: Every claim needs a citation!""")
        ])
        
        chain = prompt | structured_llm
        
        logger.info("Generating report draft...")
        report_draft = chain.invoke({
            "research_plan": research_plan_str,
            "qualitative_research": qualitative_research,
            "analyst_output": analyst_output_str,
            "source_references": source_references,
            "feedback_context": feedback_context
        })
        
        logger.info("Report draft generated successfully")
        
        return {
            "report_draft": report_draft,
            "revision_count": revision_count
        }
        
    except Exception as e:
        logger.error(f"Error in Writer agent: {e}")
        return {
            "report_draft": None
        }

