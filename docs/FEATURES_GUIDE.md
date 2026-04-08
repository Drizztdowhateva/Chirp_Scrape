# FreqFinder - Enhanced Features Guide

## Overview
FreqFinder has been significantly enhanced with professional-grade radio model support, comprehensive customization options, and extensive customer support features.

---

## 🎯 New Features

### 1. **Radio Model Selection**

The application now supports multiple radio models with model-specific feature detection:

#### Supported Models:
- **Generic Radio (Default)**
  - Compatible with most CHIRP-supported radios
  - Max Channels: 10,000
  - Features: CTCSS Tones, DTCS, Duplex, Offset

- **Baofeng UV-5R/UV-82**
  - Popular budget-friendly handheld (UV-5R includes Mini variant)
  - Max Channels: 128
  - Features: CTCSS Tones, DTCS, Duplex, Offset
  - Best for: Budget-conscious operators

- **Motorola (Professional)**
  - Professional grade digital/analog
  - Max Channels: 1,000
  - Features: CTCSS Tones, DTCS, Duplex, Offset, Color Code
  - Best for: Professional/commercial use

- **Kenwood (VHF/UHF)**
  - Mobile and portable units
  - Max Channels: 500
  - Features: CTCSS Tones, DTCS, Duplex, Offset
  - Best for: VHF/UHF operators

**Accessing Model Selection:**
1. Click **Preferences** menu → **Radio & Export Settings**
2. Choose your radio model from the dropdown
3. View supported features and specifications
4. Click **Apply**

---

### 2. **Export Quality & Customization Levels**

Choose the perfect balance between simplicity and advanced features:

#### **Default** (Basic)
- Essential features only
- CTCSS Tones, Tone decoding
- Frequency validation
- Best for: Quick exports, simple setups
- Settings: Comments, Tones, Offset

#### **Standard** (Enhanced)
- All Default features plus:
- Duplicate frequency removal
- Additional metadata
- Best for: Most users
- Settings: Comments, Tones, Offset, Skip fields

#### **Advanced** (Power Users)
- All Standard features plus:
- Tone decode information
- Automatic frequency sorting
- Advanced filtering
- Best for: Experienced operators
- Settings: Tone decode, Frequency sorting, Smart filtering

#### **High Quality** (Professional)
- Maximum optimization and quality
- All previous features plus:
- Intelligent step size optimization
- Metadata enrichment
- Comprehensive validation
- Best for: Critical applications, premium quality
- Settings: All optimization features enabled

**Accessing Quality Levels:**
1. Click **Preferences** menu → **Radio & Export Settings**
2. Select desired quality level (radio buttons)
3. Review feature descriptions for your selection
4. Click **Apply**

---

### 3. **Comprehensive Tooltips**

Hover over any GUI element to get instant help:

- **ZIP Code Fields**: Enter location information
- **Band Selection**: Understand each frequency band
- **Order Buttons**: Prioritize bands for export
- **Export Button**: Quick export information
- **Model Options Panel**: Current radio model and quality level

**Tooltip Behavior:**
- Appears after 1 second of hovering
- Follows cursor position
- Automatically hides when mouse leaves element
- Wraps text for readability

---

### 4. **Getting Started Guide**

New comprehensive help for new users:

1. Click **Help** menu → **Getting Started**
2. Scrollable guide with:
   - Step-by-step instructions
   - Band explanations
   - Quality level descriptions
   - Tips and tricks
   - Model information

**Topics Covered:**
- Entering locations
- Selecting and ordering bands
- Setting preferences
- Exporting and saving files
- Understanding quality levels
- Radio model features
- Helpful tips and support

---

### 5. **Dynamic Radio Model Options Panel**

Real-time display showing:
- Selected radio model
- Current export quality level
- Supported features list
- Updates automatically when preferences change

**Display:**
```
Model: Baofeng UV-5R/UV-82 | Quality: High Quality
Features: CTCSS Tones • DTCS • Duplex • Offset
```

---

### 6. **File/Save As Menu**

Enhanced file management:

- **Save As...** (File menu)
  - Save previously exported data to new locations
  - Useful for saving same data under different names
  - No need to re-export
  - Requires data to be exported first

---

### 7. **Export Progress Indicator**

Visual feedback during export:

- Animated progress bar
- Status messages:
  - "Building DataFrame..."
  - "Preparing X rows..."
  - "Choose save location..."
  - "Writing to file..."
- Professional progress window
- Centered on main window
- Prevents accidental cancellation

---

### 8. **Customer Service & Quality Assurance**

#### Support Channels:
- **Help Menu**
  - Getting Started guide
  - RadioReference link (frequency database)
  - How-To documentation
  
- **Contact Menu**
  - Donation support (Coffee/PayPal)
  - GitHub project link
  
- **Preferences Help**
  - Model descriptions
  - Feature explanations
  - Quality level comparisons

#### Quality Features:
- Input validation
- Frequency validation based on band ranges
- Duplicate detection
- Tone frequency validation (50-260 Hz)
- Error messages with helpful context
- Graceful fallback handling

---

## 🎮 User Interface Improvements

### Layout Enhancements:
1. **Input Section**: Up to 4 ZIP codes with real-time location resolution
2. **Band Selection**: Checkboxes with Up/Down reordering buttons
3. **Model Information**: Live-updating panel showing current configuration
4. **Status Feedback**: Clear messaging at each step
5. **Professional Styling**: Color-coded buttons, organized sections

### Theme Support:
- Light (Default)
- Dark
- Solarized Light/Dark
- Gruvbox
- Monokai
- Nord
- Dracula
- High Contrast
- Classic

---

## 🔧 Technical Details

### Data Structures:

**RADIO_MODELS Dictionary:**
- Supports arbitrary feature flags
- Easily extensible for future models
- Includes max channel capacity
- Stores model descriptions

**CUSTOMIZATION_LEVELS Dictionary:**
- Four quality tiers
- Each with specific feature set
- Descriptions for user guidance
- Boolean flags for feature toggling

### Error Handling:
- Try/except blocks around all file operations
- User-friendly error messages
- Graceful degradation
- Recovery options

---

## 💡 Tips & Tricks

### For Best Results:
1. **Start with Getting Started guide** (Help menu)
2. **Select your radio model** before exporting
3. **Choose quality level** based on your needs
4. **Hover over elements** for quick help
5. **Use Preferences** to explore features

### Common Workflows:

**Quick Export (Beginner):**
- ZIP code → Default quality → Export

**Advanced Export (Power User):**
- Multiple ZIPs → Advanced quality → Custom band ordering → Export

**Professional Setup (DM32UV):**
- Select DM32UV model → High Quality → Include all bands → Export

---

## 🚀 Future Enhancements

Planned additions:
- More radio model definitions
- Frequency list import/export
- Advanced filtering options
- Custom frequency templates
- API integration for online frequency updates

---

## 📞 Support

Need help?
- **Getting Started**: Help → Getting Started
- **GitHub Issues**: Help → Contact → GitHub Project
- **Documentation**: Help → How-To
- **Donations**: Help → Contact → Donations (Support the developer!)

---

## Version Info

- **Last Updated**: February 2026
- **Features**: Model Selection, Quality Levels, DM32UV Support, Tooltips, Help System
- **Status**: Production Ready

