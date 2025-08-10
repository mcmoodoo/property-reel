#!/usr/bin/env python3
"""Update RunPod template with new Docker image."""

import os
import sys
import requests
from utils.config import settings

def update_template_image(template_id: str, new_image: str):
    """Update RunPod template with new Docker image."""
    
    api_key = os.getenv('RUNPOD_API_KEY') or settings.runpod_api_key
    if not api_key:
        print("❌ RUNPOD_API_KEY not found")
        return False
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Update template
    update_data = {
        "imageName": new_image
    }
    
    try:
        print(f"🔄 Updating template {template_id} with image: {new_image}")
        
        response = requests.patch(
            f"https://rest.runpod.io/v1/templates/{template_id}",
            headers=headers,
            json=update_data,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Template updated successfully!")
            print("⚠️  Note: Endpoint workers will use new image on next cold start")
            return True
        else:
            print(f"❌ Failed to update template: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Error updating template: {e}")
        return False

def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python update_runpod_image.py <template_id> <docker_image>")
        print("Example: python update_runpod_image.py fmhv2snzok yourusername/real-estate-processor:latest")
        sys.exit(1)
    
    template_id = sys.argv[1]
    docker_image = sys.argv[2]
    
    success = update_template_image(template_id, docker_image)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()