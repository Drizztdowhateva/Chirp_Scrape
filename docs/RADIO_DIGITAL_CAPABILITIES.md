# Radio Digital Mode Capabilities

This document outlines which radio models support which digital modes in FreqFinder.

## Digital Mode Support Matrix

| Radio Model | P25 | D-STAR | C4FM/System Fusion | EDACS | DMR | NXDN | Digital Mode |
|-------------|-----|--------|-------------------|-------|-----|------|--------------|
| **Analog-Only Radios** | | | | | | | |
| Baofeng UV-5R | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Baofeng UV-5R Mini | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Baofeng UV-5R Plus | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Baofeng UV-82 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Baofeng UV-82LP | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **D-STAR Radios** | | | | | | | |
| Icom ID-51A PLUS2 | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Icom ID-5100E | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **System Fusion Radios** | | | | | | | |
| Yaesu FTM-400DR | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ |
| Yaesu FTM-100DR | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ |
| **Professional P25 Radios** | | | | | | | |
| Motorola (Professional) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Kenwood (VHF/UHF) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Motorola APX Series | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Icom P25-capable | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

## Digital Mode Filtering Behavior

### How FreqFinder Filters Digital Modes

1. **D-STAR Detection**: Filters out entries containing:
   - `d-star` or `dstar` in the name
   - D-STAR repeaters and reflectors

2. **P25 Detection**: Filters out entries containing:
   - `p25` in name, comment, or raw text
   - `[P25]` tags in names
   - P25 repeaters and systems

3. **C4FM/System Fusion Detection**: Filters out entries containing:
   - `c4fm` in name, comment, or raw text
   - `system fusion` in combined text
   - `fusion` in name

4. **EDACS Detection**: Filters out entries containing:
   - `[EDACS]` tags in names

5. **Other Digital Modes**: Filters out entries containing:
   - `dmr`, `nxdn`, `tdma`, `trunk`, `trunking`, `digital`

### Filtering Logic

- **Analog-only radios** (Baofeng series): All digital modes filtered out
- **D-STAR radios** (Icom ID series): Only D-STAR allowed, other digital modes filtered
- **System Fusion radios** (Yaesu FTM series): Only C4FM allowed, other digital modes filtered
- **Professional radios** (Motorola, Kenwood, Icom P25): P25 allowed, other digital modes filtered based on customization level

## Radio Model Details

### Baofeng Series (Analog Only)
- **Frequency Range**: 136-174 MHz, 400-520 MHz
- **Max Channels**: 125
- **Digital Support**: None
- **Best For**: Basic analog FM repeaters and simplex

### Icom D-STAR Series
- **Icom ID-51A PLUS2**: Handheld with GPS, Bluetooth
- **Icom ID-5100E**: Mobile with touchscreen, GPS
- **Frequency Range**: 136-174 MHz, 400-470 MHz
- **Max Channels**: 500-1000
- **Digital Support**: D-STAR only

### Yaesu System Fusion Series
- **Yaesu FTM-400DR**: Full-featured mobile
- **Yaesu FTM-100DR**: Compact mobile
- **Frequency Range**: 136-174 MHz, 400-470 MHz
- **Max Channels**: 500
- **Digital Support**: C4FM/System Fusion only

### Professional Digital Series
- **Motorola APX**: Professional P25 with extended range
- **Kenwood**: P25-capable mobile/portable
- **Icom P25**: Multi-band P25 capable
- **Frequency Range**: 136-174 MHz, 380-520 MHz, 700-900 MHz
- **Max Channels**: 1000-5000
- **Digital Support**: P25 only

## Usage Recommendations

### For Beginners
- Choose **Baofeng UV-5R Mini** for basic analog operation
- All digital repeaters will be automatically filtered out

### For Digital Mode Users
- **D-STAR users**: Choose Icom ID-51A or ID-5100E
- **System Fusion users**: Choose Yaesu FTM-400DR or FTM-100DR
- **P25 users**: Choose Motorola APX or Kenwood professional models

### For Advanced Users
- Professional radios support P25 and can be configured for other digital modes
- Higher customization levels may allow mixed digital/analog operation

## Frequency Band Compatibility

All listed radios support:
- **2m Band**: 144-148 MHz (VHF)
- **70cm Band**: 420-450 MHz (UHF)

Additional bands supported by some models:
- **1.25m Band**: 222-225 MHz (Kenwood, Icom P25)
- **Professional Bands**: 380-400 MHz, 700-900 MHz (Motorola APX, Icom P25)

## Notes

- Digital mode filtering is automatic based on selected radio model
- Customization level affects whether digital modes are included
- Emergency frequencies with digital modes are filtered for incompatible radios
- Some professional radios may support multiple digital modes with advanced customization
