"""Base class for modular section writers."""

from pathlib import Path
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)

class BaseWriter:
    """Base class for all section writers."""
    
    def __init__(self, state: Dict[str, Any]):
        self.state = state
        self.llm = ChatOpenAI(
            model=Config.AGENT_MODELS["writer"],
            temperature=0.4,
            api_key=Config.OPENAI_API_KEY
        )
        self.base_prompt_path = Path(__file__).parent.parent.parent / "prompts"

    def load_prompt(self, section_prompt_file: str) -> str:
        """Load the combined global instructions and section-specific prompt."""
        # Load global instructions
        global_path = self.base_prompt_path / "05_writer.md"
        global_instr = ""
        if global_path.exists():
            with open(global_path, "r", encoding="utf-8") as f:
                global_instr = f.read() + "\n\n"
        
        # Load section prompt
        section_path = self.base_prompt_path / "sections" / section_prompt_file
        if not section_path.exists():
            logger.error(f"Section prompt not found: {section_path}")
            return global_instr
            
        with open(section_path, "r", encoding="utf-8") as f:
            return global_instr + f.read()

    def format_source_references_for_llm(self) -> str:
        """Format source documents for LLM injection."""
        source_documents = self.state.get("source_documents", [])
        if not source_documents:
            return "No references available."
            
        references = []
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
            source_name = metadata.get("source_title") or metadata.get("title") or "Unknown Source"
            if "/" in source_name: source_name = source_name.split("/")[-1]
            if "\\" in source_name: source_name = source_name.split("\\")[-1]
            if source_name.endswith(".pdf"): source_name = source_name[:-4]
            
            references.append(f"[{i}] {source_name}")
            
        return "\n".join(references)

    def generate(self, prompt_template: str, context: Dict[str, Any]) -> str:
        """Generate content using the LLM."""
        try:
            prompt = ChatPromptTemplate.from_template(prompt_template)
            chain = prompt | self.llm | StrOutputParser()
            return chain.invoke(context)
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return f"[Error generating content: {e}]"
            
    def write(self) -> str:
        """Abstract method to be implemented by child classes."""
        raise NotImplementedError
