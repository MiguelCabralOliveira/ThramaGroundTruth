"""RLM (Recursive Language Model) processor for handling extremely long documents.

RLM enables processing of contexts up to 2 orders of magnitude beyond standard
context windows by recursively decomposing and examining document chunks.
"""

from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RLMProcessor:
    """Recursive Language Model processor for long document handling."""
    
    def __init__(
        self,
        chunk_size: int = 15000,  # Increased default for fewer chunks
        chunk_overlap: int = 500,
        max_recursion_depth: int = 2,  # Reduced depth
        model: Optional[str] = None,
        batch_size: int = 5,  # Process 5 chunks in parallel
        max_workers: int = 5  # Parallel workers
    ):
        """
        Initialize RLM processor.
        
        Args:
            chunk_size: Size of each document chunk (larger = fewer chunks)
            chunk_overlap: Overlap between chunks
            max_recursion_depth: Maximum recursion depth for processing
            model: LLM model to use (defaults to researcher model)
            batch_size: Number of chunks to process in parallel
            max_workers: Maximum parallel workers for processing
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_recursion_depth = max_recursion_depth
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.model_name = model or Config.AGENT_MODELS.get("researcher", "gpt-4o")
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )
        
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=0.3,
            api_key=Config.OPENAI_API_KEY
        )
    
    def process_documents(
        self,
        documents: List[str],
        processing_instruction: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Process long documents using recursive decomposition.
        
        Args:
            documents: List of document texts to process
            processing_instruction: Instruction for what to extract/analyze
            system_prompt: Optional system prompt for the LLM
            
        Returns:
            Synthesized result from processing all documents
        """
        if not documents:
            return ""
        
        # Combine all documents
        combined_text = "\n\n--- Document Separator ---\n\n".join(documents)
        
        # Check if we need recursive processing
        estimated_tokens = len(combined_text) // 4  # Rough estimate: 1 token ≈ 4 chars
        max_tokens = 100000  # Conservative limit for single-pass processing
        
        if estimated_tokens <= max_tokens:
            logger.info(f"Document within limits ({estimated_tokens} tokens), processing directly")
            return self._process_single_pass(combined_text, processing_instruction, system_prompt)
        
        logger.info(f"Document exceeds limits ({estimated_tokens} tokens), using recursive processing")
        return self._process_recursive(combined_text, processing_instruction, system_prompt, depth=0)
    
    def _process_single_pass(
        self,
        text: str,
        instruction: str,
        system_prompt: Optional[str]
    ) -> str:
        """Process text in a single pass."""
        prompt_text = system_prompt or "You are an expert analyst processing documents."
        
        # Escape curly braces in text and instruction to prevent LangChain template variable errors
        instruction_escaped = instruction.replace("{", "{{").replace("}", "}}")
        text_escaped = text.replace("{", "{{").replace("}", "}}")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_text),
            ("human", f"""{instruction_escaped}

Documents:
{text_escaped}

Please analyze and synthesize the information according to the instruction above.""")
        ])
        
        chain = prompt | self.llm
        response = chain.invoke({})
        # Return response with braces unescaped (they were only escaped for the template)
        return response.content
    
    def _process_recursive(
        self,
        text: str,
        instruction: str,
        system_prompt: Optional[str],
        depth: int
    ) -> str:
        """
        Recursively process text by decomposing into chunks and synthesizing.
        
        Args:
            text: Text to process
            instruction: Processing instruction
            system_prompt: System prompt
            depth: Current recursion depth
            
        Returns:
            Synthesized result
        """
        if depth >= self.max_recursion_depth:
            logger.warning(f"Max recursion depth reached ({self.max_recursion_depth}), truncating")
            # Fallback: truncate and process
            max_length = self.chunk_size * 10  # Process ~10 chunks worth
            truncated = text[:max_length] + "\n\n[Document truncated due to recursion limit...]"
            return self._process_single_pass(truncated, instruction, system_prompt)
        
        # Split into chunks
        chunks = self.text_splitter.split_text(text)
        logger.info(f"Recursive processing depth {depth}: split into {len(chunks)} chunks")
        
        # Safety limit: if too many chunks, sample or use smarter strategy
        max_chunks = 50  # Limit to prevent excessive processing
        if len(chunks) > max_chunks:
            logger.warning(f"Too many chunks ({len(chunks)}), sampling first {max_chunks} chunks")
            # Take evenly distributed samples
            step = len(chunks) // max_chunks
            chunks = chunks[::step][:max_chunks]
            logger.info(f"Sampled down to {len(chunks)} chunks")
        
        if len(chunks) == 1:
            # Single chunk, process directly
            return self._process_single_pass(chunks[0], instruction, system_prompt)
        
        # Process chunks in parallel batches
        chunk_results = self._process_chunks_parallel(chunks, instruction, system_prompt, depth)
        
        # If we have too many results, synthesize in batches first
        if len(chunk_results) > 20:
            logger.info(f"Too many chunks ({len(chunk_results)}), synthesizing in batches first")
            chunk_results = self._synthesize_in_batches(chunk_results, instruction, system_prompt)
        
        # Final synthesis
        logger.info(f"Final synthesis of {len(chunk_results)} results at depth {depth}")
        synthesis_text = "\n\n---\n\n".join(chunk_results)
        
        # Use string concatenation to avoid f-string brace interpretation issues
        synthesis_instruction = """Synthesize the following analyses into a coherent response.

Original instruction: """ + instruction + """

Analyses:
""" + synthesis_text + """

Please combine the information, removing redundancy and creating a unified analysis."""
        
        # Process with _process_single_pass which handles escaping internally for LangChain templates
        result = self._process_single_pass(synthesis_text, synthesis_instruction, system_prompt)
        return result
    
    def _process_chunks_parallel(
        self,
        chunks: List[str],
        instruction: str,
        system_prompt: Optional[str],
        depth: int
    ) -> List[str]:
        """Process chunks in parallel batches for speed."""
        chunk_results = []
        
        def process_chunk(chunk_data):
            """Process a single chunk."""
            i, chunk = chunk_data
            try:
                chunk_tokens = len(chunk) // 4
                if chunk_tokens > 20000 and depth < self.max_recursion_depth:  # Still too large, recurse
                    result = self._process_recursive(chunk, instruction, system_prompt, depth + 1)
                else:
                    result = self._process_single_pass(chunk, instruction, system_prompt)
                # Use string concatenation instead of f-string to avoid brace interpretation issues
                return (i, "[Chunk " + str(i+1) + "]\n" + result)
            except Exception as e:
                logger.error(f"Error processing chunk {i+1}: {e}")
                return (i, "[Chunk " + str(i+1) + "]\n[Error: " + str(e) + "]")
        
        # Process chunks in parallel batches
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all chunks
            future_to_chunk = {
                executor.submit(process_chunk, (i, chunk)): i 
                for i, chunk in enumerate(chunks)
            }
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_chunk):
                completed += 1
                if completed % 5 == 0 or completed == len(chunks):
                    logger.info(f"Processed {completed}/{len(chunks)} chunks at depth {depth}")
                try:
                    result = future.result()
                    chunk_results.append(result)
                except Exception as e:
                    logger.error(f"Chunk processing failed: {e}")
                    chunk_idx = future_to_chunk[future]
                    chunk_results.append((chunk_idx, f"[Chunk {chunk_idx+1}]\n[Processing failed]"))
        
        # Sort by original index to maintain order
        chunk_results.sort(key=lambda x: x[0])
        return [result[1] for result in chunk_results]
    
    def _synthesize_in_batches(
        self,
        chunk_results: List[str],
        instruction: str,
        system_prompt: Optional[str]
    ) -> List[str]:
        """Synthesize chunk results in batches to avoid overwhelming the final synthesis."""
        batch_size = 10  # Synthesize 10 chunks at a time
        synthesized = []
        
        for i in range(0, len(chunk_results), batch_size):
            batch = chunk_results[i:i + batch_size]
            batch_text = "\n\n---\n\n".join(batch)
            
            # Use string formatting to avoid f-string brace interpretation issues
            batch_num = i//batch_size + 1
            batch_instruction = """Synthesize the following chunk analyses into a concise summary.

Original instruction: """ + instruction + """

Chunk analyses (batch """ + str(batch_num) + """):
""" + batch_text + """

Create a concise synthesis focusing on key information and removing redundancy."""
            
            batch_result = self._process_single_pass(batch_text, batch_instruction, system_prompt)
            # Use string concatenation to avoid f-string issues
            synthesized.append("[Batch " + str(batch_num) + "]\n" + batch_result)
            logger.info(f"Synthesized batch {batch_num} ({len(batch)} chunks)")
        
        return synthesized
    
    def extract_with_rag_fallback(
        self,
        documents: List[str],
        query: str,
        rag_results: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Extract information using RLM, with RAG results as context.
        
        This combines RAG retrieval with RLM processing for optimal results.
        
        Args:
            documents: Full document texts
            query: Query to extract information for
            rag_results: Optional RAG retrieval results for additional context
            
        Returns:
            Extracted and synthesized information
        """
        # Start with RAG context if available
        context_parts = []
        if rag_results:
            for doc in rag_results:
                text = doc.get("metadata", {}).get("text", doc.get("text", ""))
                source = doc.get("metadata", {}).get("source", "Unknown")
                context_parts.append(f"[Source: {source}]\n{text}")
        
        # Add full documents if needed
        if documents:
            context_parts.extend(documents)
        
        if not context_parts:
            return ""
        
        instruction = f"""Extract and synthesize information relevant to the following query:

Query: {query}

Focus on:
- Key facts and statistics
- Trends and patterns
- Important details
- Quantitative data

Provide a comprehensive synthesis with citations."""
        
        return self.process_documents(context_parts, instruction)

