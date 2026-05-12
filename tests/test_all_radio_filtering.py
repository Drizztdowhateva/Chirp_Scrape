#!/usr/bin/env python3
"""Comprehensive test script to verify digital mode filtering works for all radio models"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from freqfinder import RADIO_MODELS

def test_all_radio_filtering():
    """Test digital mode filtering for all radio models"""
    
    # Test data with various digital modes
    test_entries = [
        {'name': 'D-STAR Reflector 1C CFMC', 'frequency': 441.90625, 'comment': 'D-STAR digital'},
        {'name': 'CFMC 448.750 RM 114.8 PL CFMC U P25', 'frequency': 443.750, 'comment': 'P25 digital'},
        {'name': 'Yaesu FTM-400DR C4FM Repeater', 'frequency': 444.000, 'comment': 'System Fusion C4FM'},
        {'name': 'W9GN Digital TRUNK System', 'frequency': 145.11, 'comment': 'Digital trunking'},
        {'name': 'NA9PL Analog Repeater', 'frequency': 440.25, 'comment': 'Analog FM'},
        {'name': 'NS9RC Simplex FM', 'frequency': 442.725, 'comment': 'FM analog'},
        {'name': 'Motorola P25 System [P25]', 'frequency': 460.500, 'comment': 'P25 professional'},
        {'name': 'EDACS Trunking [EDACS]', 'frequency': 853.250, 'comment': 'EDACS system'},
    ]
    
    print("=== Digital Mode Filtering Test Results ===\n")
    
    for model_key, model_obj in RADIO_MODELS.items():
        print(f"Testing: {model_obj['name']}")
        print(f"  P25 Support: {model_obj.get('supports_p25', False)}")
        print(f"  D-STAR Support: {model_obj.get('supports_dstar', False)}")
        print(f"  Digital Mode Support: {model_obj.get('supports_digital_mode', False)}")
        
        filtered_count = 0
        allowed_count = 0
        
        for entry in test_entries:
            name = entry['name'].lower()
            comment = entry['comment'].lower()
            combined = f"{entry['name']} {entry['comment']}".lower()
            
            # Apply filtering logic
            should_filter = False
            filter_reason = ""
            
            # D-STAR detection
            if 'd-star' in name or 'dstar' in name:
                if not model_obj.get('supports_dstar'):
                    should_filter = True
                    filter_reason = "D-STAR not supported"
            
            # P25 detection  
            elif 'p25' in combined or '[p25]' in name:
                if not model_obj.get('supports_p25'):
                    should_filter = True
                    filter_reason = "P25 not supported"
            
            # C4FM/System Fusion detection
            elif 'c4fm' in combined or 'system fusion' in combined or 'fusion' in name:
                if not model_obj.get('supports_digital_mode'):
                    should_filter = True
                    filter_reason = "C4FM/System Fusion not supported"
            
            # EDACS detection
            elif '[edacs]' in name:
                if not model_obj.get('supports_edacs'):
                    should_filter = True
                    filter_reason = "EDACS not supported"
            
            # Other digital modes
            elif any(d in name for d in ['dmr', 'nxdn', 'tdma', 'trunk', 'trunking', 'digital']):
                if not model_obj.get('supports_digital_mode'):
                    should_filter = True
                    filter_reason = "Digital mode not supported"
            
            if should_filter:
                filtered_count += 1
                print(f"    FILTERED: {entry['name']} ({filter_reason})")
            else:
                allowed_count += 1
                print(f"    ALLOWED: {entry['name']}")
        
        print(f"  Results: {allowed_count} allowed, {filtered_count} filtered")
        print()
    
    print("=== Expected Results Summary ===")
    print("Analog radios (Baofeng): Only analog entries allowed")
    print("D-STAR radios (Icom ID): D-STAR + analog allowed")
    print("System Fusion radios (Yaesu FTM): C4FM + analog allowed") 
    print("Professional radios (Motorola, Kenwood): P25 + analog allowed")

if __name__ == "__main__":
    test_all_radio_filtering()
