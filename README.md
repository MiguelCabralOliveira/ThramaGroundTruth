# GroundTruth - Real Estate Market Intelligence Agent

A comprehensive AI-powered system that uses LangGraph to orchestrate 6 specialized agents to research, analyze, and generate professional real estate market intelligence reports.

## Overview

GroundTruth is an agentic RAG (Retrieval-Augmented Generation) backend that transforms user research requests into comprehensive market intelligence reports. The system uses multiple AI agents working in parallel to search, analyze, and synthesize real estate market data into institutional-quality reports.

## Features

- **Multi-Agent Architecture**: 6 specialized agents working in orchestrated workflow
- **Automated Research**: Searches and ingests market reports from multiple sources
- **Qualitative & Quantitative Analysis**: Combines narrative insights with data-driven metrics
- **Vector Database Integration**: Pinecone for semantic search and document storage
- **Professional PDF Generation**: Typst-based PDF compilation with fallback to markdown
- **Quality Assurance**: Built-in audit and revision loop for report quality
- **Error Handling**: Robust error handling prevents workflow crashes

## Architecture

### Agent Workflow

```
User Request
    ↓
[Strategist] → Converts request to structured research plan
    ↓
[Scout] → Searches for and ingests PDF documents
    ↓
    ├─→ [Researcher] → Qualitative analysis (parallel)
    └─→ [Analyst] → Quantitative metrics extraction (parallel)
    ↓
[Writer] → Generates comprehensive report
    ↓
[Auditor] → Reviews and critiques report
    ↓
    ├─→ Approved → End
    └─→ Rejected → Loop back to Writer (with feedback)
```

### The 6 Agents

All agents use configurable LLM models (set via `OPENAI_MODEL` and `ANTHROPIC_MODEL` environment variables):

1. **Strategist** (Anthropic): Converts user requests into structured research plans
2. **Scout** (Anthropic): Searches for market reports and ingests PDF documents
3. **Researcher** (Anthropic): Performs qualitative research synthesis
4. **Analyst** (Anthropic): Extracts quantitative metrics and generates charts
5. **Writer** (Anthropic): Writes institutional-quality reports
6. **Auditor** (Anthropic): Reviews reports for quality and completeness

**Note**: Model selection is centralized in `src/config.py`. Change models by updating `OPENAI_MODEL` or `ANTHROPIC_MODEL` in your `.env` file.

## Installation

### Prerequisites

