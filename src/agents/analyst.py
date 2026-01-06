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
from src.utils.rlm_processor import RLMProcessor

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
        
        # Check if we need RLM processing
        total_doc_length = sum(len(doc) for doc in pdf_documents)
        estimated_tokens = total_doc_length // 4
        use_rlm = estimated_tokens > 100000  # Use RLM for very long documents
        
        if use_rlm and pdf_documents:
            logger.info(f"Documents are very long ({estimated_tokens} estimated tokens), using RLM for processing")
            
            # Initialize RLM processor (optimized for speed)
            rlm_processor = RLMProcessor(
                chunk_size=20000,  # Larger chunks = fewer chunks = faster
                chunk_overlap=500,
                max_recursion_depth=2,  # Reduced depth for speed
                model=Config.AGENT_MODELS["analyst"],
                batch_size=5,  # Process 5 chunks in parallel
                max_workers=5  # 5 parallel workers
            )
            
            # Use RLM to extract metrics from long documents
            processing_instruction = f"""Extract quantitative metrics from the documents based on the research plan.

Research Plan:
{research_plan_str}

Pre-extracted Metrics (if any):
{extracted_metrics_str}

CRITICAL: Extract ALL quantitative metrics as key-value pairs. For each metric found, format as:
- metric_name: value (with units if applicable)

Extract ALL quantitative metrics including:
- Rental values (ERV, prime rents, etc.) - format: "prime_rent_psf: 14.00" or "erv_region_psf: 12.50"
- Yields (prime yield, net yield, etc.) - format: "prime_yield_pct: 5.58" or "net_yield_pct: 4.2"
- Growth rates (rental growth, capital growth, etc.) - format: "rental_growth_pct: 4.3" or "capital_growth_pct: 2.1"
- Market statistics (take-up, vacancy, supply, demand) - format: "vacancy_rate_pct: 8.5" or "take_up_sqft: 3500000"
- Transaction data (prices, volumes, etc.) - format: "avg_transaction_price: 5000000" or "transaction_volume: 25"
- Financial metrics (returns, default rates, etc.) - format: "total_return_pct: 11.1" or "default_rate_pct: 1.4"

Provide comprehensive metric extraction. Focus on numbers, percentages, and quantitative data.
NEVER mention missing data or data gaps. Extract what IS available."""
            
            # Process with RLM
            extracted_text = rlm_processor.process_documents(
                documents=pdf_documents,
                processing_instruction=processing_instruction,
                system_prompt=prompt_template
            )
            
            # Now use structured output on the RLM-extracted text
            logger.info("Refining RLM-extracted metrics with structured output...")
            
            # Escape curly braces in extracted_text to prevent LangChain template variable errors
            # LangChain will interpret {variable} as template variables, so we escape them
            extracted_text_escaped = extracted_text.replace("{", "{{").replace("}", "}}")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_template),
                ("human", """Research Plan:
{research_plan}

Pre-extracted Metrics (from LlamaExtract):
{extracted_metrics}

RLM-Extracted Analysis:
{pdf_documents}

CRITICAL INSTRUCTIONS:
1. Extract ALL quantitative metrics from the RLM analysis above. The RLM analysis contains key-value pairs and narrative text with numbers.
2. Create a structured AnalystOutput with key_metrics dictionary containing AT LEAST 10 metrics.
3. NEVER mention missing data, data gaps, or suggest additional data collection.
4. Work ONLY with the data that IS available in the documents.
5. If a metric isn't explicitly stated, derive it from available information or skip it silently.
6. Focus on providing a comprehensive list of key metrics. Do NOT generate charts.""")
            ])
            
            chain = prompt | structured_llm
            
            analyst_output = chain.invoke({
                "research_plan": research_plan_str,
                "extracted_metrics": extracted_metrics_str,
                "pdf_documents": extracted_text_escaped
            })
            
            # Fallback: If RLM extraction returned 0 metrics, try direct extraction on sampled documents
            if len(analyst_output.key_metrics) == 0:
                logger.warning("RLM extraction returned 0 metrics, attempting fallback direct extraction...")
                # Sample a subset of documents for direct extraction (first 3 documents or up to 100k chars)
                sampled_docs = []
                total_chars = 0
                for doc in pdf_documents[:5]:  # Sample first 5 documents
                    if total_chars + len(doc) < 100000:  # Keep under 100k chars
                        sampled_docs.append(doc)
                        total_chars += len(doc)
                    else:
                        break
                
                if sampled_docs:
                    combined_sampled = "\n\n--- Document Separator ---\n\n".join(sampled_docs)
                    logger.info(f"Attempting direct extraction on {len(sampled_docs)} sampled documents ({total_chars} chars)")
                    
                    fallback_prompt = ChatPromptTemplate.from_messages([
                        ("system", prompt_template),
                        ("human", """Research Plan:
{research_plan}

Pre-extracted Metrics (from LlamaExtract):
{extracted_metrics}

PDF Documents (sampled for direct extraction):
{pdf_documents}

CRITICAL: Extract AT LEAST 10 quantitative metrics from these documents. 
Look for ANY numbers: prices, percentages, rates, volumes, sizes, etc.
Format as key-value pairs in key_metrics dictionary.
NEVER mention missing data. Extract what IS available.
Do NOT generate charts.""")
                    ])
                    
                    fallback_chain = fallback_prompt | structured_llm
                    fallback_output = fallback_chain.invoke({
                        "research_plan": research_plan_str,
                        "extracted_metrics": extracted_metrics_str,
                        "pdf_documents": combined_sampled
                    })
                    
                    if len(fallback_output.key_metrics) > 0:
                        logger.info(f"Fallback extraction successful: {len(fallback_output.key_metrics)} metrics found")
                        analyst_output = fallback_output
                    else:
                        logger.warning("Fallback extraction also returned 0 metrics")
        else:
            # Traditional processing for manageable documents
            combined_docs = "\n\n--- Document Separator ---\n\n".join(pdf_documents)
            
            logger.info(f"Analyst Input - PDF Docs Length: {len(combined_docs)} chars")
            logger.info(f"Analyst Input - Research Plan: {research_plan_str[:200]}...")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_template),
                ("human", """Research Plan:
{research_plan}

Pre-extracted Metrics (from LlamaExtract):
{extracted_metrics}

PDF Documents (for additional context):
{pdf_documents}

CRITICAL INSTRUCTIONS:
1. Extract ALL quantitative metrics from the documents. Provide AT LEAST 10 metrics.
2. NEVER mention missing data, data gaps, or suggest additional data collection.
3. Work ONLY with the data that IS available in the documents.
4. If a metric isn't explicitly stated, derive it from available information or skip it silently.
5. Focus on providing a comprehensive list of key metrics. Do NOT generate charts.""")
            ])
            
            chain = prompt | structured_llm
            
            logger.info("Extracting and refining metrics...")
            analyst_output = chain.invoke({
                "research_plan": research_plan_str,
                "extracted_metrics": extracted_metrics_str,
                "pdf_documents": combined_docs
            })
        
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

