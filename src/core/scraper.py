"""Core profile scraping functionality."""

import json
import random
import asyncio
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from ..utils.logger import get_logger
from ..utils.rate_limiter import ServiceRateLimiters
from ..models.responses import ProfileData, ContactInfo, CompanyInfo

logger = get_logger(__name__)


class ProfileScraper:
    """Core LinkedIn profile scraper."""
    
    def __init__(self):
        """Initialize the profile scraper."""
        self.session_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize LinkedIn URL to ensure proper format.
        
        Args:
            url: LinkedIn profile URL
            
        Returns:
            Normalized URL
        """
        if not url.startswith("http"):
            url = f"https://{url}"
        
        if "https://www." not in url:
            parsed = urlparse(url)
            if parsed.netloc and not parsed.netloc.startswith("www."):
                url = url.replace(parsed.netloc, f"www.{parsed.netloc}")
        
        return url
    
    async def random_delay(self, min_seconds: int = 10, max_seconds: int = 20) -> None:
        """Add random delay between requests."""
        delay = random.uniform(min_seconds, max_seconds)
        logger.debug(f"Adding random delay: {delay:.2f} seconds")
        await asyncio.sleep(delay)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def fetch_profile_page(self, profile_url: str) -> Optional[str]:
        """
        Fetch LinkedIn profile page content.
        
        Args:
            profile_url: LinkedIn profile URL
            
        Returns:
            HTML content or None if failed
        """
        # Apply rate limiting
        await ServiceRateLimiters.wait_for_linkedin()
        
        normalized_url = self.normalize_url(profile_url)
        
        try:
            async with httpx.AsyncClient(
                headers=self.session_headers,
                timeout=30.0,
                follow_redirects=True
            ) as client:
                logger.info(f"Fetching profile: {normalized_url}")
                response = await client.get(normalized_url)
                
                if response.status_code == 200:
                    logger.info(f"Successfully fetched profile: {normalized_url}")
                    await self.random_delay()
                    return response.text
                elif response.status_code == 429:
                    logger.warning(f"Rate limited for URL: {normalized_url}")
                    await asyncio.sleep(60)  # Wait 1 minute for rate limit
                    raise httpx.HTTPStatusError(f"Rate limited: {response.status_code}", request=response.request, response=response)
                else:
                    logger.warning(f"HTTP {response.status_code} for URL: {normalized_url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching profile {normalized_url}: {e}")
            raise
    
    def extract_json_ld_data(self, html_content: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON-LD structured data from LinkedIn profile.
        
        Args:
            html_content: HTML content of the profile page
            
        Returns:
            Parsed JSON-LD data or None if not found
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            json_ld_tag = soup.find("script", type="application/ld+json")
            
            if json_ld_tag and json_ld_tag.string:
                return json.loads(json_ld_tag.string)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting JSON-LD data: {e}")
            return None
    
    def parse_profile_data(self, json_ld_data: Dict[str, Any], profile_url: str) -> ProfileData:
        """
        Parse profile data from JSON-LD.
        
        Args:
            json_ld_data: JSON-LD structured data
            profile_url: Original profile URL
            
        Returns:
            Parsed profile data
        """
        try:
            # Initialize profile data
            profile_data = ProfileData(profile_url=profile_url)
            
            # Look for Person data in the graph
            graph = json_ld_data.get('@graph', [])
            for item in graph:
                if item.get('@type') == 'Person':
                    profile_data.name = item.get('name')
                    profile_data.headline = item.get('description')
                    
                    # Extract job title
                    job_title = item.get('jobTitle')
                    if isinstance(job_title, str):
                        profile_data.job_title = job_title
                    
                    # Extract company information
                    works_for = item.get('worksFor', [])
                    if works_for and isinstance(works_for, list) and len(works_for) > 0:
                        company_info = works_for[0]
                        if isinstance(company_info, dict):
                            profile_data.company = company_info.get('name')
                    
                    # Extract follower count
                    interaction_stat = item.get('interactionStatistic', {})
                    if isinstance(interaction_stat, dict):
                        followers = interaction_stat.get('userInteractionCount')
                        if followers:
                            try:
                                profile_data.followers_count = int(followers)
                            except (ValueError, TypeError):
                                pass
                    
                    break
            
            return profile_data
            
        except Exception as e:
            logger.error(f"Error parsing profile data: {e}")
            return ProfileData(profile_url=profile_url)
    
    async def scrape_profile(self, profile_url: str) -> Optional[ProfileData]:
        """
        Scrape a LinkedIn profile and extract basic information.
        
        Args:
            profile_url: LinkedIn profile URL
            
        Returns:
            ProfileData object or None if scraping failed
        """
        try:
            # Fetch the profile page
            html_content = await self.fetch_profile_page(profile_url)
            if not html_content:
                logger.warning(f"Failed to fetch profile content for: {profile_url}")
                return None
            
            # Extract JSON-LD data
            json_ld_data = self.extract_json_ld_data(html_content)
            if not json_ld_data:
                logger.warning(f"No JSON-LD data found for: {profile_url}")
                return ProfileData(profile_url=profile_url)
            
            # Parse profile data
            profile_data = self.parse_profile_data(json_ld_data, profile_url)
            
            logger.info(f"Successfully scraped profile: {profile_data.name} at {profile_data.company}")
            return profile_data
            
        except Exception as e:
            logger.error(f"Error scraping profile {profile_url}: {e}")
            return None
    
    async def scrape_multiple_profiles(self, profile_urls: List[str], max_concurrent: int = 5) -> List[ProfileData]:
        """
        Scrape multiple profiles concurrently.
        
        Args:
            profile_urls: List of LinkedIn profile URLs
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of ProfileData objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(url: str) -> Optional[ProfileData]:
            async with semaphore:
                return await self.scrape_profile(url)
        
        logger.info(f"Scraping {len(profile_urls)} profiles with max {max_concurrent} concurrent requests")
        
        tasks = [scrape_with_semaphore(url) for url in profile_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        valid_results = []
        for result in results:
            if isinstance(result, ProfileData):
                valid_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Exception during profile scraping: {result}")
        
        logger.info(f"Successfully scraped {len(valid_results)} out of {len(profile_urls)} profiles")
        return valid_results