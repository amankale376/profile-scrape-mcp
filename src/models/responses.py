"""Response models for the Profile Scraping MCP Server."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ContactInfo(BaseModel):
    """Contact information for a profile."""
    email: Optional[str] = None
    phone: Optional[str] = None
    company_phone: Optional[str] = None


class CompanyInfo(BaseModel):
    """Company information for a profile."""
    name: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None


class ProfileData(BaseModel):
    """Basic profile data structure."""
    profile_url: str
    name: Optional[str] = None
    headline: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    followers_count: Optional[int] = None


class SearchMetadata(BaseModel):
    """Metadata about the search operation."""
    query_used: str
    locations_searched: List[str]
    total_urls_found: int
    duplicates_removed: int


class SearchProfilesResponse(BaseModel):
    """Response schema for search_profiles tool."""
    profiles_found: int
    search_time_ms: int
    profiles: List[ProfileData]
    search_metadata: SearchMetadata


class ExtractProfileResponse(BaseModel):
    """Response schema for extract_profile tool."""
    profile_url: str
    author_name: Optional[str] = None
    headline: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    followers_count: Optional[int] = None
    contact_info: Optional[ContactInfo] = None
    company_info: Optional[CompanyInfo] = None
    activity_summary: Optional[str] = None
    extraction_time_ms: int
    data_sources: List[str]


class EnrichmentResult(BaseModel):
    """Result of profile enrichment."""
    profile_url: str
    enrichment_status: str  # "success", "failed", "partial"
    contact_info: Optional[ContactInfo] = None
    error: Optional[str] = None


class EnrichProfilesResponse(BaseModel):
    """Response schema for enrich_profiles tool."""
    total_profiles: int
    successfully_enriched: int
    failed_enrichments: int
    processing_time_ms: int
    enriched_profiles: List[EnrichmentResult]
    failed_profiles: List[EnrichmentResult]


class ValidationResult(BaseModel):
    """Result of profile validation."""
    profile_url: str
    relevance_score: float
    is_relevant: bool
    reasoning: str


class ValidateProfilesResponse(BaseModel):
    """Response schema for validate_profiles tool."""
    total_profiles: int
    relevant_profiles: int
    filtered_out: int
    validation_time_ms: int
    validated_profiles: List[ValidationResult]


class SearchHistoryItem(BaseModel):
    """Individual search history item."""
    search_id: str
    query: str
    timestamp: datetime
    results_count: int
    locations_used: List[str]
    search_type: str


class GetSearchHistoryResponse(BaseModel):
    """Response schema for get_search_history tool."""
    search_history: List[SearchHistoryItem]
    total_searches: int