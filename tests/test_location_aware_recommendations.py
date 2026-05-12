#!/usr/bin/env python3
"""Test script to verify location-aware frequency recommendations"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from freqfinder import (
    get_location_based_recommendations,
    detect_area_type,
    generate_suggested_config,
    DEFAULT_BAND_PROFILES
)

def test_area_type_detection():
    """Test ZIP code area type detection"""
    print("=== Area Type Detection Test ===\n")
    
    test_zip_codes = [
        {'zip': '10001', 'expected': 'urban_areas', 'description': 'New York City'},
        {'zip': '60601', 'expected': 'urban_areas', 'description': 'Chicago'},
        {'zip': '90210', 'expected': 'rural_areas', 'description': 'Los Angeles'},
        {'zip': '33101', 'expected': 'suburban_areas', 'description': 'Miami'},
        {'zip': '85001', 'expected': 'rural_areas', 'description': 'Phoenix'},
        {'zip': '98101', 'expected': 'rural_areas', 'description': 'Seattle'},
        {'zip': '30301', 'expected': 'suburban_areas', 'description': 'Atlanta'},
        {'zip': '78201', 'expected': 'suburban_areas', 'description': 'San Antonio'},
    ]
    
    for test_case in test_zip_codes:
        zip_code = test_case['zip']
        expected = test_case['expected']
        description = test_case['description']
        
        detected = detect_area_type(zip_code)
        status = "✓" if detected == expected else "✗"
        
        print(f"{status} {zip_code} ({description})")
        print(f"    Expected: {expected}")
        print(f"    Detected: {detected}")
        
        if detected != expected:
            print(f"    ERROR: Area type detection incorrect")
        
        print()

def test_location_recommendations():
    """Test location-based recommendations for different areas"""
    print("=== Location-Based Recommendations Test ===\n")
    
    test_scenarios = [
        {
            'zip': '60601',
            'profile': 'Emergency Comms',
            'area_type': 'urban_areas',
            'description': 'Chicago Urban Emergency'
        },
        {
            'zip': '33101',
            'profile': 'Traveler',
            'area_type': 'suburban_areas',
            'description': 'Miami Suburban Travel'
        },
        {
            'zip': '90210',
            'profile': 'HamScan',
            'area_type': 'rural_areas',
            'description': 'Los Angeles Rural Ham'
        },
    ]
    
    for scenario in test_scenarios:
        print(f"Scenario: {scenario['description']}")
        print(f"ZIP Code: {scenario['zip']}")
        print(f"Profile: {scenario['profile']}")
        print(f"Area Type: {scenario['area_type']}")
        print("-" * 40)
        
        recommendations = get_location_based_recommendations(scenario['zip'], scenario['profile'])
        
        # Display area recommendations
        area_rec = recommendations['recommendations']
        print(f"Area Description: {area_rec['description']}")
        print(f"Suggested Bands: {', '.join(area_rec['suggested_bands'])}")
        print(f"Channel Priorities: {', '.join(area_rec['channel_priorities'])}")
        print(f"Max Range: {area_rec['max_range_miles']} miles")
        print(f"Special Considerations: {', '.join(area_rec['special_considerations'])}")
        
        # Display profile-specific recommendations
        profile_rec = recommendations['profile_specific']
        if profile_rec:
            print(f"\nProfile-Specific:")
            if 'focus' in profile_rec:
                print(f"  Focus: {profile_rec['focus']}")
            if 'exclude_bands' in profile_rec:
                print(f"  Exclude Bands: {', '.join(profile_rec['exclude_bands'])}")
            if 'include_bands' in profile_rec:
                print(f"  Include Bands: {', '.join(profile_rec['include_bands'])}")
            if 'max_channels' in profile_rec:
                print(f"  Max Channels: {profile_rec['max_channels']}")
            if 'mobile_optimized' in profile_rec:
                print(f"  Mobile Optimized: {profile_rec['mobile_optimized']}")
        
        # Display suggested configuration
        suggested_config = recommendations['suggested_config']
        print(f"\nSuggested Configuration:")
        print(f"  Scanner Mode: {suggested_config.get('scanner_mode', False)}")
        print(f"  Step Size: {suggested_config.get('step_size', 5.0)} kHz")
        print(f"  Priority Channels: {suggested_config.get('priority_channels', False)}")
        print(f"  NOAA Auto-Skip: {suggested_config.get('noaa_auto_skip', False)}")
        
        if 'extended_range' in suggested_config:
            print(f"  Extended Range: {suggested_config['extended_range']}")
        if 'mobile_optimized' in suggested_config:
            print(f"  Mobile Optimized: {suggested_config['mobile_optimized']}")
        
        print("\n" + "=" * 50 + "\n")

def test_suggested_config_generation():
    """Test suggested configuration generation"""
    print("=== Suggested Configuration Generation Test ===\n")
    
    test_combinations = [
        {'area': 'urban_areas', 'profile': 'Emergency Comms'},
        {'area': 'suburban_areas', 'profile': 'Traveler'},
        {'area': 'rural_areas', 'profile': 'HamScan'},
        {'area': 'highway_corridors', 'profile': 'Traveler'},
    ]
    
    for combo in test_combinations:
        area = combo['area']
        profile = combo['profile']
        
        print(f"Area: {area}")
        print(f"Profile: {profile}")
        print("-" * 30)
        
        config = generate_suggested_config(area, profile)
        
        print(f"Generated Configuration:")
        for key, value in config.items():
            print(f"  {key}: {value}")
        
        print()

def test_profile_integration():
    """Test integration with existing profile system"""
    print("=== Profile Integration Test ===\n")
    
    profiles_to_test = ['Emergency Comms', 'Traveler', 'HamScan']
    
    for profile_name in profiles_to_test:
        profile = DEFAULT_BAND_PROFILES[profile_name]
        
        print(f"Profile: {profile_name}")
        print(f"Description: {profile.get('description', 'No description')}")
        print(f"Bands: {', '.join(profile['bands'])}")
        print(f"Priority Order: {', '.join(profile.get('priority_order', []))}")
        print(f"Auto-skip NOAA: {profile.get('auto_skip_noaa', False)}")
        print(f"Max Channels: {profile.get('max_channels', 'No limit')}")
        
        # Test location recommendation integration
        test_zip = '60601'  # Chicago
        location_rec = get_location_based_recommendations(test_zip, profile_name)
        
        print(f"Location Recommendations for {test_zip}:")
        print(f"  Area Type: {location_rec['area_type']}")
        print(f"  Suggested Bands: {', '.join(location_rec['recommendations']['suggested_bands'])}")
        
        # Verify compatibility
        profile_bands = set(profile['bands'])
        suggested_bands = set(location_rec['recommendations']['suggested_bands'])
        
        overlap = profile_bands.intersection(suggested_bands)
        if overlap:
            print(f"  ✓ Compatible bands: {', '.join(overlap)}")
        
        missing = suggested_bands - profile_bands
        if missing:
            print(f"  ⚠ Missing bands: {', '.join(missing)}")
        
        extra = profile_bands - suggested_bands
        if extra:
            print(f"  ℹ Extra bands: {', '.join(extra)}")
        
        print()

def main():
    """Run all location-aware recommendation tests"""
    print("FreqFinder Location-Aware Recommendations Test Suite")
    print("=" * 60)
    print()
    
    test_area_type_detection()
    print("-" * 60)
    
    test_location_recommendations()
    print("-" * 60)
    
    test_suggested_config_generation()
    print("-" * 60)
    
    test_profile_integration()
    print("=" * 60)
    print("Location-aware recommendation tests completed!")

if __name__ == "__main__":
    main()
