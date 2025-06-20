"""Main Fast MCP server for Profile Scraping."""

import time
import asyncio
from typing import Dict, Any, List
from fastmcp import FastMCP
from pathlib import Path

from .models.requests import (
    SearchProfilesRequest,
    ExtractProfileRequest,
    EnrichProfilesRequest,
    ValidateProfilesRequest,
    GetSearchHistoryRequest,
)
from .models.responses import (
    SearchProfilesResponse,
    ExtractProfileResponse,
    EnrichProfilesResponse,
    ValidateProfilesResponse,
    GetSearchHistoryResponse,
    ProfileData,
    ContactInfo,
    CompanyInfo,
    SearchMetadata,
    ValidationResult,
    EnrichmentResult,
    SearchHistoryItem,
)
from .services.profile_service import ProfileService
from .services.search_service import SearchService
from .services.enrichment_service import EnrichmentService
from .services.validation_service import ValidationService
from .utils.config import config
from .utils.logger import get_logger, setup_logger
from .utils.cache import CacheManager

# Setup logging
setup_logger(level="INFO" if not config.debug else "DEBUG")
logger = get_logger(__name__)

# Initialize Fast MCP app
app = FastMCP(config.server_name)

# Initialize services
profile_service = ProfileService()
search_service = SearchService()
enrichment_service = EnrichmentService()
validation_service = ValidationService()

# Initialize cache
cache_manager = CacheManager(
    db_path=config.database_path.replace('.db', '_cache.db'),
    ttl=config.cache_ttl
)

logger.info(f"Profile Scraping MCP Server initialized")
logger.info(f"Available AI providers: {config.get_available_ai_providers()}")


