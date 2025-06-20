"""
Setup script for profile-scraping-mcp package.
This is a fallback setup.py for compatibility.
"""

from setuptools import setup, find_packages
import os

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements from pyproject.toml or define them here
requirements = [
    "fastmcp>=1.0.0",
    "mcp>=1.9.4",
    "pydantic>=2.0.0",
    "httpx>=0.24.0",
    "beautifulsoup4>=4.12.0",
    "pandas>=2.0.0",
    "python-dotenv>=1.0.0",
    "loguru>=0.7.0",
    "aiofiles>=23.0.0",
    "tenacity>=8.0.0",
    "ratelimit>=2.2.0",
    "openai>=1.0.0",
    "google-generativeai>=0.3.0",
    "requests>=2.31.0",
    "lxml>=4.9.0",
]

dev_requirements = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "isort>=5.12.0",
    "flake8>=6.0.0",
    "mypy>=1.0.0",
    "pre-commit>=3.0.0",
]

setup(
    name="profile-scraping-mcp",
    version="1.0.0",
    author="Profile Scraping Team",
    author_email="team@example.com",
    description="Fast MCP server for LinkedIn profile scraping and enrichment",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/profile-scraping-mcp",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    extras_require={
        "dev": dev_requirements,
    },
    entry_points={
        "console_scripts": [
            "profile-scraping-mcp=src.server:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml", "*.json"],
    },
    keywords=["mcp", "profile-scraping", "linkedin", "data-mining", "contact-enrichment"],
    project_urls={
        "Bug Reports": "https://github.com/your-org/profile-scraping-mcp/issues",
        "Source": "https://github.com/your-org/profile-scraping-mcp",
        "Documentation": "https://github.com/your-org/profile-scraping-mcp#readme",
    },
)