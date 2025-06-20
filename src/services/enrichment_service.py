"""Enrichment service for adding contact information to profiles."""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple

from ..integrations.apollo_client import ApolloClient
from ..integrations.nubela_client import NubelaClient
from ..models.responses import EnrichmentResult, ContactInfo, CompanyInfo
from ..utils.config import config
from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter
from ..utils.cache import CacheManager

logger = get_logger(__name__)


class EnrichmentService:
    """Service for enriching profiles with contact information."""
    
    def __init__(self):
        """Initialize the enrichment service."""
        self.apollo_client = ApolloClient()
        self.nubela_client = NubelaClient()
        self.apollo_rate_limiter = RateLimiter(
            max_requests=config.apollo_rate_limit,
            time_window=60
        )
        self.nubela_rate_limiter = RateLimiter(
            max_requests=config.nubela_rate_limit,
            time_window=60
        )
        self.cache_manager = CacheManager(
            db_path=config.database_path.replace('.db', '_enrichment.db'),
            ttl=config.cache_ttl
        )
    
    async def enrich_multiple_profiles(
        self,
        profile_urls: List[str],
        apollo_api_key: Optional[str] = None,
        nubela_api_key: Optional[str] = None,
        batch_size: int = 10
    ) -> Tuple[List[EnrichmentResult], List[EnrichmentResult]]:
        """
        Enrich multiple profiles with contact information.
        
        Args:
            profile_urls: List of LinkedIn profile URLs
            apollo_api_key: Apollo.io API key
            nubela_api_key: Nubela API key
            batch_size: Number of profiles to process concurrently
            
        Returns:
            Tuple of (successful_enrichments, failed_enrichments)
        """
        try:
            logger.info(f"Starting enrichment for {len(profile_urls)} profiles")
            
            # Process profiles in batches
            successful_enrichments = []
            failed_enrichments = []
            
            for i in range(0, len(profile_urls), batch_size):
                batch = profile_urls[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} profiles")
                
                # Process batch concurrently
                batch_results = await self._enrich_batch(
                    profile_urls=batch,
                    apollo_api_key=apollo_api_key,
                    nubela_api_key=nubela_api_key
                )
                
                # Separate successful and failed enrichments
                for result in batch_results:
                    if result.enrichment_status == "success":
                        successful_enrichments.append(result)
                    else:
                        failed_enrichments.append(result)
                
                # Add delay between batches to respect rate limits
                if i + batch_size < len(profile_urls):
                    await asyncio.sleep(1)
            
            logger.info(f"Enrichment completed: {len(successful_enrichments)}/{len(profile_urls)} successful")
            return successful_enrichments, failed_enrichments
            
        except Exception as e:
            logger.error(f"Error in enrich_multiple_profiles: {e}")
            # Return all as failed
            failed_results = [
                EnrichmentResult(
                    profile_url=url,
                    enrichment_status="failed",
                    error=str(e)
                )
                for url in profile_urls
            ]
            return [], failed_results
    
    async def _enrich_batch(
        self,
        profile_urls: List[str],
        apollo_api_key: Optional[str] = None,
        nubela_api_key: Optional[str] = None
    ) -> List[EnrichmentResult]:
        """Enrich a batch of profiles concurrently."""
        semaphore = asyncio.Semaphore(5)  # Limit concurrent enrichments
        
        async def enrich_single(url: str) -> EnrichmentResult:
            async with semaphore:
                return await self.enrich_profile(
                    profile_url=url,
                    apollo_api_key=apollo_api_key,
                    nubela_api_key=nubela_api_key
                )
        
        # Execute all enrichments concurrently
        tasks = [enrich_single(url) for url in profile_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        enrichment_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Enrichment failed for {profile_urls[i]}: {result}")
                enrichment_results.append(
                    EnrichmentResult(
                        profile_url=profile_urls[i],
                        enrichment_status="failed",
                        error=str(result)
                    )
                )
            else:
                enrichment_results.append(result)
        
        return enrichment_results
    
    async def enrich_profile(
        self,
        profile_url: str,
        apollo_api_key: Optional[str] = None,
        nubela_api_key: Optional[str] = None
    ) -> EnrichmentResult:
        """
        Enrich a single profile with contact information.
        
        Args:
            profile_url: LinkedIn profile URL
            apollo_api_key: Apollo.io API key
            nubela_api_key: Nubela API key
            
        Returns:
            EnrichmentResult with contact information
        """
        start_time = time.time()
        
        try:
            logger.info(f"Enriching profile: {profile_url}")
            
            # Check cache first
            cache_key = f"enrichment:{profile_url}"
            if config.enable_caching:
                cached_result = self.cache_manager.get(cache_key)
                if cached_result:
                    logger.info(f"Returning cached enrichment for {profile_url}")
                    return EnrichmentResult(**cached_result)
            
            # Extract basic profile info first (needed for enrichment)
            profile_info = await self._extract_basic_profile_info(profile_url)
            if not profile_info:
                raise Exception("Failed to extract basic profile information")
            
            # Try Apollo.io enrichment first
            contact_info = None
            company_info = None
            data_sources = []
            
            if apollo_api_key or config.apollo_api_key:
                try:
                    await self.apollo_rate_limiter.acquire()
                    api_key = apollo_api_key or config.apollo_api_key
                    
                    apollo_result = await self.apollo_client.get_contact_info(
                        name=profile_info.get("name"),
                        company=profile_info.get("company"),
                        api_key=api_key
                    )
                    
                    if apollo_result:
                        contact_info = ContactInfo(**apollo_result)
                        data_sources.append("apollo")
                        logger.info(f"Apollo enrichment successful for {profile_url}")
                    
                except Exception as e:
                    logger.warning(f"Apollo enrichment failed for {profile_url}: {e}")
            
            # Try Nubela as fallback if Apollo failed
            if not contact_info and (nubela_api_key or config.nubela_api_key):
                try:
                    await self.nubela_rate_limiter.acquire()
                    api_key = nubela_api_key or config.nubela_api_key
                    
                    nubela_result = await self.nubela_client.get_contact_info(
                        linkedin_url=profile_url,
                        api_key=api_key
                    )
                    
                    if nubela_result:
                        contact_info = ContactInfo(**nubela_result)
                        data_sources.append("nubela")
                        logger.info(f"Nubela enrichment successful for {profile_url}")
                    
                except Exception as e:
                    logger.warning(f"Nubela enrichment failed for {profile_url}: {e}")
            
            # Get company information if available
            if profile_info.get("company"):
                company_info = await self._get_company_info(
                    company_name=profile_info["company"],
                    apollo_api_key=apollo_api_key
                )
                if company_info:
                    data_sources.append("company_enrichment")
            
            # Create enrichment result
            enrichment_time_ms = int((time.time() - start_time) * 1000)
            
            result = EnrichmentResult(
                profile_url=profile_url,
                contact_info=contact_info,
                company_info=company_info,
                enrichment_status="success" if contact_info else "partial",
                enrichment_time_ms=enrichment_time_ms,
                data_sources=data_sources
            )
            
            # Cache the result
            if config.enable_caching:
                self.cache_manager.set(cache_key, result.dict(), ttl=7200)  # 2 hours
            
            logger.info(f"Profile enrichment completed for {profile_url} in {enrichment_time_ms}ms")
            return result
            
        except Exception as e:
            logger.error(f"Error enriching profile {profile_url}: {e}")
            enrichment_time_ms = int((time.time() - start_time) * 1000)
            
            return EnrichmentResult(
                profile_url=profile_url,
                enrichment_status="failed",
                enrichment_time_ms=enrichment_time_ms,
                error=str(e)
            )
    
    async def _extract_basic_profile_info(self, profile_url: str) -> Optional[Dict[str, Any]]:
        """Extract basic profile information needed for enrichment."""
        try:
            # This would typically use the scraper to get basic info
            # For now, we'll extract from the URL and make educated guesses
            
            # Extract LinkedIn username from URL
            username = profile_url.split('/in/')[-1].split('/')[0]
            
            # Basic info that would come from scraping
            # In a real implementation, this would call the scraper
            return {
                "name": None,  # Would be extracted from LinkedIn
                "company": None,  # Would be extracted from LinkedIn
                "job_title": None,  # Would be extracted from LinkedIn
                "username": username
            }
            
        except Exception as e:
            logger.error(f"Error extracting basic profile info: {e}")
            return None
    
    async def _get_company_info(
        self,
        company_name: str,
        apollo_api_key: Optional[str] = None
    ) -> Optional[CompanyInfo]:
        """Get company information."""
        try:
            if not (apollo_api_key or config.apollo_api_key):
                return None
            
            api_key = apollo_api_key or config.apollo_api_key
            company_data = await self.apollo_client.get_company_info(
                company_name=company_name,
                api_key=api_key
            )
            
            if company_data:
                return CompanyInfo(**company_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting company info for {company_name}: {e}")
            return None
    
    async def get_enrichment_stats(self) -> Dict[str, Any]:
        """Get enrichment statistics."""
        try:
            cache_stats = self.cache_manager.get_stats()
            apollo_stats = self.apollo_rate_limiter.get_stats()
            nubela_stats = self.nubela_rate_limiter.get_stats()
            
            return {
                "cache_stats": cache_stats,
                "apollo_rate_limiter": apollo_stats,
                "nubela_rate_limiter": nubela_stats,
                "available_providers": {
                    "apollo": bool(config.apollo_api_key),
                    "nubela": bool(config.nubela_api_key)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting enrichment stats: {e}")
            return {}
    
    async def clear_cache(self) -> bool:
        """Clear enrichment cache."""
        try:
            self.cache_manager.clear()
            logger.info("Enrichment cache cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing enrichment cache: {e}")
            return False
    
    async def validate_api_keys(
        self,
        apollo_api_key: Optional[str] = None,
        nubela_api_key: Optional[str] = None
    ) -> Dict[str, bool]:
        """Validate API keys for enrichment services."""
        results = {}
        
        # Test Apollo API key
        if apollo_api_key or config.apollo_api_key:
            try:
                api_key = apollo_api_key or config.apollo_api_key
                is_valid = await self.apollo_client.validate_api_key(api_key)
                results["apollo"] = is_valid
            except Exception as e:
                logger.error(f"Error validating Apollo API key: {e}")
                results["apollo"] = False
        else:
            results["apollo"] = False
        
        # Test Nubela API key
        if nubela_api_key or config.nubela_api_key:
            try:
                api_key = nubela_api_key or config.nubela_api_key
                is_valid = await self.nubela_client.validate_api_key(api_key)
                results["nubela"] = is_valid
            except Exception as e:
                logger.error(f"Error validating Nubela API key: {e}")
                results["nubela"] = False
        else:
            results["nubela"] = False
        
        return results