# Profile Scraping MCP Server

A comprehensive Fast MCP server for LinkedIn profile scraping, enrichment, and AI-powered validation. This server provides powerful tools for finding, extracting, and enriching LinkedIn profile data with contact information and relevance scoring.

## Features

### 🔍 Core Tools
- **search_profiles**: Search LinkedIn for profiles matching specific criteria
- **extract_profile**: Extract detailed information from LinkedIn profile URLs
- **enrich_profiles**: Add contact information using Apollo.io and Nubela APIs
- **validate_profiles**: AI-powered relevance filtering and confidence scoring
- **get_search_history**: Retrieve search history and cached results

### 🚀 Key Capabilities
- **Multi-location Global Search**: Search across multiple geographic regions
- **AI-Powered Validation**: Use OpenAI, Gemini, OpenRouter, or Ollama for profile relevance
- **Contact Enrichment**: Apollo.io and Nubela API integration for contact details
- **Intelligent Caching**: SQLite-based caching with TTL for performance
- **Rate Limiting**: Built-in rate limiting for all external APIs
- **Async Processing**: Concurrent profile processing with semaphores
- **Comprehensive Logging**: Structured logging with Loguru

## Installation

### Prerequisites
- Python 3.8+
- pip or poetry

### Setup

#### Quick Installation (Recommended)

1. **Clone and navigate to the project:**
```bash
cd profile-scraping-mcp
```

2. **Run the automated build and install script:**
```bash
python scripts/build_and_install.py
```

This script will automatically:
- Check Python version compatibility
- Clean previous build artifacts
- Try multiple installation methods
- Test the installation
- Provide next steps

#### Manual Installation

If the automated script fails, try these methods:

**Method 1: Hatchling (Recommended)**
```bash
# Install build tools
pip install --upgrade build hatchling setuptools wheel

# Build and install
python -m build
pip install -e .
```

**Method 2: Setuptools**
```bash
python setup.py develop
```

**Method 3: Direct Requirements**
```bash
pip install -r requirements.txt
# Note: You may need to manually add src/ to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

#### Post-Installation Setup

3. **Test installation:**
```bash
python scripts/test_install.py
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

5. **Create data directory:**
```bash
mkdir -p data
```

6. **Validate setup:**
```bash
python scripts/run_server.py --validate-keys
```

#### Troubleshooting Installation

If you encounter build issues:

1. **Check Python version:**
```bash
python --version  # Should be 3.11+
```

2. **Upgrade pip and build tools:**
```bash
pip install --upgrade pip setuptools wheel build hatchling
```

3. **Clear cache and retry:**
```bash
pip cache purge
python scripts/build_and_install.py
```

4. **Install minimal dependencies:**
```bash
pip install fastmcp pydantic httpx beautifulsoup4 loguru python-dotenv
```

## Configuration

### Required API Keys

Add these to your `.env` file:

```env
# Essential for contact enrichment
APOLLO_API_KEY=your_apollo_api_key_here
NUBELA_API_KEY=your_nubela_api_key_here

# Required for AI validation (choose at least one)
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
```

### API Key Sources

