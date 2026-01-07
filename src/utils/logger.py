"""Custom logging utility with colored output."""

import logging
import sys
import json
import os
from pathlib import Path
from typing import Optional, Any
from datetime import datetime

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',        # Green
        'WARNING': '\033[33m',     # Yellow
        'ERROR': '\033[31m',       # Red
        'CRITICAL': '\033[35m',    # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


class LangSmithFilter(logging.Filter):
    """Filter to suppress LangSmith multipart ingest warnings."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Suppress LangSmith multipart ingest errors (non-critical warnings)
        message = str(record.getMessage())
        if "Failed to send compressed multipart ingest" in message:
            return False
        if "Failed to multipart ingest runs" in message:
            return False
        if "langsmith.utils.LangSmithError" in message and "403" in message and "multipart" in message:
            return False
        return True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger with colored output.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name or __name__)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Console handler with colored formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    formatter = ColoredFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    # Add filter to suppress LangSmith multipart warnings
    langsmith_filter = LangSmithFilter()
    logger.addFilter(langsmith_filter)
    
    # Also filter langsmith logger directly
    langsmith_logger = logging.getLogger("langsmith")
    if not langsmith_logger.filters:
        langsmith_logger.addFilter(langsmith_filter)
        langsmith_logger.setLevel(logging.WARNING)  # Only show warnings and errors, not info
    
    return logger


def save_agent_io(agent_name: str, input_data: Any, output_data: Any):
    """
    Save the input and output of an agent to a JSON file for debugging.
    
    Args:
        agent_name: Name of the agent (e.g., 'Analyst', 'Writer')
        input_data: The input data (e.g., state)
        output_data: The output data (e.g., result)
    """
    try:
        # Create outputs/debug directory if it doesn't exist
        debug_dir = Path("outputs/debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{agent_name}.json"
        
        # Serialize only serializable data
        def json_serial(obj):
            if isinstance(obj, (datetime,)):
                return obj.isoformat()
            if hasattr(obj, "dict"):
                return obj.dict()
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            return str(obj)

        log_data = {
            "agent": agent_name,
            "timestamp": datetime.now().isoformat(),
            "input": input_data,
            "output": output_data
        }
        
        try:
            with open(debug_dir / filename, "w", encoding="utf-8") as f:
                json.dump(log_data, f, default=json_serial, indent=2)
        except TypeError as e:
            # Fallback for circular references or complex objects
            with open(debug_dir / filename, "w", encoding="utf-8") as f:
                f.write(str(log_data))
                
    except Exception as e:
        print(f"Error saving debug IO for {agent_name}: {e}")
