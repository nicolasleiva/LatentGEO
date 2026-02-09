
import unittest
from unittest.mock import MagicMock
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.services.pipeline_service import PipelineService

class TestNormalization(unittest.TestCase):
    def test_normalize_items_keywords(self):
        # Mock data as it comes from DB (list of models)
        mock_kw = MagicMock()
        mock_kw.term = "test term"
        mock_kw.volume = 100
        mock_kw.difficulty = 10
        mock_kw.cpc = 1.0
        mock_kw.intent = "Commercial"
        
        # Test direct list of objects
        data = [mock_kw]
        # normalize_items is a static method (if I made it so) or a local function 
        # Actually in my previous edit I defined it inside generate_report or as a helper.
        # Let me check where I put 'normalize_items'.
        pass

if __name__ == "__main__":
    # Check where normalize_items is defined
    with open("backend/app/services/pipeline_service.py", "r", encoding="utf-8") as f:
        content = f.read()
        if "def normalize_items" in content:
            print("normalize_items found in pipeline_service.py")
        else:
            print("normalize_items NOT found as global function")
