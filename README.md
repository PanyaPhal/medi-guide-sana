# MediGuide 2026 — AI Emergency Assistant

## Project Structure

```
mediguide/
├── index.html           ← Main app (Home, Emergency, Hospitals, Guides screens)
├── css/
│   └── style.css        ← Complete design system (all styles in one file)
├── js/
│   └── app.js           ← All logic: navigation, protocols, Google Maps, forms
└── pages/
    ├── survey.html      ← User experience survey
    └── profile.html     ← Medical profile & appointments
```

## How to Run

**Option A — Open directly:**
Open `index.html` in Chrome, Edge, or Firefox. No server needed.

**Option B — Live Server (VSCode, recommended):**
1. Install the **Live Server** extension
2. Right-click `index.html` → **Open with Live Server**
3. Opens at `http://127.0.0.1:5500`

**Option C — Python:**
```bash
python -m http.server 8080
# Visit http://localhost:8080
```

## Google Maps Integration

Each hospital card has an **"Open in Google Maps"** button.

- If the user **allows location access** → opens turn-by-turn directions from their GPS position
- If location is **denied or unavailable** → opens a place search for the hospital

No API key required — uses standard Google Maps URLs.

## Design System

| Token | Value |
|---|---|
| Background | `#0b1e3d` (Deep Navy) |
| Teal accent | `#00c9b1` |
| Coral/SOS | `#ff4757` |
| Sky blue | `#3d9be9` |
| Font Brand | Syne (Google Fonts) |
| Font Body | Plus Jakarta Sans (Google Fonts) |

## Customization

**Add a hospital:** Push a new object to the `hospitals` array in `js/app.js`

**Add an emergency protocol:** Add a key to the `protocols` object in `js/app.js`

**Change colors:** Edit `:root` CSS variables in `css/style.css`

## Dependencies

Google Fonts only (internet required for fonts, all else is offline-ready):
- **Syne** — brand/display
- **Plus Jakarta Sans** — body

No npm · No build step · No framework · Pure HTML/CSS/JS
