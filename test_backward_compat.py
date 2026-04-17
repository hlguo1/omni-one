#!/usr/bin/env python3
"""
Backward Compatibility Test
Verifies that all existing APIs still work after implementation
"""

import sys
import time
sys.path.insert(0, "/Users/guohaolin/Desktop/omni-one/src/omni_one/core")

from data_processing_pipeline import MultiLayerDataPipeline

def test_all_apis():
    print("Testing Backward Compatibility...")
    print("=" * 60)
    
    pipeline = MultiLayerDataPipeline()
    
    test_record = {
        "timestamp": time.time(),
        "source": "test",
        "entity_id": "test_001",
        "value": 100,
        "metadata": {}
    }
    
    # Test 1: process_batch (original method)
    try:
        results, metrics = pipeline.process_batch([test_record])
        print("✅ process_batch() - WORKS")
        print(f"   Returned {len(results)} results, metrics has {metrics.total_records_processed} records")
    except Exception as e:
        print(f"❌ process_batch() - FAILED: {e}")
        return False
    
    # Test 2: process_batch_optimized (new method)
    try:
        results, metrics = pipeline.process_batch_optimized([test_record])
        print("✅ process_batch_optimized() - WORKS")
        print(f"   Returned {len(results)} results with optimization")
    except Exception as e:
        print(f"❌ process_batch_optimized() - FAILED: {e}")
        return False
    
    # Test 3: process_record (original method)
    try:
        result = pipeline.process_record(test_record)
        print("✅ process_record() - WORKS")
        print(f"   Record ID: {result.record_id}, Stage: {result.processing_stage.value}")
    except Exception as e:
        print(f"❌ process_record() - FAILED: {e}")
        return False
    
    # Test 4: Check new fields exist
    try:
        results, _ = pipeline.process_batch_optimized([test_record])
        result = results[0]
        
        # Check batch context
        batch_ctx = result.final_record.get("_batch_context")
        if batch_ctx is None:
            print("❌ Batch context injection - FAILED: _batch_context not found")
            return False
        
        # Check layer 3 skip marker
        l3_results = result.final_record.get("_layer3_results", {})
        has_skip_marker = "skipped" in l3_results
        
        print("✅ New features present:")
        print(f"   - _batch_context injected: batch_size={batch_ctx['batch_size']}")
        print(f"   - Layer 3 skip tracking: {has_skip_marker}")
        
    except Exception as e:
        print(f"❌ New features check - FAILED: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Backward Compatibility Verified!")
    return True

if __name__ == "__main__":
    success = test_all_apis()
    sys.exit(0 if success else 1)
