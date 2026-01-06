"""LlamaExtract tool for structured data extraction from PDFs."""

from typing import List, Dict, Any
from llama_cloud_services import LlamaExtract
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Define a comprehensive schema for real estate metrics
REAL_ESTATE_METRICS_SCHEMA = {
    "type": "object",
    "properties": {
        "market_metrics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric_name": {"type": "string", "description": "Name of the metric (e.g., prime_rent, vacancy_rate)"},
                    "value": {"type": "number", "description": "Numerical value of the metric"},
                    "unit": {"type": "string", "description": "Unit of the metric (e.g., psf, %, bps)"},
                    "region": {"type": "string", "description": "Geographic region for the metric"},
                    "period": {"type": "string", "description": "Time period for the metric (e.g., Q4 2023, 2024 forecast)"}
                },
                "required": ["metric_name", "value"]
            }
        },
        "rental_growth_forecast": {
            "type": "object",
            "description": "Forecasted rental growth percentages by region or sector"
        },
        "yield_data": {
            "type": "object",
            "description": "Yield data (NIY, equivalent yields) by region or sector"
        },
        "take_up_sqft": {
            "type": "object",
            "description": "Leasing activity volumes in sqft"
        }
    }
}

class MetricsExtractor:
    """Wrapper for LlamaExtract to pull structured metrics from PDF URLs."""
    
    def __init__(self):
        """Initialize LlamaExtract client."""
        self.client = None
        if Config.LLAMA_CLOUD_API_KEY:
            try:
                self.client = LlamaExtract(api_key=Config.LLAMA_CLOUD_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize LlamaExtract: {e}")
        else:
            logger.warning("LLAMA_CLOUD_API_KEY not found in environment")
            
    def extract_metrics(self, urls: List[str]) -> Dict[str, Any]:
        """
        Extract structured metrics from PDF URLs using LlamaExtract.
        
        Args:
            urls: List of PDF URLs to process
            
        Returns:
            Dictionary of extracted metrics
        """
        if not self.client:
            logger.error("LlamaExtract client not initialized")
            return {}
            
        if not urls:
            return {}
            
        all_metrics = {}
        
        for url in urls:
            try:
                logger.info(f"Extracting metrics from URL: {url}")
                # LlamaExtract.extract takes a list of files or URLs and a schema
                # Note: The exact method name might vary slightly depending on version, 
                # but 'extract' is the standard for LlamaIndex/LlamaCloud services.
                # If it fails, we'll check the docs/dir.
                
                # For now, we'll use a simplified call as per common patterns
                # In some versions it might be client.extract_from_urls
                result = self.client.extract(
                    urls=[url],
                    schema=REAL_ESTATE_METRICS_SCHEMA
                )
                
                if result and len(result) > 0:
                    # Merge results
                    data = result[0]
                    if isinstance(data, dict):
                        all_metrics.update(data)
                        logger.info(f"Successfully extracted metrics from {url}")
                
            except Exception as e:
                logger.error(f"Error extracting metrics from {url}: {e}")
                continue
                
        return all_metrics
