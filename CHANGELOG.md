# ChirpScrape Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Professional donation dialog that stays in focus on app launch
- Modern gradient-based HTML donation portal
- Responsive donation page with mobile optimization
- Clickable donation links with 💵 emoji for PayPal and Cash App
- Email contact option on donation page

### Changed
- Improved donation dialog initialization (500ms delay for proper focus)
- Enhanced donation portal with professional typography and styling
- Better text wrapping and spacing in donation content

### Fixed
- Donation dialog no longer hides behind main window on startup
- Donation portal text now fits properly in all window sizes

---

## [2.2.0] - 2026-02-04

### Added - Enhanced Radio Models & Safety Features
- **✨ Expanded Baofeng Radio Support**
  - Baofeng UV-5R (Full-size variant)
  - Baofeng UV-5R Mini (Compact variant)
  - Baofeng UV-82 (Rugged/Waterproof variant)
  - Individual feature matrices for each model

- **📚 Help → Firmware Submenu**
  - Firmware Unlock Guide with resource window
  - Baofeng UV-5R Unlock (Miklor) direct link
  - Baofeng Full Guide (Miklor) documentation
  - CHIRP Firmware Database integration
  - Warranty warnings and best practices

- **🛡️ Safety & Startup Options** (New Preferences Tab)
  - Text Mode Startup (CLI alternative)
  - Disable Startup Tips
  - Confirm Before Export
  - Auto Backup Before Save
  - Safe Frequency Validation
  - Channel Limit Warnings

- **🎚️ Advanced Preferences Tabs** (Complete UI Redesign)
  - 📻 Radio Models Tab - Model selection and capabilities
  - ⚙️ Export Quality Tab - 4 quality levels with features
  - 🛡️ Safety & Startup Tab - Safety options for ease of use
  - 🔧 Advanced Tweaks Tab - Power user customization

- **📏 Improved Preferences Window**
  - Resizable interface (750x650px, min 700x600px)
  - Scrollable content in all tabs
  - Professional layout with improved spacing
  - Better font sizing and organization

### Changed
- Preferences window redesigned with tabbed interface
- Radio model selection now with specific variants
- Preferences window expanded for better content visibility
- Getting Started guide updated with new model references
- Menu structure enhanced with new Firmware submenu

### Improved
- User interface organization and usability
- Content accessibility with scrollable tabs
- Professional appearance with emoji indicators
- Documentation clarity and comprehensiveness
- Radio model specificity and accuracy

### Backward Compatible
- ✅ 100% compatible with existing installations
- ✅ All features optional with sensible defaults
- ✅ No breaking changes to existing functionality
- ✅ Automatic preference migration

### Documentation
- Updated Getting Started guide with Baofeng variants
- New firmware unlock resources and links
- Comprehensive setting descriptions
- Professional release notes (New_media_22.md)

---

## [2.1.0] - 2026-02-04

### Added - Major Enhancement Release
- **Radio Model Selection System**: 5 professional radio models
  - Generic (Default)
  - Anytone DM32UV (NEW) - Full DMR Digital + Analog support
  - Baofeng UV-5R/UV-82
  - Motorola (Professional)
  - Kenwood (VHF/UHF)

- **Export Quality Levels**: 4 customization tiers
  - Default (Essential only)
  - Standard (Deduplication)
  - Advanced (Tone decode, Sorting)
  - High Quality (Optimization, Metadata)

- **Comprehensive Tooltip System**
  - Reusable ToolTip class with smart delays
  - Auto-positioning and text wrapping
  - Applied to all major UI elements

- **Interactive Getting Started Guide**
  - 9 detailed feature sections
  - Scrollable content for easy navigation
  - In-app help documentation

- **Professional Preferences Dialog**
  - Model selection dropdown
  - Live feature display
  - Quality level selection with descriptions
  - Professional centered layout

- **Dynamic Model Options Panel**
  - Real-time model information display
  - Supported features list
  - Auto-updates on preference changes

- **Enhanced File Operations**
  - Save As menu option
  - Save previously exported data to new locations

- **Professional Export Progress Indicator**
  - Animated progress bar
  - Real-time status messages
  - Centered on main window

- **Organized Menu Structure**
  - File → Save As, Themes, Exit
  - API → API Key Management
  - Preferences → Radio & Export Settings
  - Help → Getting Started, RadioReference, How-To, Contact

### Changed
- Menu structure reorganized for better navigation
- Enhanced customer service features
- Improved documentation structure

### Improved
- Code quality with comprehensive error handling
- User experience with tooltips and guides
- Performance with lazy-loaded tooltips

### Backward Compatible
- 100% compatible with existing code
- All features optional with sensible defaults
- Non-breaking changes

---

## [2.0.1] - 2026-01-15

### Added
- Screenshot to README
- .gitignore for local build/venv

### Fixed
- Build artifacts moved to Unused_Files directory

---

## [2.0.0] - 2026-01-10

### Added
- 70cm/2m band support
- NOAA/MURS/FRS-GMRS defaults loaded from csv_files
- FRS/GMRS band support
- Menu reorganization
- 10 theme options
- Help menu with RadioReference and How-To
- Donation QR code display on right-hand area of GUI

### Changed
- GUI window layout widened for better display
- Menu reorganized (File, API, Help structure)
- Enhanced theme system

### Removed
- SOAP Debug menu option
- Backup CSVs from version control (moved to backups_csvs/)

### Improved
- Frequency database loading from local CSV files
- Band management and selection
- Visual display of donation options

---

## [1.0.0] - 2025-12-20

### Added
- Initial stable release
- Core RadioReference scraper functionality
- CTID to ZIP code mapping
- CSV export functionality
- Basic GUI with Tkinter
- API key management
- Band selection and filtering
- Theme support

### Features
- Support for RadioReference API integration
- RadioReference index file (radioref.csv) for CTID mapping
- ZIP code to frequency scraping
- Multiple band selection
- CSV format export
- GUI Bootstrap launcher

---

## [0.5.0] - 2025-12-01

### Added
- Initial pre-release
- Basic project structure
- RadioReference API integration
- CSV file handling
- Bootstrap installation script

---

## Getting Help

For questions or support:
1. Check the **Getting Started** guide (Help menu)
2. Hover over UI elements for **context-sensitive tooltips**
3. Visit the **RadioReference** link for frequency database
4. Open an **issue** on GitHub
5. **Support** the developer via donations

---

## Versioning

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR** version: Breaking changes
- **MINOR** version: New features (backward compatible)
- **PATCH** version: Bug fixes

---

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## License

See LICENSE file for details.

---

**Last Updated**: February 4, 2026  
**Maintainer**: Tim Rohe (trstechie@gmail.com)  
**Repository**: [Chirp_Scrape](https://github.com/Drizztdowhateva/Chirp_Scrape)
