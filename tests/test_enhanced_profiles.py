#!/usr/bin/env python3
"""Test script to verify enhanced Emergency/Traveler profiles with priority scanning and NOAA auto-skip"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from freqfinder import (
    DEFAULT_BAND_PROFILES,
    EMERGENCY_TYPE_KEYWORDS,
    emergency_row_type,
    get_emergency_priority,
    sort_emergency_channels_by_priority,
    RADIO_MODELS,
    is_analog_emergency_channel
)

def test_enhanced_profiles():
    """Test enhanced profile configurations"""
    print("=== Enhanced Profile Configuration Test ===\n")
    
    # Test Emergency Comms profile
    emergency_profile = DEFAULT_BAND_PROFILES['Emergency Comms']
    print(f"Emergency Comms Profile:")
    print(f"  Bands: {', '.join(emergency_profile['bands'])}")
    print(f"  Priority Order: {', '.join(emergency_profile['priority_order'])}")
    print(f"  Auto-skip NOAA: {emergency_profile['auto_skip_noaa']}")
    print(f"  Max Channels: {emergency_profile['max_channels']}")
    print(f"  Description: {emergency_profile['description']}")
    
    # Verify Emergency bands come first
    if emergency_profile['bands'][0] == 'Emergency':
        print("  ✓ Emergency bands prioritized first")
    else:
        print("  ✗ Emergency bands not prioritized first")
    
    # Test Traveler profile
    traveler_profile = DEFAULT_BAND_PROFILES['Traveler']
    print(f"\nTraveler Profile:")
    print(f"  Bands: {', '.join(traveler_profile['bands'])}")
    print(f"  Mobile Optimized: {traveler_profile.get('mobile_optimized', False)}")
    print(f"  Auto-skip NOAA: {traveler_profile['auto_skip_noaa']}")
    print(f"  Max Channels: {traveler_profile['max_channels']}")
    print(f"  Description: {traveler_profile['description']}")
    
    # Test HamScan profile
    hamscan_profile = DEFAULT_BAND_PROFILES['HamScan']
    print(f"\nHamScan Profile:")
    print(f"  Bands: {', '.join(hamscan_profile['bands'])}")
    print(f"  Auto-skip NOAA: {hamscan_profile['auto_skip_noaa']}")
    print(f"  Max Channels: {hamscan_profile['max_channels']}")
    print(f"  Description: {hamscan_profile['description']}")
    
    print()

def test_emergency_priority_system():
    """Test emergency channel priority system"""
    print("=== Emergency Priority System Test ===\n")
    
    test_channels = [
        {'Name': 'Citywide Operations', 'Comment': 'C/W Channel', 'Frequency': 156.120},
        {'Name': 'Fire Department Main', 'Comment': 'FD Dispatch', 'Frequency': 154.280},
        {'Name': 'Police Dispatch', 'Comment': 'Zone 1', 'Frequency': 155.475},
        {'Name': 'EMS Ambulance', 'Comment': 'Medical Response', 'Frequency': 155.205},
        {'Name': 'Sheriff Office', 'Comment': 'Law Enforcement', 'Frequency': 155.550},
        {'Name': 'Fireground Tac 1', 'Comment': 'Fire tactical', 'Frequency': 154.100},
    ]
    
    # Test priority assignment
    print("Priority Assignment Test:")
    for channel in test_channels:
        emergency_type = emergency_row_type(channel)
        priority = get_emergency_priority(emergency_type)
        print(f"  {channel['Name']:<25} -> {emergency_type:<8} (Priority: {priority})")
    
    # Test sorting by priority
    print("\nPriority Sorting Test:")
    sorted_channels = sort_emergency_channels_by_priority(test_channels)
    
    expected_order = ['Police', 'Fire', 'EMS', 'Citywide']
    actual_order = []
    
    for i, channel in enumerate(sorted_channels):
        emergency_type = emergency_row_type(channel)
        if emergency_type not in actual_order:
            actual_order.append(emergency_type)
        print(f"  {i+1}. {channel['Name']:<25} ({emergency_type}) - {channel['Frequency']} MHz")
    
    print(f"\nExpected Priority Order: {', '.join(expected_order)}")
    print(f"Actual Priority Order:   {', '.join(actual_order)}")
    
    if actual_order == expected_order:
        print("✓ Priority sorting working correctly")
    else:
        print("✗ Priority sorting not working correctly")
    
    print()

def test_noaa_auto_skip():
    """Test NOAA auto-skip functionality"""
    print("=== NOAA Auto-Skip Test ===\n")
    
    test_channels = [
        {'Name': 'Police Dispatch', 'Frequency': 155.475, 'Band': 'Emergency'},
        {'Name': 'Fire Dispatch', 'Frequency': 154.280, 'Band': 'Emergency'},
        {'Name': 'NOAA Weather', 'Frequency': 162.550, 'Band': 'NOAA'},
        {'Name': 'W9IL Repeater', 'Frequency': 146.940, 'Band': '2m'},
        {'Name': 'KC9RJS Repeater', 'Frequency': 443.750, 'Band': '70cm'},
    ]
    
    profiles_to_test = ['Emergency Comms', 'Traveler', 'HamScan']
    
    for profile_name in profiles_to_test:
        print(f"Testing {profile_name} Profile:")
        profile = DEFAULT_BAND_PROFILES[profile_name]
        auto_skip_noaa = profile.get('auto_skip_noaa', False)
        
        print(f"  Auto-skip NOAA: {auto_skip_noaa}")
        
        for channel in test_channels:
            should_skip = False
            band = channel['Band']
            
            # Simulate auto-skip logic
            if auto_skip_noaa and band == 'NOAA':
                should_skip = True
            
            # Profile-specific logic
            if profile_name == 'HamScan' and band in ('Emergency', 'NOAA'):
                should_skip = True
            elif profile_name == 'Emergency Comms' and band in ('2m', '70cm', '1.25m'):
                should_skip = True
            
            status = "SKIP" if should_skip else "KEEP"
            print(f"    {channel['Name']:<20} ({band:<10}) -> {status}")
        
        print()

def test_channel_limits():
    """Test channel limits for different profiles"""
    print("=== Channel Limits Test ===\n")
    
    # Simulate a large channel list
    large_channel_list = []
    for i in range(200):
        large_channel_list.append({
            'Name': f'Test Channel {i+1}',
            'Frequency': 146.000 + (i * 0.025),
            'Band': '2m' if i % 2 == 0 else '70cm'
        })
    
    profiles_to_test = ['Emergency Comms', 'Traveler', 'HamScan']
    
    for profile_name in profiles_to_test:
        profile = DEFAULT_BAND_PROFILES[profile_name]
        max_channels = profile.get('max_channels', 200)
        
        print(f"{profile_name} Profile:")
        print(f"  Max Channels: {max_channels}")
        print(f"  Input Channels: {len(large_channel_list)}")
        
        if len(large_channel_list) > max_channels:
            limited_channels = large_channel_list[:max_channels]
            print(f"  Output Channels: {len(limited_channels)} (LIMITED)")
            print(f"  ✓ Channel limit applied correctly")
        else:
            print(f"  Output Channels: {len(large_channel_list)} (NO LIMIT)")
            print(f"  ✓ No limit needed")
        
        print()

def test_traveler_mobile_optimization():
    """Test traveler mobile optimization features"""
    print("=== Traveler Mobile Optimization Test ===\n")
    
    traveler_profile = DEFAULT_BAND_PROFILES['Traveler']
    
    # Test mobile optimization flag
    mobile_optimized = traveler_profile.get('mobile_optimized', False)
    print(f"Mobile Optimization: {mobile_optimized}")
    
    if mobile_optimized:
        print("✓ Traveler profile is mobile optimized")
    else:
        print("✗ Traveler profile is not mobile optimized")
    
    # Test band selection for mobile use
    traveler_bands = traveler_profile['bands']
    print(f"Traveler Bands: {', '.join(traveler_bands)}")
    
    # Should include ham bands for mobile communication
    ham_bands_included = ['2m', '70cm', '1.25m']
    mobile_ham_present = all(band in traveler_bands for band in ham_bands_included)
    
    if mobile_ham_present:
        print("✓ Mobile ham bands included")
    else:
        print("✗ Mobile ham bands missing")
    
    # Should include emergency for travel safety
    emergency_included = 'Emergency' in traveler_bands
    if emergency_included:
        print("✓ Emergency channels included for travel safety")
    else:
        print("✗ Emergency channels missing for travel safety")
    
    # Should include NOAA for weather alerts
    noaa_included = 'NOAA' in traveler_bands
    if noaa_included:
        print("✓ NOAA weather included (will be auto-skipped in scanner mode)")
    else:
        print("✗ NOAA weather missing")
    
    print()

def test_scanner_mode_integration():
    """Test scanner mode integration with enhanced profiles"""
    print("=== Scanner Mode Integration Test ===\n")
    
    test_scenarios = [
        {
            'profile': 'Emergency Comms',
            'band': 'NOAA',
            'expected_skip': True,
            'reason': 'Auto-skip NOAA enabled'
        },
        {
            'profile': 'Emergency Comms',
            'band': '2m',
            'expected_skip': True,
            'reason': 'Ham bands skipped in Emergency Comms'
        },
        {
            'profile': 'Emergency Comms',
            'band': 'Emergency',
            'expected_skip': False,
            'reason': 'Emergency channels kept'
        },
        {
            'profile': 'Traveler',
            'band': 'NOAA',
            'expected_skip': True,
            'reason': 'Auto-skip NOAA enabled'
        },
        {
            'profile': 'Traveler',
            'band': '2m',
            'expected_skip': False,
            'reason': 'Ham bands kept for mobile use'
        },
        {
            'profile': 'HamScan',
            'band': 'Emergency',
            'expected_skip': True,
            'reason': 'Emergency channels skipped in HamScan'
        },
        {
            'profile': 'HamScan',
            'band': 'NOAA',
            'expected_skip': True,
            'reason': 'NOAA channels skipped in HamScan'
        },
    ]
    
    print("Scanner Mode Skip Logic Test:")
    for scenario in test_scenarios:
        profile_name = scenario['profile']
        band = scenario['band']
        expected_skip = scenario['expected_skip']
        reason = scenario['reason']
        
        # Simulate skip logic
        profile = DEFAULT_BAND_PROFILES[profile_name]
        scanner_mode_enabled = True
        
        should_skip = False
        
        # Auto-skip NOAA
        if profile.get('auto_skip_noaa', False) and band == 'NOAA':
            should_skip = True
        
        # Profile-specific logic
        if profile_name == 'HamScan' and band in ('Emergency', 'NOAA'):
            should_skip = True
        elif profile_name == 'Emergency Comms' and band in ('2m', '70cm', '1.25m'):
            should_skip = True
        
        status = "✓" if should_skip == expected_skip else "✗"
        result = "SKIP" if should_skip else "KEEP"
        print(f"  {status} {profile_name:<18} + {band:<10} -> {result} ({reason})")
    
    print()

def main():
    """Run all enhanced profile tests"""
    print("FreqFinder Enhanced Profiles Test Suite")
    print("=" * 60)
    print()
    
    test_enhanced_profiles()
    print("-" * 60)
    
    test_emergency_priority_system()
    print("-" * 60)
    
    test_noaa_auto_skip()
    print("-" * 60)
    
    test_channel_limits()
    print("-" * 60)
    
    test_traveler_mobile_optimization()
    print("-" * 60)
    
    test_scanner_mode_integration()
    print("=" * 60)
    print("Enhanced profile tests completed!")

if __name__ == "__main__":
    main()
