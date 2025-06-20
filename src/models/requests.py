"""Request models for the Profile Scraping MCP Server."""

from pydantic import BaseModel, Field
from typing import List, Optional


class SearchProfilesRequest(BaseModel):
    """Request schema for search_profiles tool."""
    query: str = Field(..., description="Search keywords (e.g., 'AI podcast host', 'blockchain developer')")
    num_results: int = Field(default=20, ge=1, le=100, description="Number of profiles to find")
    locations: Optional[List[str]] = Field(default=None, description="Optional location filters (e.g., ['US', 'UK', 'CA'])")
    use_global_search: bool = Field(default=False, description="Whether to use global multi-location search")
    target_results: int = Field(default=100, ge=10, le=500, description="Target results for global search")


class ExtractProfileRequest(BaseModel):
    """Request schema for extract_profile tool."""
    profile_url: str = Field(..., description="LinkedIn profile URL")
    include_contact_info: bool = Field(default=True, description="Whether to enrich with contact information")
    include_activity_summary: bool = Field(default=False, description="Whether to generate activity summary")
    apollo_api_key: Optional[str] = Field(default=None, description="Optional Apollo.io API key override")


class EnrichProfilesRequest(BaseModel):
    """Request schema for enrich_profiles tool."""
    profile_urls: List[str] = Field(..., description="List of LinkedIn profile URLs")
    apollo_api_key: str = Field(..., description="Apollo.io API key")
    nubela_api_key: Optional[str] = Field(default=None, description="Optional Nubela API key for fallback")
    batch_size: int = Field(default=5, ge=1, le=10, description="Number of profiles to process in parallel")


class ValidateProfilesRequest(BaseModel):
    """Request schema for validate_profiles tool."""
    profiles: List[dict] = Field(..., description="List of profile data objects")
    search_criteria: str = Field(..., description="Original search criteria for validation")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence score")
    ai_provider: str = Field(default="openai", description="AI provider to use ('openai', 'gemini', 'openrouter', 'ollama')")


class GetSearchHistoryRequest(BaseModel):
    """Request schema for get_search_history tool."""
    limit: int = Field(default=10, ge=1, le=50, description="Number of recent searches to return")
    include_results: bool = Field(default=False, description="Whether to include cached results")