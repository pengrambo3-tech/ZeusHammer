#!/usr/bin/env python3
"""
ZeusHammer Setup

Package installation configuration.

Usage:
    pip install .
    pip install -e .  # Development mode
    pip install -e ".[dev]"  # With dev dependencies
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file, encoding="utf-8") as f:
        requirements = [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

setup(
    name="zueshammer",
    version="2.0.0",
    author="ZeusHammer Team",
    author_email="contact@zueshammer.ai",
    description="Super AI Agent - Claude + Hermes + OpenClaw",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zueshammer/zueshammer",
    project_urls={
        "Bug Tracker": "https://github.com/zueshammer/zueshammer/issues",
        "Documentation": "https://github.com/zueshammer/zueshammer#readme",
        "Source": "https://github.com/zueshammer/zueshammer",
    },
    packages=find_packages(exclude=["tests", "tests.*", "docs"]),
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "voice": [
            "edge-tts>=6.1.0",
            "SpeechRecognition>=3.10.0",
        ],
        "web": [
            "fastapi>=0.100.0",
            "uvicorn>=0.23.0",
            "websockets>=12.0",
        ],
        "browser": [
            "playwright>=1.40.0",
        ],
        "all": [
            "edge-tts>=6.1.0",
            "SpeechRecognition>=3.10.0",
            "fastapi>=0.100.0",
            "uvicorn>=0.23.0",
            "websockets>=12.0",
            "playwright>=1.40.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "zueshammer=src.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="ai agent claude openai gpt assistant mcp",
    include_package_data=True,
    zip_safe=False,
)
