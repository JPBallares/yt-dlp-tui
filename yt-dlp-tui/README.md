# yt-dlp-tui

A terminal user interface (TUI) wrapper for [yt-dlp](https://github.com/yt-dlp/yt-dlp) with saved configurations for format, quality, and cookies.

## Features

- **Configurable Quality Presets**: best, 1080p, 720p, 480p, 360p, or audio-only
- **Container Format Selection**: mkv, mp4, webm, or best available
- **Cookie Management**: Use cookies from browser (Firefox recommended) or a cookie.txt file
- **Download Options**: Embed thumbnails, metadata, and audio extraction
- **Persistent Config**: Settings saved to `~/.config/yt-dlp-tui/config.toml`

## Project Structure

```
yt-dlp-tui/
├── pyproject.toml              # Project metadata and dependencies
└── src/
    └── yt_dlp_tui/
        ├── __init__.py         # Package exports
        ├── config.py           # Config dataclasses and persistence
        └── main.py             # Textual TUI application
```

## Local Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
# Clone or navigate to the project directory
cd yt-dlp-tui

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

## Usage

### Running the App

```bash
yt-dlp-tui
```

### Controls

| Key | Action |
|-----|--------|
| `q` | Quit application |
| `c` | Open Config screen |
| `d` | Open Download screen |
| `Escape` | Back to previous screen |

### Main Screen

1. Enter a YouTube URL in the input field
2. Click **Start Download** or press the button
3. View progress in the progress bar

### Config Screen

#### Cookie Settings

- **No Cookies**: Download public videos without authentication
- **From Browser**: Extract cookies from your browser (Firefox recommended)
  - Note: Chrome/Edge have encrypted cookie databases and may not work reliably
- **From File**: Use a Netscape-format cookie file (e.g., from browser extension)

#### Format Settings

- **Quality**: Select resolution limit or audio-only
- **Container**: Choose video format (mp4, mkv, webm)

#### Download Settings

- **Output Directory**: Where to save downloads (default: `~/Downloads`)
- **Filename Template**: yt-dlp format string (default: `%(title)s.%(ext)s`)
- **Embed Thumbnail**: Add video thumbnail as cover art
- **Embed Metadata**: Add video metadata (title, uploader, etc.)
- **Extract Audio Only**: Convert to audio with selected format

### Cookie Recommendation

For age-restricted or private videos:

1. Use **Firefox** (recommended for cookie extraction)
2. Log into YouTube in Firefox
3. In the TUI, select **From Browser** → **Firefox**
4. Cookies expire ~2 weeks; refresh by logging in again

## Configuration File

Settings are stored at:

- **Linux/macOS**: `~/.config/yt-dlp-tui/config.toml`
- **Windows**: `%APPDATA%\yt-dlp-tui\config.toml`

Example:

```toml
[cookie]
mode = "browser"
browser = "firefox"
file_path = ""

[format]
quality = "best"
container = "best"
codec = ""

[download]
output_template = "%(title)s.%(ext)s"
output_dir = "~/Downloads"
embed_thumbnail = true
embed_metadata = true
extract_audio = false
audio_format = "mp3"
```

## Dependencies

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloader
- [Textual](https://github.com/Textualize/textual) - TUI framework
- [platformdirs](https://github.com/platformdirs/platformdirs) - Config directory
- [toml](https://github.com/uiri/toml) - Config file parsing
