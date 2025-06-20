"""Profile service for handling LinkedIn profile extraction and processing."""

import asyncio
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

from ..core.scraper import LinkedInScraper
from ..integrations.apollo_client import ApolloClient
from ..integrations.nubela_client import NubelaClient
from ..models.responses import ProfileData, ContactInfo, CompanyInfo
from ..utils.config import config
from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter
from ..utils.cache import CacheManager

logger = get_logger(__name__)


class ProfileService:
    """Service for handling LinkedIn profile operations."""
    
    def __init__(self):
        """Initialize the profile service."""
        self.scraper = LinkedInScraper()
        self.apollo_client = ApolloClient()
        self.nubela_client = NubelaClient()
        self.rate_limiter = RateLimiter(
            max_requests=config.linkedin_rate_limit,
            time_window=60
        )
        self.cache_manager = CacheManager(
            db_path=config.database_path.replace('.db', '_profiles.db'),
            ttl=config.cache_ttl
        )
    
    async def extract_profile(
        self,
        profile_url: str,
        include_contact_info: bool = False,
        include_activity_summary: bool = False,
        apollo_api_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extract detailed information from a LinkedIn profile.
        
        Args:
            profile_url: LinkedIn profile URL
            include_contact_info: Whether to include contact information
            include_activity_summary: Whether to include activity summary
            apollo_api_key: Apollo.io API key for contact enrichment
            
        Returns:
            Profile data dictionary or None if extraction failed
        """
        try:
            # Validate URL
            if not self._is_valid_linkedin_url(profile_url):
                raise ValueError(f"Invalid LinkedIn profile URL: {profile_url}")
            
            # Check cache first
            cache_key = f"profile_extract:{profile_url}:{include_contact_info}:{include_activity_summary}"
            if config.enable_caching:
                cached_data = self.cache_manager.get(cache_key)
                if cached_data:
                    logger.info(f"Returning cached profile data for {profile_url}")
                    return cached_data
            
            # Rate limiting
            await self.rate_limiter.acquire()
            
            logger.info(f"Extracting profile: {profile_url}")
            
            # Extract basic profile data
            profile_data = await self.scraper.extract_profile(profile_url)
            if not profile_data:
                logger.error(f"Failed to extract basic profile data from {profile_url}")
                return None
            
            # Enrich with contact information if requested
            if include_contact_info:
                contact_info = await self._get_contact_info(
                    profile_data=profile_data,
                    apollo_api_key=apollo_api_key
                )
                if contact_info:
                    profile_data["contact_info"] = contact_info
            
            # Add activity summary if requested
            if include_activity_summary:
                activity_summary = await self._get_activity_summary(profile_url)
                if activity_summary:
                    profile_data["activity_summary"] = activity_summary
            
            # Add metadata
            profile_data["extraction_timestamp"] = int(time.time())
            profile_data["data_sources"] = ["linkedin_scraping"]
            
            if include_contact_info:
                profile_data["data_sources"].append("apollo_enrichment")
            
            # Cache the result
            if config.enable_caching:
                self.cache_manager.set(cache_key, profile_data, ttl=3600)
            
            logger.info(f"Successfully extracted profile: {profile_data.get('name', 'Unknown')}")
            return profile_data
            
        except Exception as e:
            logger.error(f"Error extracting profile {profile_url}: {e}")
            return None
    
    async def extract_multiple_profiles(
        self,
        profile_urls: List[str],
        include_contact_info: bool = False,
        include_activity_summary: bool = False,
        apollo_api_key: Optional[str] = None,
        max_concurrent: int = 5
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Extract multiple profiles concurrently.
        
        Args:
            profile_urls: List of LinkedIn profile URLs
            include_contact_info: Whether to include contact information
            include_activity_summary: Whether to include activity summary
            apollo_api_key: Apollo.io API key for contact enrichment
            max_concurrent: Maximum concurrent extractions
            
        Returns:
            Tuple of (successful_profiles, failed_urls)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_single(url: str) -> tuple[Optional[Dict[str, Any]], str]:
            async with semaphore:
                profile_data = await self.extract_profile(
                    profile_url=url,
                    include_contact_info=include_contact_info,
                    include_activity_summary=include_activity_summary,
                    apollo_api_key=apollo_api_key
                )
                return profile_data, url
        
        # Execute all extractions concurrently
        tasks = [extract_single(url) for url in profile_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_profiles = []
        failed_urls = []
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Profile extraction failed with exception: {result}")
                failed_urls.append("unknown")
            else:
                profile_data, url = result
                if profile_data:
                    successful_profiles.append(profile_data)
                else:
                    failed_urls.append(url)
        
        logger.info(f"Extracted {len(successful_profiles)}/{len(profile_urls)} profiles successfully")
        return successful_profiles, failed_urls
    
    async def _get_contact_info(
        self,
        profile_data: Dict[str, Any],
        apollo_api_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get contact information for a profile."""
        try:
            # Try Apollo.io first
            if apollo_api_key or config.apollo_api_key:
                api_key = apollo_api_key or config.apollo_api_key
                contact_info = await self.apollo_client.get_contact_info(
                    name=profile_data.get("name"),
                    company=profile_data.get("company"),
                    api_key=api_key
                )
                if contact_info:
                    return contact_info
            
            # Fallback to Nubela if available
            if config.nubela_api_key:
                contact_info = await self.nubela_client.get_contact_info(
                    linkedin_url=profile_data.get("profile_url"),
                    api_key=config.nubela_api_key
                )
                if contact_info:
                    return contact_info
            
            logger.warning("No contact enrichment APIs available")
            return None
            
        except Exception as e:
            logger.error(f"Error getting contact info: {e}")
            return None
    
    async def _get_activity_summary(self, profile_url: str) -> Optional[Dict[str, Any]]:
        """Get activity summary for a profile."""
        try:
            # Extract recent activity from LinkedIn
            activity_data = await self.scraper.extract_activity(profile_url)
            if not activity_data:
                return None
            
            # Process activity data
            summary = {
                "recent_posts_count": len(activity_data.get("posts", [])),
                "recent_comments_count": len(activity_data.get("comments", [])),
                "recent_likes_count": len(activity_data.get("likes", [])),
                "last_activity_date": activity_data.get("last_activity_date"),
                "activity_topics": activity_data.get("topics", []),
                "engagement_score": self._calculate_engagement_score(activity_data)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting activity summary: {e}")
            return None
    
    def _calculate_engagement_score(self, activity_data: Dict[str, Any]) -> float:
        """Calculate engagement score based on activity data."""
        try:
            posts_count = len(activity_data.get("posts", []))
            comments_count = len(activity_data.get("comments", []))
            likes_count = len(activity_data.get("likes", []))
            
            # Simple engagement score calculation
            score = (posts_count * 3) + (comments_count * 2) + (likes_count * 1)
            
            # Normalize to 0-100 scale
            max_score = 100
            normalized_score = min(score / max_score * 100, 100)
            
            return round(normalized_score, 2)
            
        except Exception:
            return 0.0
    
    def _is_valid_linkedin_url(self, url: str) -> bool:
        """Validate if URL is a valid LinkedIn profile URL."""
        try:
            parsed = urlparse(url)
            return (
                parsed.netloc in ["www.linkedin.com", "linkedin.com"] and
                "/in/" in parsed.path
            )
        except Exception:
            return False
    
    async def get_profile_stats(self) -> Dict[str, Any]:
        """Get statistics about profile extractions."""
        try:
            # Get cache statistics
            cache_stats = self.cache_manager.get_stats()
            
            # Get rate limiter statistics
            rate_stats = self.rate_limiter.get_stats()
            
            return {
                "cache_stats": cache_stats,
                "rate_limiter_stats": rate_stats,
                "scraper_stats": await self.scraper.get_stats()
            }
            
        except Exception as e:
            logger.error(f"Error getting profile stats: {e}")
            return {}
    
    async def clear_cache(self) -> bool:
        """Clear profile cache."""
        try:
            self.cache_manager.clear()
            logger.info("Profile cache cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False