"""Configuration management for the Profile Scraping MCP Server."""

import os
from typing import Optional, List
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config(BaseModel):
    """Configuration settings for the Profile Scraping MCP Server."""
    
    # Server settings
    server_name: str = "profile-scraping-server"
    debug: bool = False
    
    # API Keys
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    apollo_api_key: Optional[str] = None
    nubela_api_key: Optional[str] = None
    
    # AI Settings
    preferred_ai_provider: str = "openai"
    ollama_model: str = "llama3"
    
    # Database settings
    database_path: str = "data/profiles.db"
    
    # Rate limiting settings
    linkedin_rate_limit: int = 100  # requests per hour
    apollo_rate_limit: int = 1000   # requests per month
    nubela_rate_limit: int = 100    # requests per month
    
    # Performance settings
    max_concurrent_requests: int = 10
    request_timeout: int = 30
    retry_attempts: int = 3
    
    # Search settings
    default_search_results: int = 20
    max_search_results: int = 100
    default_locations: List[str] = ["US", "UK", "CA", "AU"]
    
    # Cache settings
    cache_ttl: int = 3600  # 1 hour
    enable_caching: bool = True
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        return cls(
            # Server settings
            debug=os.getenv("DEBUG", "false").lower() == "true",
            
            # API Keys
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            apollo_api_key=os.getenv("APOLLO_API_KEY"),
            nubela_api_key=os.getenv("NUBELA_API_KEY"),
            
            # AI Settings
            preferred_ai_provider=os.getenv("PREFERRED_AI_PROVIDER", "openai"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
            
            # Database settings
            database_path=os.getenv("DATABASE_PATH", "data/profiles.db"),
            
            # Performance settings
            max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "10")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
            retry_attempts=int(os.getenv("RETRY_ATTEMPTS", "3")),
            
            # Search settings
            default_search_results=int(os.getenv("DEFAULT_SEARCH_RESULTS", "20")),
            max_search_results=int(os.getenv("MAX_SEARCH_RESULTS", "100")),
            
            # Cache settings
            cache_ttl=int(os.getenv("CACHE_TTL", "3600")),
            enable_caching=os.getenv("ENABLE_CACHING", "true").lower() == "true",
        )
    
    def validate_api_keys(self) -> List[str]:
        """Validate that required API keys are present."""
        missing_keys = []
        
        # Check if at least one AI provider is available
        ai_providers = [
            self.openai_api_key,
            self.gemini_api_key, 
            self.openrouter_api_key,
            self.ollama_base_url
        ]
        
        if not any(ai_providers):
            missing_keys.append("At least one AI provider (OpenAI, Gemini, OpenRouter, or Ollama)")
        
        # Apollo API key is recommended but not required
        if not self.apollo_api_key:
            missing_keys.append("APOLLO_API_KEY (recommended for contact enrichment)")
        
        return missing_keys
    
    def get_available_ai_providers(self) -> List[str]:
        """Get list of available AI providers based on API keys."""
        providers = []
        
        if self.openai_api_key:
            providers.append("openai")
        if self.gemini_api_key:
            providers.append("gemini")
        if self.openrouter_api_key:
            providers.append("openrouter")
        if self.ollama_base_url:
            providers.append("ollama")
            
        return providers


# Global configuration instance
config = Config.from_env()