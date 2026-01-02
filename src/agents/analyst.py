"""Analyst Agent: Extracts quantitative metrics and generates charts."""

import json
from pathlib import Path
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.schemas import AnalystOutput
from src.tools.chart_gen import DataAnalyst
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_prompt() -> str:
    """Load the analyst prompt from markdown file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "04_analyst.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def agent_node(state: AgentGraphState) -> dict:
    """
    Analyst agent node: Extract metrics and generate charts.
    
    Args:
        state: Current graph state
        
    Returns:
        State update dictionary with analyst_output
    """
    logger.info("Analyst Agent: Starting quantitative analysis")
    
    try:
        research_plan = state.get("research_plan")
        pdf_documents = state.get("pdf_documents", [])
        
        if not pdf_documents:
            logger.warning("No PDF documents available for analysis")
            return {
                "analyst_output": AnalystOutput(
                    key_metrics={},
                    charts_generated=[]
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
        structured_llm = llm.with_structured_output(AnalystOutput, method="function_calling")
        
        # Combine PDF documents
        combined_docs = "\n\n--- Document Separator ---\n\n".join(pdf_documents)
        
        # Truncate if too long
        max_length = 200000
        if len(combined_docs) > max_length:
            logger.warning(f"Documents too long, truncating")
            combined_docs = combined_docs[:max_length] + "\n\n[Document truncated...]"
        
        research_plan_str = research_plan.model_dump_json(indent=2) if research_plan else "N/A"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
            ("human", """Research Plan:
{research_plan}

PDF Documents:
{pdf_documents}

Please extract quantitative metrics and identify charts to generate.""")
        ])
        
        chain = prompt | structured_llm
        
        logger.info("Extracting metrics from documents...")
        analyst_output = chain.invoke({
            "research_plan": research_plan_str,
            "pdf_documents": combined_docs
        })
        
        logger.info(f"Extracted {len(analyst_output.key_metrics)} key metrics")
        
        # Generate charts if chart data is provided in key_metrics
        chart_generator = DataAnalyst()
        charts_generated = []
        
        # Look for chart data in key_metrics (analyst might have included it)
        # For now, generate a simple chart from key metrics if possible
        if analyst_output.key_metrics:
            try:
                # Try to create a bar chart of key numeric metrics
                numeric_metrics = {
                    k: v for k, v in analyst_output.key_metrics.items()
                    if isinstance(v, (int, float))
                }
                
                if len(numeric_metrics) > 0:
                    # Create a chart with top metrics
                    chart_data = {
                        "categories": list(numeric_metrics.keys())[:10],  # Top 10
                        "values": list(numeric_metrics.values())[:10]
                    }
                    chart_path = chart_generator.generate_chart(
                        chart_data,
                        f"Key Metrics - {research_plan.target_sector if research_plan else 'Market'}"
                    )
                    if chart_path:
                        charts_generated.append(chart_path)
            except Exception as e:
                logger.warning(f"Could not generate default chart: {e}")
        
        # Update analyst_output with generated charts
        analyst_output.charts_generated = charts_generated
        
        logger.info(f"Generated {len(charts_generated)} charts")
        
        return {
            "analyst_output": analyst_output
        }
        
    except Exception as e:
        logger.error(f"Error in Analyst agent: {e}")
        return {
            "analyst_output": AnalystOutput(
                key_metrics={},
                charts_generated=[]
            )
        }

