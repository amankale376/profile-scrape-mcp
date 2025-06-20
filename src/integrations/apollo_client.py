"""Apollo.io API client for contact enrichment."""

import httpx
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from ..utils.logger import get_logger
from ..utils.rate_limiter import ServiceRateLimiters
from ..models.responses import ContactInfo, CompanyInfo

logger = get_logger(__name__)


class ApolloClient:
    """Client for Apollo.io API integration."""
    
    def __init__(self, api_key: str):
        """
        Initialize Apollo client.
        
        Args:
            api_key: Apollo.io API key
        """
        self.api_key = api_key
        self.base_url = "https://api.apollo.io/api/v1"
        self.headers = {
            "accept": "application/json",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def find_person_match(
        self,
        person_name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company_name: Optional[str] = None,
        reveal_personal_emails: bool = True,
        reveal_phone_number: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Find person match using Apollo.io API.
        
        Args:
            person_name: Full name of the person
            first_name: First name of the person
            last_name: Last name of the person
            company_name: Company name
            reveal_personal_emails: Whether to reveal personal emails
            reveal_phone_number: Whether to reveal phone numbers
            
        Returns:
            Apollo API response or None if failed
        """
        if not company_name:
            logger.warning("Company name is required for Apollo person match")
            return None
        
        if not (person_name or (first_name and last_name)):
            logger.warning("Person name or first/last name is required for Apollo person match")
            return None
        
        # Apply rate limiting
        await ServiceRateLimiters.wait_for_apollo()
        
        try:
            params = {
                "organization_name": company_name,
                "reveal_personal_emails": reveal_personal_emails,
                "reveal_phone_number": reveal_phone_number,
            }
            
            if person_name:
                params["name"] = person_name
            else:
                params["first_name"] = first_name
                params["last_name"] = last_name
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Apollo API request for {person_name or f'{first_name} {last_name}'} at {company_name}")
                
                response = await client.post(
                    f"{self.base_url}/people/match",
                    headers=self.headers,
                    json=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Apollo API success for {person_name or f'{first_name} {last_name}'}")
                    return data
                elif response.status_code == 401:
                    logger.error("Apollo API authentication failed - check API key")
                    return None
                elif response.status_code == 429:
                    logger.warning("Apollo API rate limit exceeded")
                    return None
                else:
                    logger.warning(f"Apollo API returned status {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Apollo API error: {e}")
            return None
    
    def extract_contact_info(self, apollo_response: Dict[str, Any]) -> ContactInfo:
        """
        Extract contact information from Apollo API response.
        
        Args:
            apollo_response: Apollo API response
            
        Returns:
            ContactInfo object
        """
        try:
            person_data = apollo_response.get("person", {})
            organization_data = person_data.get("organization", {})
            
            contact_info = ContactInfo(
                email=person_data.get("email"),
                phone=organization_data.get("primary_phone", {}).get("number"),
                company_phone=organization_data.get("sanitized_phone")
            )
            
            return contact_info
            
        except Exception as e:
            logger.error(f"Error extracting contact info from Apollo response: {e}")
            return ContactInfo()
    
    def extract_company_info(self, apollo_response: Dict[str, Any]) -> CompanyInfo:
        """
        Extract company information from Apollo API response.
        
        Args:
            apollo_response: Apollo API response
            
        Returns:
            CompanyInfo object
        """
        try:
            person_data = apollo_response.get("person", {})
            organization_data = person_data.get("organization", {})
            
            company_info = CompanyInfo(
                name=organization_data.get("name"),
                description=organization_data.get("short_description"),
                website=organization_data.get("website_url")
            )
            
            return company_info
            
        except Exception as e:
            logger.error(f"Error extracting company info from Apollo response: {e}")
            return CompanyInfo()
    
    async def enrich_profile(
        self,
        person_name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> tuple[Optional[ContactInfo], Optional[CompanyInfo]]:
        """
        Enrich profile with contact and company information.
        
        Args:
            person_name: Full name of the person
            first_name: First name of the person
            last_name: Last name of the person
            company_name: Company name
            
        Returns:
            Tuple of (ContactInfo, CompanyInfo) or (None, None) if failed
        """
        apollo_response = await self.find_person_match(
            person_name=person_name,
            first_name=first_name,
            last_name=last_name,
            company_name=company_name
        )
        
        if not apollo_response:
            return None, None
        
        contact_info = self.extract_contact_info(apollo_response)
        company_info = self.extract_company_info(apollo_response)
        
        return contact_info, company_info