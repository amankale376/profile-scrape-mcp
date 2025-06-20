"""Validation service for AI-powered profile relevance filtering."""

import asyncio
import json
from typing import List, Dict, Any, Optional

from ..integrations.ai_client import AIClient
from ..models.responses import ValidationResult, ProfileData
from ..utils.config import config
from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter
from ..utils.cache import CacheManager

logger = get_logger(__name__)


class ValidationService:
    """Service for validating profile relevance using AI."""
    
    def __init__(self):
        """Initialize the validation service."""
        self.ai_client = AIClient()
        self.rate_limiter = RateLimiter(
            max_requests=config.ai_rate_limit,
            time_window=60
        )
        self.cache_manager = CacheManager(
            db_path=config.database_path.replace('.db', '_validation.db'),
            ttl=config.cache_ttl
        )
    
    async def validate_multiple_profiles(
        self,
        profiles: List[Dict[str, Any]],
        search_criteria: str,
        confidence_threshold: float = 0.7,
        ai_provider: str = "openai"
    ) -> List[ValidationResult]:
        """
        Validate multiple profiles for relevance to search criteria.
        
        Args:
            profiles: List of profile data dictionaries
            search_criteria: Original search criteria/query
            confidence_threshold: Minimum confidence score for relevance
            ai_provider: AI provider to use for validation
            
        Returns:
            List of ValidationResult objects
        """
        try:
            logger.info(f"Validating {len(profiles)} profiles with AI provider: {ai_provider}")
            
            # Process profiles in batches to avoid overwhelming the AI API
            batch_size = 5
            all_results = []
            
            for i in range(0, len(profiles), batch_size):
                batch = profiles[i:i + batch_size]
                logger.info(f"Processing validation batch {i//batch_size + 1}: {len(batch)} profiles")
                
                # Process batch concurrently
                batch_results = await self._validate_batch(
                    profiles=batch,
                    search_criteria=search_criteria,
                    confidence_threshold=confidence_threshold,
                    ai_provider=ai_provider
                )
                
                all_results.extend(batch_results)
                
                # Add delay between batches to respect rate limits
                if i + batch_size < len(profiles):
                    await asyncio.sleep(1)
            
            # Calculate summary statistics
            relevant_count = sum(1 for result in all_results if result.is_relevant)
            avg_confidence = sum(result.confidence_score for result in all_results) / len(all_results)
            
            logger.info(f"Validation completed: {relevant_count}/{len(profiles)} relevant (avg confidence: {avg_confidence:.2f})")
            return all_results
            
        except Exception as e:
            logger.error(f"Error in validate_multiple_profiles: {e}")
            # Return all profiles as failed validation
            return [
                ValidationResult(
                    profile_url=profile.get("profile_url", ""),
                    is_relevant=False,
                    confidence_score=0.0,
                    validation_status="failed",
                    error=str(e)
                )
                for profile in profiles
            ]
    
    async def _validate_batch(
        self,
        profiles: List[Dict[str, Any]],
        search_criteria: str,
        confidence_threshold: float,
        ai_provider: str
    ) -> List[ValidationResult]:
        """Validate a batch of profiles concurrently."""
        semaphore = asyncio.Semaphore(3)  # Limit concurrent AI calls
        
        async def validate_single(profile: Dict[str, Any]) -> ValidationResult:
            async with semaphore:
                return await self.validate_profile(
                    profile=profile,
                    search_criteria=search_criteria,
                    confidence_threshold=confidence_threshold,
                    ai_provider=ai_provider
                )
        
        # Execute all validations concurrently
        tasks = [validate_single(profile) for profile in profiles]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        validation_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Validation failed for profile {i}: {result}")
                validation_results.append(
                    ValidationResult(
                        profile_url=profiles[i].get("profile_url", ""),
                        is_relevant=False,
                        confidence_score=0.0,
                        validation_status="failed",
                        error=str(result)
                    )
                )
            else:
                validation_results.append(result)
        
        return validation_results
    
    async def validate_profile(
        self,
        profile: Dict[str, Any],
        search_criteria: str,
        confidence_threshold: float = 0.7,
        ai_provider: str = "openai"
    ) -> ValidationResult:
        """
        Validate a single profile for relevance to search criteria.
        
        Args:
            profile: Profile data dictionary
            search_criteria: Original search criteria/query
            confidence_threshold: Minimum confidence score for relevance
            ai_provider: AI provider to use for validation
            
        Returns:
            ValidationResult with relevance assessment
        """
        try:
            profile_url = profile.get("profile_url", "")
            logger.info(f"Validating profile: {profile_url}")
            
            # Check cache first
            cache_key = f"validation:{profile_url}:{search_criteria}:{ai_provider}"
            if config.enable_caching:
                cached_result = self.cache_manager.get(cache_key)
                if cached_result:
                    logger.info(f"Returning cached validation for {profile_url}")
                    return ValidationResult(**cached_result)
            
            # Rate limiting
            await self.rate_limiter.acquire()
            
            # Prepare profile summary for AI analysis
            profile_summary = self._create_profile_summary(profile)
            
            # Create validation prompt
            prompt = self._create_validation_prompt(profile_summary, search_criteria)
            
            # Get AI assessment
            ai_response = await self.ai_client.generate_text(
                prompt=prompt,
                max_tokens=200,
                provider=ai_provider
            )
            
            if not ai_response:
                raise Exception("No response from AI provider")
            
            # Parse AI response
            validation_data = self._parse_ai_response(ai_response)
            
            # Create validation result
            confidence_score = validation_data.get("confidence", 0.0)
            is_relevant = confidence_score >= confidence_threshold
            
            result = ValidationResult(
                profile_url=profile_url,
                is_relevant=is_relevant,
                confidence_score=confidence_score,
                relevance_reasons=validation_data.get("reasons", []),
                validation_status="success",
                ai_provider=ai_provider
            )
            
            # Cache the result
            if config.enable_caching:
                self.cache_manager.set(cache_key, result.dict(), ttl=3600)  # 1 hour
            
            logger.info(f"Profile validation completed: {profile_url} - relevant: {is_relevant} (confidence: {confidence_score:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"Error validating profile {profile.get('profile_url', '')}: {e}")
            
            return ValidationResult(
                profile_url=profile.get("profile_url", ""),
                is_relevant=False,
                confidence_score=0.0,
                validation_status="failed",
                error=str(e)
            )
    
    def _create_profile_summary(self, profile: Dict[str, Any]) -> str:
        """Create a concise profile summary for AI analysis."""
        summary_parts = []
        
        # Basic information
        if profile.get("name"):
            summary_parts.append(f"Name: {profile['name']}")
        
        if profile.get("headline"):
            summary_parts.append(f"Headline: {profile['headline']}")
        
        if profile.get("job_title"):
            summary_parts.append(f"Job Title: {profile['job_title']}")
        
        if profile.get("company"):
            summary_parts.append(f"Company: {profile['company']}")
        
        if profile.get("location"):
            summary_parts.append(f"Location: {profile['location']}")
        
        # Additional information
        if profile.get("industry"):
            summary_parts.append(f"Industry: {profile['industry']}")
        
        if profile.get("skills"):
            skills = profile["skills"][:5]  # Limit to top 5 skills
            summary_parts.append(f"Skills: {', '.join(skills)}")
        
        if profile.get("experience"):
            exp_summary = []
            for exp in profile["experience"][:3]:  # Limit to recent 3 experiences
                if exp.get("title") and exp.get("company"):
                    exp_summary.append(f"{exp['title']} at {exp['company']}")
            if exp_summary:
                summary_parts.append(f"Experience: {'; '.join(exp_summary)}")
        
        return "\n".join(summary_parts)
    
    def _create_validation_prompt(self, profile_summary: str, search_criteria: str) -> str:
        """Create AI prompt for profile validation."""
        prompt = f"""
You are an expert recruiter evaluating LinkedIn profiles for relevance to a search query.

SEARCH CRITERIA: "{search_criteria}"

PROFILE TO EVALUATE:
{profile_summary}

TASK: Determine if this profile is relevant to the search criteria.

Consider:
1. Job title alignment with search terms
2. Company/industry relevance
3. Skills and experience match
4. Overall professional background fit

Respond with a JSON object containing:
{{
    "confidence": <float between 0.0 and 1.0>,
    "reasons": [<list of specific reasons for the confidence score>],
    "relevant_aspects": [<list of profile aspects that match the criteria>],
    "concerns": [<list of potential mismatches or concerns>]
}}

Be precise and objective in your assessment.
"""
        return prompt
    
    def _parse_ai_response(self, ai_response: str) -> Dict[str, Any]:
        """Parse AI response into structured data."""
        try:
            # Try to extract JSON from the response
            response_text = ai_response.strip()
            
            # Find JSON block
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                parsed_data = json.loads(json_text)
                
                # Validate required fields
                confidence = float(parsed_data.get("confidence", 0.0))
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
                
                return {
                    "confidence": confidence,
                    "reasons": parsed_data.get("reasons", []),
                    "relevant_aspects": parsed_data.get("relevant_aspects", []),
                    "concerns": parsed_data.get("concerns", [])
                }
            
            # Fallback: try to extract confidence score from text
            confidence = self._extract_confidence_from_text(response_text)
            return {
                "confidence": confidence,
                "reasons": ["AI response could not be fully parsed"],
                "relevant_aspects": [],
                "concerns": []
            }
            
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return {
                "confidence": 0.0,
                "reasons": [f"Failed to parse AI response: {str(e)}"],
                "relevant_aspects": [],
                "concerns": []
            }
    
    def _extract_confidence_from_text(self, text: str) -> float:
        """Extract confidence score from unstructured text."""
        import re
        
        # Look for confidence patterns
        patterns = [
            r"confidence[:\s]+([0-9]*\.?[0-9]+)",
            r"score[:\s]+([0-9]*\.?[0-9]+)",
            r"([0-9]*\.?[0-9]+)(?:\s*(?:out of|/)\s*(?:1|10|100))?",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text.lower())
            if matches:
                try:
                    score = float(matches[0])
                    # Normalize score to [0, 1] range
                    if score > 1:
                        if score <= 10:
                            score = score / 10
                        elif score <= 100:
                            score = score / 100
                        else:
                            score = 1.0
                    return max(0.0, min(1.0, score))
                except ValueError:
                    continue
        
        # Default to low confidence if no score found
        return 0.3
    
    async def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        try:
            cache_stats = self.cache_manager.get_stats()
            rate_limiter_stats = self.rate_limiter.get_stats()
            
            return {
                "cache_stats": cache_stats,
                "rate_limiter_stats": rate_limiter_stats,
                "available_ai_providers": config.get_available_ai_providers()
            }
            
        except Exception as e:
            logger.error(f"Error getting validation stats: {e}")
            return {}
    
    async def clear_cache(self) -> bool:
        """Clear validation cache."""
        try:
            self.cache_manager.clear()
            logger.info("Validation cache cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing validation cache: {e}")
            return False
    
    async def test_ai_provider(self, provider: str) -> Dict[str, Any]:
        """Test an AI provider with a simple validation task."""
        try:
            test_profile = {
                "name": "John Smith",
                "headline": "Software Engineer at Tech Corp",
                "job_title": "Senior Software Engineer",
                "company": "Tech Corp",
                "location": "San Francisco, CA"
            }
            
            test_criteria = "software engineer"
            
            result = await self.validate_profile(
                profile=test_profile,
                search_criteria=test_criteria,
                ai_provider=provider
            )
            
            return {
                "provider": provider,
                "status": "success" if result.validation_status == "success" else "failed",
                "confidence_score": result.confidence_score,
                "error": result.error
            }
            
        except Exception as e:
            logger.error(f"Error testing AI provider {provider}: {e}")
            return {
                "provider": provider,
                "status": "failed",
                "error": str(e)
            }