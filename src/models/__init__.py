"""Data models for the Profile Scraping MCP Server."""

from .requests import (
    SearchProfilesRequest,
    ExtractProfileRequest,
    EnrichProfilesRequest,
    ValidateProfilesRequest,
    GetSearchHistoryRequest,
)

from .responses import (
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

__all__ = [
    # Requests
    "SearchProfilesRequest",
    "ExtractProfileRequest", 
    "EnrichProfilesRequest",
    "ValidateProfilesRequest",
    "GetSearchHistoryRequest",
    # Responses
    "SearchProfilesResponse",
    "ExtractProfileResponse",
    "EnrichProfilesResponse", 
    "ValidateProfilesResponse",
    "GetSearchHistoryResponse",
    "ProfileData",
    "ContactInfo",
    "CompanyInfo",
    "SearchMetadata",
    "ValidationResult",
    "EnrichmentResult",
    "SearchHistoryItem",
]