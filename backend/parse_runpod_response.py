#!/usr/bin/env python3
"""Helper script to parse RunPod API responses."""

import json
import sys


def parse_templates(data):
    """Parse templates response."""
    if isinstance(data, list):
        if len(data) == 0:
            print("No templates found.")
        else:
            print(f"Found {len(data)} templates:")
            print("=" * 50)
            for template in data:
                print(f"Name: {template.get('name', 'N/A')}")
                print(f"ID: {template.get('id', 'N/A')}")
                print(f"Image: {template.get('imageName', 'N/A')}")
                print(f"Runtime: {template.get('runtime', 'N/A')}")
                print("-" * 30)
    else:
        print("API Response:", json.dumps(data, indent=2))


def parse_endpoints(data):
    """Parse endpoints response."""
    if isinstance(data, list):
        if len(data) == 0:
            print("No endpoints found. Create one with: just runpod-create-endpoint")
        else:
            print(f"Found {len(data)} endpoints:")
            print("=" * 50)
            for endpoint in data:
                print(f"Name: {endpoint.get('name', 'N/A')}")
                print(f"ID: {endpoint.get('id', 'N/A')}")
                print(f"Status: {endpoint.get('status', 'N/A')}")
                print(
                    f"Workers: {endpoint.get('workersMin', 0)}-{endpoint.get('workersMax', 0)}"
                )
                print(f"GPU: {endpoint.get('gpuTypeIds', 'N/A')}")
                print("-" * 30)
    else:
        print("API Response:", json.dumps(data, indent=2))


def main():
    """Main parser function."""
    if len(sys.argv) < 2:
        print("Usage: python parse_runpod_response.py <templates|endpoints>")
        sys.exit(1)

    response_type = sys.argv[1]

    try:
        data = json.load(sys.stdin)

        if response_type == "templates":
            parse_templates(data)
        elif response_type == "endpoints":
            parse_endpoints(data)
        else:
            print(f"Unknown response type: {response_type}")
            print("Raw response:", json.dumps(data, indent=2))

    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        sys.stdin.seek(0)
        raw_response = sys.stdin.read()
        print("Raw response:", raw_response)
    except Exception as e:
        print(f"Error: {e}")
        sys.stdin.seek(0)
        raw_response = sys.stdin.read()
        print("Raw response:", raw_response)


if __name__ == "__main__":
    main()
