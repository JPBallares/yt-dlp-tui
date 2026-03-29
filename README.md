# ytdownloads

A collection of YouTube download utilities and wrappers, featuring a Textual-based Terminal User Interface (TUI) for `yt-dlp`.

## Project Structure

- `yt-dlp-tui/`: A comprehensive TUI wrapper for `yt-dlp` with persistent configurations.
- `requirements.txt`: Project-wide dependencies.

## Getting Started

### Prerequisites

- Python 3.11+ (Tested on 3.13.2)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/) (required for merging formats)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd ytdownloads
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Sub-projects

### yt-dlp-tui

The main TUI application located in the `yt-dlp-tui/` directory. It allows for easy configuration of quality, formats, and cookie management through a graphical terminal interface.

See [yt-dlp-tui/README.md](./yt-dlp-tui/README.md) for detailed instructions.
