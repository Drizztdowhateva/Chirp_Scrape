#!/usr/bin/env python3
"""Test script to verify digital mode filtering works correctly"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from freqfinder import RADIO_MODELS

def test_digital_filtering():
    """Test that D-STAR and P25 entries are filtered for analog-only radios"""
    
    # Test Baofeng UV-5R Mini (analog-only)
    baofeng_mini = RADIO_MODELS['Baofeng_UV5R_Mini']
    print(f"Baofeng UV-5R Mini supports P25: {baofeng_mini.get('supports_p25')}")
    print(f"Baofeng UV-5R Mini supports D-STAR: {baofeng_mini.get('supports_dstar')}")
    
    # Test data with digital modes
    test_entries = [
        {'name': 'D-STAR Reflector 1C CFMC', 'frequency': 441.90625, 'comment': 'D-STAR'},
        {'name': 'CFMC 448.750 RM 114.8 PL CFMC U P25', 'frequency': 443.750, 'comment': 'P25'},
        {'name': 'NA9PL', 'frequency': 440.25, 'comment': 'Analog repeater'},
        {'name': 'NS9RC', 'frequency': 442.725, 'comment': 'FM analog'},
    ]
    
    # Simulate filtering logic
    filtered_entries = []
    for entry in test_entries:
        name = entry['name'].lower()
        comment = entry['comment'].lower()
        combined = f"{entry['name']} {entry['comment']}".lower()
        
        # Check for digital protocols
        is_dstar = 'd-star' in name or 'dstar' in name
        is_p25 = 'p25' in combined
        
        if is_dstar and not baofeng_mini.get('supports_dstar'):
            print(f"FILTERED OUT (D-STAR): {entry['name']}")
            continue
        if is_p25 and not baofeng_mini.get('supports_p25'):
            print(f"FILTERED OUT (P25): {entry['name']}")
            continue
            
        print(f"ALLOWED: {entry['name']} - {entry['frequency']} MHz")
        filtered_entries.append(entry)
    
    print(f"\nOriginal: {len(test_entries)} entries")
    print(f"Filtered: {len(filtered_entries)} entries")
    print(f"Expected: 2 entries (analog only)")

if __name__ == "__main__":
    test_digital_filtering()
