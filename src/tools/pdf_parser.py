"""PDF parsing tool using PyMuPDF (fitz)."""

import requests
import fitz  # PyMuPDF
from typing import List
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PDFIngest:
    """Wrapper for PyMuPDF to extract text from PDF URLs."""
    
    def __init__(self):
        """Initialize PDFIngest."""
        # No API key needed for PyMuPDF
        pass
    
    def parse_urls(self, urls: List[str]) -> List[str]:
        """
        Parse PDFs from URLs and extract text using PyMuPDF.
        
        Args:
            urls: List of PDF URLs to parse
            
        Returns:
            List of text strings (one per PDF)
        """
        parsed_documents = []
        
        for url in urls:
            try:
                logger.info(f"Downloading PDF from URL: {url}")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                # Open PDF from bytes
                with fitz.open(stream=response.content, filetype="pdf") as doc:
                    text = ""
                    for page in doc:
                        text += page.get_text() + "\n\n"
                    
                    if text.strip():
                        parsed_documents.append(text)
                        logger.info(f"Successfully parsed PDF: {len(text)} characters")
                    else:
                        logger.warning(f"No text extracted from URL: {url}")
                    
            except Exception as e:
                logger.error(f"Error parsing PDF from '{url}': {e}")
                continue
        
        logger.info(f"Successfully parsed {len(parsed_documents)} PDFs")
        return parsed_documents

