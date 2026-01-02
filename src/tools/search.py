"""Market search tool using Tavily API."""

from typing import List
from tavily import TavilyClient
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MarketSearch:
    """Wrapper for Tavily search API to find real estate market reports."""
    
    def __init__(self):
        """Initialize Tavily client with API key."""
        self.client = None
        if Config.TAVILY_API_KEY:
            try:
                self.client = TavilyClient(api_key=Config.TAVILY_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize Tavily client: {e}")
        else:
            logger.warning("TAVILY_API_KEY not found in environment")
    
    def find_reports(self, queries: List[str]) -> List[str]:
        """
        Search for market reports using Tavily API.
        
        Args:
            queries: List of search query strings
            
        Returns:
            List of URLs to relevant reports/documents
        """
        if not self.client:
            logger.error("Tavily client not initialized")
            return []
        
        all_urls = []
        
        for query in queries:
            try:
                logger.info(f"Searching Tavily for: {query}")
                response = self.client.search(
                    query=query,
                    search_depth="advanced",
                    max_results=5
                )
                
                # Extract URLs from results
                if response and "results" in response:
                    for result in response["results"]:
                        if "url" in result:
                            all_urls.append(result["url"])
                            logger.info(f"Found URL: {result['url']}")
                
            except Exception as e:
                logger.error(f"Error searching Tavily for '{query}': {e}")
                continue
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in all_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        logger.info(f"Total unique URLs found: {len(unique_urls)}")
        return unique_urls