- **Apollo.io**: [Get API key](https://apolloapi.com/)
- **Nubela (Proxycurl)**: [Get API key](https://rapidapi.com/nubela-nubela-default/api/proxycurl-linkedin-company-api/)
- **OpenAI**: [Get API key](https://platform.openai.com/api-keys)
- **Google Gemini**: [Get API key](https://makersuite.google.com/app/apikey)
- **OpenRouter**: [Get API key](https://openrouter.ai/keys)
- **Ollama**: [Install locally](https://ollama.ai/)

## Usage

### Starting the Server

```bash
# Run the MCP server
python -m profile_scraping_mcp

# Or using the entry point
profile-scraping-mcp
```

### Tool Examples

#### 1. Search for Profiles
```json
{
  "tool": "search_profiles",
  "arguments": {
    "query": "software engineer python",
    "num_results": 20,
    "locations": ["San Francisco", "New York"],
    "use_global_search": false
  }
}
```

#### 2. Extract Profile Details
```json
{
  "tool": "extract_profile",
  "arguments": {
    "profile_url": "https://linkedin.com/in/johndoe",
    "include_contact_info": true,
    "include_activity_summary": true,
    "apollo_api_key": "optional_override_key"
  }
}
```

#### 3. Enrich Multiple Profiles
```json
{
  "tool": "enrich_profiles",
  "arguments": {
    "profile_urls": [
      "https://linkedin.com/in/johndoe",
      "https://linkedin.com/in/janedoe"
    ],
    "batch_size": 5,
    "apollo_api_key": "your_apollo_key",
    "nubela_api_key": "your_nubela_key"
  }
}
```

#### 4. Validate Profile Relevance
```json
{
  "tool": "validate_profiles",
  "arguments": {
    "profiles": [
      {
        "profile_url": "https://linkedin.com/in/johndoe",
        "name": "John Doe",
        "headline": "Senior Software Engineer",
        "company": "Tech Corp"
      }
    ],
    "search_criteria": "python developer with machine learning experience",
    "confidence_threshold": 0.7,
    "ai_provider": "openai"
  }
}
```

#### 5. Get Search History
```json
{
  "tool": "get_search_history",
  "arguments": {
    "limit": 50,
    "include_results": true
  }
}
```

## Architecture

### Project Structure
```
profile-scraping-mcp/
├── src/
│   ├── models/           # Pydantic request/response models
│   ├── utils/            # Utilities (config, logging, cache, rate limiting)
│   ├── core/             # Core scraping functionality
│   ├── integrations/     # External API clients
│   ├── services/         # Business logic services
│   └── server.py         # Fast MCP server implementation
├── tests/                # Test suite
├── data/                 # Database and cache files
├── .env.example          # Environment configuration template
└── README.md
```

### Key Components

- **Fast MCP Framework**: Simplified MCP server development
- **Pydantic Models**: Type-safe request/response validation
- **SQLite Caching**: Performance optimization with TTL
- **Rate Limiting**: Token bucket algorithm for API protection
- **Async Processing**: Concurrent operations with semaphores
- **Multi-provider AI**: Support for multiple AI services

## Performance & Limits

### Rate Limits (per minute)
- LinkedIn Scraping: 30 requests
- Apollo.io API: 100 requests
- Nubela API: 50 requests
- AI APIs: 60 requests

### Caching
- Profile data: 1 hour TTL
- Search results: 30 minutes TTL
- Enrichment data: 2 hours TTL
- Validation results: 1 hour TTL

### Concurrent Processing
- Profile extraction: 5 concurrent
- Enrichment: 5 concurrent
- AI validation: 3 concurrent

## Error Handling

The server includes comprehensive error handling:

- **Rate Limit Exceeded**: Automatic retry with exponential backoff
- **API Failures**: Graceful fallback to alternative providers
- **Network Issues**: Retry logic with configurable attempts
- **Invalid Data**: Detailed error messages and partial results
- **Cache Failures**: Fallback to direct API calls

## Monitoring & Logging

### Structured Logging
- Request/response logging
- Performance metrics
- Error tracking
- API usage statistics

### Health Checks
- API key validation
- Database connectivity
- Cache performance
- Rate limiter status

## Development

### Running Tests
```bash
# Install test dependencies
pip install -e ".[test]"

# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

### Code Quality
```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

## Deployment

### Docker Deployment
```bash
# Build image
docker build -t profile-scraping-mcp .

# Run container
docker run -d \
  --name profile-scraping-mcp \
  -p 8000:8000 \
  --env-file .env \
  profile-scraping-mcp
```

### Environment Variables
See `.env.example` for all configuration options.

## Troubleshooting

### Common Issues

1. **API Key Errors**
   - Verify API keys in `.env` file
   - Check API key permissions and quotas
   - Test with `validate_api_keys` method

2. **Rate Limiting**
   - Reduce concurrent requests
   - Increase delays between batches
   - Monitor rate limiter statistics

3. **Cache Issues**
   - Check database file permissions
   - Clear cache with `clear_cache` methods
   - Verify disk space availability

4. **LinkedIn Scraping**
   - Use proxy rotation if blocked
   - Implement session management
   - Respect robots.txt and terms of service

### Debug Mode
Enable debug logging:
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational and research purposes. Users are responsible for:
- Complying with LinkedIn's Terms of Service
- Respecting rate limits and API usage policies
- Ensuring data privacy and protection compliance
- Following applicable laws and regulations

Use responsibly and ethically.