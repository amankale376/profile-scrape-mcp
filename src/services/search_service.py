"""Search service for handling LinkedIn profile searches."""

import asyncio
import time
import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from ..core.scraper import LinkedInScraper
from ..integrations.ai_client import AIClient
from ..models.responses import ProfileData, SearchMetadata, SearchHistoryItem
from ..utils.config import config
from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter
from ..utils.cache import CacheManager

logger = get_logger(__name__)


class SearchService:
    """Service for handling LinkedIn profile searches."""
    
    def __init__(self):
        """Initialize the search service."""
        self.scraper = LinkedInScraper()
        self.ai_client = AIClient()
        self.rate_limiter = RateLimiter(
            max_requests=config.linkedin_rate_limit,
            time_window=60
        )
        self.cache_manager = CacheManager(
            db_path=config.database_path.replace('.db', '_searches.db'),
            ttl=config.cache_ttl
        )
        self._init_search_history_db()
    
    def _init_search_history_db(self):
        """Initialize search history database."""
        try:
            with sqlite3.connect(config.database_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS search_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query TEXT NOT NULL,
                        locations TEXT,
                        num_results INTEGER,
                        profiles_found INTEGER,
                        search_time_ms INTEGER,
                        timestamp INTEGER,
                        metadata TEXT
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Error initializing search history database: {e}")
    
    async def basic_search(
        self,
        query: str,
        num_results: int = 10,
        locations: Optional[List[str]] = None
    ) -> Tuple[List[ProfileData], SearchMetadata]:
        """
        Perform a basic LinkedIn profile search.
        
        Args:
            query: Search query string
            num_results: Number of results to return
            locations: Optional list of locations to filter by
            
        Returns:
            Tuple of (profiles, search_metadata)
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting basic search: '{query}' (results: {num_results})")
            
            # Check cache first
            cache_key = f"basic_search:{query}:{num_results}:{locations}"
            if config.enable_caching:
                cached_result = self.cache_manager.get(cache_key)
                if cached_result:
                    logger.info("Returning cached search results")
                    return cached_result["profiles"], cached_result["metadata"]
            
            # Rate limiting
            await self.rate_limiter.acquire()
            
            # Expand query using AI if available
            expanded_query = await self._expand_search_query(query)
            search_query = expanded_query if expanded_query else query
            
            # Perform LinkedIn search
            search_results = await self.scraper.search_profiles(
                query=search_query,
                num_results=num_results,
                locations=locations
            )
            
            if not search_results:
                logger.warning(f"No search results found for query: {query}")
                return [], self._create_empty_metadata(query, locations)
            
            # Process search results
            profiles = []
            for result in search_results[:num_results]:
                profile_data = ProfileData(
                    profile_url=result.get("profile_url", ""),
                    name=result.get("name", ""),
                    headline=result.get("headline", ""),
                    company=result.get("company", ""),
                    job_title=result.get("job_title", ""),
                    location=result.get("location", ""),
                    followers_count=result.get("followers_count"),
                    connections_count=result.get("connections_count")
                )
                profiles.append(profile_data)
            
            # Create metadata
            search_time_ms = int((time.time() - start_time) * 1000)
            metadata = SearchMetadata(
                query_used=search_query,
                original_query=query,
                locations_searched=locations or [],
                total_urls_found=len(search_results),
                duplicates_removed=0,
                search_time_ms=search_time_ms
            )
            
            # Cache the result
            if config.enable_caching:
                cache_data = {"profiles": profiles, "metadata": metadata}
                self.cache_manager.set(cache_key, cache_data, ttl=1800)  # 30 minutes
            
            # Save to search history
            await self._save_search_history(
                query=query,
                locations=locations,
                num_results=num_results,
                profiles_found=len(profiles),
                search_time_ms=search_time_ms,
                metadata=metadata.dict()
            )
            
            logger.info(f"Basic search completed: found {len(profiles)} profiles in {search_time_ms}ms")
            return profiles, metadata
            
        except Exception as e:
            logger.error(f"Error in basic search: {e}")
            search_time_ms = int((time.time() - start_time) * 1000)
            return [], SearchMetadata(
                query_used=query,
                original_query=query,
                locations_searched=locations or [],
                total_urls_found=0,
                duplicates_removed=0,
                search_time_ms=search_time_ms
            )
    
    async def global_search(
        self,
        query: str,
        target_results: int = 50,
        locations: Optional[List[str]] = None
    ) -> Tuple[List[ProfileData], SearchMetadata]:
        """
        Perform a global LinkedIn search across multiple locations.
        
        Args:
            query: Search query string
            target_results: Target number of total results
            locations: List of locations to search in
            
        Returns:
            Tuple of (profiles, search_metadata)
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting global search: '{query}' (target: {target_results})")
            
            # Use default global locations if none provided
            if not locations:
                locations = [
                    "United States", "United Kingdom", "Canada", "Australia",
                    "Germany", "France", "Netherlands", "India", "Singapore"
                ]
            
            # Calculate results per location
            results_per_location = max(1, target_results // len(locations))
            
            # Search in each location concurrently
            search_tasks = []
            for location in locations:
                task = self._search_in_location(
                    query=query,
                    location=location,
                    num_results=results_per_location
                )
                search_tasks.append(task)
            
            # Execute searches concurrently
            location_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Combine and deduplicate results
            all_profiles = []
            seen_urls = set()
            duplicates_removed = 0
            
            for result in location_results:
                if isinstance(result, Exception):
                    logger.error(f"Location search failed: {result}")
                    continue
                
                profiles, _ = result
                for profile in profiles:
                    if profile.profile_url not in seen_urls:
                        all_profiles.append(profile)
                        seen_urls.add(profile.profile_url)
                    else:
                        duplicates_removed += 1
            
            # Limit to target results
            final_profiles = all_profiles[:target_results]
            
            # Create metadata
            search_time_ms = int((time.time() - start_time) * 1000)
            metadata = SearchMetadata(
                query_used=query,
                original_query=query,
                locations_searched=locations,
                total_urls_found=len(all_profiles),
                duplicates_removed=duplicates_removed,
                search_time_ms=search_time_ms
            )
            
            # Save to search history
            await self._save_search_history(
                query=query,
                locations=locations,
                num_results=target_results,
                profiles_found=len(final_profiles),
                search_time_ms=search_time_ms,
                metadata=metadata.dict()
            )
            
            logger.info(f"Global search completed: found {len(final_profiles)} profiles in {search_time_ms}ms")
            return final_profiles, metadata
            
        except Exception as e:
            logger.error(f"Error in global search: {e}")
            search_time_ms = int((time.time() - start_time) * 1000)
            return [], SearchMetadata(
                query_used=query,
                original_query=query,
                locations_searched=locations or [],
                total_urls_found=0,
                duplicates_removed=0,
                search_time_ms=search_time_ms
            )
    
    async def _search_in_location(
        self,
        query: str,
        location: str,
        num_results: int
    ) -> Tuple[List[ProfileData], SearchMetadata]:
        """Search for profiles in a specific location."""
        try:
            # Rate limiting
            await self.rate_limiter.acquire()
            
            # Perform search with location filter
            search_results = await self.scraper.search_profiles(
                query=query,
                num_results=num_results,
                locations=[location]
            )
            
            if not search_results:
                return [], self._create_empty_metadata(query, [location])
            
            # Convert to ProfileData objects
            profiles = []
            for result in search_results:
                profile_data = ProfileData(
                    profile_url=result.get("profile_url", ""),
                    name=result.get("name", ""),
                    headline=result.get("headline", ""),
                    company=result.get("company", ""),
                    job_title=result.get("job_title", ""),
                    location=result.get("location", location),
                    followers_count=result.get("followers_count"),
                    connections_count=result.get("connections_count")
                )
                profiles.append(profile_data)
            
            metadata = SearchMetadata(
                query_used=query,
                original_query=query,
                locations_searched=[location],
                total_urls_found=len(profiles),
                duplicates_removed=0,
                search_time_ms=0  # Will be calculated at higher level
            )
            
            return profiles, metadata
            
        except Exception as e:
            logger.error(f"Error searching in location {location}: {e}")
            return [], self._create_empty_metadata(query, [location])
    
    async def _expand_search_query(self, query: str) -> Optional[str]:
        """Expand search query using AI to improve results."""
        try:
            if not config.get_available_ai_providers():
                return None
            
            prompt = f"""
            Expand this LinkedIn search query to find more relevant profiles:
            Original query: "{query}"
            
            Provide an expanded query that includes:
            - Related job titles and roles
            - Industry keywords
            - Relevant skills and technologies
            - Alternative terminology
            
            Return only the expanded query, no explanation.
            """
            
            expanded_query = await self.ai_client.generate_text(
                prompt=prompt,
                max_tokens=100,
                provider="openai"  # Use most reliable provider
            )
            
            if expanded_query and len(expanded_query.strip()) > len(query):
                logger.info(f"Query expanded from '{query}' to '{expanded_query.strip()}'")
                return expanded_query.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error expanding search query: {e}")
            return None
    
    async def _save_search_history(
        self,
        query: str,
        locations: Optional[List[str]],
        num_results: int,
        profiles_found: int,
        search_time_ms: int,
        metadata: Dict[str, Any]
    ):
        """Save search to history database."""
        try:
            import json
            
            with sqlite3.connect(config.database_path) as conn:
                conn.execute("""
                    INSERT INTO search_history 
                    (query, locations, num_results, profiles_found, search_time_ms, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    query,
                    json.dumps(locations) if locations else None,
                    num_results,
                    profiles_found,
                    search_time_ms,
                    int(time.time()),
                    json.dumps(metadata)
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error saving search history: {e}")
    
    async def get_search_history(
        self,
        limit: int = 50,
        include_results: bool = False
    ) -> Tuple[List[SearchHistoryItem], int]:
        """Get search history."""
        try:
            import json
            
            with sqlite3.connect(config.database_path) as conn:
                # Get total count
                cursor = conn.execute("SELECT COUNT(*) FROM search_history")
                total_searches = cursor.fetchone()[0]
                
                # Get recent searches
                cursor = conn.execute("""
                    SELECT query, locations, num_results, profiles_found, 
                           search_time_ms, timestamp, metadata
                    FROM search_history 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                
                history_items = []
                for row in cursor.fetchall():
                    query, locations_json, num_results, profiles_found, search_time_ms, timestamp, metadata_json = row
                    
                    locations = json.loads(locations_json) if locations_json else []
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    
                    item = SearchHistoryItem(
                        query=query,
                        locations=locations,
                        num_results=num_results,
                        profiles_found=profiles_found,
                        search_time_ms=search_time_ms,
                        timestamp=timestamp,
                        search_date=datetime.fromtimestamp(timestamp).isoformat()
                    )
                    
                    if include_results and "profiles" in metadata:
                        item.profiles = metadata["profiles"]
                    
                    history_items.append(item)
                
                return history_items, total_searches
                
        except Exception as e:
            logger.error(f"Error getting search history: {e}")
            return [], 0
    
    def _create_empty_metadata(
        self,
        query: str,
        locations: Optional[List[str]] = None
    ) -> SearchMetadata:
        """Create empty search metadata."""
        return SearchMetadata(
            query_used=query,
            original_query=query,
            locations_searched=locations or [],
            total_urls_found=0,
            duplicates_removed=0,
            search_time_ms=0
        )
    
    async def get_search_stats(self) -> Dict[str, Any]:
        """Get search statistics."""
        try:
            with sqlite3.connect(config.database_path) as conn:
                # Total searches
                cursor = conn.execute("SELECT COUNT(*) FROM search_history")
                total_searches = cursor.fetchone()[0]
                
                # Recent searches (last 24 hours)
                yesterday = int(time.time()) - 86400
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM search_history WHERE timestamp > ?",
                    (yesterday,)
                )
                recent_searches = cursor.fetchone()[0]
                
                # Average results per search
                cursor = conn.execute("SELECT AVG(profiles_found) FROM search_history")
                avg_results = cursor.fetchone()[0] or 0
                
                # Most common queries
                cursor = conn.execute("""
                    SELECT query, COUNT(*) as count 
                    FROM search_history 
                    GROUP BY query 
                    ORDER BY count DESC 
                    LIMIT 10
                """)
                popular_queries = [{"query": row[0], "count": row[1]} for row in cursor.fetchall()]
                
                return {
                    "total_searches": total_searches,
                    "recent_searches_24h": recent_searches,
                    "average_results_per_search": round(avg_results, 2),
                    "popular_queries": popular_queries,
                    "cache_stats": self.cache_manager.get_stats(),
                    "rate_limiter_stats": self.rate_limiter.get_stats()
                }
                
        except Exception as e:
            logger.error(f"Error getting search stats: {e}")
            return {}