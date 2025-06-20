"""Rate limiting utilities for the Profile Scraping MCP Server."""

import time
import asyncio
from typing import Dict, Optional
from collections import defaultdict, deque
from .logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API calls."""
    
    def __init__(self):
        """Initialize rate limiter."""
        self._buckets: Dict[str, Dict] = defaultdict(lambda: {
            'tokens': 0,
            'last_refill': time.time(),
            'requests': deque()
        })
    
    async def acquire(
        self,
        key: str,
        max_requests: int,
        time_window: int,
        burst_size: Optional[int] = None
    ) -> bool:
        """
        Acquire a token for the given key.
        
        Args:
            key: Unique identifier for the rate limit (e.g., 'linkedin', 'apollo')
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
            burst_size: Maximum burst size (defaults to max_requests)
            
        Returns:
            True if request is allowed, False if rate limited
        """
        if burst_size is None:
            burst_size = max_requests
        
        current_time = time.time()
        bucket = self._buckets[key]
        
        # Clean old requests outside the time window
        while bucket['requests'] and bucket['requests'][0] <= current_time - time_window:
            bucket['requests'].popleft()
        
        # Check if we're within the rate limit
        if len(bucket['requests']) >= max_requests:
            logger.warning(f"Rate limit exceeded for {key}: {len(bucket['requests'])}/{max_requests} requests in {time_window}s")
            return False
        
        # Add current request
        bucket['requests'].append(current_time)
        
        logger.debug(f"Rate limit check passed for {key}: {len(bucket['requests'])}/{max_requests} requests")
        return True
    
    async def wait_if_needed(
        self,
        key: str,
        max_requests: int,
        time_window: int,
        burst_size: Optional[int] = None
    ) -> None:
        """
        Wait if rate limit would be exceeded.
        
        Args:
            key: Unique identifier for the rate limit
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
            burst_size: Maximum burst size (defaults to max_requests)
        """
        while not await self.acquire(key, max_requests, time_window, burst_size):
            # Calculate wait time until oldest request expires
            bucket = self._buckets[key]
            if bucket['requests']:
                oldest_request = bucket['requests'][0]
                wait_time = time_window - (time.time() - oldest_request)
                if wait_time > 0:
                    logger.info(f"Rate limited for {key}, waiting {wait_time:.2f} seconds")
                    await asyncio.sleep(wait_time + 0.1)  # Add small buffer
                else:
                    # Clean up and try again
                    bucket['requests'].popleft()
    
    def get_remaining_requests(self, key: str, max_requests: int, time_window: int) -> int:
        """
        Get remaining requests for the given key.
        
        Args:
            key: Unique identifier for the rate limit
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
            
        Returns:
            Number of remaining requests
        """
        current_time = time.time()
        bucket = self._buckets[key]
        
        # Clean old requests
        while bucket['requests'] and bucket['requests'][0] <= current_time - time_window:
            bucket['requests'].popleft()
        
        return max(0, max_requests - len(bucket['requests']))
    
    def reset(self, key: str) -> None:
        """
        Reset rate limit for the given key.
        
        Args:
            key: Unique identifier for the rate limit
        """
        if key in self._buckets:
            del self._buckets[key]
            logger.info(f"Rate limit reset for {key}")
    
    def get_stats(self) -> Dict[str, Dict]:
        """
        Get rate limiting statistics.
        
        Returns:
            Dictionary with rate limiting stats for each key
        """
        stats = {}
        current_time = time.time()
        
        for key, bucket in self._buckets.items():
            # Clean old requests
            while bucket['requests'] and bucket['requests'][0] <= current_time - 3600:  # 1 hour window
                bucket['requests'].popleft()
            
            stats[key] = {
                'active_requests': len(bucket['requests']),
                'oldest_request_age': current_time - bucket['requests'][0] if bucket['requests'] else 0,
                'newest_request_age': current_time - bucket['requests'][-1] if bucket['requests'] else 0
            }
        
        return stats


# Global rate limiter instance
rate_limiter = RateLimiter()


# Predefined rate limiters for common services
class ServiceRateLimiters:
    """Predefined rate limiters for external services."""
    
    @staticmethod
    async def linkedin_scraping() -> bool:
        """Rate limiter for LinkedIn scraping (100 requests per hour)."""
        return await rate_limiter.acquire("linkedin", max_requests=100, time_window=3600)
    
    @staticmethod
    async def apollo_api() -> bool:
        """Rate limiter for Apollo API (1000 requests per month)."""
        return await rate_limiter.acquire("apollo", max_requests=1000, time_window=2592000)  # 30 days
    
    @staticmethod
    async def nubela_api() -> bool:
        """Rate limiter for Nubela API (100 requests per month)."""
        return await rate_limiter.acquire("nubela", max_requests=100, time_window=2592000)  # 30 days
    
    @staticmethod
    async def openai_api() -> bool:
        """Rate limiter for OpenAI API (3500 requests per minute)."""
        return await rate_limiter.acquire("openai", max_requests=3500, time_window=60)
    
    @staticmethod
    async def wait_for_linkedin() -> None:
        """Wait if LinkedIn rate limit would be exceeded."""
        await rate_limiter.wait_if_needed("linkedin", max_requests=100, time_window=3600)
    
    @staticmethod
    async def wait_for_apollo() -> None:
        """Wait if Apollo rate limit would be exceeded."""
        await rate_limiter.wait_if_needed("apollo", max_requests=1000, time_window=2592000)
    
    @staticmethod
    async def wait_for_nubela() -> None:
        """Wait if Nubela rate limit would be exceeded."""
        await rate_limiter.wait_if_needed("nubela", max_requests=100, time_window=2592000)
    
    @staticmethod
    async def wait_for_openai() -> None:
        """Wait if OpenAI rate limit would be exceeded."""
        await rate_limiter.wait_if_needed("openai", max_requests=3500, time_window=60)