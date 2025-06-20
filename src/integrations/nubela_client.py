"""Nubela API client for LinkedIn profile data enrichment."""

import asyncio
import httpx
from typing import Dict, Any, Optional

from ..utils.config import config
from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


class NubelaClient:
    """Client for Nubela (Proxycurl) API integration."""
    
    def __init__(self):
        """Initialize the Nubela client."""
        self.base_url = "https://nubela-proxycurl-linkedin-company-api.p.rapidapi.com"
        self.rate_limiter = RateLimiter(
            max_requests=config.nubela_rate_limit,
            time_window=60
        )
        self.timeout = httpx.Timeout(30.0)
    
    async def get_contact_info(
        self,
        linkedin_url: str,
        api_key: str,
        include_skills: bool = True,
        include_experience: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get contact information for a LinkedIn profile using Nubela API.
        
        Args:
            linkedin_url: LinkedIn profile URL
            api_key: Nubela API key
            include_skills: Whether to include skills data
            include_experience: Whether to include experience data
            
        Returns:
            Contact information dictionary or None if failed
        """
        try:
            logger.info(f"Getting contact info from Nubela for: {linkedin_url}")
            
            # Rate limiting
            await self.rate_limiter.acquire()
            
            # Prepare request
            headers = {
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "nubela-proxycurl-linkedin-company-api.p.rapidapi.com"
            }
            
            params = {
                "url": linkedin_url,
                "fallback_to_cache": "on-error",
                "use_cache": "if-present",
                "skills": "include" if include_skills else "exclude",
                "inferred_salary": "include",
                "personal_email": "include",
                "personal_contact_number": "include",
                "twitter_profile_id": "include",
                "facebook_profile_id": "include",
                "github_profile_id": "include",
                "extra": "include" if include_experience else "exclude"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/v2/",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_nubela_response(data)
                elif response.status_code == 429:
                    logger.warning("Nubela API rate limit exceeded")
                    await asyncio.sleep(60)  # Wait before retry
                    return None
                else:
                    logger.error(f"Nubela API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting contact info from Nubela: {e}")
            return None
    
    async def get_company_info(
        self,
        company_url: str,
        api_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get company information using Nubela API.
        
        Args:
            company_url: LinkedIn company URL
            api_key: Nubela API key
            
        Returns:
            Company information dictionary or None if failed
        """
        try:
            logger.info(f"Getting company info from Nubela for: {company_url}")
            
            # Rate limiting
            await self.rate_limiter.acquire()
            
            headers = {
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "nubela-proxycurl-linkedin-company-api.p.rapidapi.com"
            }
            
            params = {
                "url": company_url,
                "resolve_numeric_id": "true",
                "categories": "include",
                "funding_data": "include",
                "extra": "include",
                "exit_data": "include",
                "acquisitions": "include",
                "use_cache": "if-present"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/v2/company",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_company_response(data)
                elif response.status_code == 429:
                    logger.warning("Nubela API rate limit exceeded")
                    await asyncio.sleep(60)
                    return None
                else:
                    logger.error(f"Nubela company API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting company info from Nubela: {e}")
            return None
    
    async def search_profiles(
        self,
        query: str,
        api_key: str,
        location: Optional[str] = None,
        industry: Optional[str] = None,
        current_company: Optional[str] = None,
        past_company: Optional[str] = None,
        limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Search for LinkedIn profiles using Nubela API.
        
        Args:
            query: Search query
            api_key: Nubela API key
            location: Location filter
            industry: Industry filter
            current_company: Current company filter
            past_company: Past company filter
            limit: Maximum number of results
            
        Returns:
            List of profile dictionaries or None if failed
        """
        try:
            logger.info(f"Searching profiles with Nubela: {query}")
            
            # Rate limiting
            await self.rate_limiter.acquire()
            
            headers = {
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "nubela-proxycurl-linkedin-company-api.p.rapidapi.com"
            }
            
            params = {
                "country": "US",  # Default to US, can be parameterized
                "enrich_profiles": "enrich",
                "use_cache": "if-present",
                "page_size": min(limit, 100)  # API limit
            }
            
            # Add search filters
            if query:
                params["keyword"] = query
            if location:
                params["region"] = location
            if industry:
                params["industry"] = industry
            if current_company:
                params["current_company_name"] = current_company
            if past_company:
                params["past_company_name"] = past_company
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/v2/search",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_search_response(data)
                elif response.status_code == 429:
                    logger.warning("Nubela search API rate limit exceeded")
                    await asyncio.sleep(60)
                    return None
                else:
                    logger.error(f"Nubela search API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error searching profiles with Nubela: {e}")
            return None
    
    def _parse_nubela_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Nubela profile response into standardized format."""
        try:
            contact_info = {}
            
            # Basic contact information
            if data.get("personal_emails"):
                contact_info["email"] = data["personal_emails"][0]
            
            if data.get("personal_numbers"):
                contact_info["phone"] = data["personal_numbers"][0]
            
            # Social profiles
            social_profiles = {}
            if data.get("twitter_profile_id"):
                social_profiles["twitter"] = f"https://twitter.com/{data['twitter_profile_id']}"
            
            if data.get("facebook_profile_id"):
                social_profiles["facebook"] = f"https://facebook.com/{data['facebook_profile_id']}"
            
            if data.get("github_profile_id"):
                social_profiles["github"] = f"https://github.com/{data['github_profile_id']}"
            
            if social_profiles:
                contact_info["social_profiles"] = social_profiles
            
            # Professional information
            if data.get("inferred_salary"):
                salary_info = data["inferred_salary"]
                contact_info["estimated_salary"] = {
                    "min": salary_info.get("min"),
                    "max": salary_info.get("max"),
                    "currency": salary_info.get("currency", "USD")
                }
            
            # Location information
            if data.get("city") or data.get("state") or data.get("country"):
                contact_info["location"] = {
                    "city": data.get("city"),
                    "state": data.get("state"),
                    "country": data.get("country"),
                    "country_full_name": data.get("country_full_name")
                }
            
            # Skills
            if data.get("skills"):
                contact_info["skills"] = data["skills"]
            
            # Experience
            if data.get("experiences"):
                contact_info["experience"] = [
                    {
                        "title": exp.get("title"),
                        "company": exp.get("company"),
                        "company_linkedin_profile_url": exp.get("company_linkedin_profile_url"),
                        "description": exp.get("description"),
                        "location": exp.get("location"),
                        "starts_at": exp.get("starts_at"),
                        "ends_at": exp.get("ends_at")
                    }
                    for exp in data["experiences"][:5]  # Limit to recent 5
                ]
            
            # Education
            if data.get("education"):
                contact_info["education"] = [
                    {
                        "school": edu.get("school"),
                        "degree_name": edu.get("degree_name"),
                        "field_of_study": edu.get("field_of_study"),
                        "starts_at": edu.get("starts_at"),
                        "ends_at": edu.get("ends_at")
                    }
                    for edu in data["education"][:3]  # Limit to recent 3
                ]
            
            return contact_info
            
        except Exception as e:
            logger.error(f"Error parsing Nubela response: {e}")
            return {}
    
    def _parse_company_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Nubela company response into standardized format."""
        try:
            company_info = {}
            
            # Basic company information
            company_info["name"] = data.get("name")
            company_info["description"] = data.get("description")
            company_info["website"] = data.get("website")
            company_info["industry"] = data.get("industry")
            company_info["company_size"] = data.get("company_size")
            company_info["headquarters"] = data.get("hq")
            company_info["founded_year"] = data.get("founded_year")
            company_info["company_type"] = data.get("company_type")
            
            # Funding information
            if data.get("funding_data"):
                funding = data["funding_data"]
                company_info["funding"] = {
                    "total_funding": funding.get("total_funding_amount"),
                    "last_funding_type": funding.get("last_funding_type"),
                    "last_funding_amount": funding.get("last_funding_amount"),
                    "num_funding_rounds": funding.get("num_funding_rounds")
                }
            
            # Specialties
            if data.get("specialities"):
                company_info["specialties"] = data["specialities"]
            
            # Locations
            if data.get("locations"):
                company_info["locations"] = [
                    {
                        "country": loc.get("country"),
                        "city": loc.get("city"),
                        "is_hq": loc.get("is_hq", False)
                    }
                    for loc in data["locations"]
                ]
            
            return company_info
            
        except Exception as e:
            logger.error(f"Error parsing Nubela company response: {e}")
            return {}
    
    def _parse_search_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Nubela search response into standardized format."""
        try:
            profiles = []
            
            if data.get("results"):
                for result in data["results"]:
                    profile = {
                        "profile_url": result.get("linkedin_profile_url"),
                        "name": result.get("full_name"),
                        "headline": result.get("headline"),
                        "location": result.get("city"),
                        "country": result.get("country"),
                        "industry": result.get("industry"),
                        "summary": result.get("summary")
                    }
                    
                    # Current position
                    if result.get("experiences") and len(result["experiences"]) > 0:
                        current_exp = result["experiences"][0]
                        profile["job_title"] = current_exp.get("title")
                        profile["company"] = current_exp.get("company")
                    
                    profiles.append(profile)
            
            return profiles
            
        except Exception as e:
            logger.error(f"Error parsing Nubela search response: {e}")
            return []
    
    async def validate_api_key(self, api_key: str) -> bool:
        """
        Validate Nubela API key.
        
        Args:
            api_key: API key to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            headers = {
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "nubela-proxycurl-linkedin-company-api.p.rapidapi.com"
            }
            
            # Test with a simple request
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/v2/",
                    headers=headers,
                    params={"url": "https://linkedin.com/in/test"}  # Test URL
                )
                
                # API key is valid if we don't get 401/403
                return response.status_code not in [401, 403]
                
        except Exception as e:
            logger.error(f"Error validating Nubela API key: {e}")
            return False
    
    async def get_api_usage(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Get API usage statistics.
        
        Args:
            api_key: Nubela API key
            
        Returns:
            Usage statistics or None if failed
        """
        try:
            # Note: Nubela doesn't provide a direct usage endpoint
            # This would need to be tracked internally or through RapidAPI dashboard
            logger.info("Nubela API usage tracking not directly available")
            return {
                "message": "Usage tracking available through RapidAPI dashboard",
                "rate_limiter_stats": self.rate_limiter.get_stats()
            }
            
        except Exception as e:
            logger.error(f"Error getting Nubela API usage: {e}")
            return None