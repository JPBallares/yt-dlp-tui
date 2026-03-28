from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any
import tomllib
import platformdirs
import toml
import shutil

CONFIG_DIR = Path(platformdirs.user_config_dir("yt-dlp-tui"))
CONFIG_FILE = CONFIG_DIR / "config.toml"

BROWSERS = ["firefox", "chrome", "chromium", "edge", "opera", "brave", "vivaldi", "safari"]
QUALITIES = ["best", "1080p", "720p", "480p", "360p", "audio"]
CONTAINERS = ["best", "mkv", "mp4", "webm"]
CODECS = ["h264", "h265", "vp9", "none"]
AUDIO_FORMATS = ["mp3", "flac", "m4a", "wav", "opus"]

QUALITY_FORMAT_MAP = {
    "best": "bv*+ba/b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p": "bv*[height<=720]+ba/b[height<=720]",
    "480p": "bv*[height<=480]+ba/b[height<=480]",
    "360p": "bv*[height<=360]+ba/b[height<=360]",
    "audio": "ba/b",
}


@dataclass
class CookieSettings:
    mode: str = "none"
    browser: str = "firefox"
    file_path: str = ""


@dataclass
class FormatSettings:
    quality: str = "best"
    container: str = "mp4"
    codec: str = "h264"


@dataclass
class DownloadSettings:
    output_template: str = "%(title)s [%(id)s].%(ext)s"
    output_dir: str = str(Path.home() / "Downloads")
    embed_thumbnail: bool = False
    embed_metadata: bool = False
    extract_audio: bool = False
    audio_format: str = "mp3"


@dataclass
class Config:
    cookie: CookieSettings = field(default_factory=CookieSettings)
    format: FormatSettings = field(default_factory=FormatSettings)
    download: DownloadSettings = field(default_factory=DownloadSettings)

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "wb") as f:
            content = toml.dumps(self._to_dict()).encode()
            f.write(content)

    def _to_dict(self) -> dict:
        return {
            "cookie": asdict(self.cookie),
            "format": asdict(self.format),
            "download": asdict(self.download),
        }

    @classmethod
    def load(cls) -> Config:
        if not CONFIG_FILE.exists():
            return cls()

        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)

        return cls(
            cookie=CookieSettings(**data.get("cookie", {})),
            format=FormatSettings(**data.get("format", {})),
            download=DownloadSettings(**data.get("download", {})),
        )

    def build_cli_args(self, url: str) -> list[str]:
        """Build the yt-dlp CLI argument list from config."""
        yt_dlp_bin = shutil.which("yt-dlp") or "yt-dlp"
        args: list[str] = [yt_dlp_bin]

        # Format
        fmt = self._build_format_string()
        args.extend(["-f", fmt])

        # Container merge
        if self.format.container != "best":
            args.extend(["--merge-output-format", self.format.container])

        # Cookies
        if self.cookie.mode == "browser":
            args.extend(["--cookies-from-browser", self.cookie.browser])
        elif self.cookie.mode == "file" and self.cookie.file_path:
            args.extend(["--cookies", self.cookie.file_path])

        # Output
        output_dir = Path(self.download.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(output_dir / self.download.output_template)
        args.extend(["-o", outtmpl])

        # Post-processing
        if self.download.embed_thumbnail:
            args.append("--embed-thumbnail")
        if self.download.embed_metadata:
            args.append("--embed-metadata")
        if self.download.extract_audio:
            args.extend(["-x", "--audio-format", self.download.audio_format])

        # Progress: use newline mode so each update is a separate line
        args.append("--newline")

        args.append(url)
        return args

    def _build_format_string(self) -> str:
        fmt = QUALITY_FORMAT_MAP.get(self.format.quality, "bv*+ba/b")

        # Prefer specific container extensions when not "best"
        if self.format.container == "mp4":
            fmt = fmt.replace("bv*", "bv*[ext=mp4]").replace("ba", "ba[ext=m4a]")
        elif self.format.container in ("mkv", "webm"):
            ext = self.format.container
            fmt = fmt.replace("bv*", f"bv*[ext={ext}]").replace("ba", f"ba[ext={ext}]")

        return fmt
