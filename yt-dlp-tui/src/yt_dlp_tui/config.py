from __future__ import annotations

import shlex
import shutil
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import platformdirs
import toml

CONFIG_DIR = Path(platformdirs.user_config_dir("yt-dlp-tui"))
CONFIG_FILE = CONFIG_DIR / "config.toml"
HISTORY_FILE = CONFIG_DIR / "history.json"

BROWSERS = [
    "firefox",
    "chrome",
    "chromium",
    "edge",
    "opera",
    "brave",
    "vivaldi",
    "safari",
]
QUALITIES = ["best", "1080p", "720p", "480p", "360p", "audio"]
CONTAINERS = ["best", "mkv", "mp4", "webm"]
CODECS = ["h264", "h265", "vp9", "none"]
AUDIO_FORMATS = ["mp3", "flac", "m4a", "wav", "opus"]
ARIA2_CONNECTIONS = ["4", "8", "16"]
MAX_PARALLEL_OPTIONS = ["1", "2", "3", "4", "5"]
SEARCH_PROVIDERS = {
    "YouTube": "ytsearch",
    "SoundCloud": "scsearch",
    "Google Video": "gvsearch",
}

QUALITY_FORMAT_MAP = {
    "best": "bv*+ba/b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p": "bv*[height<=720]+ba/b[height<=720]",
    "480p": "bv*[height<=480]+ba/b[height<=480]",
    "360p": "bv*[height<=360]+ba/b[height<=360]",
    "audio": "ba/b",
}


@dataclass
class DownloadTask:
    url: str
    id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))
    title: str = ""
    status: str = "queued"  # queued, downloading, finished, failed
    progress: str = "0%"
    eta: str = ""
    speed: str = ""
    error_msg: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    download_sections: str = ""
    split_chapters: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DownloadTask:
        return cls(**data)


@dataclass
class CookieSettings:
    mode: str = "none"
    browser: str = "firefox"
    file_path: str = ""


@dataclass
class FormatSettings:
    quality: str = "best"
    container: str = "mp4"
    codec: str = "none"


