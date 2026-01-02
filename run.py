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

{report_draft.executive_summary}

## Key Takeaways

{report_draft.key_takeaways}

## Investment Thesis

{report_draft.investment_thesis}

## Go/No-Go Scorecard

{report_draft.go_no_go_scorecard}

## Macro & Market Context

{report_draft.macro_market_context}

## Market Overview

{report_draft.market_overview}

## Data Analysis

{report_draft.data_analysis}

## Risk Assessment

{report_draft.risk_assessment}

## Conclusion

{report_draft.conclusion}
"""
    return markdown


def main():
    """Main execution function."""
    # Suppress LangSmith multipart warnings globally
    import logging
    langsmith_logger = logging.getLogger("langsmith")
    langsmith_logger.setLevel(logging.ERROR)  # Only show errors, suppress warnings
    
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
    
    # Create graph
    logger.info("Initializing agent graph...")
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()  # Required for LangGraph Studio
    graph = create_graph(checkpointer=checkpointer)
    
    # User request (hardcoded example as specified)
    user_request = "Analyze the Uk multitenant light industry facilities markets for renting"
    
    logger.info(f"Processing request: {user_request}")
    logger.info("-" * 60)
    
    # Initialize state
    initial_state: AgentGraphState = {
        "user_request": user_request,
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
        
        # Config for checkpointer (required when using MemorySaver)
        # Also set recursion limit to prevent infinite loops
        config = {
            "configurable": {"thread_id": "1"},
            "recursion_limit": 50  # Maximum number of graph steps
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
            
            report_path = pdf_compiler.compile_report_to_pdf(
                report_data,
                charts,
                user_request,
                "final_report"
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

