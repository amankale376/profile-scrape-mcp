"""Basic tests for the Profile Scraping MCP server."""

import pytest
import asyncio
from unittest.mock import Mock, patch

from src.models.requests import SearchProfilesRequest, ExtractProfileRequest
from src.models.responses import ProfileData, SearchMetadata


class TestProfileScrapingMCP:
    """Test cases for Profile Scraping MCP server."""
    
    def test_search_profiles_request_validation(self):
        """Test SearchProfilesRequest validation."""
        # Valid request
        request = SearchProfilesRequest(
            query="software engineer",
            num_results=10,
            locations=["San Francisco"]
        )
        assert request.query == "software engineer"
        assert request.num_results == 10
        assert request.locations == ["San Francisco"]
        
        # Test defaults
        minimal_request = SearchProfilesRequest(query="test")
        assert minimal_request.num_results == 10
        assert minimal_request.locations is None
        assert minimal_request.use_global_search is False
    
    def test_extract_profile_request_validation(self):
        """Test ExtractProfileRequest validation."""
        request = ExtractProfileRequest(
            profile_url="https://linkedin.com/in/johndoe",
            include_contact_info=True
        )
        assert request.profile_url == "https://linkedin.com/in/johndoe"
        assert request.include_contact_info is True
        assert request.include_activity_summary is False
    
    def test_profile_data_model(self):
        """Test ProfileData model."""
        profile = ProfileData(
            profile_url="https://linkedin.com/in/johndoe",
            name="John Doe",
            headline="Software Engineer",
            company="Tech Corp",
            job_title="Senior Engineer",
            location="San Francisco, CA"
        )
        assert profile.name == "John Doe"
        assert profile.company == "Tech Corp"
    
    def test_search_metadata_model(self):
        """Test SearchMetadata model."""
        metadata = SearchMetadata(
            query_used="software engineer",
            original_query="software engineer",
            locations_searched=["San Francisco"],
            total_urls_found=25,
            duplicates_removed=5,
            search_time_ms=1500
        )
        assert metadata.total_urls_found == 25
        assert metadata.duplicates_removed == 5
        assert metadata.search_time_ms == 1500


class TestConfigValidation:
    """Test configuration validation."""
    
    @patch.dict('os.environ', {
        'APOLLO_API_KEY': 'test_apollo_key',
        'OPENAI_API_KEY': 'test_openai_key'
    })
    def test_config_with_api_keys(self):
        """Test configuration with API keys."""
        from src.utils.config import Config
        config = Config()
        
        assert config.apollo_api_key == 'test_apollo_key'
        assert config.openai_api_key == 'test_openai_key'
        
        # Test API key validation
        missing_keys = config.validate_api_keys()
        assert 'apollo' not in missing_keys
        assert 'openai' not in missing_keys
    
    def test_config_defaults(self):
        """Test configuration defaults."""
        from src.utils.config import Config
        config = Config()
        
        assert config.server_name == "profile-scraping-mcp"
        assert config.linkedin_rate_limit == 30
        assert config.apollo_rate_limit == 100
        assert config.cache_ttl == 3600


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self):
        """Test basic rate limiter functionality."""
        from src.utils.rate_limiter import RateLimiter
        
        # Create rate limiter with high limit for testing
        limiter = RateLimiter(max_requests=10, time_window=1)
        
        # Should allow requests within limit
        for _ in range(5):
            await limiter.acquire()
        
        # Check stats
        stats = limiter.get_stats()
        assert stats['requests_made'] == 5
        assert stats['requests_remaining'] >= 5


class TestCacheManager:
    """Test caching functionality."""
    
    def test_cache_basic_operations(self):
        """Test basic cache operations."""
        from src.utils.cache import CacheManager
        import tempfile
        import os
        
        # Use temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            cache = CacheManager(db_path=tmp.name, ttl=3600)
            
            # Test set and get
            cache.set('test_key', {'data': 'test_value'})
            result = cache.get('test_key')
            
            assert result is not None
            assert result['data'] == 'test_value'
            
            # Test non-existent key
            assert cache.get('non_existent') is None
            
            # Cleanup
            os.unlink(tmp.name)


class TestAIClient:
    """Test AI client functionality."""
    
    @pytest.mark.asyncio
    async def test_ai_client_initialization(self):
        """Test AI client initialization."""
        from src.integrations.ai_client import AIClient
        
        client = AIClient()
        assert client is not None
        
        # Test provider availability check
        providers = client.get_available_providers()
        assert isinstance(providers, list)


class TestApolloClient:
    """Test Apollo client functionality."""
    
    @pytest.mark.asyncio
    async def test_apollo_client_initialization(self):
        """Test Apollo client initialization."""
        from src.integrations.apollo_client import ApolloClient
        
        client = ApolloClient()
        assert client is not None
        assert client.base_url == "https://api.apollo.io/v1"


if __name__ == "__main__":
    pytest.main([__file__])