@app.tool("search_profiles")
async def search_profiles(request: SearchProfilesRequest) -> Dict[str, Any]:
    """
    Search for LinkedIn profiles based on keywords and criteria.
    
    This tool searches LinkedIn for profiles matching the specified criteria,
    with support for location filtering and global multi-location search.
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting profile search: '{request.query}' (num_results: {request.num_results})")
        
        # Check cache first
        cache_key = f"search:{request.query}:{request.num_results}:{request.use_global_search}"
        if config.enable_caching:
            cached_result = cache_manager.get(cache_key)
            if cached_result:
                logger.info("Returning cached search results")
                return cached_result
        
        # Perform search
        if request.use_global_search:
            profiles, metadata = await search_service.global_search(
                query=request.query,
                target_results=request.target_results,
                locations=request.locations
            )
        else:
            profiles, metadata = await search_service.basic_search(
                query=request.query,
                num_results=request.num_results,
                locations=request.locations
            )
        
        # Prepare response
        search_time_ms = int((time.time() - start_time) * 1000)
        
        response_data = {
            "profiles_found": len(profiles),
            "search_time_ms": search_time_ms,
            "profiles": [profile.dict() for profile in profiles],
            "search_metadata": metadata.dict()
        }
        
        # Cache the result
        if config.enable_caching:
            cache_manager.set(cache_key, response_data, ttl=1800)  # 30 minutes
        
        logger.info(f"Search completed: found {len(profiles)} profiles in {search_time_ms}ms")
        return response_data
        
    except Exception as e:
        logger.error(f"Error in search_profiles: {e}")
        return {
            "profiles_found": 0,
            "search_time_ms": int((time.time() - start_time) * 1000),
            "profiles": [],
            "search_metadata": {
                "query_used": request.query,
                "locations_searched": request.locations or [],
                "total_urls_found": 0,
                "duplicates_removed": 0
            },
            "error": str(e)
        }


@app.tool("extract_profile")
async def extract_profile(request: ExtractProfileRequest) -> Dict[str, Any]:
    """
    Extract detailed information from a LinkedIn profile URL.
    
    This tool scrapes a LinkedIn profile and optionally enriches it with
    contact information and activity summaries.
    """
    start_time = time.time()
    
    try:
        logger.info(f"Extracting profile: {request.profile_url}")
        
        # Check cache first
        cache_key = f"profile:{request.profile_url}:{request.include_contact_info}"
        if config.enable_caching:
            cached_result = cache_manager.get(cache_key)
            if cached_result:
                logger.info("Returning cached profile data")
                return cached_result
        
        # Extract profile data
        profile_data = await profile_service.extract_profile(
            profile_url=request.profile_url,
            include_contact_info=request.include_contact_info,
            include_activity_summary=request.include_activity_summary,
            apollo_api_key=request.apollo_api_key
        )
        
        if not profile_data:
            raise Exception("Failed to extract profile data")
        
        # Prepare response
        extraction_time_ms = int((time.time() - start_time) * 1000)
        
        response_data = {
            "profile_url": request.profile_url,
            "author_name": profile_data.get("name"),
            "headline": profile_data.get("headline"),
            "company": profile_data.get("company"),
            "job_title": profile_data.get("job_title"),
            "followers_count": profile_data.get("followers_count"),
            "contact_info": profile_data.get("contact_info"),
            "company_info": profile_data.get("company_info"),
            "activity_summary": profile_data.get("activity_summary"),
            "extraction_time_ms": extraction_time_ms,
            "data_sources": profile_data.get("data_sources", ["linkedin_scraping"])
        }
        
        # Cache the result
        if config.enable_caching:
            cache_manager.set(cache_key, response_data, ttl=3600)  # 1 hour
        
        logger.info(f"Profile extraction completed in {extraction_time_ms}ms")
        return response_data
        
    except Exception as e:
        logger.error(f"Error in extract_profile: {e}")
        return {
            "profile_url": request.profile_url,
            "author_name": None,
            "headline": None,
            "company": None,
            "job_title": None,
            "followers_count": None,
            "contact_info": None,
            "company_info": None,
            "activity_summary": None,
            "extraction_time_ms": int((time.time() - start_time) * 1000),
            "data_sources": [],
            "error": str(e)
        }


@app.tool("enrich_profiles")
async def enrich_profiles(request: EnrichProfilesRequest) -> Dict[str, Any]:
    """
    Enrich multiple profiles with contact information.
    
    This tool takes a list of LinkedIn profile URLs and enriches them
    with contact information using Apollo.io and fallback APIs.
    """
    start_time = time.time()
    
    try:
        logger.info(f"Enriching {len(request.profile_urls)} profiles")
        
        # Enrich profiles
        enriched_profiles, failed_profiles = await enrichment_service.enrich_multiple_profiles(
            profile_urls=request.profile_urls,
            apollo_api_key=request.apollo_api_key,
            nubela_api_key=request.nubela_api_key,
            batch_size=request.batch_size
        )
        
        # Prepare response
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        response_data = {
            "total_profiles": len(request.profile_urls),
            "successfully_enriched": len(enriched_profiles),
            "failed_enrichments": len(failed_profiles),
            "processing_time_ms": processing_time_ms,
            "enriched_profiles": [profile.dict() for profile in enriched_profiles],
            "failed_profiles": [profile.dict() for profile in failed_profiles]
        }
        
        logger.info(f"Profile enrichment completed: {len(enriched_profiles)}/{len(request.profile_urls)} successful")
        return response_data
        
    except Exception as e:
        logger.error(f"Error in enrich_profiles: {e}")
        return {
            "total_profiles": len(request.profile_urls),
            "successfully_enriched": 0,
            "failed_enrichments": len(request.profile_urls),
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "enriched_profiles": [],
            "failed_profiles": [
                {"profile_url": url, "enrichment_status": "failed", "error": str(e)}
                for url in request.profile_urls
            ]
        }


@app.tool("validate_profiles")
async def validate_profiles(request: ValidateProfilesRequest) -> Dict[str, Any]:
    """
    Validate profile relevance using AI filtering.
    
    This tool uses AI to determine if profiles are relevant to the
    original search criteria and provides confidence scores.
    """
    start_time = time.time()
    
    try:
        logger.info(f"Validating {len(request.profiles)} profiles")
        
        # Validate profiles
        validated_profiles = await validation_service.validate_multiple_profiles(
            profiles=request.profiles,
            search_criteria=request.search_criteria,
            confidence_threshold=request.confidence_threshold,
            ai_provider=request.ai_provider
        )
        
        # Count relevant profiles
        relevant_count = sum(1 for profile in validated_profiles if profile.is_relevant)
        
        # Prepare response
        validation_time_ms = int((time.time() - start_time) * 1000)
        
        response_data = {
            "total_profiles": len(request.profiles),
            "relevant_profiles": relevant_count,
            "filtered_out": len(request.profiles) - relevant_count,
            "validation_time_ms": validation_time_ms,
            "validated_profiles": [profile.dict() for profile in validated_profiles]
        }
        
        logger.info(f"Profile validation completed: {relevant_count}/{len(request.profiles)} relevant")
        return response_data
        
    except Exception as e:
        logger.error(f"Error in validate_profiles: {e}")
        return {
            "total_profiles": len(request.profiles),
            "relevant_profiles": 0,
            "filtered_out": 0,
            "validation_time_ms": int((time.time() - start_time) * 1000),
            "validated_profiles": [],
            "error": str(e)
        }


@app.tool("get_search_history")
async def get_search_history(request: GetSearchHistoryRequest) -> Dict[str, Any]:
    """
    Retrieve search history and cached results.
    
    This tool returns recent search queries and their results,
    useful for tracking search patterns and reusing cached data.
    """
    try:
        logger.info(f"Retrieving search history (limit: {request.limit})")
        
        # Get search history
        search_history, total_searches = await search_service.get_search_history(
            limit=request.limit,
            include_results=request.include_results
        )
        
        response_data = {
            "search_history": [item.dict() for item in search_history],
            "total_searches": total_searches
        }
        
        logger.info(f"Retrieved {len(search_history)} search history items")
        return response_data
        
    except Exception as e:
        logger.error(f"Error in get_search_history: {e}")
        return {
            "search_history": [],
            "total_searches": 0,
            "error": str(e)
        }


def main():
    """Main entry point for the MCP server."""
    try:
        # Validate configuration
        missing_keys = config.validate_api_keys()
        if missing_keys:
            logger.warning(f"Missing API keys: {', '.join(missing_keys)}")
            logger.warning("Some features may not be available")
        
        # Create data directory
        Path(config.database_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Clean expired cache entries
        if config.enable_caching:
            cache_manager.clear_expired()
        
        logger.info("Profile Scraping MCP Server starting...")
        logger.info(f"Server name: {config.server_name}")
        logger.info(f"Debug mode: {config.debug}")
        logger.info(f"Available tools: search_profiles, extract_profile, enrich_profiles, validate_profiles, get_search_history")
        
        # Run the server
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()