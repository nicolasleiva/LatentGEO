
import requests
import time
import os
import sys

BASE_URL = "http://localhost:8000"

def wait_for_backend():
    print("Waiting for backend to be ready...")
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/health")
            if r.status_code == 200:
                print("Backend is ready!")
                return True
        except:
            pass
        time.sleep(2)
    return False

def test_docker_pdf_generation():
    if not wait_for_backend():
        print("Backend not available at http://localhost:8000")
        sys.exit(1)

    # 1. Create a quick dummy audit
    print("Creating test audit...")
    audit_data = {
        "url": "https://example.com/docker-test",
        "competitors": [],
        "market": "us" # Minimal config to avoid heavy tasks if possible, but we need to pass validation
    }
    
    # We use a trick: if we don't pass 'competitors', the pipeline might not start automatically (depending on logic).
    # But checking the code: create_audit starts pipeline if competitors OR market is present.
    # We want to minimize external calls.
    # Actually, we can just create it without config, then manually set status to COMPLETED via DB?? 
    # No, we can't access DB easily from here.
    
    # We will create an audit and wait for it, OR we can try to generate PDF for an OLD audit if one exists.
    # Let's try to list audits first.
    
    r = requests.get(f"{BASE_URL}/audits?limit=1")
    audits = r.json()
    
    target_audit_id = None
    
    if audits:
        target_audit_id = audits[0]['id']
        status = audits[0]['status']
        print(f"Found existing audit {target_audit_id} with status {status}")
        
        # If not completed, we might fail generating PDF.
        if status != "completed":
            print("Audit not completed. We need a completed audit to generate PDF.")
            # We can try to wait or just warn.
    else:
        # Create one
        r = requests.post(f"{BASE_URL}/audits", json={"url": "https://docker-test.com"})
        audit = r.json()
        target_audit_id = audit['id']
        print(f"Created new audit {target_audit_id}")
        
        # We need to simulate completion or force it. 
        # Since this is a black-box test against Docker, we can't easily force DB state.
        # However, the user wants to test "when using docker", implying the whole flow.
        pass

    if not target_audit_id:
        print("No audit ID available.")
        return

    print(f"Attempting to generate PDF for Audit {target_audit_id} (V11)...")
    
    # Call the NEW endpoint
    try:
        url = f"{BASE_URL}/api/audits/{target_audit_id}/generate-pdf?force_pagespeed_refresh=false"
        # Note: In audits.py config, router prefix is usually /audits, verify main.py
        # Actually in audits.py: @router.post("/{audit_id}/generate-pdf") 
        # In main.py: app.include_router(audits.router, prefix="/audits", tags=["audits"])
        # So URL is /audits/{id}/generate-pdf
        
        url = f"{BASE_URL}/audits/{target_audit_id}/generate-pdf"
        print(f"POST {url}")
        r = requests.post(url)
        
        if r.status_code == 200:
            data = r.json()
            print("SUCCESS: PDF Generated!")
            print(f"Path: {data.get('pdf_path')}")
            print(f"Size: {data.get('file_size')} bytes")
            print(f"PageSpeed Included: {data.get('pagespeed_included')}")
        else:
            print(f"Request failed with {r.status_code}: {r.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_docker_pdf_generation()
