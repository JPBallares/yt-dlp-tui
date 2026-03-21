from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Literal, Any
import tomllib
import platformdirs
import toml

CONFIG_DIR = Path(platformdirs.user_config_dir("yt-dlp-tui"))
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class CookieSettings:
    mode: Literal["none", "browser", "file"] = "none"
    browser: Literal["firefox", "chrome", "chromium", "edge", "opera", "brave", "vivaldi", "safari"] = "firefox"
    file_path: str = ""


@dataclass
class FormatSettings:
    quality: Literal["best", "1080p", "720p", "480p", "360p", "audio"] = "best"
    container: Literal["mkv", "mp4", "webm", "best"] = "best"
    codec: str = ""


@dataclass
class DownloadSettings:
    output_template: str = "%(title)s.%(ext)s"
    output_dir: str = str(Path.home() / "Downloads")
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    extract_audio: bool = False
    audio_format: Literal["mp3", "flac", "m4a", "wav", "opus"] = "mp3"


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
    def load(cls) -> "Config":
        if not CONFIG_FILE.exists():
            return cls()
        
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
        
        return cls(
            cookie=CookieSettings(**data.get("cookie", {})),
            format=FormatSettings(**data.get("format", {})),
            download=DownloadSettings(**data.get("download", {})),
        )

    def get_yt_dlp_options(self, url: str) -> dict[str, Any]:
        opts: dict[str, Any] = {"default_search": "ytsearch", "outtmpl": self._get_output_template()}
        
        opts["format"] = self._build_format_string()
        
        if self.cookie.mode == "browser":
            opts["cookiesfrombrowser"] = (self.cookie.browser,)  # type: ignore[assignment]
        elif self.cookie.mode == "file" and self.cookie.file_path:
            opts["cookiefile"] = self.cookie.file_path
        
        if self.download.embed_thumbnail:
            opts["embedthumbnail"] = True  # type: ignore[assignment]
        if self.download.embed_metadata:
            opts["addmetadata"] = True  # type: ignore[assignment]
        if self.download.extract_audio:
            opts["postprocessors"] = [{  # type: ignore[assignment]
                "key": "FFmpegExtractAudio",
                "preferredcodec": self.download.audio_format,
            }]
        
        return opts

    def _build_format_string(self) -> str:
        quality_map = {
            "best": "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
            "audio": "bestaudio/best",
        }
        
        fmt = quality_map.get(self.format.quality, "bestvideo+bestaudio/best")
        
        if self.format.container != "best":
            fmt += f"[ext={self.format.container}]"
        
        if self.format.codec:
            fmt += f"[vcodec={self.format.codec}]"
        
        return fmt

    def _get_output_template(self) -> str:
        output_dir = Path(self.download.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        return str(output_dir / self.download.output_template)
