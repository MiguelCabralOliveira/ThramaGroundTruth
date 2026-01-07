from src.agents.writers.base_writer import BaseWriter
from src.utils.toon_serializer import pydantic_to_toon

class DataAnalysisWriter(BaseWriter):
    def write(self) -> str:
        prompt = self.load_prompt("07_data_analysis.md")
        
        # Project Context
        analyst_output = self.state.get("analyst_output")
        
        context = {
            "analyst_output": pydantic_to_toon(analyst_output) if analyst_output else "N/A",
            "source_references": self.format_source_references_for_llm()
        }
        
        return self.generate(prompt, context)
