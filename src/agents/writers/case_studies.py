from src.agents.writers.base_writer import BaseWriter
# from src.agents.writer import format_source_references # Copied logic to avoid circular import if needed, but let's see. 
# We need to format source docs. Let's duplicate the helper or move it to utils. 
# For now, I will implement a simple formatter here or import it if I move it.
# Actually, I'll rely on the text representation of source docs in the state for now, 
# or better, I will assume the format_references function is available or I'll implement a simple one here.

class CaseStudiesWriter(BaseWriter):
    def write(self) -> str:
        prompt = self.load_prompt("04_case_studies.md")
        
        # Project Context
        source_documents = self.state.get("source_documents", [])
        
        # Format documents for the LLM to extract case studies
        formatted_docs = "\n".join([f"Source [{i}]: {d.get('metadata', {}).get('source', 'Unknown')}\nContent: {d.get('page_content', d.get('text', ''))[:1000]}" for i, d in enumerate(source_documents, 1)])

        context = {
            "source_documents": formatted_docs,
            "source_references": self.format_source_references_for_llm()
        }
        
        return self.generate(prompt, context)
