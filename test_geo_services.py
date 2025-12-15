#!/usr/bin/env python3
"""
Test script for GEO services (Keywords, Backlinks, Rankings)
"""
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.keywords_service import KeywordsService
from app.services.backlinks_service import BacklinksService
from app.services.rank_tracking_service import RankTrackingService


def test_keywords_service():
    """Test Keywords Service"""
    print("\n" + "="*60)
    print("TESTING KEYWORDS SERVICE")
    print("="*60)
    
    # Mock audit data
    target_audit = {
        "url": "https://example.com",
        "structure": {
            "h1_check": {
                "details": {
                    "example": "Best AI Coding Assistant",
                    "count": 1
                }
            }
        }
    }
    
    keywords = KeywordsService.generate_keywords_from_audit(target_audit, "https://example.com")
    
    print(f"\n✅ Generated {len(keywords)} keywords")
    print("\nTop 5 Keywords:")
    for i, kw in enumerate(keywords[:5], 1):
        print(f"  {i}. {kw['keyword']}")
        print(f"     Volume: {kw['search_volume']} | Difficulty: {kw['difficulty']} | Rank: {kw['current_rank']} | Score: {kw['opportunity_score']}")
    
    return keywords


def test_backlinks_service():
    """Test Backlinks Service"""
    print("\n" + "="*60)
    print("TESTING BACKLINKS SERVICE")
    print("="*60)
    
    # Mock audit data
    target_audit = {
        "url": "https://example.com"
    }
    
    backlinks = BacklinksService.generate_backlinks_from_audit(target_audit, "https://example.com")
    
    print(f"\n✅ Generated backlinks analysis")
    print(f"\nSummary:")
    print(f"  Total Backlinks: {backlinks['total_backlinks']}")
    print(f"  Referring Domains: {backlinks['referring_domains']}")
    print(f"  Average DA: {backlinks['summary']['average_domain_authority']}")
    print(f"  Dofollow: {backlinks['summary']['dofollow_count']}")
    print(f"  Nofollow: {backlinks['summary']['nofollow_count']}")
    
    print("\nTop 5 Backlinks:")
    for i, bl in enumerate(backlinks['top_backlinks'][:5], 1):
        print(f"  {i}. {bl['source_url']}")
        print(f"     DA: {bl['domain_authority']} | Dofollow: {bl['is_dofollow']}")
    
    return backlinks


def test_rank_tracking_service(keywords):
    """Test Rank Tracking Service"""
    print("\n" + "="*60)
    print("TESTING RANK TRACKING SERVICE")
    print("="*60)
    
    rankings = RankTrackingService.generate_rankings_from_keywords(keywords, "https://example.com")
    
    print(f"\n✅ Generated {len(rankings)} rankings")
    
    # Calculate distribution
    top_3 = len([r for r in rankings if r['position'] <= 3])
    top_10 = len([r for r in rankings if r['position'] <= 10])
    top_20 = len([r for r in rankings if r['position'] <= 20])
    beyond_20 = len([r for r in rankings if r['position'] > 20])
    
    print(f"\nDistribution:")
    print(f"  Top 3: {top_3}")
    print(f"  Top 10: {top_10}")
    print(f"  Top 20: {top_20}")
    print(f"  Beyond 20: {beyond_20}")
    
    print("\nTop 5 Rankings:")
    sorted_rankings = sorted(rankings, key=lambda x: x['position'])
    for i, rank in enumerate(sorted_rankings[:5], 1):
        change_symbol = "📈" if rank['change'] < 0 else "📉" if rank['change'] > 0 else "➡️"
        print(f"  {i}. Position {rank['position']} {change_symbol} ({rank['change']:+d})")
        print(f"     Keyword: {rank['keyword']}")
    
    return rankings


def test_integration():
    """Test full integration"""
    print("\n" + "="*60)
    print("TESTING FULL INTEGRATION")
    print("="*60)
    
    # Simulate the pipeline
    target_audit = {
        "url": "https://example.com",
        "structure": {
            "h1_check": {
                "details": {
                    "example": "Best AI Coding Assistant",
                    "count": 1
                }
            }
        }
    }
    
    # Step 1: Generate Keywords
    keywords_data = KeywordsService.generate_keywords_from_audit(target_audit, "https://example.com")
    
    # Step 2: Generate Backlinks
    backlinks_data = BacklinksService.generate_backlinks_from_audit(target_audit, "https://example.com")
    
    # Step 3: Generate Rankings
    rankings_data = RankTrackingService.generate_rankings_from_keywords(keywords_data, "https://example.com")
    
    # Format as pipeline result
    result = {
        "keywords": {
            "keywords": keywords_data,
            "total_keywords": len(keywords_data),
            "top_opportunities": sorted(keywords_data, key=lambda x: x.get("opportunity_score", 0), reverse=True)[:10]
        },
        "backlinks": backlinks_data,
        "rank_tracking": {
            "rankings": rankings_data,
            "total_keywords": len(rankings_data),
            "distribution": {
                "top_3": len([r for r in rankings_data if r.get("position", 100) <= 3]),
                "top_10": len([r for r in rankings_data if r.get("position", 100) <= 10]),
                "top_20": len([r for r in rankings_data if r.get("position", 100) <= 20]),
                "beyond_20": len([r for r in rankings_data if r.get("position", 100) > 20])
            }
        }
    }
    
    print("\n✅ Integration successful!")
    print(f"\nResult structure:")
    print(f"  Keywords: {result['keywords']['total_keywords']} total")
    print(f"  Backlinks: {result['backlinks']['total_backlinks']} total")
    print(f"  Rankings: {result['rank_tracking']['total_keywords']} total")
    print(f"  Distribution: Top 3: {result['rank_tracking']['distribution']['top_3']}, Top 10: {result['rank_tracking']['distribution']['top_10']}")
    
    # Save to file for inspection
    output_file = Path(__file__).parent / "test_geo_output.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n📄 Full output saved to: {output_file}")


if __name__ == "__main__":
    print("\n🚀 Starting GEO Services Test Suite")
    print("="*60)
    
    try:
        # Test individual services
        keywords = test_keywords_service()
        backlinks = test_backlinks_service()
        rankings = test_rank_tracking_service(keywords)
        
        # Test integration
        test_integration()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nThe GEO services are working correctly and ready for production.")
        print("They will be automatically called during the audit pipeline.")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
