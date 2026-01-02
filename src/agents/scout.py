"""Scout Agent: Searches for and ingests PDF documents."""

import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.tools.search import MarketSearch
from src.tools.pdf_parser import PDFIngest
from src.tools.database import VectorDatabase
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_prompt() -> str:
    """Load the scout prompt from markdown file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "02_scout.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def agent_node(state: AgentGraphState) -> dict:
    """
    Scout agent node: Search for and ingest PDF documents.
    
    Args:
        state: Current graph state
        
    Returns:
        State update dictionary with pdf_documents
    """
    logger.info("Scout Agent: Starting document search and ingestion")
    
    try:
        research_plan = state.get("research_plan")
        if not research_plan:
            logger.error("No research plan found in state")
            return {"pdf_documents": []}
        
        # Step 1: Search for reports
        logger.info("Searching for market reports...")
        search_tool = MarketSearch()
        all_urls = search_tool.find_reports(research_plan.search_queries)
        
        if not all_urls:
            logger.warning("No URLs found from search")
            return {"pdf_documents": []}
        
        logger.info(f"Found {len(all_urls)} URLs from search")
        
        # Step 2: Use LLM to select best URLs
        logger.info("Selecting best URLs for analysis...")
        prompt_template = load_prompt()
        
        llm = ChatOpenAI(
            model=Config.OPENAI_MODEL,
            temperature=0.2,
            api_key=Config.OPENAI_API_KEY
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
            ("human", """Research Plan:
{research_plan}

Search Results URLs:
{urls}

Please select the best URLs for analysis.""")
        ])
        
        chain = prompt | llm
        
        research_plan_str = json.dumps(research_plan.model_dump(), indent=2)
        urls_str = "\n".join([f"- {url}" for url in all_urls])
        
        response = chain.invoke({
            "research_plan": research_plan_str,
            "urls": urls_str
        })
        
        # Parse JSON from response
        response_text = response.content
        try:
            # Try to extract JSON from response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            selection_result = json.loads(response_text)
            selected_urls = selection_result.get("selected_urls", all_urls[:5])  # Fallback to first 5
        except json.JSONDecodeError:
            logger.warning("Could not parse URL selection, using first 5 URLs")
            selected_urls = all_urls[:5]
        
        logger.info(f"Selected {len(selected_urls)} URLs for parsing")
        
        # Step 3: Parse PDFs
        logger.info("Parsing PDF documents...")
        pdf_tool = PDFIngest()
        pdf_documents = pdf_tool.parse_urls(selected_urls)
        
        logger.info(f"Successfully parsed {len(pdf_documents)} PDF documents")
        
        # Step 4: Store in Pinecone
        if pdf_documents:
            logger.info("Storing documents in Pinecone...")
            vector_db = VectorDatabase()
            
            # Create metadata for each document
            metadata = []
            for i, url in enumerate(selected_urls[:len(pdf_documents)]):
                metadata.append({
                    "source": url,
                    "type": "market_report",
                    "sector": research_plan.target_sector,
                    "geography": research_plan.geography
                })
            
            success = vector_db.store_documents(pdf_documents, metadata)
            if success:
                logger.info("✓ Documents successfully stored in Pinecone")
            else:
                logger.warning("Failed to store documents in Pinecone")
        
        return {
            "pdf_documents": pdf_documents
        }
        
    except Exception as e:
        logger.error(f"Error in Scout agent: {e}")
        return {
            "pdf_documents": []
        }

