"""AI client for profile validation and query expansion."""

import json
from typing import List, Dict, Any, Optional
from enum import Enum
import httpx
import openai
import google.generativeai as genai

from ..utils.logger import get_logger
from ..utils.rate_limiter import ServiceRateLimiters
from ..utils.config import config

logger = get_logger(__name__)


class AIProvider(Enum):
    """Available AI providers."""
    OPENAI = "openai"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"


class AIClient:
    """Client for AI-powered profile validation and query expansion."""
    
    def __init__(self):
        """Initialize AI client with available providers."""
        self.available_providers = []
        self._setup_providers()
    
    def _setup_providers(self) -> None:
        """Setup available AI providers based on configuration."""
        # OpenAI
        if config.openai_api_key:
            try:
                openai.api_key = config.openai_api_key
                self.available_providers.append(AIProvider.OPENAI)
                logger.info("OpenAI provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")
        
        # Gemini
        if config.gemini_api_key:
            try:
                genai.configure(api_key=config.gemini_api_key)
                self.available_providers.append(AIProvider.GEMINI)
                logger.info("Gemini provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")
        
        # OpenRouter
        if config.openrouter_api_key:
            self.available_providers.append(AIProvider.OPENROUTER)
            logger.info("OpenRouter provider initialized")
        
        # Ollama
        if config.ollama_base_url:
            self.available_providers.append(AIProvider.OLLAMA)
            logger.info("Ollama provider initialized")
        
        if not self.available_providers:
            logger.warning("No AI providers available")
    
    async def _call_openai(self, messages: List[Dict[str, str]], model: str = "gpt-4o-mini") -> Optional[str]:
        """Call OpenAI API."""
        try:
            await ServiceRateLimiters.wait_for_openai()
            
            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None
    
    async def _call_gemini(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """Call Gemini API."""
        try:
            model = genai.GenerativeModel('gemini-pro')
            
            # Convert messages to Gemini format
            prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
            
            response = await model.generate_content_async(prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
    
    async def _call_openrouter(self, messages: List[Dict[str, str]], model: str = "openai/gpt-4o-mini") -> Optional[str]:
        """Call OpenRouter API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.openrouter_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": 1000,
                        "temperature": 0.7
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    logger.error(f"OpenRouter API error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            return None
    
    async def _call_ollama(self, messages: List[Dict[str, str]], model: str = None) -> Optional[str]:
        """Call Ollama API."""
        try:
            if model is None:
                model = config.ollama_model
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{config.ollama_base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False
                    },
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["message"]["content"].strip()
                else:
                    logger.error(f"Ollama API error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return None
    
    async def chat_completion(self, messages: List[Dict[str, str]], preferred_provider: Optional[str] = None) -> Optional[str]:
        """
        Get chat completion from available AI providers with fallback.
        
        Args:
            messages: List of message dictionaries
            preferred_provider: Preferred provider to try first
            
        Returns:
            AI response or None if all providers failed
        """
        providers_to_try = list(self.available_providers)
        
        # Move preferred provider to front if specified
        if preferred_provider:
            try:
                pref_enum = AIProvider(preferred_provider)
                if pref_enum in providers_to_try:
                    providers_to_try.remove(pref_enum)
                    providers_to_try.insert(0, pref_enum)
            except ValueError:
                logger.warning(f"Unknown preferred provider: {preferred_provider}")
        
        for provider in providers_to_try:
            try:
                logger.debug(f"Trying AI provider: {provider.value}")
                
                if provider == AIProvider.OPENAI:
                    result = await self._call_openai(messages)
                elif provider == AIProvider.GEMINI:
                    result = await self._call_gemini(messages)
                elif provider == AIProvider.OPENROUTER:
                    result = await self._call_openrouter(messages)
                elif provider == AIProvider.OLLAMA:
                    result = await self._call_ollama(messages)
                else:
                    continue
                
                if result:
                    logger.info(f"AI response received from {provider.value}")
                    return result
                    
            except Exception as e:
                logger.warning(f"Provider {provider.value} failed: {e}")
                continue
        
        logger.error("All AI providers failed")
        return None
    
    async def generate_search_queries(self, base_query: str, num_queries: int = 5) -> List[str]:
        """
        Generate additional search queries based on the base query.
        
        Args:
            base_query: Original search query
            num_queries: Number of additional queries to generate
            
        Returns:
            List of generated search queries
        """
        prompt = f"""Generate {num_queries} alternative LinkedIn search queries based on this original query: "{base_query}"

The queries should:
1. Use different keywords and synonyms
2. Target similar professionals but with varied approaches
3. Include location specifiers like "US", "UK", "CA" where appropriate
4. Be specific enough to find relevant LinkedIn profiles
5. Use the format: site:linkedin.com/in [search terms]

Return only the search queries, one per line, without numbering or explanations."""

        messages = [{"role": "user", "content": prompt}]
        
        response = await self.chat_completion(messages)
        if not response:
            logger.warning("Failed to generate search queries, using base query variations")
            return [f"site:linkedin.com/in {base_query} expert", f"site:linkedin.com/in {base_query} professional"]
        
        # Parse response into individual queries
        queries = [line.strip() for line in response.split('\n') if line.strip()]
        return queries[:num_queries]
    
    async def validate_profile_relevance(self, profile_data: Dict[str, Any], search_criteria: str) -> tuple[bool, float, str]:
        """
        Validate if a profile is relevant to the search criteria.
        
        Args:
            profile_data: Profile information
            search_criteria: Original search criteria
            
        Returns:
            Tuple of (is_relevant, confidence_score, reasoning)
        """
        profile_text = f"""
Name: {profile_data.get('name', 'N/A')}
Headline: {profile_data.get('headline', 'N/A')}
Company: {profile_data.get('company', 'N/A')}
Job Title: {profile_data.get('job_title', 'N/A')}
"""

        prompt = f"""Analyze if this LinkedIn profile is relevant to the search criteria: "{search_criteria}"

Profile Information:
{profile_text}

Please evaluate:
1. How well does this profile match the search criteria?
2. Is this person likely to be what the searcher is looking for?
3. Rate the relevance on a scale of 0.0 to 1.0

Respond in JSON format:
{{
    "is_relevant": true/false,
    "confidence_score": 0.0-1.0,
    "reasoning": "Brief explanation of why this profile is or isn't relevant"
}}"""

        messages = [{"role": "user", "content": prompt}]
        
        response = await self.chat_completion(messages)
        if not response:
            logger.warning("Failed to validate profile relevance, assuming relevant")
            return True, 0.5, "AI validation unavailable"
        
        try:
            # Try to parse JSON response
            result = json.loads(response)
            return (
                result.get("is_relevant", True),
                float(result.get("confidence_score", 0.5)),
                result.get("reasoning", "No reasoning provided")
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse AI validation response: {e}")
            # Fallback: check if response contains positive indicators
            response_lower = response.lower()
            is_relevant = any(word in response_lower for word in ["relevant", "match", "suitable", "yes", "true"])
            return is_relevant, 0.5, "Parsed from text response"
    
    async def generate_activity_summary(self, profile_data: Dict[str, Any]) -> Optional[str]:
        """
        Generate a summary of profile activity and interests.
        
        Args:
            profile_data: Profile information including activity data
            
        Returns:
            Activity summary or None if generation failed
        """
        activity_text = profile_data.get('activity_text', '')
        if not activity_text:
            return None
        
        prompt = f"""Generate a concise summary of this LinkedIn user's activity and interests.
Focus on their professional interests, expertise areas, and content they engage with.
Provide 3-4 lines that would be useful for personalized outreach.

User activity:
{activity_text}

Keep the summary professional and factual."""

        messages = [{"role": "user", "content": prompt}]
        
        response = await self.chat_completion(messages)
        return response