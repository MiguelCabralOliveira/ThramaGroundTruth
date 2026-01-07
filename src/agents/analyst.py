"""Analyst Agent: Extracts quantitative metrics and generates text-based analysis."""

import json
from pathlib import Path
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.schemas import AnalystOutput
from src.config import Config
from src.utils.logger import get_logger
from src.utils.toon_serializer import pydantic_to_toon, dict_to_toon
from src.tools.database import VectorDatabase
from src.utils.logger import save_agent_io

logger = get_logger(__name__)


def load_prompt() -> str:
    """Load the analyst prompt from markdown file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "04_analyst.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def agent_node(state: AgentGraphState) -> dict:
    """
    Analyst agent node: Extract metrics and provide quantitative analysis.
    
    Args:
        state: Current graph state
        
    Returns:
        State update dictionary with analyst_output
    """
    logger.info("Analyst Agent: Starting quantitative analysis")
    
    try:
        research_plan = state.get("research_plan")
        pdf_documents = state.get("pdf_documents", [])
        pdf_urls = state.get("pdf_urls", [])
        
        # Step 1: Try structured extraction with LlamaExtract
        extracted_metrics = {}
        # LlamaExtract disabled to avoid API limits - relying on LLM extraction below
        # if pdf_urls:
        #     try:
        #         from src.tools.llama_extract import MetricsExtractor
        #         extractor = MetricsExtractor()
        #         logger.info(f"Attempting LlamaExtract on {len(pdf_urls)} URLs")
        #         extracted_metrics = extractor.extract_metrics(pdf_urls)
        #         if extracted_metrics:
        #             logger.info(f"LlamaExtract success: {len(extracted_metrics)} metric categories found")
        #     except Exception as e:
        #         logger.warning(f"LlamaExtract failed, falling back to LLM parsing: {e}")

        if not pdf_documents and not extracted_metrics:
            logger.warning("No PDF documents or extracted metrics available for analysis")
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
            model=Config.AGENT_MODELS["analyst"],
            temperature=0.2,
            api_key=Config.OPENAI_API_KEY
        )
        
        # Use with_structured_output instead of PydanticOutputParser to avoid template variable conflicts
        structured_llm = llm.with_structured_output(AnalystOutput, method="function_calling")
        
        # Prepare inputs (using TOON for token efficiency)
        research_plan_str = pydantic_to_toon(research_plan) if research_plan else "N/A"
        extracted_metrics_str = dict_to_toon(extracted_metrics) if extracted_metrics else "None"
        
        # Try to use RAG from Pinecone for quantitative data
        source_documents = []
        try:
            vector_db = VectorDatabase()
            if vector_db.index and research_plan:
                # Build "Open RAG" quantitative-focused search queries
                search_queries = [
                    f"Quantitative data and key metrics for {research_plan.target_sector} in {research_plan.geography}",
                    f"Market statistics table rents yields vacancy {research_plan.target_sector} {research_plan.geography}",
                    f"Financial performance benchmarks and transaction volumes {research_plan.target_sector}",
                    f"Numerical market outlook and forecasts 2025 2026 {research_plan.target_sector}",
                    f"Investment returns statistics capital values prime secondary yields",
                    f"Comprehensive market data report PDF statistics {research_plan.target_sector}"
                ]
                
                logger.info("Querying Pinecone for quantitative context (Open RAG strategy)...")
                
                source_counts = {}
                max_chunks_per_source = 12 # Even higher limit for "Open RAG"
                
                for query in search_queries:
                    # top_k=20 for broader discovery
                    results = vector_db.search_similar(query, top_k=20)
                    for result in results:
                        source_url = result.get("metadata", {}).get("source", "unknown")
                        if source_url not in source_counts:
                            source_counts[source_url] = 0
                        
                        if source_counts[source_url] < max_chunks_per_source:
                            is_duplicate = any(
                                r.get("id") == result.get("id") or 
                                r.get("metadata", {}).get("text") == result.get("metadata", {}).get("text")
                                for r in source_documents
                            )
                            if not is_duplicate:
                                source_documents.append(result)
                                source_counts[source_url] += 1
                
                logger.info(f"Retrieved {len(source_documents)} quantitative chunks from Pinecone")
        except Exception as e:
            logger.warning(f"RAG search failed for Analyst: {e}")

        # Determine if we should use RAG or fallback (threshold 10 chunks)
        if len(source_documents) >= 10:
            logger.info(f"Using {len(source_documents)} RAG results for quantitative analysis")
            context_parts = []
            for i, doc in enumerate(source_documents):
                text = doc.get("metadata", {}).get("text", doc.get("text", ""))
                context_parts.append(f"[Context {i+1}]\n{text}")
            combined_context = "\n\n---\n\n".join(context_parts)
        else:
            if source_documents:
                logger.warning(f"Only found {len(source_documents)} RAG chunks. Falling back to full PDF documents for higher density.")
            else:
                logger.info("No RAG results, using full PDF documents.")
                
            combined_context = "\n\n--- Document Separator ---\n\n".join(pdf_documents)
            # Truncate to stay within safe model limits but provide plenty of data
            combined_context = combined_context[:500000] + "\n\n[TRUNCATED]"
        
        # Invoke LLM for extraction
        logger.info(f"Extracting metrics from context ({len(combined_context)} chars)")
        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | structured_llm
        
        analyst_output = chain.invoke({
            "research_plan": research_plan_str,
            "extracted_metrics": extracted_metrics_str,
            "pdf_documents": combined_context
        })
        
        # Enhanced Save for direct auditing
        debug_state = {
            **state,
            "debug_context": combined_context # Include final context in debug log
        }
        save_agent_io("Analyst", debug_state, analyst_output.model_dump())
        
        # Merge LlamaExtract metrics into key_metrics if they are not already there
        if extracted_metrics:
            # Flatten extracted_metrics if it has nested structure from LlamaExtract
            # LlamaExtract schema has 'market_metrics' list
            if "market_metrics" in extracted_metrics:
                for item in extracted_metrics["market_metrics"]:
                    name = item.get("metric_name")
                    value = item.get("value")
                    if name and value is not None:
                        if name not in analyst_output.key_metrics:
                            analyst_output.key_metrics[name] = value
            
            # Also merge other top-level keys if they are simple values
            for k, v in extracted_metrics.items():
                if k != "market_metrics" and isinstance(v, (int, float, str)):
                    if k not in analyst_output.key_metrics:
                        analyst_output.key_metrics[k] = v
        
        logger.info(f"Extracted {len(analyst_output.key_metrics)} key metrics")
        
        # Ensure charts_generated is empty list (as we removed generation)
        analyst_output.charts_generated = []
        analyst_output.chart_data = [] # Clear chart data requests
        
        result = {
            "analyst_output": analyst_output
        }
        
        save_agent_io("Analyst", state, analyst_output.model_dump())
        return result
        
    except Exception as e:
        logger.error(f"Error in Analyst agent: {e}")
        return {
            "analyst_output": AnalystOutput(
                key_metrics={},
                charts_generated=[]
            )
        }

