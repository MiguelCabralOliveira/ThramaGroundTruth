from src.agents.writers.base_writer import BaseWriter
from src.utils.toon_serializer import pydantic_to_toon

class MarketAssessmentWriter(BaseWriter):
    def write(self) -> str:
        prompt = self.load_prompt("03_market_assessment.md")
        
        # Project Context
        analyst_output = self.state.get("analyst_output")
        qualitative_research = self.state.get("qualitative_research", "")
        
        context = {
            "analyst_output": pydantic_to_toon(analyst_output) if analyst_output else "N/A",
            "qualitative_research": qualitative_research,
            "source_references": self.format_source_references_for_llm()
        }
        
        return self.generate(prompt, context)
