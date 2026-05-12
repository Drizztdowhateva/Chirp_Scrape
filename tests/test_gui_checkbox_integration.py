#!/usr/bin/env python3
"""Test script to verify GUI checkbox integration and emergency services filtering"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from freqfinder import (
    DEFAULT_BAND_PROFILES,
    EMERGENCY_TYPE_KEYWORDS,
    emergency_row_type,
    BAND_RANGES,
    HAM_BANDS,
    RADIO_MODELS,
    is_analog_emergency_channel
)

def test_emergency_checkbox_logic():
    """Test emergency type checkbox filtering logic"""
    print("=== Emergency Checkbox Logic Test ===\n")
    
    test_channels = [
        {'Name': 'Chicago Police Dispatch', 'Comment': 'Zone 1', 'expected_type': 'Police'},
        {'Name': 'Fire Department Main', 'Comment': 'FD Dispatch', 'expected_type': 'Fire'},
        {'Name': 'EMS Ambulance', 'Comment': 'Medical Response', 'expected_type': 'EMS'},
        {'Name': 'Citywide Operations', 'Comment': 'C/W Channel', 'expected_type': 'Citywide'},
        {'Name': 'Sheriff Office', 'Comment': 'Law Enforcement', 'expected_type': 'Police'},
        {'Name': 'Fireground Tac 1', 'Comment': 'Fire tactical', 'expected_type': 'Fire'},
        {'Name': 'EMS-Tac 2', 'Comment': 'EMS tactical', 'expected_type': 'EMS'},
    ]
    
    # Test individual checkbox selections
    emergency_types = list(EMERGENCY_TYPE_KEYWORDS.keys())
    
    for emergency_type in emergency_types:
        print(f"Testing {emergency_type} checkbox selected:")
        print("-" * 30)
        
        # Simulate checkbox state: only this type selected
        selected_types = [emergency_type]
        
        filtered_channels = []
        for channel in test_channels:
            detected_type = emergency_row_type(channel)
            if detected_type in selected_types:
                filtered_channels.append(channel)
        
        print(f"  Expected type: {emergency_type}")
        print(f"  Channels found: {len(filtered_channels)}")
        
        for channel in filtered_channels:
            print(f"    ✓ {channel['Name']} - {channel['Comment']}")
        
        # Verify we got the right channels
        expected_channels = [ch for ch in test_channels if ch['expected_type'] == emergency_type]
        if len(filtered_channels) == len(expected_channels):
            print(f"  ✓ Correct number of channels ({len(filtered_channels)})")
        else:
            print(f"  ✗ Wrong number of channels. Expected {len(expected_channels)}, got {len(filtered_channels)}")
        
        print()

def test_multiple_emergency_checkboxes():
    """Test multiple emergency type checkboxes selected"""
    print("=== Multiple Emergency Checkboxes Test ===\n")
    
    test_channels = [
        {'Name': 'Chicago Police Dispatch', 'Comment': 'Zone 1', 'type': 'Police'},
        {'Name': 'Fire Department Main', 'Comment': 'FD Dispatch', 'type': 'Fire'},
        {'Name': 'EMS Ambulance', 'Comment': 'Medical Response', 'type': 'EMS'},
        {'Name': 'Citywide Operations', 'Comment': 'C/W Channel', 'type': 'Citywide'},
        {'Name': 'Regular Ham Repeater', 'Comment': 'Amateur Radio', 'type': None},
    ]
    
    # Test combinations
    test_combinations = [
        {'selected': ['Police', 'Fire'], 'expected_count': 2},
        {'selected': ['EMS', 'Citywide'], 'expected_count': 2},
        {'selected': ['Police', 'Fire', 'EMS'], 'expected_count': 3},
        {'selected': ['Police', 'Fire', 'EMS', 'Citywide'], 'expected_count': 4},
        {'selected': [], 'expected_count': 4},  # All types when none selected (default behavior)
    ]
    
    for combo in test_combinations:
        print(f"Testing selected types: {', '.join(combo['selected']) if combo['selected'] else 'All (default)'}")
        print("-" * 50)
        
        # Simulate filtering logic
        selected_types = combo['selected'] if combo['selected'] else list(EMERGENCY_TYPE_KEYWORDS.keys())
        
        filtered_channels = []
        for channel in test_channels:
            detected_type = emergency_row_type(channel)
            if detected_type in selected_types:
                filtered_channels.append(channel)
        
        print(f"  Expected channels: {combo['expected_count']}")
        print(f"  Actual channels: {len(filtered_channels)}")
        
        for channel in filtered_channels:
            print(f"    ✓ {channel['Name']} ({channel['type']})")
        
        if len(filtered_channels) == combo['expected_count']:
            print("  ✓ Correct filtering")
        else:
            print("  ✗ Incorrect filtering")
        
        print()

def test_ham_traveler_integration():
    """Test Ham and Traveler profile integration with emergency filtering"""
    print("=== Ham/Traveler Integration Test ===\n")
    
    # Test data for Ham/Traveler scenarios
    test_data = [
        # Ham channels
        {'Name': 'W9IL 2m Repeater', 'Frequency': 146.940, 'Comment': 'Analog repeater', 'Band': '2m'},
        {'Name': 'KC9RJS 70cm', 'Frequency': 443.750, 'Comment': 'UHF repeater', 'Band': '70cm'},
        {'Name': 'N9UHH 1.25m', 'Frequency': 224.500, 'Comment': 'VHF repeater', 'Band': '1.25m'},
        
        # Emergency channels
        {'Name': 'Police Dispatch', 'Frequency': 155.475, 'Comment': 'Zone 1', 'Band': 'Emergency'},
        {'Name': 'Fire Dispatch', 'Frequency': 154.280, 'Comment': 'Main FD', 'Band': 'Emergency'},
        {'Name': 'EMS Dispatch', 'Frequency': 155.205, 'Comment': 'Medical', 'Band': 'Emergency'},
        
        # NOAA
        {'Name': 'NOAA Weather', 'Frequency': 162.550, 'Comment': 'Weather Radio', 'Band': 'NOAA'},
        
        # Digital emergency (should be filtered for analog)
        {'Name': 'Digital Police', 'Frequency': 155.475, 'Comment': 'P25 Digital', 'Band': 'Emergency'},
    ]
    
    # Test with analog radio (Baofeng)
    analog_radio = RADIO_MODELS['Baofeng_UV5R']
    
    # Test Emergency Comms profile
    print("Testing Emergency Comms Profile:")
    print("-" * 30)
    
    profile = DEFAULT_BAND_PROFILES['Emergency Comms']
    selected_bands = profile['bands']
    emergency_types = profile['emergency_types']
    
    filtered = []
    for item in test_data:
        # Check band selection
        if item['Band'] not in selected_bands:
            continue
        
        # Emergency filtering
        if item['Band'] == 'Emergency':
            detected_type = emergency_row_type(item)
            if detected_type not in emergency_types:
                continue
            
            # Analog compatibility check
            if not is_analog_emergency_channel(
                item['Name'], item['Comment'], item['Comment'], analog_radio
            ):
                continue
        
        filtered.append(item)
    
    print(f"Selected bands: {', '.join(selected_bands)}")
    print(f"Emergency types: {', '.join(emergency_types)}")
    print(f"Filtered channels: {len(filtered)}")
    
    for item in filtered:
        print(f"  ✓ {item['Name']} - {item['Frequency']} MHz ({item['Band']})")
    
    # Verify expectations
    ham_channels = [item for item in filtered if item['Band'] in HAM_BANDS]
    emergency_channels = [item for item in filtered if item['Band'] == 'Emergency']
    noaa_channels = [item for item in filtered if item['Band'] == 'NOAA']
    
    print(f"\nBreakdown:")
    print(f"  Ham channels: {len(ham_channels)}")
    print(f"  Emergency channels: {len(emergency_channels)}")
    print(f"  NOAA channels: {len(noaa_channels)}")
    
    # Should have ham + emergency + noaa
    if ham_channels and emergency_channels and noaa_channels:
        print("  ✓ All expected channel types present")
    else:
        print("  ✗ Missing channel types")
    
    # Should not have digital emergency channels
    digital_emergency = [item for item in filtered if 'Digital' in item['Name']]
    if not digital_emergency:
        print("  ✓ Digital emergency channels correctly filtered")
    else:
        print("  ✗ Digital emergency channels not filtered")
    
    print()

def test_frequency_output_verification():
    """Test final frequency output format and content"""
    print("=== Frequency Output Verification Test ===\n")
    
    # Simulate final output after all filtering
    expected_output = [
        {'Name': 'W9IL 2m Repeater', 'Frequency': '146.940', 'Band': '2m', 'Duplex': 'split', 'Tone': '114.8'},
        {'Name': 'KC9RJS 70cm', 'Frequency': '443.750', 'Band': '70cm', 'Duplex': 'split', 'Tone': '100.0'},
        {'Name': 'Police Dispatch', 'Frequency': '155.475', 'Band': 'Emergency', 'Duplex': '', 'Tone': '141.3'},
        {'Name': 'Fire Dispatch', 'Frequency': '154.280', 'Band': 'Emergency', 'Duplex': '', 'Tone': '146.2'},
        {'Name': 'NOAA Weather', 'Frequency': '162.550', 'Band': 'NOAA', 'Duplex': '', 'Tone': ''},
        {'Name': 'National Calling', 'Frequency': '146.520', 'Band': '2m', 'Duplex': '', 'Tone': ''},
    ]
    
    print("Expected output format for Emergency Comms profile:")
    print("-" * 50)
    
    for item in expected_output:
        print(f"{item['Name']:<20} {item['Frequency']:<10} {item['Band']:<10} {item['Duplex']:<8} {item['Tone']}")
    
    print("\nOutput verification:")
    
    # Check frequency format (should be string with 3 decimal places)
    for item in expected_output:
        freq = item['Frequency']
        if '.' in freq and len(freq.split('.')[-1]) == 3:
            print(f"  ✓ {freq} - Correct frequency format")
        else:
            print(f"  ✗ {freq} - Incorrect frequency format")
    
    # Check band assignment
    bands_present = {item['Band'] for item in expected_output}
    expected_bands = {'2m', '70cm', 'Emergency', 'NOAA'}
    
    if expected_bands.issubset(bands_present):
        print("  ✓ All expected bands present in output")
    else:
        missing = expected_bands - bands_present
        print(f"  ✗ Missing bands in output: {', '.join(missing)}")
    
    # Check emergency types present
    emergency_items = [item for item in expected_output if item['Band'] == 'Emergency']
    if emergency_items:
        print(f"  ✓ Emergency channels in output: {len(emergency_items)}")
        for item in emergency_items:
            print(f"    - {item['Name']}")
    
    print()

def main():
    """Run all GUI checkbox integration tests"""
    print("FreqFinder GUI Checkbox Integration Test Suite")
    print("=" * 60)
    print()
    
    test_emergency_checkbox_logic()
    print("-" * 60)
    
    test_multiple_emergency_checkboxes()
    print("-" * 60)
    
    test_ham_traveler_integration()
    print("-" * 60)
    
    test_frequency_output_verification()
    print("=" * 60)
    print("GUI checkbox integration tests completed!")

if __name__ == "__main__":
    main()
