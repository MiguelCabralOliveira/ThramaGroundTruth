from src.agents.writers.base_writer import BaseWriter

class ConclusionWriter(BaseWriter):
    def write(self) -> str:
        prompt = self.load_prompt("09_conclusion.md")
        
        # Project Context
        # Conclusion needs a sense of what has been written.
        # We can pass the full draft so far, or just key sections.
        # For simplicity, we assume the previous_sections are passed in the state or we build them here.
        # Since we are writing sections independently, we might not have the full text easily unless we store it in state incrementally.
        # However, the previous Writer implementation accumulated it.
        # In this new architecture, the `writer.py` orchestrator will likely hold the `ReportDraft` object.
        # We can pass the relevant parts of the draft if available in state.
        
        report_draft = self.state.get("report_draft")
        previous_sections = ""
        if report_draft:
             # This might be None if we are creating it from scratch. 
             # But usually we create sections sequentially.
             # If `writer.py` orchestrates it, it should pass the partial draft.
             pass
        
        # For now, let's just pass the research summary and analyst output as the "context" for conclusion
        # as it synthesizes the findings.
        qualitative_research = self.state.get("qualitative_research", "")
        
        context = {
            "previous_sections": self.state.get("report_sections", {}),
            "source_references": self.format_source_references_for_llm()
        }
        
        return self.generate(prompt, context)
