# ChirpScrape UI Enhancement Overview

## Menu Structure

```
┌─ File Menu
│  ├─ Save As...                    → Save exported CSV to new location
│  ├─ Separator
│  ├─ Themes                        → 10 theme options
│  │  ├─ Light
│  │  ├─ Dark
│  │  ├─ Solarized Light/Dark
│  │  ├─ Gruvbox
│  │  ├─ Monokai
│  │  ├─ Nord
│  │  ├─ Dracula
│  │  ├─ High Contrast
│  │  └─ Classic
│  └─ Exit                          → Close application
│
├─ API Menu
│  ├─ Enter API key...              → Manually enter API credentials
│  └─ Use built-in (encrypted)      → Use provided API key
│
├─ Preferences Menu ⭐ NEW
│  └─ Radio & Export Settings       → Customize model & quality
│
└─ Help Menu
   ├─ Getting Started ⭐ NEW         → Interactive tutorial
   ├─ Separator
   ├─ RadioReference                → Link to frequency database
   ├─ How-To                        → Project documentation
   └─ Contact
      ├─ Donations
      └─ GitHub Project
```

## Main Window Layout

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                          ChirpScrape                      [QR Code Area]  ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZIP Code 1:  [____________]  ← Resolved to → [County, State (ctid)]     ║
║               [Tooltip: Enter ZIP or URL]                                  ║
║                                                                              ║
║  ZIP Code 2:  [____________]                                              ║
║  ZIP Code 3:  [____________]                                              ║
║  ZIP Code 4:  [____________]                                              ║
║                                                                              ║
║  Available Bands:                                                           ║
║  ☑ 70cm        ║ Selected Bands:                                           ║
║  ☑ 2m          ║ ┌──────────────┐                                          ║
║  ☐ NOAA        ║ │ 70cm         │                                          ║
║  ☐ MURS        ║ │ 2m           │                                          ║
║  ☐ FRS/GMRS    ║ └──────────────┘                                          ║
║                ║ [↑ Up] [↓ Down]                                            ║
║                ║                                                             ║
║  ┌─ Radio Model Options ─────────────────────────────────────────────────┐  ║
║  │ Model: Generic | Quality: Default                                      │  ║
║  │ Features: CTCSS Tones • DTCS • Duplex • Offset                        │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║            [              Export CSV              ]                         ║
║                                                                              ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

## Preferences Dialog

```
╔═════════════════════════════════════════════════════╗
║  Preferences - Radio & Export Settings             ║
╠═════════════════════════════════════════════════════╣
║                                                     ║
║  ┌─ Radio Model Selection ──────────────────────┐  ║
║  │ Select Your Radio:                           │  ║
║  │ [Generic Radio (Default)          ▼]         │  ║
║  │                                              │  ║
║  │ Compatible with most CHIRP-supported radios │  ║
║  │                                              │  ║
║  │ Supported Features:                          │  ║
║  │ ✓ CTCSS Tones                                │  ║
║  │ ✓ DTCS Codes                                 │  ║
║  │ ✓ Duplex (+/-)                               │  ║
║  │ ✓ Offset                                     │  ║
║  │ ✓ Mode                                       │  ║
║  │ ✓ Skip                                       │  ║
║  │ Max Channels: 10000                          │  ║
║  └─────────────────────────────────────────────┘  ║
║                                                     ║
║  ┌─ Export Quality & Customization ───────────┐   ║
║  │ Choose Export Quality Level:                │   ║
║  │ ○ Default                                   │   ║
║  │   Basic settings with essential features   │   ║
║  │                                              │   ║
║  │ ● Standard                                  │   ║
║  │   Standard settings with extended features │   ║
║  │                                              │   ║
║  │ ○ Advanced                                  │   ║
║  │   Advanced customization for power users   │   ║
║  │                                              │   ║
║  │ ○ High Quality                              │   ║
║  │   Maximum quality with all optimization   │   ║
║  │                                              │   ║
║  │ ✓ include_comment                           │   ║
║  │ ✓ include_tone                              │   ║
║  │ ✓ include_offset                            │   ║
║  │ ✓ include_skip                              │   ║
║  │ ✓ validate_frequencies                      │   ║
║  │ ✓ remove_duplicates                         │   ║
║  └─────────────────────────────────────────────┘   ║
║                                                     ║
║  [         Cancel         ] [  Apply  ]             ║
║                                                     ║
╚═════════════════════════════════════════════════════╝
```

## Getting Started Guide Window

