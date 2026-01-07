"""Researcher Agent: Performs qualitative research synthesis using RAG."""

from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.tools.database import VectorDatabase
from src.config import Config
from src.utils.logger import get_logger
from src.utils.toon_serializer import pydantic_to_toon
from src.utils.logger import save_agent_io

logger = get_logger(__name__)


def load_prompt() -> str:
    """Load the researcher prompt from markdown file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "03_researcher.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def agent_node(state: AgentGraphState) -> dict:
    """
    Researcher agent node: Synthesize qualitative research using RAG.
    
    Args:
        state: Current graph state
        
    Returns:
        State update dictionary with qualitative_research and source_documents
    """
    logger.info("Researcher Agent: Starting qualitative research synthesis with RAG")
    
    try:
        research_plan = state.get("research_plan")
        pdf_documents = state.get("pdf_documents", [])
        
        if not pdf_documents:
            logger.warning("No PDF documents available for research")
            return {
               "qualitative_research": "No documents were available for qualitative analysis.",
                "source_documents": []
            }
        
        # Load prompt
        prompt_template = load_prompt()
        
        # Initialize LLM
        llm = ChatOpenAI(
            model=Config.AGENT_MODELS["researcher"],
            temperature=0.3,
            api_key=Config.OPENAI_API_KEY
        )
        
        
        # Try to use RAG from Pinecone (hybrid approach: RAG + RLM)
        source_documents = []
        use_rlm = False
        
        try:
            vector_db = VectorDatabase()
            
            if vector_db.index and research_plan:
                # Build search queries based on research plan - diverse queries targeting different data types
                search_queries = [
                    f"{research_plan.target_sector} {research_plan.geography} market overview",
                    f"{research_plan.target_sector} investment yields returns cap rates",
                    f"{research_plan.target_sector} supply demand trends",
                    f"{research_plan.target_sector} risks regulations",
                    f"{research_plan.target_sector} {research_plan.geography} recent transactions case studies",
                    f"{research_plan.target_sector} {research_plan.geography} major deals 2024 2025",
                    f"{research_plan.target_sector} yields cap rates statistics {research_plan.geography}",
                    f"{research_plan.target_sector} prices per sqft rental rates {research_plan.geography}",
                    f"{research_plan.target_sector} rental growth percentages statistics {research_plan.geography}",
                    f"{research_plan.target_sector} market data report PDF statistics {research_plan.geography}",
                    f"{research_plan.target_sector} vacancy rates occupancy metrics {research_plan.geography}",
                    f"{research_plan.target_sector} transaction volumes pricing data {research_plan.geography}"
                ]
                
                logger.info("Querying Pinecone for relevant context...")
                
                # Track source usage to ensure diversity
                source_counts = {}
                max_chunks_per_source = 5  # Increased from 3 to allow more chunks per source
                min_unique_sources = 10  # Minimum threshold for unique sources
                
                for query in search_queries:
                    # Fetch more candidates to allow for filtering and diversity
                    results = vector_db.search_similar(query, top_k=25)  # Increased from 10 to 25
                    
                    for result in results:
                        source_url = result.get("metadata", {}).get("source", "unknown")
                        
                        # Initialize count for this source
                        if source_url not in source_counts:
                            source_counts[source_url] = 0
                        
                        # Add if we haven't hit the limit for this source
                        if source_counts[source_url] < max_chunks_per_source:
                            # Check for duplicates based on ID or content
                            is_duplicate = any(
                                r.get("id") == result.get("id") or 
                                r.get("metadata", {}).get("text") == result.get("metadata", {}).get("text")
                                for r in source_documents
                            )
                            
                            if not is_duplicate:
                                source_documents.append(result)
                                source_counts[source_url] += 1
                
                # Check if we have enough unique sources, if not, try to get more
                unique_sources_count = len(source_counts)
                if unique_sources_count < min_unique_sources:
                    logger.info(f"Only {unique_sources_count} unique sources found, attempting to retrieve more...")
                    # Try additional queries with different angles
                    additional_queries = [
                        f"{research_plan.target_sector} financial metrics {research_plan.geography}",
                        f"{research_plan.target_sector} market statistics data {research_plan.geography}",
                        f"{research_plan.target_sector} quantitative analysis {research_plan.geography}"
                    ]
                    
                    for query in additional_queries:
                        if unique_sources_count >= min_unique_sources:
                            break
                        results = vector_db.search_similar(query, top_k=25)
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
                                    unique_sources_count = len(source_counts)
                                    if unique_sources_count >= min_unique_sources:
                                        break
                                
                logger.info(f"Retrieved {len(source_documents)} relevant chunks from {len(source_counts)} unique sources")
                    
        except Exception as e:
            logger.warning(f"RAG search failed, will use RLM on full documents: {e}")
        
        # Determine processing strategy
        research_plan_str = pydantic_to_toon(research_plan) if research_plan else "N/A"
        
        # Use RAG results for synthesis
        logger.info(f"Synthesizing qualitative research from {len(source_documents)} RAG chunks")
        
        context_parts = []
        for i, doc in enumerate(source_documents):
            source_info = doc.get("metadata", {}).get("source", "Unknown Source")
            text = doc.get("metadata", {}).get("text", doc.get("text", ""))
            context_parts.append(f"[Source {i+1}: {source_info}]\n{text}")
        
        context_text = "\n\n---\n\n".join(context_parts)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
            ("human", """Research Plan:
{research_plan}

Documents and Sources:
{pdf_documents}

Please synthesize the qualitative research. IMPORTANT: For every key claim or statistic, include a citation in the format [Source: Source Name] based on the source information provided above.""")
        ])
        
        chain = prompt | llm
        response = chain.invoke({
            "research_plan": research_plan_str,
            "pdf_documents": context_text
        })
        qualitative_research = response.content
        
        logger.info(f"Qualitative research generated: {len(qualitative_research)} characters")
        
        result = {
            "qualitative_research": qualitative_research,
            "source_documents": source_documents
        }
        
        save_agent_io("Researcher", state, result)
        return result
        
    except Exception as e:
        logger.error(f"Error in Researcher agent: {e}")
        return {
            "qualitative_research": f"Error during qualitative research: {str(e)}",
            "source_documents": []
        }
