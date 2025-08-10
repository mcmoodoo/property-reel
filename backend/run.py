#!/usr/bin/env python
"""Simple runner script for the backend API."""

import os
import sys
from pathlib import Path


def check_env():
    """Check if .env file exists, create from example if not."""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists():
        if env_example.exists():
            print("⚠️  No .env file found. Creating from .env.example...")
            env_example.rename(env_file)
            print("✅ Created .env file. Please edit it with your configuration.")
            print("   Then run this script again.")
            sys.exit(1)
        else:
            print("❌ No .env or .env.example file found.")
            print("   Please create a .env file with your configuration.")
            sys.exit(1)


def run():
    """Run the FastAPI application."""
    check_env()
    
    # Import here to ensure .env is loaded
    from utils.config import settings
    import uvicorn
    
    print("🚀 Starting Real Estate Video Processing Backend")
    print(f"📍 API: http://{settings.api_host}:{settings.api_port}")
    
    if settings.debug:
        print(f"📚 Docs: http://localhost:{settings.api_port}/docs")
        print("⚠️  Debug mode enabled - auto-reload is active")
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
        access_log=True
    )


if __name__ == "__main__":
    run()