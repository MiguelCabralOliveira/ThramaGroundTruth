"""PDF parsing tool using LlamaParse API."""

from typing import List
from llama_parse import LlamaParse
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PDFIngest:
    """Wrapper for LlamaParse to extract text from PDF URLs."""
    
    def __init__(self):
        """Initialize LlamaParse client with API key."""
        self.parser = None
        if Config.LLAMA_CLOUD_API_KEY:
            try:
                self.parser = LlamaParse(
                    api_key=Config.LLAMA_CLOUD_API_KEY,
                    result_type="markdown"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize LlamaParse: {e}")
        else:
            logger.warning("LLAMA_CLOUD_API_KEY not found in environment")
    
    def parse_urls(self, urls: List[str]) -> List[str]:
        """
        Parse PDFs from URLs and extract markdown text.
        
        Args:
            urls: List of PDF URLs to parse
            
        Returns:
            List of markdown text strings (one per PDF)
        """
        if not self.parser:
            logger.error("LlamaParse not initialized")
            return []
        
        parsed_documents = []
        
        for url in urls:
            try:
                logger.info(f"Parsing PDF from URL: {url}")
                documents = self.parser.load_data(url)
                
                # Combine all pages into a single markdown string
                full_text = "\n\n".join([doc.text for doc in documents if hasattr(doc, 'text')])
                if full_text:
                    parsed_documents.append(full_text)
                    logger.info(f"Successfully parsed PDF: {len(full_text)} characters")
                else:
                    logger.warning(f"No text extracted from URL: {url}")
                    
            except Exception as e:
                logger.error(f"Error parsing PDF from '{url}': {e}")
                continue
        
        logger.info(f"Successfully parsed {len(parsed_documents)} PDFs")
        return parsed_documents

