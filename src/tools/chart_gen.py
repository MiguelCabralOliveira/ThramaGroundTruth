"""Chart generation tool using matplotlib (local execution for MVP)."""

import os
from typing import Dict, Any
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DataAnalyst:
    """Tool for generating charts from data using matplotlib."""
    
    def __init__(self):
        """Initialize chart generator."""
        self.output_dir = "outputs/images"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_chart(self, data: Dict[str, Any], title: str) -> str:
        """
        Generate a chart from data and save as PNG.
        
        Args:
            data: Dictionary containing chart data (format depends on chart type)
            title: Chart title
            
        Returns:
            Path to the generated chart image file
        """
        try:
            logger.info(f"Generating chart: {title}")
            
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Determine chart type from data structure
            if "x" in data and "y" in data:
                # Line or bar chart
                if "chart_type" in data and data["chart_type"] == "bar":
                    ax.bar(data["x"], data["y"])
                else:
                    ax.plot(data["x"], data["y"], marker='o')
            elif "values" in data and "labels" in data:
                # Pie chart
                ax.pie(data["values"], labels=data["labels"], autopct='%1.1f%%')
            elif "categories" in data and "values" in data:
                # Bar chart with categories
                ax.bar(data["categories"], data["values"])
            else:
                # Default: try to plot as key-value pairs
                keys = list(data.keys())
                values = [v for v in data.values() if isinstance(v, (int, float))]
                if values:
                    ax.bar(keys[:len(values)], values)
                else:
                    logger.warning(f"Could not determine chart type for data: {data}")
                    plt.close(fig)
                    return ""
            
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
            filename = f"{safe_title}_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            
            # Save chart
            plt.tight_layout()
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            logger.info(f"Chart saved to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error generating chart '{title}': {e}")
            return ""

