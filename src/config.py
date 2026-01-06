"""Centralized configuration for loading environment variables."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)


class Config:
    """Configuration class for API keys and settings."""

    # OpenAI
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5-mini-2025-08-07")
    # gpt-5.2-2025-12-11
    OPENAI_MODEL_PRO: str = os.getenv("OPENAI_MODEL_PRO", "gpt-5-mini-2025-08-07")
    
    # Per-agent model configuration
    AGENT_MODELS = {
        "prompt_enhancer": OPENAI_MODEL,
        "strategist": OPENAI_MODEL,
        "scout": OPENAI_MODEL,
        "researcher": OPENAI_MODEL,
        "analyst": OPENAI_MODEL_PRO,
        "writer": OPENAI_MODEL_PRO,
        "auditor": OPENAI_MODEL,
    }
    
    # Anthropic
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    
    # Tavily
    TAVILY_API_KEY: Optional[str] = os.getenv("TAVILY_API_KEY")
    
    # Exa
    EXA_API_KEY: Optional[str] = os.getenv("EXA_API_KEY")
    
    
    LLAMA_CLOUD_API_KEY: Optional[str] = os.getenv("LLAMA_CLOUD_API_KEY")
    
    
    E2B_API_KEY: Optional[str] = os.getenv("E2B_API_KEY")
    
    
    PINECONE_API_KEY: Optional[str] = os.getenv("PINECONE_API_KEY")
    PINECONE_HOST: Optional[str] = os.getenv("PINECONE_HOST")
    PINECONE_ENVIRONMENT: Optional[str] = os.getenv("PINECONE_ENVIRONMENT")
    PINECONE_INDEX_NAME: Optional[str] = os.getenv("PINECONE_INDEX_NAME")
    
   
    LANGCHAIN_TRACING_V2: Optional[str] = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    LANGCHAIN_PROJECT: Optional[str] = os.getenv("LANGCHAIN_PROJECT", "groundtruth")
    LANGCHAIN_ENDPOINT: Optional[str] = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

    @classmethod
    def validate_required_keys(cls) -> list[str]:
        """
        Validate that all required API keys are present.
        
        Returns:
            List of missing required API key names.
        """
        required_keys = [
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
            ("ANTHROPIC_API_KEY", cls.ANTHROPIC_API_KEY),
            ("TAVILY_API_KEY", cls.TAVILY_API_KEY),
            ("LLAMA_CLOUD_API_KEY", cls.LLAMA_CLOUD_API_KEY),
        ]
        
        missing = [key_name for key_name, key_value in required_keys if not key_value]
        return missing

