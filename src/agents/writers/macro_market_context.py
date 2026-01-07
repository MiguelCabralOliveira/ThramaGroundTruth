from src.agents.writers.base_writer import BaseWriter
from src.utils.toon_serializer import pydantic_to_toon

class MacroMarketContextWriter(BaseWriter):
    def write(self) -> str:
        prompt = self.load_prompt("05_macro_market_context.md")
        
        # Project Context
        research_plan = self.state.get("research_plan")
        source_documents = self.state.get("source_documents", [])
        
        # Filter for macro docs if possible, or just pass all references
        # For this implementation I will pass all docs descriptions with citation numbers
        formatted_docs = "\n".join([f"Source [{i}] ({d.get('metadata', {}).get('title', 'Doc')}): {d.get('page_content', d.get('text', ''))[:500]}..." for i, d in enumerate(source_documents, 1)])
        
        context = {
            "research_plan": pydantic_to_toon(research_plan) if research_plan else "N/A",
            "macro_documents": formatted_docs,
            "source_references": self.format_source_references_for_llm()
        }
        
        return self.generate(prompt, context)
