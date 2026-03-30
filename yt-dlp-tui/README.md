# yt-dlp-tui

A terminal user interface (TUI) wrapper for [yt-dlp](https://github.com/yt-dlp/yt-dlp) with saved configurations for format, quality, and cookies.

While originally named for YouTube, it supports **thousands of sites** including Facebook, Instagram, Twitter, TikTok, and more—anywhere `yt-dlp` works!

Built with [Textual](https://github.com/Textualize/textual). Downloads run as a subprocess so yt-dlp's JS challenge solver (JavaScriptCore on macOS) works without issues.

## Features

- **Supports 1000+ Sites** -- any platform supported by `yt-dlp` (Facebook, TikTok, etc.)
- **Configurable Quality Presets** -- best, 1080p, 720p, 480p, 360p, or audio-only
- **Container Format Selection** -- mp4 (default), mkv, webm, or best available
- **Cookie Management** -- use cookies from a browser or a `cookies.txt` file
- **Download Options** -- embed thumbnails, metadata, and audio extraction
- **Live Progress** -- real-time yt-dlp output streamed into the TUI
- **Persistent Config** -- settings saved to a TOML file across sessions
- **External Downloader Support** -- use `aria2c` for multi-connection download speed boosts

## Project Structure

```
yt-dlp-tui/
├── pyproject.toml              # Project metadata and dependencies
└── src/
    └── yt_dlp_tui/
        ├── __init__.py         # Package exports
        ├── config.py           # Config dataclasses, persistence, CLI arg builder
        └── main.py             # Textual TUI (MainScreen, ConfigScreen)
```

### Key modules

- **`config.py`** -- `Config` dataclass with `save()`, `load()`, and `build_cli_args(url)` which converts saved settings into a `yt-dlp` CLI command.
- **`main.py`** -- Textual app with two screens:
  - `MainScreen` -- URL input, download button, live status/log output
  - `ConfigScreen` -- radio sets and switches for all settings

## Local Setup

### Prerequisites

- Python 3.11+ (Tested on 3.13.2)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) installed and on `PATH`
- [ffmpeg](https://ffmpeg.org/) (required by yt-dlp for merging formats)
- [aria2](https://aria2.github.io/) (optional, for faster multi-connection downloads)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

`pyproject.toml` is the standard Python packaging metadata file. Both `uv pip` and `pip` read it to resolve dependencies.

```bash
cd yt-dlp-tui

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

The `-e` flag installs in **editable mode** -- changes to source code take effect immediately without reinstalling.

## Usage

### Running the App

```bash
yt-dlp-tui
```

### Keyboard Controls

| Key      | Action                  |
|----------|-------------------------|
| `q`      | Quit application        |
| `c`      | Open Config screen      |
| `Escape` | Back to previous screen |

All hotkeys work even when an input field is focused.

### Main Screen

1. Enter a video URL (YouTube, Facebook, etc.) in the input field
2. Click **Start Download**
3. Watch live yt-dlp output stream in the log area:
   ```
   [youtube] Extracting URL: ...
   [youtube] [jsc:apple-webkit-jsi] Solving JS challenges...
   [download]  31.9% of 6.26MiB at 11.45MiB/s ETA 00:00
   Done!
   ```

### Config Screen

Press `c` or click the **Config** button to open settings.

#### Cookie Settings

| Option          | Description                                                  |
|-----------------|--------------------------------------------------------------|
| **No Cookies**  | Download public videos without authentication                |
| **From Browser**| Extract cookies from a browser (`--cookies-from-browser`)    |
| **From File**   | Use a Netscape-format `cookies.txt` (`--cookies`)            |

#### Format Settings

| Option        | Description                                    |
|---------------|------------------------------------------------|
| **Quality**   | Resolution cap: best, 1080p, 720p, 480p, 360p, audio-only |
| **Container** | Output format: mp4 (default), mkv, webm, best |

When container is set to `mp4`, the format string becomes `bv*[ext=mp4]+ba[ext=m4a]/b` with `--merge-output-format mp4`, matching the recommended yt-dlp usage for YouTube.

#### Download Settings

| Option             | Default                        | Description                          |
|--------------------|--------------------------------|--------------------------------------|
| **Output Dir**     | `~/Downloads`                  | Where to save files                  |
| **Filename**       | `%(title)s [%(id)s].%(ext)s`   | yt-dlp output template               |
| **Embed Thumbnail**| off                            | `--embed-thumbnail`                  |
| **Embed Metadata** | off                            | `--embed-metadata`                   |
| **Extract Audio**  | off                            | `-x --audio-format <format>`         |
| **Audio Format**   | mp3                            | mp3, flac, m4a, wav, opus            |
| **Use aria2c**     | off                            | use `aria2c` for multi-connection downloads |

### Faster Downloads with aria2c

You can significantly speed up downloads by enabling `aria2c` support in the config. This allows `yt-dlp` to open multiple connections per file.

#### 1. Install aria2

- **macOS**: `brew install aria2`
- **Linux**: `sudo apt install aria2` (Ubuntu/Debian) or `sudo pacman -S aria2` (Arch)
- **Windows**: `scoop install aria2` or download from [aria2.github.io](https://aria2.github.io/)

#### 2. Enable in TUI

1. Press `c` to open **Config**
2. Scroll to **Download Settings**
3. Toggle **Use aria2c (external downloader)** to **on**
4. Click **Save Config**

When enabled, the TUI uses these optimized defaults: `-c -j 16 -x 16 -s 16 -k 1M --summary-interval=1`.

### Performance Tips

- **Codec: None (Recommended)**: By default, the TUI is now set to `none`. This tells `yt-dlp` to download the best matching streams and "mux" (copy) them into your container without re-encoding. This is much faster.
- **Codec: H.264/H.265**: Setting a specific codec forces `yt-dlp` to re-encode the entire video using FFmpeg. This is very slow and CPU-intensive. Only use this if you need to ensure compatibility with a specific device that cannot play the original format.
- **Container**: `mp4` is the default. If `codec` is `none`, `yt-dlp` will try to find native `mp4` streams or mux them into an `mp4` container.

### Cookie Tips

For age-restricted or private videos:

- **From File** (recommended): Export cookies from your browser using an extension, save as `cookies.txt`, and point the config to that file
- **From Browser**: Select your browser in the config. Firefox works most reliably; Chrome/Edge have encrypted cookie databases that may fail
- Cookies expire after ~2 weeks; re-export when downloads start failing

## Configuration File

Settings persist at (via [platformdirs](https://github.com/platformdirs/platformdirs)):

| Platform  | Path                                               |
|-----------|----------------------------------------------------|
| **macOS** | `~/Library/Application Support/yt-dlp-tui/config.toml` |
| **Linux** | `~/.config/yt-dlp-tui/config.toml`                |
| **Windows** | `%APPDATA%\yt-dlp-tui\config.toml`              |

Example:

```toml
[cookie]
mode = "file"
browser = "firefox"
file_path = "/path/to/www.youtube.com_cookies.txt"

[format]
quality = "best"
container = "mp4"
codec = ""

[download]
output_template = "%(title)s [%(id)s].%(ext)s"
output_dir = "~/Downloads"
embed_thumbnail = false
embed_metadata = false
extract_audio = false
audio_format = "mp3"
```

## How It Works

The TUI does **not** use yt-dlp's Python API. Instead it:

1. Builds a CLI argument list from the saved config (`Config.build_cli_args()`)
2. Spawns `yt-dlp` as a subprocess with `--newline` for line-by-line progress
3. Streams stdout/stderr into the TUI in real time via a background thread

This approach is necessary because yt-dlp's JavaScript challenge solver uses Apple's JavaScriptCore on macOS, which requires the main thread. Since Textual owns the main thread, running yt-dlp in-process would hang.

## Dependencies

| Package | Purpose |
|---------|---------|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Video downloader (CLI) |
| [Textual](https://github.com/Textualize/textual) | TUI framework |
| [platformdirs](https://github.com/platformdirs/platformdirs) | Cross-platform config directory |
| [toml](https://github.com/uiri/toml) | Config file writing |
