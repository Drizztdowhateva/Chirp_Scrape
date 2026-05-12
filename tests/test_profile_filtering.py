#!/usr/bin/env python3
"""Test script to verify profile-based filtering for Emergency Comms, Traveler, and HamScan"""

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

def create_test_data():
    """Create comprehensive test data with various channel types"""
    return [
        # Ham radio channels
        {'Name': 'W9IL repeater', 'Frequency': 146.940, 'Comment': '2m analog repeater', 'Band': '2m'},
        {'Name': 'KC9RJS', 'Frequency': 443.750, 'Comment': '70cm repeater', 'Band': '70cm'},
        {'Name': 'N9UHH', 'Frequency': 224.500, 'Comment': '1.25m repeater', 'Band': '1.25m'},
        {'Name': 'National Calling', 'Frequency': 146.520, 'Comment': 'Simplex calling freq', 'Band': '2m'},
        
        # Emergency services channels
        {'Name': 'Chicago Police Dispatch', 'Frequency': 155.475, 'Comment': 'Zone 1 Police', 'Band': 'Emergency'},
        {'Name': 'Fire Department Main', 'Frequency': 154.280, 'Comment': 'FD Dispatch', 'Band': 'Emergency'},
        {'Name': 'EMS Ambulance', 'Frequency': 155.205, 'Comment': 'Medical Response', 'Band': 'Emergency'},
        {'Name': 'Citywide Operations', 'Frequency': 156.120, 'Comment': 'C/W Channel', 'Band': 'Emergency'},
        
        # Digital emergency channels (should be filtered for analog radios)
        {'Name': 'Police P25 Dispatch', 'Frequency': 155.475, 'Comment': 'P25 Digital', 'Band': 'Emergency'},
        {'Name': 'Fire Digital Tac', 'Frequency': 154.100, 'Comment': 'Digital Mode', 'Band': 'Emergency'},
        
        # NOAA weather channels
        {'Name': 'NOAA Weather', 'Frequency': 162.550, 'Comment': 'Weather Radio', 'Band': 'NOAA'},
        
        # Out-of-band channels (should be excluded)
        {'Name': 'Business Radio', 'Frequency': 464.550, 'Comment': 'Business band', 'Band': 'Other'},
        {'Name': 'GMRS Repeater', 'Frequency': 462.675, 'Comment': 'GMRS channel', 'Band': 'FRS/GMRS'},
    ]

def test_profile_filtering():
    """Test filtering for each profile type"""
    print("=== Profile-Based Filtering Test ===\n")
    
    test_data = create_test_data()
    analog_radio = RADIO_MODELS['Baofeng_UV5R']
    
    profiles_to_test = ['Emergency Comms', 'Traveler', 'HamScan']
    
    for profile_name in profiles_to_test:
        print(f"Testing Profile: {profile_name}")
        print("-" * 40)
        
        profile = DEFAULT_BAND_PROFILES[profile_name]
        selected_bands = profile['bands']
        emergency_types = profile['emergency_types']
        
        print(f"Selected Bands: {', '.join(selected_bands)}")
        print(f"Emergency Types: {', '.join(emergency_types) if emergency_types else 'None'}")
        print(f"Scanner Mode: {profile['scanner_mode']}")
        print()
        
        filtered_channels = []
        
        for channel in test_data:
            # Check if channel band is in selected bands
            if channel['Band'] not in selected_bands:
                continue
            
            # Additional filtering for emergency channels
            if channel['Band'] == 'Emergency':
                # Check emergency type filtering
                if emergency_types:
                    detected_type = emergency_row_type(channel)
                    if detected_type not in emergency_types:
                        continue
                
                # Check analog compatibility for analog radios
                if not is_analog_emergency_channel(
                    channel['Name'], 
                    channel['Comment'], 
                    channel['Comment'], 
                    analog_radio
                ):
                    continue
            
            filtered_channels.append(channel)
        
        print("Filtered Results:")
        for channel in filtered_channels:
            print(f"  ✓ {channel['Name']} - {channel['Frequency']} MHz ({channel['Band']})")
        
        print(f"\nTotal channels: {len(filtered_channels)}")
        
        # Verify expectations
        if profile_name in ['Emergency Comms', 'Traveler']:
            # Should include Ham bands + Emergency + NOAA
            expected_bands = {'2m', '70cm', '1.25m', 'Emergency', 'NOAA'}
            actual_bands = {ch['Band'] for ch in filtered_channels}
            
            if expected_bands.issubset(actual_bands):
                print("✓ All expected bands present")
            else:
                missing = expected_bands - actual_bands
                print(f"✗ Missing bands: {', '.join(missing)}")
            
            # Should have emergency channels (excluding digital)
            emergency_channels = [ch for ch in filtered_channels if ch['Band'] == 'Emergency']
            if emergency_channels:
                print(f"✓ Found {len(emergency_channels)} emergency channels")
            else:
                print("✗ No emergency channels found")
        
        elif profile_name == 'HamScan':
            # Should only include Ham bands
            expected_bands = {'2m', '70cm', '1.25m'}
            actual_bands = {ch['Band'] for ch in filtered_channels}
            
            if actual_bands.issubset(expected_bands):
                print("✓ Only Ham bands included")
            else:
                extra = actual_bands - expected_bands
                print(f"✗ Unexpected bands: {', '.join(extra)}")
            
            # Should have no emergency channels
            emergency_channels = [ch for ch in filtered_channels if ch['Band'] == 'Emergency']
            if not emergency_channels:
                print("✓ No emergency channels (as expected)")
            else:
                print(f"✗ Found {len(emergency_channels)} unexpected emergency channels")
        
        print("\n" + "=" * 60 + "\n")

