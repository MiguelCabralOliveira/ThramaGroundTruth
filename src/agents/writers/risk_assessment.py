from src.agents.writers.base_writer import BaseWriter
from src.utils.toon_serializer import pydantic_to_toon

class RiskAssessmentWriter(BaseWriter):
    def write(self) -> str:
        prompt = self.load_prompt("08_risk_assessment.md")
        
        # Project Context
        analyst_output = self.state.get("analyst_output")
        qualitative_research = self.state.get("qualitative_research", "")
        
        context = {
            "risk_data": f"Analyst Data:\n{pydantic_to_toon(analyst_output)}\n\nResearch:\n{qualitative_research}",
            "source_references": self.format_source_references_for_llm()
        }
        
        return self.generate(prompt, context)
