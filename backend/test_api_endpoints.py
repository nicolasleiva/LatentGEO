import json

import requests

BASE_URL = "http://localhost:8000/api"


def test_keywords():
    print("Testing Keywords Research...")
    url = f"{BASE_URL}/keywords/research/1"
    params = {"domain": "v0-auditor-geo-landing-page.vercel.app"}
    try:
        response = requests.post(url, params=params, json=[], timeout=90)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"Success: {len(response.json())} keywords found")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")


def test_backlinks():
    print("\nTesting Backlinks Analysis...")
    url = f"{BASE_URL}/backlinks/analyze/1"
    params = {"domain": "v0-auditor-geo-landing-page.vercel.app"}
    try:
        response = requests.post(url, params=params, timeout=90)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"Success: {len(response.json())} backlinks found")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")


def test_rank_tracking():
    print("\nTesting Rank Tracking...")
    url = f"{BASE_URL}/v1/rank-tracking/track/1"
    params = {"domain": "v0-auditor-geo-landing-page.vercel.app"}
    try:
        response = requests.post(
            url, params=params, json=["seo auditor", "geo seo tool"], timeout=90
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"Success: {len(response.json())} rankings tracked")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")


def test_llm_visibility():
    print("\nTesting LLM Visibility Analysis...")
    url = f"{BASE_URL}/v1/llm-visibility/check/1"
    params = {"brand_name": "Auditor GEO"}
    try:
        response = requests.post(
            url, params=params, json=["Is Auditor GEO a good tool?"], timeout=90
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"Success: {len(response.json())} visibility checks completed")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")


if __name__ == "__main__":
    test_keywords()
    test_backlinks()
    test_rank_tracking()
    test_llm_visibility()