@dataclass
class DownloadSettings:
    output_template: str = "%(title)s [%(id)s].%(ext)s"
    output_dir: str = str(Path.home() / "Downloads")
    embed_thumbnail: bool = False
    embed_metadata: bool = False
    extract_audio: bool = False
    audio_format: str = "mp3"
    use_aria2c: bool = False
    aria2_connections: int = 8
    desktop_notifications: bool = True
    embed_subs: bool = False
    write_auto_subs: bool = False
    sub_langs: str = "en.*"
    sponsorblock_remove: bool = False
    custom_args: str = ""
    limit_rate: str = ""
    playlist_mode: str = "default"
    playlist_items: str = ""
    max_parallel_downloads: int = 1
    split_chapters: bool = False


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

    @classmethod
    def save_history(cls, history: list[DownloadTask]) -> None:
        import json

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([h.to_dict() for h in history], f, indent=2)

    @classmethod
    def load_history(cls) -> list[DownloadTask]:
        import json

        if not HISTORY_FILE.exists():
            return []

        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return [DownloadTask.from_dict(d) for d in data]
        except Exception:
            return []

    def build_cli_args(self, url: str, task: DownloadTask | None = None) -> list[str]:
        """Build the yt-dlp CLI argument list from config."""
        yt_dlp_bin = shutil.which("yt-dlp")
        if not yt_dlp_bin:
            # Fallback to current executable's directory if it's a script
            # or just 'yt-dlp'
            yt_dlp_bin = "yt-dlp"

        args: list[str] = [yt_dlp_bin]

        # Use task settings if provided, otherwise fallback to defaults
        split_chapters = task.split_chapters if task else self.download.split_chapters
        download_sections = task.download_sections if task else ""

        # Format
        fmt = self._build_format_string()
        args.extend(["-f", fmt])

        # Sections & Splitting
        if download_sections:
            args.extend(["--download-sections", download_sections])
        if split_chapters:
            args.append("--split-chapters")
            # For splitting chapters, we might want to use the section title in filename
            # But the current template is fixed.
            # If splitting, yt-dlp automatically modifies filenames if not using
            # specific templates.

        # Container merge
        if self.format.container != "best":
            args.extend(["--merge-output-format", self.format.container])

        # Recode if a specific codec is requested
        if self.format.codec != "none":
            recode_map = {
                "h264": "mp4",
                "h265": "mp4",
                "vp9": "webm",
            }
            target = recode_map.get(self.format.codec)
            if target:
                args.extend(["--recode-video", target])
                # Ensure h265 uses correct encoder if requested
                if self.format.codec == "h265":
                    args.extend(["--postprocessor-args", "ffmpeg:-c:v libx265"])
                elif self.format.codec == "h264":
                    # Optionally force slow/crf 22 for h264 as well if desired
                    args.extend(
                        [
                            "--postprocessor-args",
                            "ffmpeg:-c:v libx264 -preset slow -crf 22",
                        ]
                    )

        # Cookies
        if self.cookie.mode == "browser":
            args.extend(["--cookies-from-browser", self.cookie.browser])
        elif self.cookie.mode == "file" and self.cookie.file_path:
            args.extend(["--cookies", self.cookie.file_path])

        # Output
        output_dir = Path(self.download.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(output_dir / self.download.output_template)
        args.extend(["-o", outtmpl])

        # Post-processing
        if self.download.embed_thumbnail:
            args.append("--embed-thumbnail")
            args.extend(["--convert-thumbnails", "jpg"])
        if self.download.embed_metadata:
            args.append("--embed-metadata")
            args.extend(["--compat-options", "embed-metadata"])
        if self.download.extract_audio:
            args.extend(["-x", "--audio-format", self.download.audio_format])

        # Subtitles
        if self.download.embed_subs:
            args.append("--embed-subs")
            # For MP4 compatibility, we might need to convert subs
            if self.format.container == "mp4":
                args.extend(["--convert-subs", "srt"])
        if self.download.write_auto_subs:
            args.append("--write-auto-subs")
        if self.download.sub_langs:
            args.extend(["--sub-langs", self.download.sub_langs])

        # SponsorBlock
        if self.download.sponsorblock_remove:
            args.extend(["--sponsorblock-remove", "all"])

        # Custom arguments
        if self.download.custom_args:
            try:
                args.extend(shlex.split(self.download.custom_args))
            except Exception:
                pass  # Ignore invalid custom args

        # Rate limiting
        if self.download.limit_rate:
            args.extend(["--limit-rate", self.download.limit_rate])

        # Playlist controls
        if self.download.playlist_mode == "yes":
            args.append("--yes-playlist")
        elif self.download.playlist_mode == "no":
            args.append("--no-playlist")

        if self.download.playlist_items:
            args.extend(["--playlist-items", self.download.playlist_items])

        # External downloader
        if self.download.use_aria2c:
            conn = str(self.download.aria2_connections)
            args.extend(
                [
                    "--downloader",
                    "aria2c",
                    "--downloader-args",
                    (
                        f"aria2c:-c -j {conn} -x {conn} -s {conn} "
                        "-k 1M --summary-interval=1"
                    ),
                ]
            )

        # Progress: use newline mode so each update is a separate line
        args.append("--newline")

        args.append(url)
        return args

    def _build_format_string(self) -> str:
        base_selector = QUALITY_FORMAT_MAP.get(self.format.quality, "bv*+ba/b")

        # If codec is h264, prefer it natively
        if self.format.codec == "h264":
            # Prefer avc1+mp4a (native h264/aac)
            h264_selector = base_selector.replace("bv*", "bv*[vcodec^=avc1]").replace(
                "ba", "ba[acodec^=mp4a]"
            )
            # Fallback to base selector if not found
            return f"{h264_selector}/{base_selector}"

        if self.format.codec == "vp9":
            # Prefer vp9
            vp9_selector = base_selector.replace("bv*", "bv*[vcodec^=vp09]")
            return f"{vp9_selector}/{base_selector}"

        # Otherwise just return the base selector, possibly with container filters
        fmt = base_selector
        if self.format.container == "mp4":
            fmt = fmt.replace("bv*", "bv*[ext=mp4]").replace("ba", "ba[ext=m4a]")
        elif self.format.container in ("mkv", "webm"):
            ext = self.format.container
            fmt = fmt.replace("bv*", f"bv*[ext={ext}]").replace("ba", f"ba[ext={ext}]")

        return fmt
