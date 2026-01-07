from src.agents.writers.base_writer import BaseWriter
from src.utils.toon_serializer import pydantic_to_toon

class KeyTakeawaysWriter(BaseWriter):
    def write(self) -> str:
        prompt = self.load_prompt("02_key_takeaways.md")
        
        # Project Context
        analyst_output = self.state.get("analyst_output")
        qualitative_research = self.state.get("qualitative_research", "")
        
        context = {
            "research_summary": qualitative_research,
            "analyst_highlights": pydantic_to_toon(analyst_output) if analyst_output else "N/A",
            "detail_sections": self.state.get("report_sections", {}),
            "source_references": self.format_source_references_for_llm()
        }
        
        return self.generate(prompt, context)
