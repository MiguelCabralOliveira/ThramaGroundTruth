from src.agents.writers.base_writer import BaseWriter
from src.utils.toon_serializer import pydantic_to_toon

class MarketOverviewWriter(BaseWriter):
    def write(self) -> str:
        prompt = self.load_prompt("06_market_overview.md")
        
        # Project Context
        research_plan = self.state.get("research_plan")
        qualitative_research = self.state.get("qualitative_research", "")
        
        context = {
            "research_plan": pydantic_to_toon(research_plan) if research_plan else "N/A",
            "qualitative_research": qualitative_research,
            "source_references": self.format_source_references_for_llm()
        }
        
        return self.generate(prompt, context)
