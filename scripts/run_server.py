#!/usr/bin/env python3
"""
CLI script to run the Profile Scraping MCP Server.
"""

import sys
import os
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.server import main
from src.utils.config import config
from src.utils.logger import setup_logger, get_logger


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Profile Scraping MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_server.py                    # Run with default settings
  python scripts/run_server.py --debug            # Run in debug mode
  python scripts/run_server.py --port 8080        # Run on custom port
  python scripts/run_server.py --validate-keys    # Validate API keys only
        """
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the server to (default: localhost)"
    )
    
    parser.add_argument(
        "--validate-keys",
        action="store_true",
        help="Validate API keys and exit"
    )
    
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all caches and exit"
    )
    
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show server statistics and exit"
    )
    
    return parser.parse_args()


async def validate_api_keys():
    """Validate all configured API keys."""
    from src.services.enrichment_service import EnrichmentService
    from src.integrations.ai_client import AIClient
    
    logger = get_logger(__name__)
    
    logger.info("Validating API keys...")
    
    # Validate enrichment API keys
    enrichment_service = EnrichmentService()
    enrichment_results = await enrichment_service.validate_api_keys()
    
    # Validate AI API keys
    ai_client = AIClient()
    ai_providers = ai_client.get_available_providers()
    
    # Print results
    print("\n=== API Key Validation Results ===")
    
    print("\nEnrichment APIs:")
    for provider, is_valid in enrichment_results.items():
        status = "✓ Valid" if is_valid else "✗ Invalid/Missing"
        print(f"  {provider.capitalize()}: {status}")
    
    print("\nAI Providers:")
    if ai_providers:
        for provider in ai_providers:
            print(f"  {provider.capitalize()}: ✓ Available")
    else:
        print("  No AI providers configured")
    
    # Check missing keys
    missing_keys = config.validate_api_keys()
    if missing_keys:
        print(f"\nMissing API keys: {', '.join(missing_keys)}")
        print("Add them to your .env file for full functionality")
    else:
        print("\n✓ All API keys are configured")


async def clear_all_caches():
    """Clear all caches."""
    from src.services.profile_service import ProfileService
    from src.services.enrichment_service import EnrichmentService
    from src.services.validation_service import ValidationService
    
    logger = get_logger(__name__)
    
    logger.info("Clearing all caches...")
    
    profile_service = ProfileService()
    enrichment_service = EnrichmentService()
    validation_service = ValidationService()
    
    results = []
    results.append(await profile_service.clear_cache())
    results.append(await enrichment_service.clear_cache())
    results.append(await validation_service.clear_cache())
    
    if all(results):
        print("✓ All caches cleared successfully")
    else:
        print("✗ Some caches failed to clear")


async def show_stats():
    """Show server statistics."""
    from src.services.profile_service import ProfileService
    from src.services.search_service import SearchService
    from src.services.enrichment_service import EnrichmentService
    from src.services.validation_service import ValidationService
    
    logger = get_logger(__name__)
    
    logger.info("Gathering server statistics...")
    
    profile_service = ProfileService()
    search_service = SearchService()
    enrichment_service = EnrichmentService()
    validation_service = ValidationService()
    
    print("\n=== Server Statistics ===")
    
    # Profile stats
    profile_stats = await profile_service.get_profile_stats()
    print(f"\nProfile Service:")
    print(f"  Cache hits: {profile_stats.get('cache_stats', {}).get('hits', 0)}")
    print(f"  Cache misses: {profile_stats.get('cache_stats', {}).get('misses', 0)}")
    
    # Search stats
    search_stats = await search_service.get_search_stats()
    print(f"\nSearch Service:")
    print(f"  Total searches: {search_stats.get('total_searches', 0)}")
    print(f"  Recent searches (24h): {search_stats.get('recent_searches_24h', 0)}")
    print(f"  Average results per search: {search_stats.get('average_results_per_search', 0)}")
    
    # Enrichment stats
    enrichment_stats = await enrichment_service.get_enrichment_stats()
    print(f"\nEnrichment Service:")
    available_providers = enrichment_stats.get('available_providers', {})
    print(f"  Apollo available: {available_providers.get('apollo', False)}")
    print(f"  Nubela available: {available_providers.get('nubela', False)}")
    
    # Validation stats
    validation_stats = await validation_service.get_validation_stats()
    print(f"\nValidation Service:")
    ai_providers = validation_stats.get('available_ai_providers', [])
    print(f"  Available AI providers: {', '.join(ai_providers) if ai_providers else 'None'}")


def main_cli():
    """Main CLI entry point."""
    args = parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logger(level=log_level)
    logger = get_logger(__name__)
    
    # Handle special commands
    if args.validate_keys:
        import asyncio
        asyncio.run(validate_api_keys())
        return
    
    if args.clear_cache:
        import asyncio
        asyncio.run(clear_all_caches())
        return
    
    if args.stats:
        import asyncio
        asyncio.run(show_stats())
        return
    
    # Run the server
    logger.info(f"Starting Profile Scraping MCP Server...")
    logger.info(f"Debug mode: {args.debug}")
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main_cli()