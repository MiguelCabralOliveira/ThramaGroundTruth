"""Main execution script for the GroundTruth Real Estate Market Intelligence Agent."""

import os
import json
from pathlib import Path
from src.graph import create_graph
from src.state import AgentGraphState
from src.config import Config
from src.utils.logger import get_logger
from src.utils.pdf_compiler import PDFCompiler

logger = get_logger(__name__)


def format_report_draft(report_draft) -> str:
    """Format report draft as markdown."""
    if not report_draft:
        return "# Report Draft\n\nNo report draft available."
    
    markdown = f"""# {report_draft.executive_summary.split('\\n')[0] if report_draft.executive_summary else 'Market Intelligence Report'}
    
## Executive Summary
{report_draft.executive_summary or 'N/A'}

## Key Takeaways
{report_draft.key_takeaways or 'N/A'}

## Market Assessment
{report_draft.market_assessment or 'N/A'}

## Case Studies
{report_draft.case_studies or 'N/A'}

## Macro & Market Context
{report_draft.macro_market_context or 'N/A'}

## Market Overview
{report_draft.market_overview or 'N/A'}

## Data Analysis
{report_draft.data_analysis or 'N/A'}

## Risk Assessment
{report_draft.risk_assessment or 'N/A'}

## Conclusion
{report_draft.conclusion or 'N/A'}
"""
    return markdown


def main():
    """Main execution function."""
    # Suppress LangSmith multipart warnings globally
    import logging
    langsmith_logger = logging.getLogger("langsmith")
    langsmith_logger.setLevel(logging.ERROR)  
    
    logger.info("=" * 60)
    logger.info("GroundTruth Real Estate Market Intelligence Agent")
    logger.info("=" * 60)
    
    # Validate API keys
    missing_keys = Config.validate_required_keys()
    if missing_keys:
        logger.error(f"Missing required API keys: {', '.join(missing_keys)}")
        logger.error("Please set these in your .env file")
        return
    
    # Setup LangSmith tracing if configured
    if Config.LANGCHAIN_TRACING_V2 and Config.LANGCHAIN_TRACING_V2.lower() == "true":
        if Config.LANGCHAIN_API_KEY:
            # Validate API key format (LangSmith keys start with 'lsv2_pt_' or 'lsv2_')
            api_key = Config.LANGCHAIN_API_KEY.strip()
            if not (api_key.startswith("lsv2_pt_") or api_key.startswith("lsv2_")):
                logger.warning(f"LangSmith API key format may be incorrect. Expected format: 'lsv2_pt_...' or 'lsv2_...'")
                logger.warning("Please verify your API key at https://smith.langchain.com/settings")
            
            # Set environment variables for LangSmith
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = api_key
            os.environ["LANGCHAIN_PROJECT"] = Config.LANGCHAIN_PROJECT or "groundtruth"
            
            # Set endpoint if provided
            if Config.LANGCHAIN_ENDPOINT:
                os.environ["LANGCHAIN_ENDPOINT"] = Config.LANGCHAIN_ENDPOINT
            
            # Suppress multipart ingest errors (non-critical, LangSmith will still work)
            # These errors occur when data is too large for multipart upload
            os.environ["LANGCHAIN_SUPPRESS_MULTIPART_WARNINGS"] = "true"
            
            logger.info(f"LangSmith tracing enabled for project: {Config.LANGCHAIN_PROJECT or 'groundtruth'}")
            logger.info("Note: Multipart ingest warnings are normal and don't affect tracing functionality")
        else:
            logger.warning("LANGCHAIN_TRACING_V2 is true but LANGCHAIN_API_KEY is missing")
            logger.warning("Get your API key from: https://smith.langchain.com/settings")
    
    
    logger.info("Initializing agent graph...")
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver() 
    graph = create_graph(checkpointer=checkpointer)
    
    # User request
    user_request = "Investment analysis of the Pennsylvania, USA multi-let light industrial facilities sector"
    logger.info(f"Processing request: {user_request}")
    logger.info("-" * 60)
    
    # Initialize state
    initial_state: AgentGraphState = {
        "user_request": user_request,
        "enhanced_request": None,
        "research_plan": None,
        "pdf_documents": [],
        "source_documents": [],
        "analyst_output": None,
        "qualitative_research": "",
        "report_draft": None,
        "review_feedback": None,
        "revision_count": 0
    }
    
    # Run graph with streaming
    try:
        logger.info("Starting agent workflow...")
        
        
        config = {
            "configurable": {"thread_id": "1"},
            "recursion_limit": 10 
        }
        
        # Stream events
        final_state = None
        for event in graph.stream(initial_state, config=config):
            # Log each node completion
            for node_name, node_output in event.items():
                logger.info(f"✓ {node_name.upper()} completed")
                
                # Update final state
                if final_state is None:
                    final_state = node_output
                else:
                    final_state.update(node_output)
        
        logger.info("-" * 60)
        logger.info("Workflow completed!")
        
        # Check final state
        if final_state is None:
            logger.error("No final state returned")
            return
        
        # Display results
        report_draft = final_state.get("report_draft")
        review_feedback = final_state.get("review_feedback")
        
        if report_draft:
            logger.info("Report draft generated successfully")
            
            # Save report
            output_dir = Path("outputs/reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_compiler = PDFCompiler()
            
            # Prepare data for HTML compiler
            report_data = report_draft.model_dump()
            analyst_output = final_state.get("analyst_output")
            charts = analyst_output.charts_generated if analyst_output else []
            
            # Prepare section groups based on boolean toggles
            main_sections = []
            annex_sections = []
            
            for section_id, is_main in Config.REPORT_SECTIONS.items():
                if not report_data.get(section_id):
                    continue
                    
                section_info = {"id": section_id, "title": Config.SECTION_METADATA.get(section_id, section_id)}
                if is_main:
                    main_sections.append(section_info)
                else:
                    annex_sections.append(section_info)
            
            # Add bibliography to conclusion if it exists
            if "conclusion" in report_data and report_data["conclusion"]:
                if not any(s["id"] == "conclusion" for s in main_sections + annex_sections):
                    main_sections.append({"id": "conclusion", "title": Config.SECTION_METADATA.get("conclusion", "Conclusion")})
            
            report_path = pdf_compiler.compile_report_to_pdf(
                report_data,
                charts,
                user_request,
                "final_report",
                main_sections=main_sections,
                annex_sections=annex_sections
            )
            
            if report_path:
                logger.info(f"Report saved to: {report_path}")
            
            # Display approval status
            if review_feedback:
                if review_feedback.approved:
                    logger.info("✓ Report APPROVED by Auditor")
                else:
                    logger.warning("✗ Report REJECTED by Auditor")
                    logger.info(f"Feedback: {review_feedback.feedback[:200]}...")
                    logger.info(f"Revision count: {final_state.get('revision_count', 0)}")
        else:
            logger.error("No report draft was generated")
            
    except Exception as e:
        logger.error(f"Error during workflow execution: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()