```
╔═════════════════════════════════════════════════════╗
║  Getting Started with ChirpScrape                   ║
╠═════════════════════════════════════════════════════╣
║  [Scrollable Content Area]                          ║
║  ┌─────────────────────────────────────────────┐  ║
║  │ 📍 Enter Location                            │  ║
║  │ Enter a 5-digit ZIP code or RadioReference  │  ║
║  │ URL to search for frequencies...            │  ║
║  │                                              │  ║
║  │ 📡 Select Bands                              │  ║
║  │ Choose which frequency bands to include:    │  ║
║  │ • 70cm: 420-450 MHz                          │  ║
║  │ • 2m: 144-148 MHz                            │  ║
║  │ • NOAA: Weather alerts                       │  ║
║  │ • MURS: License-free                         │  ║
║  │ • FRS/GMRS: Family radio service            │  ║
║  │                                              │  ║
║  │ 🎚️ Order Bands                               │  ║
║  │ Use Up/Down buttons to prioritize bands...  │  ║
║  │                                              │  ║
║  │ ⚙️ Set Preferences                           │  ║
║  │ Go to Preferences > Radio & Export Settings │  ║
║  │ to configure your setup...                  │  ║
║  │                                              │  ║
║  │ 💾 Export                                    │  ║
║  │ Click Export CSV to create your CHIRP file  │  ║
║  │                                              │  ║
║  │ 📱 Radio Models                              │  ║
║  │ ChirpScrape supports:                        │  ║
║  │ • Generic (all CHIRP radios)                │  ║
║  │ • DM32UV (DMR + analog)                     │  ║
║  │ • Baofeng (UV-5R/UV-82)                     │  ║
║  │ • Motorola (Professional)                   │  ║
║  │ • Kenwood (VHF/UHF)                         │  ║
║  │                                              │  ║
║  │ 💡 Tips                                      │  ║
║  │ • Hover over elements for helpful tips      │  ║
║  │ • RadioReference has the most complete data │  ║
║  │ • Contact GitHub for support/issues         │  ║
║  │                                              │  ║
║  │ Hover over any button or field for help!   │  ║
║  └─────────────────────────────────────────────┘  ║
║  ▲                                                  ║
│  │ [Scrollbar for additional content]              ║
║  ▼                                                  ║
╚═════════════════════════════════════════════════════╝
```

## Export Progress Dialog

```
╔════════════════════════════════╗
║     Exporting CSV              ║
╠════════════════════════════════╣
║                                ║
║  Processing and building CSV...║
║                                ║
║  [████████░░░░░░░░░░░░░░░░░]  ║
║                                ║
║  Building DataFrame...         ║
║                                ║
╚════════════════════════════════╝
```

## Tooltip Examples

```
When hovering over ZIP Code field:
┌────────────────────────┐
│ Enter a 5-digit ZIP    │
│ code or RadioReference │
│ URL to search for      │
│ frequencies in that    │
│ area. You can enter    │
│ up to 4 locations.     │
└────────────────────────┘

When hovering over Band checkbox:
┌────────────────────────┐
│ 70cm band              │
│ (420-450 MHz)          │
│ Ultra High Frequency - │
│ local area coverage    │
└────────────────────────┘

When hovering over Export button:
┌──────────────────────────────┐
│ Export scraped frequencies   │
│ to CHIRP CSV file for        │
│ programming into your radio  │
└──────────────────────────────┘
```

## Supported Radio Models with Features

```
┌─ Generic Radio ─────────────────────┐
│ • CTCSS Tones                       │
│ • DTCS Codes                        │
│ • Duplex (+/-)                      │
│ • Offset                            │
│ • Max Channels: 10,000              │
└─────────────────────────────────────┘

┌─ Anytone DM32UV ⭐ NEW ──────────────┐
│ • CTCSS Tones                       │
│ • DTCS Codes                        │
│ • Duplex (+/-)                      │
│ • Offset                            │
│ • DMR Color Code                    │
│ • DMR Timeslot                      │
│ • Digital Mode                      │
│ • Max Channels: 10,000              │
└─────────────────────────────────────┘

┌─ Baofeng UV-5R/UV-82 ───────────────┐
│ • CTCSS Tones                       │
│ • DTCS Codes                        │
│ • Duplex (+/-)                      │
│ • Offset                            │
│ • Max Channels: 128                 │
└─────────────────────────────────────┘

┌─ Motorola Professional ─────────────┐
│ • CTCSS Tones                       │
│ • DTCS Codes                        │
│ • Duplex (+/-)                      │
│ • Offset                            │
│ • Color Code                        │
│ • Max Channels: 1,000               │
└─────────────────────────────────────┘

┌─ Kenwood VHF/UHF ──────────────────┐
│ • CTCSS Tones                       │
│ • DTCS Codes                        │
│ • Duplex (+/-)                      │
│ • Offset                            │
│ • Max Channels: 500                 │
└─────────────────────────────────────┘
```

## Workflow Examples

### Quick Export (Beginner)
```
1. Enter ZIP code in first field
2. Select bands (default is 70cm & 2m)
3. Click "Export CSV"
4. Choose save location
5. Done! ✓
```

### Advanced Export (Power User)
```
1. Enter multiple ZIP codes (up to 4)
2. Select specific bands
3. Use Up/Down to order by priority
4. Go to Preferences → Select Advanced quality
5. Click "Export CSV"
6. Choose save location
7. Optionally save to other locations using File → Save As
8. Done! ✓
```

### Professional Setup (DM32UV)
```
1. Go to Preferences → Radio & Export Settings
2. Select "Anytone DM32UV" from dropdown
3. Choose "High Quality" for maximum optimization
4. View supported features (includes DMR options)
5. Click Apply
6. Enter location/bands as needed
7. Click "Export CSV"
8. Model Options panel shows DM32UV configuration
9. Done! ✓
```

