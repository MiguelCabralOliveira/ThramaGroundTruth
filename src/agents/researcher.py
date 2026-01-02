"""Researcher Agent: Performs qualitative research synthesis using RAG."""

from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.state import AgentGraphState
from src.tools.database import VectorDatabase
from src.config import Config
from src.utils.logger import get_logger

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
            model=Config.OPENAI_MODEL,
            temperature=0.3,
            api_key=Config.OPENAI_API_KEY
        )
        
        # Try to use RAG from Pinecone
        source_documents = []
        context_text = ""
        
        try:
            vector_db = VectorDatabase()
            
            if vector_db.index and research_plan:
                # Build search queries based on research plan
                search_queries = [
                    f"{research_plan.target_sector} {research_plan.geography} market overview",
                    f"{research_plan.target_sector} investment yields returns",
                    f"{research_plan.target_sector} supply demand trends",
                    f"{research_plan.target_sector} risks regulations"
                ]
                
                logger.info("Querying Pinecone for relevant context...")
                
                for query in search_queries:
                    results = vector_db.search_similar(query, top_k=3)
                    for result in results:
                        if result not in source_documents:
                            source_documents.append(result)
                
                logger.info(f"Retrieved {len(source_documents)} relevant chunks from Pinecone")
                
                # Build context from RAG results
                if source_documents:
                    context_parts = []
                    for i, doc in enumerate(source_documents):
                        source_info = doc.get("metadata", {}).get("source", "Unknown Source")
                        text = doc.get("metadata", {}).get("text", doc.get("text", ""))
                        context_parts.append(f"[Source {i+1}: {source_info}]\n{text}")
                    
                    context_text = "\n\n---\n\n".join(context_parts)
                    logger.info(f"Built RAG context: {len(context_text)} characters from {len(source_documents)} sources")
                    
        except Exception as e:
            logger.warning(f"RAG search failed, falling back to full documents: {e}")
        
        # If RAG didn't work, fall back to full documents
        if not context_text:
            logger.info("Using full PDF documents (no RAG)")
            context_text = "\n\n--- Document Separator ---\n\n".join(pdf_documents)
            
            # Truncate if too long
            max_length = 100000
            if len(context_text) > max_length:
                logger.warning(f"Documents too long ({len(context_text)} chars), truncating to {max_length}")
                context_text = context_text[:max_length] + "\n\n[Document truncated due to length...]"
        
        # Create prompt
        research_plan_str = research_plan.model_dump_json(indent=2) if research_plan else "N/A"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
            ("human", """Research Plan:
{research_plan}

Documents and Sources:
{pdf_documents}

Please synthesize the qualitative research. IMPORTANT: For every key claim or statistic, include a citation in the format [Source: Source Name] based on the source information provided above.""")
        ])
        
        chain = prompt | llm
        
        logger.info(f"Processing context ({len(context_text)} characters)")
        response = chain.invoke({
            "research_plan": research_plan_str,
            "pdf_documents": context_text
        })
        
        qualitative_research = response.content
        
        logger.info(f"Qualitative research generated: {len(qualitative_research)} characters")
        
        return {
            "qualitative_research": qualitative_research,
            "source_documents": source_documents
        }
        
    except Exception as e:
        logger.error(f"Error in Researcher agent: {e}")
        return {
            "qualitative_research": f"Error during qualitative research: {str(e)}",
            "source_documents": []
        }
