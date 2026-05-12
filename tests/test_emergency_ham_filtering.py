#!/usr/bin/env python3
"""Test script to verify emergency services and Ham radio filtering functionality"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from freqfinder import (
    EMERGENCY_TYPE_KEYWORDS, 
    emergency_row_type,
    is_analog_emergency_channel,
    BAND_RANGES,
    HAM_BANDS,
    DEFAULT_BAND_PROFILES,
    RADIO_MODELS
)

def test_emergency_type_detection():
    """Test emergency type detection from channel names and comments"""
    print("=== Emergency Type Detection Test ===\n")
    
    test_cases = [
        {'name': 'Chicago Police Dispatch', 'comment': 'Zone 1', 'expected': 'Police'},
        {'name': 'Fire Department Main', 'comment': 'FD Dispatch', 'expected': 'Fire'},
        {'name': 'EMS Ambulance', 'comment': 'Medical Response', 'expected': 'EMS'},
        {'name': 'Citywide Operations', 'comment': 'C/W Channel', 'expected': 'Citywide'},
        {'name': 'Sheriff Office', 'comment': 'Law Enforcement', 'expected': 'Police'},
        {'name': 'Fireground Tac 1', 'comment': 'Fire tactical', 'expected': 'Fire'},
        {'name': 'EMS-Tac 2', 'comment': 'EMS tactical', 'expected': 'EMS'},
        {'name': 'Regular Repeater', 'comment': 'Amateur Radio', 'expected': None},
    ]
    
    for case in test_cases:
        row = {'Name': case['name'], 'Comment': case['comment']}
        detected = emergency_row_type(row)
        status = "✓" if detected == case['expected'] else "✗"
        print(f"{status} {case['name']} + {case['comment']}")
        print(f"   Expected: {case['expected']}, Detected: {detected}")
        if detected != case['expected']:
            print(f"   ERROR: Mismatch in emergency type detection!")
        print()

def test_analog_emergency_filtering():
    """Test that analog-only radios filter digital emergency channels"""
    print("=== Analog Emergency Channel Filtering Test ===\n")
    
    test_cases = [
        {'name': 'Police Dispatch', 'comment': 'Analog', 'frequency': 155.475, 'should_pass': True},
        {'name': 'Police Dispatch', 'comment': 'P25 Digital', 'frequency': 155.475, 'should_pass': False},
        {'name': 'Fire Dispatch', 'comment': 'Analog FM', 'frequency': 154.280, 'should_pass': True},
        {'name': 'EMS Dispatch', 'comment': 'Digital Mode', 'frequency': 155.205, 'should_pass': False},
    ]
    
    # Test with analog-only radio (Baofeng UV-5R)
    analog_radio = RADIO_MODELS['Baofeng_UV5R']
    print(f"Testing with: {analog_radio['name']}")
    print(f"Supports P25: {analog_radio.get('supports_p25')}")
    print(f"Supports Digital Mode: {analog_radio.get('supports_digital_mode')}")
    print()
    
    for case in test_cases:
        result = is_analog_emergency_channel(
            case['name'], 
            case['comment'], 
            case['comment'], 
            analog_radio
        )
        status = "✓" if result == case['should_pass'] else "✗"
        print(f"{status} {case['name']} ({case['comment']}) - {case['frequency']} MHz")
        print(f"   Expected: {'Pass' if case['should_pass'] else 'Filter'}, Got: {'Pass' if result else 'Filter'}")
        if result != case['should_pass']:
            print(f"   ERROR: Analog filtering not working correctly!")
        print()

def test_ham_band_ranges():
    """Test Ham band frequency ranges"""
    print("=== Ham Band Range Test ===\n")
    
    test_frequencies = [
        {'freq': 146.520, 'expected_band': '2m', 'description': '2m calling frequency'},
        {'freq': 443.750, 'expected_band': '70cm', 'description': '70cm repeater'},
        {'freq': 224.000, 'expected_band': '1.25m', 'description': '1.25m repeater'},
        {'freq': 29.600, 'expected_band': '10m', 'description': '10m HF'},
        {'freq': 52.525, 'expected_band': '6m', 'description': '6m HF'},
        {'freq': 155.475, 'expected_band': None, 'description': 'VHF public safety'},
        {'freq': 460.500, 'expected_band': None, 'description': 'UHF public safety'},
    ]
    
    for case in test_frequencies:
        found_band = None
        for band, ranges in BAND_RANGES.items():
            if band in HAM_BANDS:
                for low, high in ranges:
                    if low <= case['freq'] <= high:
                        found_band = band
                        break
            if found_band:
                break
        
        status = "✓" if found_band == case['expected_band'] else "✗"
        print(f"{status} {case['freq']} MHz - {case['description']}")
        print(f"   Expected: {case['expected_band']}, Detected: {found_band}")
        if found_band != case['expected_band']:
            print(f"   ERROR: Band detection incorrect!")
        print()

def test_emergency_band_ranges():
    """Test Emergency band frequency ranges"""
    print("=== Emergency Band Range Test ===\n")
    
    test_frequencies = [
        {'freq': 155.475, 'should_be_emergency': True, 'description': 'VHF Police'},
        {'freq': 154.280, 'should_be_emergency': True, 'description': 'VHF Fire'},
        {'freq': 155.205, 'should_be_emergency': True, 'description': 'VHF EMS'},
        {'freq': 460.500, 'should_be_emergency': True, 'description': 'UHF Public Safety'},
        {'freq': 853.250, 'should_be_emergency': True, 'description': '800 MHz Trunking'},
        {'freq': 146.520, 'should_be_emergency': False, 'description': '2m Ham (excluded)'},
        {'freq': 443.750, 'should_be_emergency': False, 'description': '70cm Ham (excluded)'},
        {'freq': 162.550, 'should_be_emergency': False, 'description': 'NOAA Weather'},
    ]
    
    for case in test_frequencies:
        is_emergency = False
        for low, high in BAND_RANGES.get('Emergency', []):
            if low <= case['freq'] <= high:
                is_emergency = True
                break
        
        status = "✓" if is_emergency == case['should_be_emergency'] else "✗"
        print(f"{status} {case['freq']} MHz - {case['description']}")
        print(f"   Expected: {'Emergency' if case['should_be_emergency'] else 'Not Emergency'}, Got: {'Emergency' if is_emergency else 'Not Emergency'}")
        if is_emergency != case['should_be_emergency']:
            print(f"   ERROR: Emergency band detection incorrect!")
        print()

def test_default_profiles():
    """Test default band profiles for Emergency and Traveler"""
    print("=== Default Band Profiles Test ===\n")
    
    profiles_to_test = ['Emergency Comms', 'Traveler', 'HamScan']
    
    for profile_name in profiles_to_test:
        profile = DEFAULT_BAND_PROFILES[profile_name]
        print(f"Profile: {profile_name}")
        print(f"  Bands: {', '.join(profile['bands'])}")
        print(f"  Emergency Types: {', '.join(profile['emergency_types'])}")
        print(f"  Scanner Mode: {profile['scanner_mode']}")
        
        # Verify Emergency and Traveler have emergency types
        if profile_name in ['Emergency Comms', 'Traveler']:
            if not profile['emergency_types']:
                print(f"  ERROR: {profile_name} should have emergency types selected!")
            else:
                print(f"  ✓ Emergency types properly configured")
        
        # Verify HamScan has no emergency types
        if profile_name == 'HamScan':
            if profile['emergency_types']:
                print(f"  ERROR: HamScan should have no emergency types!")
            else:
                print(f"  ✓ HamScan correctly configured for Ham only")
        
        print()

def main():
    """Run all tests"""
    print("FreqFinder Emergency Services & Ham Radio Filtering Test Suite")
    print("=" * 70)
    print()
    
    test_emergency_type_detection()
    print("-" * 50)
    
    test_analog_emergency_filtering()
    print("-" * 50)
    
    test_ham_band_ranges()
    print("-" * 50)
    
    test_emergency_band_ranges()
    print("-" * 50)
    
    test_default_profiles()
    print("=" * 70)
    print("Test suite completed!")

if __name__ == "__main__":
    main()
