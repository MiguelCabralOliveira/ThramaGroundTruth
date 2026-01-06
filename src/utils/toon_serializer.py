"""TOON (Token-Oriented Object Notation) serializer for efficient token usage in LLM prompts."""

from typing import Any, Dict, List, Union
from pydantic import BaseModel


def to_toon(obj: Any, indent: int = 0) -> str:
    """
    Convert Python objects (dicts, lists, Pydantic models) to TOON format.
    
    TOON format reduces token usage by 30-60% compared to JSON while maintaining readability.
    
    Args:
        obj: Object to serialize (dict, list, Pydantic model, or primitive)
        indent: Current indentation level (for nested structures)
        
    Returns:
        TOON-formatted string
    """
    if obj is None:
        return "null"
    
    if isinstance(obj, bool):
        return "true" if obj else "false"
    
    if isinstance(obj, (int, float)):
        return str(obj)
    
    if isinstance(obj, str):
        # Escape special characters and wrap in quotes if needed
        if any(c in obj for c in [":", "[", "]", "{", "}", ",", "\n", "\t"]):
            return f'"{obj.replace('"', '\\"')}"'
        return obj
    
    if isinstance(obj, BaseModel):
        return to_toon(obj.model_dump(), indent)
    
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        
        lines = []
        for key, value in obj.items():
            key_str = str(key)
            if isinstance(value, (dict, list)) and value:
                # Complex nested structure
                value_str = to_toon(value, indent + 1)
                lines.append(f"{'  ' * indent}{key_str}: {value_str}")
            else:
                # Simple value
                value_str = to_toon(value, indent)
                lines.append(f"{'  ' * indent}{key_str}: {value_str}")
        
        return "\n".join(lines) if lines else "{}"
    
    if isinstance(obj, list):
        if not obj:
            return "[]"
        
        # Check if all items are simple types (can use compact format)
        all_simple = all(isinstance(item, (str, int, float, bool, type(None))) for item in obj)
        
        if all_simple and len(obj) > 0:
            # Compact format: [item1, item2, item3]
            items = [to_toon(item, indent) for item in obj]
            return f"[{', '.join(items)}]"
        else:
            # Multi-line format for complex items
            lines = []
            for item in obj:
                item_str = to_toon(item, indent + 1)
                lines.append(f"{'  ' * indent}- {item_str}")
            return "\n".join(lines) if lines else "[]"
    
    return str(obj)


def pydantic_to_toon(model: BaseModel) -> str:
    """
    Convert a Pydantic model directly to TOON format.
    
    Args:
        model: Pydantic model instance
        
    Returns:
        TOON-formatted string
    """
    return to_toon(model.model_dump())


def dict_to_toon(data: Dict[str, Any]) -> str:
    """
    Convert a dictionary to TOON format.
    
    Args:
        data: Dictionary to convert
        
    Returns:
        TOON-formatted string
    """
    return to_toon(data)

