"""Writer Agent: Generates the final report draft."""

from pathlib import Path
from typing import Dict, Any, Optional
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.state import AgentGraphState
from src.schemas import ReportDraft
from src.config import Config
from src.tools.database import VectorDatabase
from src.utils.logger import get_logger
from src.utils.toon_serializer import pydantic_to_toon

logger = get_logger(__name__)


def load_prompt_template() -> str:
    """Load the modular writer section prompt."""
    base_path = Path(__file__).parent.parent / "prompts"
    
    # Load global instructions
    global_path = base_path / "global_instructions.md"
    global_instr = ""
    if global_path.exists():
        with open(global_path, "r", encoding="utf-8") as f:
            global_instr = f.read() + "\n\n"
            
    # Load section prompt
    prompt_path = base_path / "writer_section.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return global_instr + f.read()


def format_source_references(source_documents: list) -> str:
    """Format source documents as a numbered reference list for citations."""
    if not source_documents:
        return ""
    
    references = ["## Available Source References\n"]
    
    seen_urls = set()
    unique_docs = []
    
    # Deduplicate documents based on URL
    for doc in source_documents:
        metadata = doc.get("metadata", {})
        url = metadata.get("source", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_docs.append(doc)
        elif not url:
            # Keep documents without URL (rare but possible)
            unique_docs.append(doc)
            
    for i, doc in enumerate(unique_docs, 1):
        metadata = doc.get("metadata", {})
        
        # Extract source name
        source_name = (
            metadata.get("source_title") or 
            metadata.get("source") or 
            metadata.get("title") or 
            "Unknown Source"
        )
        
        # Get URL
        url = metadata.get("source", "")
        
        # Clean up source name
        if "/" in source_name:
            source_name = source_name.split("/")[-1]
        if "\\" in source_name:
            source_name = source_name.split("\\")[-1]
        if source_name.endswith(".pdf"):
            source_name = source_name[:-4]
            
        # Get text preview
        text_preview = doc.get("text", metadata.get("text", ""))[:200]
        
        # Format for LLM context: [1] Source Name (URL)
        if url and url.startswith("http"):
            references.append(f"[{i}] {source_name} ({url})")
        else:
            references.append(f"[{i}] {source_name}")
            
        if text_preview:
            references.append(f"    Preview: {text_preview}...")
        references.append("")
    
    return "\n".join(references)


def generate_bibliography(source_documents: list) -> str:
    """Generate a formatted bibliography HTML string."""
    if not source_documents:
        return ""
    
    bibliography = []
    seen_urls = set()
    unique_docs = []
    
    # Deduplicate documents based on URL
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
        
        # Extract details
        source_name = (
            metadata.get("source_title") or 
            metadata.get("source") or 
            metadata.get("title") or 
            "Unknown Source"
        )
        
        url = metadata.get("source", "")
        
        # Clean up source name
        if "/" in source_name:
            source_name = source_name.split("/")[-1]
        if "\\" in source_name:
            source_name = source_name.split("\\")[-1]
        if source_name.endswith(".pdf"):
            source_name = source_name[:-4]
            
        # Format: [1] Source Name • URL
        # We will format this as a list item in HTML later, or Markdown
        if url and url.startswith("http"):
            entry = f"[{i}] {source_name} • <a href='{url}'>{url}</a>"
        else:
            entry = f"[{i}] {source_name}"
            
        bibliography.append(entry)
        
    return bibliography


def make_citations_clickable(text: str, source_documents: list) -> str:
    """
    Convert text citations like [1] into clickable markdown links [[1]](url).
    """
    if not text or not source_documents:
        return text
        
    # Create a map of index -> url
    url_map = {}
    seen_urls = set()
    current_index = 1
    
    # We must iterate in the same order as format_source_references/generate_bibliography
    # to ensure indices match.
    for doc in source_documents:
        metadata = doc.get("metadata", {})
        url = metadata.get("source", "")
        
        if url and url.startswith("http"):
            if url not in seen_urls:
                seen_urls.add(url)
                url_map[current_index] = url
                current_index += 1
            # If seen, we skip incrementing index because it wasn't added to the list
        elif not url:
             # Document without URL is added to list but has no URL mapping
             current_index += 1
    
    def replace_match(match):
        citation_num = int(match.group(1))
        if citation_num in url_map:
            return f"[[{citation_num}]]({url_map[citation_num]})"
        return match.group(0)
        
    
    return re.sub(r'\[(\d+)\]', replace_match, text)


def generate_section(
    llm: ChatOpenAI, 
    template: str, 
    section_topic: str,
    section_instructions: str,
    context_data: Dict[str, Any]
) -> str:
    """
    Generate a single section of the report.
    """
    logger.info(f"Generating section: {section_topic}")
    
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | StrOutputParser()
    
    try:
        return chain.invoke({
            "section_topic": section_topic,
            "section_instructions": section_instructions,
            "research_plan": context_data.get("research_plan", "N/A"),
            "analyst_output": context_data.get("analyst_output", "N/A"),
            "source_references": context_data.get("source_references", "N/A"),
            "previous_sections": context_data.get("previous_sections", "None yet.")
        })
    except Exception as e:
        logger.error(f"Error generating section {section_topic}: {e}")
        return f"[Error generating {section_topic}]"


def agent_node(state: AgentGraphState) -> dict:
    """
    Writer agent node: Generate comprehensive report draft sequentially.
    """
    logger.info("Writer Agent: Starting sequential report generation")
    
    try:
        # 1. Prepare Context
        research_plan = state.get("research_plan")
        analyst_output = state.get("analyst_output")
        source_documents = state.get("source_documents", [])
        
        # Format inputs (using TOON for token efficiency)
        research_plan_str = pydantic_to_toon(research_plan) if research_plan else "N/A"
        analyst_output_str = pydantic_to_toon(analyst_output) if analyst_output else "N/A"
        source_references = format_source_references(source_documents)
        
        # Initialize LLM
        llm = ChatOpenAI(
            model=Config.AGENT_MODELS["writer"],
            temperature=0.4,
            api_key=Config.OPENAI_API_KEY
        )
        
        template = load_prompt_template()
        
        # Check if revision
        review_feedback = state.get("review_feedback")
        previous_draft = state.get("report_draft")
        is_revision = review_feedback is not None and previous_draft is not None
        
        sections_to_update = []
        if is_revision:
            logger.info("Revision mode detected. Analyzing feedback...")
            # Simple heuristic: If feedback mentions a section name, update it. 
            # Ideally this would be an LLM call, but for now we'll update ALL if unsure, or specific if clear.
            # For this implementation, we will use a "Surgical" approach based on keywords, 
            # or default to updating the specific sections that are most likely to be wrong.
            
            # TODO: Implement LLM-based feedback analysis for true surgical precision.
            # For now, we will re-generate the Analysis and Risk sections as they are most critical,
            # and ALWAYS regenerate the Summary to reflect changes.
            sections_to_update = ["Data Analysis", "Market Assessment", "Risk Assessment", "Conclusion", "Executive Summary"]
            logger.info(f"Surgical Revision: Updating {sections_to_update}")
        
        # Helper to decide if we should generate a section
        def should_generate(topic: str) -> bool:
            if not is_revision:
                return True # Generate everything for first draft
            return topic in sections_to_update

        # Context dictionary for the generator
        # SMART CONTEXT: We will inject specific data into this dict for each call
        # previous_sections will be updated incrementally after each section is generated
        # to ensure each new section sees all previously written sections
        context_data = {
            "source_references": source_references,
            "previous_sections": ""  # Will be populated incrementally as sections are generated
        }
        
        # --- PHASE 1: Context ---
        logger.info("--- Phase 1: Context ---")
        
        macro_market_context = previous_draft.macro_market_context if is_revision and not should_generate("Macro & Market Context") else generate_section(
            llm, template, "Macro & Market Context",
            "Provide a high-level overview of the macroeconomic environment. Focus on interest rates, inflation, and GDP.",
            {**context_data, "research_plan": research_plan_str} # Smart Context: Only Plan + Docs
        )
        
        # Update context IMMEDIATELY after first section
        if macro_market_context:
            context_data["previous_sections"] += f"\n\n## Macro & Market Context\n{macro_market_context}"
        
        market_overview = previous_draft.market_overview if is_revision and not should_generate("Market Overview") else generate_section(
            llm, template, "Market Overview",
            "Describe the specific real estate sector market. Discuss supply/demand and major trends.",
            {**context_data, "research_plan": research_plan_str} # Smart Context: Only Plan + Docs (now includes macro_market_context)
        )
        
        # Update context IMMEDIATELY after second section
        if market_overview:
            context_data["previous_sections"] += f"\n\n## Market Overview\n{market_overview}"
        
        # --- PHASE 2: Analysis ---
        logger.info("--- Phase 2: Analysis ---")
        
        data_analysis = previous_draft.data_analysis if is_revision and not should_generate("Data Analysis") else generate_section(
            llm, template, "Data Analysis",
            "Analyze the quantitative data. Discuss rental growth, yields, and pricing. Be specific with numbers.",
            {**context_data, "analyst_output": analyst_output_str} # Smart Context: Analyst Data is key here (includes all previous sections)
        )
        
        # Update context IMMEDIATELY after data_analysis
        if data_analysis:
            context_data["previous_sections"] += f"\n\n## Data Analysis\n{data_analysis}"
        
        market_assessment = previous_draft.market_assessment if is_revision and not should_generate("Market Assessment") else generate_section(
            llm, template, "Market Assessment",
            "Provide a neutral assessment of the market cycle. Tenant's or landlord's market?",
            {**context_data, "analyst_output": analyst_output_str} # Now includes data_analysis
        )
        
        # Update context IMMEDIATELY after market_assessment
        if market_assessment:
            context_data["previous_sections"] += f"\n\n## Market Assessment\n{market_assessment}"
        
        case_studies = previous_draft.case_studies if is_revision and not should_generate("Case Studies") else generate_section(
            llm, template, "Case Studies / Transaction Log",
            "Summarize relevant comparable transactions.",
            {**context_data, "research_plan": research_plan_str} # Now includes all previous sections
        )
        
        # Update context IMMEDIATELY after case_studies
        if case_studies:
            context_data["previous_sections"] += f"\n\n## Case Studies\n{case_studies}"
        
        # --- PHASE 2.5: Additional Analysis Sections ---
        logger.info("--- Phase 2.5: Additional Analysis ---")
        
        competitive_landscape = getattr(previous_draft, "competitive_landscape", "") if is_revision and not should_generate("Competitive Landscape") else generate_section(
            llm, template, "Competitive Landscape",
            "Analyze the competitive landscape. Identify major players, market share, competitive positioning, barriers to entry, and market concentration.",
            {**context_data, "research_plan": research_plan_str}
        )
        
        if competitive_landscape:
            context_data["previous_sections"] += f"\n\n## Competitive Landscape\n{competitive_landscape}"
        
        regulatory_policy_environment = getattr(previous_draft, "regulatory_policy_environment", "") if is_revision and not should_generate("Regulatory & Policy Environment") else generate_section(
            llm, template, "Regulatory & Policy Environment",
            "Analyze current regulations, pending policy changes, zoning/planning constraints, and tax implications affecting the sector.",
            {**context_data, "research_plan": research_plan_str}
        )
        
        if regulatory_policy_environment:
            context_data["previous_sections"] += f"\n\n## Regulatory & Policy Environment\n{regulatory_policy_environment}"
        
        pricing_valuation_analysis = getattr(previous_draft, "pricing_valuation_analysis", "") if is_revision and not should_generate("Pricing & Valuation Analysis") else generate_section(
            llm, template, "Pricing & Valuation Analysis",
            "Analyze current pricing vs historical, comparable transactions, valuation methodology, and price per unit/sqft trends. Include specific pricing metrics.",
            {**context_data, "analyst_output": analyst_output_str}
        )
        
        if pricing_valuation_analysis:
            context_data["previous_sections"] += f"\n\n## Pricing & Valuation Analysis\n{pricing_valuation_analysis}"
        
        operational_considerations = getattr(previous_draft, "operational_considerations", "") if is_revision and not should_generate("Operational Considerations") else generate_section(
            llm, template, "Operational Considerations",
            "Analyze management requirements, operating expenses, CapEx requirements, and operational efficiency metrics.",
            {**context_data, "analyst_output": analyst_output_str}
        )
        
        if operational_considerations:
            context_data["previous_sections"] += f"\n\n## Operational Considerations\n{operational_considerations}"
        
        # --- PHASE 3: Risks & Conclusion ---
        logger.info("--- Phase 3: Risks & Conclusion ---")
        
        risk_assessment = previous_draft.risk_assessment if is_revision and not should_generate("Risk Assessment") else generate_section(
            llm, template, "Risk Assessment",
            "Identify key risks (market, regulatory, financial) and mitigants.",
            {**context_data, "analyst_output": analyst_output_str, "research_plan": research_plan_str} # Includes all previous sections
        )
        
        # Update context IMMEDIATELY after risk_assessment
        if risk_assessment:
            context_data["previous_sections"] += f"\n\n## Risk Assessment\n{risk_assessment}"
        
        conclusion = previous_draft.conclusion if is_revision and not should_generate("Conclusion") else generate_section(
            llm, template, "Conclusion",
            "Summarize findings and provide outlook.",
            {**context_data} # Relies heavily on previous sections (now includes risk_assessment)
        )
        
        # Update context for final synthesis
        if conclusion:
            context_data["previous_sections"] += f"\n\n## Conclusion\n{conclusion}"
        
        # --- PHASE 4: Synthesis (Summary) ---
        logger.info("--- Phase 4: Synthesis ---")
        
        # Always regenerate summary on revision to ensure consistency
        executive_summary = generate_section(
            llm, template, "Executive Summary",
            "Write a concise executive summary of the ENTIRE report. Highlight most important findings.",
            context_data # Needs full context of what was just written
        )
        
        key_takeaways = generate_section(
            llm, template, "Key Takeaways",
            "List 3-5 bullet points of critical takeaways.",
            context_data
        )
        
        # Generate Bibliography
        bibliography_list = generate_bibliography(source_documents)
        bibliography_section = "\n\n# References\n\n"
        for entry in bibliography_list:
            bibliography_section += f"- {entry}\n"
            
        # Append to Conclusion
        conclusion += bibliography_section
        
        # Post-process: Make citations clickable in all sections
        # We do this before creating the object
        sections_to_process = {
            "executive_summary": executive_summary,
            "key_takeaways": key_takeaways,
            "market_assessment": market_assessment,
            "case_studies": case_studies,
            "macro_market_context": macro_market_context,
            "market_overview": market_overview,
            "data_analysis": data_analysis,
            "risk_assessment": risk_assessment,
            "conclusion": conclusion,
            "competitive_landscape": competitive_landscape,
            "regulatory_policy_environment": regulatory_policy_environment,
            "pricing_valuation_analysis": pricing_valuation_analysis,
            "operational_considerations": operational_considerations
        }
        
        processed_sections = {}
        for key, text in sections_to_process.items():
            processed_sections[key] = make_citations_clickable(text, source_documents)
        
        # Assemble ReportDraft
        report_draft = ReportDraft(
            executive_summary=processed_sections["executive_summary"],
            key_takeaways=processed_sections["key_takeaways"],
            market_assessment=processed_sections["market_assessment"],
            case_studies=processed_sections["case_studies"],
            macro_market_context=processed_sections["macro_market_context"],
            market_overview=processed_sections["market_overview"],
            data_analysis=processed_sections["data_analysis"],
            risk_assessment=processed_sections["risk_assessment"],
            conclusion=processed_sections["conclusion"],
            competitive_landscape=processed_sections["competitive_landscape"],
            regulatory_policy_environment=processed_sections["regulatory_policy_environment"],
            pricing_valuation_analysis=processed_sections["pricing_valuation_analysis"],
            operational_considerations=processed_sections["operational_considerations"]
        )
        
        logger.info("Sequential report generation completed successfully")
        
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

