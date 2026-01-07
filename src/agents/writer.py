"""Writer Agent: Generates the final report draft."""

from typing import Dict, Any, List
import re
from src.state import AgentGraphState
from src.schemas import ReportDraft
from src.config import Config
from src.utils.logger import get_logger

# Import section writers
from src.agents.writers.macro_market_context import MacroMarketContextWriter
from src.agents.writers.market_overview import MarketOverviewWriter
from src.agents.writers.data_analysis import DataAnalysisWriter
from src.agents.writers.market_assessment import MarketAssessmentWriter
from src.agents.writers.case_studies import CaseStudiesWriter
from src.agents.writers.risk_assessment import RiskAssessmentWriter
from src.agents.writers.conclusion import ConclusionWriter
from src.agents.writers.executive_summary import ExecutiveSummaryWriter
from src.agents.writers.key_takeaways import KeyTakeawaysWriter

logger = get_logger(__name__)

def format_source_references(source_documents: list) -> str:
    """Format source documents as a numbered reference list for citations."""
    if not source_documents:
        return ""
    
    references = ["## Available Source References\n"]
    seen_urls = set()
    unique_docs = []
    
    for doc in source_documents:
        metadata = doc.get("metadata", {})
        url = metadata.get("source", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_docs.append(doc)
        elif not url:
            unique_docs.append(doc)
            
    for i, doc in enumerate(unique_docs, 1):
        metadata = doc.get("metadata", {})
        source_name = (
            metadata.get("source_title") or 
            metadata.get("source") or 
            metadata.get("title") or 
            "Unknown Source"
        )
        url = metadata.get("source", "")
        if "/" in source_name: source_name = source_name.split("/")[-1]
        if "\\" in source_name: source_name = source_name.split("\\")[-1]
        if source_name.endswith(".pdf"): source_name = source_name[:-4]
            
        text_preview = doc.get("text", metadata.get("text", ""))[:200]
        
        if url and url.startswith("http"):
            references.append(f"[{i}] {source_name} ({url})")
        else:
            references.append(f"[{i}] {source_name}")
            
        if text_preview:
            references.append(f"    Preview: {text_preview}...")
        references.append("")
    
    return "\n".join(references)

def generate_bibliography(source_documents: list, bibliography_data: list = None) -> str:
    """Generate a formatted bibliography HTML string."""
    # Use bibliography_data if available (from Scout), otherwise fall back to source_documents (from RAG)
    
    docs_to_use = []
    
    if bibliography_data:
        # Convert bibliography_data to comparable format
         for item in bibliography_data:
            docs_to_use.append({
                "metadata": {
                    "source": item.get("url"),
                    "title": item.get("title"),
                    "source_title": item.get("title")
                }
            })
    
    # If we still have nothing, try source_documents
    if not docs_to_use and source_documents:
        docs_to_use = source_documents
        
    if not docs_to_use: return []
    
    bibliography = []
    seen_urls = set()
    unique_docs = []
    
    for doc in docs_to_use:
        metadata = doc.get("metadata", {})
        url = metadata.get("source", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_docs.append(doc)
        elif not url:
            unique_docs.append(doc)
    
    for i, doc in enumerate(unique_docs, 1):
        metadata = doc.get("metadata", {})
        source_name = (
            metadata.get("source_title") or 
            metadata.get("source") or 
            metadata.get("title") or 
            "Unknown Source"
        )
        url = metadata.get("source", "")
        if "/" in source_name: source_name = source_name.split("/")[-1]
        if "\\" in source_name: source_name = source_name.split("\\")[-1]
        if source_name.endswith(".pdf"): source_name = source_name[:-4]
            
        if url and url.startswith("http"):
            entry = f"[{i}] {source_name} • <a href='{url}'>{url}</a>"
        else:
            entry = f"[{i}] {source_name}"
        bibliography.append(entry)
        
    return bibliography

def make_citations_clickable(text: str, source_documents: list) -> str:
    """Convert text citations like [1] into clickable markdown links."""
    if not text or not source_documents: return text
        
    url_map = {}
    seen_urls = set()
    current_index = 1
    
    for doc in source_documents:
        metadata = doc.get("metadata", {})
        url = metadata.get("source", "")
        if url and url.startswith("http"):
            if url not in seen_urls:
                seen_urls.add(url)
                url_map[current_index] = url
                current_index += 1
        elif not url:
             current_index += 1
    
    def replace_match(match):
        citation_num = int(match.group(1))
        if citation_num in url_map:
            return f"[[{citation_num}]]({url_map[citation_num]})"
        return match.group(0)
        
    return re.sub(r'\[(\d+)\]', replace_match, text)

def agent_node(state: AgentGraphState) -> dict:
    """
    Writer agent node: Orchestrates sequential report generation using modular writers.
    """
    logger.info("Writer Agent: Starting modular report generation")
    
    try:
        # Initialize Writers
        # Map section names to writer instances
        writer_map = {
             "macro_market_context": MacroMarketContextWriter(state),
             "market_overview": MarketOverviewWriter(state),
             "data_analysis": DataAnalysisWriter(state),
             "market_assessment": MarketAssessmentWriter(state),
             "case_studies": CaseStudiesWriter(state),
             "risk_assessment": RiskAssessmentWriter(state),
             "conclusion": ConclusionWriter(state),
             "executive_summary": ExecutiveSummaryWriter(state),
             "key_takeaways": KeyTakeawaysWriter(state),
             "competitive_landscape": MarketOverviewWriter(state), # Reusing writers for now as placeholders if specific ones aren't available
             "regulatory_policy_environment": MarketOverviewWriter(state),
             "pricing_valuation_analysis": MarketOverviewWriter(state),
             "operational_considerations": MarketOverviewWriter(state)
        }
        
        # Determine active sections
        # Start with defaults from Config
        active_sections = Config.REPORT_SECTIONS
        
        # TODO: Check state for specific user overrides if implemented (e.g. in ResearchPlan)
        # if state.get("research_plan") and state["research_plan"].sections:
        #    active_sections = state["research_plan"].sections
        
        logger.info(f"Active sections: {active_sections}")
        
        report_sections = {}
        
        # Define the preferred order of generation (dependencies first)
        # Detailed sections first to provide context for synthesis
        execution_order = [
            "macro_market_context",
            "market_overview",
            "competitive_landscape",
            "regulatory_policy_environment",
            "pricing_valuation_analysis",
            "operational_considerations",
            "market_assessment",
            "data_analysis",
            "case_studies",
            "risk_assessment",
            "executive_summary",
            "key_takeaways",
            "conclusion"
        ]
        
        # Initialize state with an empty sections container for writers to access
        state["report_sections"] = {}
        
        # Generate all configured sections in order
        for section_name in execution_order:
            if section_name in Config.REPORT_SECTIONS and section_name in writer_map:
                logger.info(f"Generating section: {section_name}")
                writer = writer_map[section_name]
                # Inject current progress into writer's state
                writer.state = state
                content = writer.write()
                report_sections[section_name] = content
                state["report_sections"][section_name] = content
        
        # Additional fields that are commented out in schema but expected by code logic if we uncommented
        # For now we only generate what is in the Schema.
        # The prompt for these sections are commented out in the plan as well to keep schema valid.
        
        # Generate Bibliography
        source_documents = state.get("source_documents", [])
        bibliography_data = state.get("bibliography_data", [])
        bibliography_list = generate_bibliography(source_documents, bibliography_data)
        bibliography_section = "\n\n# References\n\n" + "\n".join([f"- {entry}" for entry in bibliography_list])
        
        # Append to Conclusion
        report_sections["conclusion"] += bibliography_section
        
        # Post-process citations
        processed_sections = {}
        for key, text in report_sections.items():
            processed_sections[key] = make_citations_clickable(text, source_documents)
            
        # Assemble ReportDraft (use get with default None for missing sections)
        report_draft = ReportDraft(
            executive_summary=processed_sections.get("executive_summary"),
            key_takeaways=processed_sections.get("key_takeaways"),
            market_assessment=processed_sections.get("market_assessment"),
            case_studies=processed_sections.get("case_studies"),
            macro_market_context=processed_sections.get("macro_market_context"),
            market_overview=processed_sections.get("market_overview"),
            data_analysis=processed_sections.get("data_analysis"),
            risk_assessment=processed_sections.get("risk_assessment"),
            conclusion=processed_sections.get("conclusion"),
            competitive_landscape=processed_sections.get("competitive_landscape"),
            regulatory_policy_environment=processed_sections.get("regulatory_policy_environment"),
            pricing_valuation_analysis=processed_sections.get("pricing_valuation_analysis"),
            operational_considerations=processed_sections.get("operational_considerations"),
        )
        
        logger.info("Modular report generation completed successfully")
        
        # Log Output (New Requirement)
        from src.utils.logger import save_agent_io
        save_agent_io("Writer", state, report_draft.model_dump())

        return {
            "report_draft": report_draft,
            "revision_count": state.get("revision_count", 0)
        }
        
    except Exception as e:
        logger.error(f"Error in Writer agent: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "report_draft": None
        }