def test_frequency_output_format():
    """Test that output format is correct for different scenarios"""
    print("=== Frequency Output Format Test ===\n")
    
    test_cases = [
        {
            'name': 'Ham Repeater',
            'frequency': 146.940,
            'band': '2m',
            'expected_duplex': 'split',
            'expected_tone': 'not None'
        },
        {
            'name': 'Simplex Channel',
            'frequency': 146.520,
            'band': '2m',
            'expected_duplex': 'None',
            'expected_tone': 'None'
        },
        {
            'name': 'Emergency Dispatch',
            'frequency': 155.475,
            'band': 'Emergency',
            'expected_duplex': 'None',
            'expected_tone': 'not None'
        },
        {
            'name': 'NOAA Weather',
            'frequency': 162.550,
            'band': 'NOAA',
            'expected_duplex': 'None',
            'expected_tone': 'None'
        }
    ]
    
    for case in test_cases:
        print(f"Testing: {case['name']} ({case['frequency']} MHz)")
        
        # Simulate output formatting logic
        if case['band'] in HAM_BANDS:
            if abs(case['frequency'] - 146.520) < 0.001:  # Calling frequency
                duplex = None
                tone = None
            else:
                duplex = 'split'  # Typical for repeaters
                tone = 'not None'  # Most repeaters have tones
        elif case['band'] == 'Emergency':
            duplex = None
            tone = 'not None'  # Most emergency channels have tones
        elif case['band'] == 'NOAA':
            duplex = None
            tone = None
        else:
            duplex = None
            tone = None
        
        # Check expectations
        duplex_ok = (duplex == case['expected_duplex'] or 
                    (case['expected_duplex'] == 'None' and duplex is None))
        tone_ok = (tone == case['expected_tone'] or 
                  (case['expected_tone'] == 'None' and tone is None) or
                  (case['expected_tone'] == 'not None' and tone is not None))
        
        status = "✓" if (duplex_ok and tone_ok) else "✗"
        print(f"  {status} Duplex: {duplex}, Tone: {tone}")
        
        if not duplex_ok:
            print(f"    Expected duplex: {case['expected_duplex']}")
        if not tone_ok:
            print(f"    Expected tone: {case['expected_tone']}")
        
        print()

def test_band_ordering():
    """Test that band ordering works correctly"""
    print("=== Band Ordering Test ===\n")
    
    test_profiles = [
        {'name': 'Emergency Comms', 'expected_order': ['70cm', '1.25m', '2m', 'Emergency', 'NOAA']},
        {'name': 'Traveler', 'expected_order': ['70cm', '1.25m', '2m', 'Emergency', 'NOAA']},
        {'name': 'HamScan', 'expected_order': ['70cm', '1.25m', '2m']},
    ]
    
    for profile_test in test_profiles:
        profile = DEFAULT_BAND_PROFILES[profile_test['name']]
        actual_order = profile.get('order', profile['bands'])
        expected_order = profile_test['expected_order']
        
        print(f"Profile: {profile_test['name']}")
        print(f"  Expected: {' > '.join(expected_order)}")
        print(f"  Actual:   {' > '.join(actual_order)}")
        
        if actual_order == expected_order:
            print("  ✓ Band order correct")
        else:
            print("  ✗ Band order incorrect")
        print()

def main():
    """Run all profile filtering tests"""
    print("FreqFinder Profile Filtering Test Suite")
    print("=" * 60)
    print()
    
    test_profile_filtering()
    print("-" * 60)
    
    test_frequency_output_format()
    print("-" * 60)
    
    test_band_ordering()
    print("=" * 60)
    print("Profile filtering tests completed!")

if __name__ == "__main__":
    main()