- Python 3.11 or higher
- Typst CLI (optional, for PDF generation)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ThramaGroundTruth
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Typst (optional, for PDF generation)**
   - Download from [typst.app](https://typst.app/docs/getting-started/installation)
   - Or install via package manager
   - The system will fallback to markdown if Typst is not available

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Required API Keys
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
TAVILY_API_KEY=your_tavily_api_key
LLAMA_CLOUD_API_KEY=your_llama_cloud_api_key

# LLM Model Configuration (Optional - defaults shown)
OPENAI_MODEL=gpt-4o
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929

# Optional API Keys
EXA_API_KEY=your_exa_api_key
E2B_API_KEY=your_e2b_api_key

# Pinecone Configuration (Optional)
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_HOST=https://your-index.svc.aped-4627-b74a.pinecone.io
PINECONE_ENVIRONMENT=us-east-1-aws
PINECONE_INDEX_NAME=your_index_name

# LangSmith Configuration (Optional, for observability)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=groundtruth
```

### Pinecone Setup

If using Pinecone vector storage:

1. Create a Pinecone index with:
   - **Dimensions**: 1024
   - **Metric**: cosine
   - **Model**: text-embedding-3-small (1024 dimensions)

2. Add the host URL to `PINECONE_HOST` in your `.env` file

## Usage

### Basic Usage

Run the main script:

```bash
python run.py
```

The script will process the hardcoded example request: *"Analyze the Industrial Outdoor Storage market in Texas"*

### Custom Requests

Edit `run.py` to change the `user_request` variable:

```python
user_request = "Your custom research request here"
```

### Output

Reports are saved to:
- **Markdown**: `outputs/reports/final_report.md`
- **PDF**: `outputs/reports/final_report.pdf` (if Typst is available)
- **Charts**: `outputs/images/` (PNG files)

## Visualization & Observability

### LangGraph Studio (Visual Debugging)

LangGraph Studio provides a visual interface to debug and monitor your agent workflow in real-time.

**Setup:**

1. **Install LangGraph CLI** (already in requirements.txt):
   ```bash
   pip install langgraph-cli
   ```

2. **Start LangGraph Studio**:
   ```bash
   langgraph dev
   ```

3. **Access the interface**:
   - Open your browser to `http://localhost:8123`
   - You'll see a visual representation of your agent graph
   - Run workflows directly from the interface
   - View state changes in real-time
   - Edit prompts and test changes without restarting

**Features:**
- 🎨 Visual graph representation
- 🔄 Real-time state monitoring
- ✏️ Edit prompts on-the-fly
- 🐛 Step-by-step debugging
- 📊 Execution history
- 🔍 State inspection at each node

### LangSmith (Observability & Monitoring)

LangSmith provides comprehensive observability for all LLM calls, agent executions, and system performance.

**Setup:**

1. **Get LangSmith API Key**:
   - Sign up at [smith.langchain.com](https://smith.langchain.com)
   - Get your API key from settings

2. **Configure in `.env`**:
   ```env
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=your_langsmith_api_key
   LANGCHAIN_PROJECT=groundtruth
   ```

3. **Run your workflow**:
   ```bash
   python run.py
   ```

4. **View traces**:
   - Go to [smith.langchain.com](https://smith.langchain.com)
   - Navigate to your project
   - See all agent executions, LLM calls, and state changes

**Features:**
- 📈 Performance metrics
- 💰 Token usage and cost tracking
- 🔍 Detailed trace inspection
- 🐛 Error debugging
- 📊 Analytics and insights
- 🔄 Execution history
- ⚡ Latency monitoring

**What you can see:**
- Every LLM call (input/output)
- Agent execution timeline
- State transitions
- Token counts and costs
- Error traces
- Performance bottlenecks

## Project Structure

```
ThramaGroundTruth/
├── .env                      # Environment variables (create this)
├── .gitignore
├── requirements.txt          # Python dependencies
├── run.py                    # Main execution script
│
├── data/                     # Temporary storage
│   ├── raw_pdfs/            # Downloaded PDFs
│   └── vector_store/        # Local vector cache
│
├── outputs/                  # Final artifacts
│   ├── images/              # Generated charts
│   └── reports/             # Final reports (PDF/MD)
│
└── src/
    ├── config.py            # Configuration management
    ├── state.py             # LangGraph state definition
    ├── schemas.py           # Pydantic models
    ├── graph.py             # LangGraph orchestration
    │
    ├── agents/              # Agent implementations
    │   ├── strategist.py
    │   ├── scout.py
    │   ├── researcher.py
    │   ├── analyst.py
    │   ├── writer.py
    │   └── auditor.py
    │
    ├── tools/               # External API wrappers
    │   ├── search.py        # Tavily search
    │   ├── pdf_parser.py    # LlamaParse
    │   ├── chart_gen.py     # Matplotlib charts
    │   └── database.py      # Pinecone vector DB
    │
    ├── prompts/             # Agent prompts (Markdown)
    │   ├── 01_strategist.md
    │   ├── 02_scout.md
    │   ├── 03_researcher.md
    │   ├── 04_analyst.md
    │   ├── 05_writer.md
    │   └── 06_auditor.md
    │
    └── utils/               # Utilities
        ├── logger.py        # Colored logging
        └── pdf_compiler.py  # Typst PDF generation
```

## API Keys Required

### Required
- **OpenAI API Key**: For Strategist, Scout, and Auditor agents
- **Anthropic API Key**: For Researcher, Analyst, and Writer agents
- **Tavily API Key**: For market report search
- **Llama Cloud API Key**: For PDF parsing

### Optional
- **Exa API Key**: Alternative search (not currently used)
- **E2B API Key**: Code execution sandbox (not currently used)
- **Pinecone API Key**: Vector database storage
- **LangSmith API Key**: For observability and monitoring (highly recommended)

## How It Works

1. **User Request**: Input a research query (e.g., "Analyze the Industrial Outdoor Storage market in Texas")

2. **Strategist**: Converts the request into a structured research plan with:
   - Target sector
   - Geography
   - Search queries
   - Currency and units

3. **Scout**: 
   - Searches Tavily for relevant market reports
   - Selects best PDF URLs using LLM
   - Parses PDFs using LlamaParse
   - Stores parsed text in state

4. **Researcher & Analyst** (Parallel):
   - **Researcher**: Synthesizes qualitative insights (trends, drivers, risks)
   - **Analyst**: Extracts quantitative metrics and generates charts

5. **Writer**: Combines all research into a comprehensive report with:
   - Executive summary
   - Market overview
   - Data analysis
   - Risk assessment
   - Conclusion

6. **Auditor**: Reviews the report for:
   - Completeness
   - Consistency
   - Accuracy
   - Quality

7. **Revision Loop**: If rejected, the report goes back to Writer with feedback for improvement

## Output Format

Reports include:

- **Executive Summary**: Key findings and investment thesis
- **Market Overview**: Sector and geography analysis
- **Data Analysis**: Quantitative metrics with charts
- **Risk Assessment**: Comprehensive risk analysis
- **Conclusion**: Recommendations and outlook

## Troubleshooting

### Common Issues

**Missing API Keys**
- Ensure all required API keys are in `.env`
- Run `python -c "from src.config import Config; print(Config.validate_required_keys())"` to check

**Typst Not Found**
- System will automatically fallback to markdown
- Install Typst CLI for PDF generation
- Check installation: `typst --version`

**Pinecone Connection Errors**
- Verify `PINECONE_HOST` is correct
- Check API key permissions
- Ensure index exists and has correct dimensions (1024)

**Import Errors**
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt` again
- Check Python version: `python --version` (requires 3.11+)

## Development

### Code Style

- Follow PEP 8 standards
- Use type hints for all functions
- Separate logic (.py) from prompts (.md)
- All tools must have try/except error handling

### Architecture Rules

1. Prompts must be in `src/prompts/` (Markdown files)
2. Agents must accept `AgentGraphState` and return dict updates
3. Use Pydantic models for structured output
4. Backend logic only (no UI libraries)

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## Support

For issues and questions, please [create an issue](link-to-issues) or contact [your contact info].
