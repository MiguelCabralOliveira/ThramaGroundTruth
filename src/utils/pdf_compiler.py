"""PDF compilation utility using WeasyPrint and Jinja2."""

import os
import markdown
from typing import Optional, Dict, Any, List
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PDFCompiler:
    """PDF compiler using WeasyPrint for professional report generation."""
    
    def __init__(self):
        """Initialize PDF compiler."""
        self.output_dir = "outputs/reports"
        self.templates_dir = "src/templates"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Add markdown filter with tables extension
        self.env.filters['markdown'] = lambda text: markdown.markdown(
            text, 
            extensions=['tables', 'fenced_code']
        ) if text else ""
        
        logger.info("PDF compiler initialized with WeasyPrint support")
    
    def compile_report_to_pdf(self, report_data: Dict[str, Any], charts: List[str], user_request: str, output_filename: str) -> Optional[str]:
        """
        Compile report data to PDF using HTML template.
        
        Args:
            report_data: Dictionary containing report sections
            charts: List of paths to chart images
            user_request: The original user request/prompt
            output_filename: Desired output filename (without extension)
            
        Returns:
            Path to generated PDF file
        """
        try:
            # Load template
            template = self.env.get_template("report_template.html")
            
            # Render HTML
            from datetime import datetime
            html_content = template.render(
                report=report_data,
                charts=charts,
                user_request=user_request,
                date=datetime.now().strftime("%B %d, %Y")
            )
            
            # Save HTML for debugging
            html_path = os.path.join(self.output_dir, f"{output_filename}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"HTML report saved to: {html_path}")
            
            # Generate PDF
            pdf_path = os.path.join(self.output_dir, f"{output_filename}.pdf")
            logger.info(f"Compiling HTML to PDF: {pdf_path}")
            
            HTML(string=html_content, base_url=os.getcwd()).write_pdf(pdf_path)
            
            logger.info(f"PDF generated successfully: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Error compiling PDF: {e}")
            return None

