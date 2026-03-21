from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import (
    Button,
    Header,
    Footer,
    Input,
    Label,
    ListView,
    ListItem,
    RadioButton,
    RadioSet,
    Static,
    Switch,
    DirectoryTree,
)
from textual import on
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .config import Config


class DownloadProgress(Static):
    progress = reactive(0.0)
    
    def render(self) -> str:
        bar_width = 40
        filled = int(bar_width * self.progress)
        bar = "█" * filled + "░" * (bar_width - filled)
        return f"[progress]{bar}[/progress] {self.progress * 100:.1f}%"


class MainScreen(Screen):
    config: Config
    current_url: reactive[str] = reactive("")
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("c", "switch_mode('config')", "Config"),
        Binding("d", "switch_mode('download')", "Download"),
    ]
    
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with VerticalScroll(id="sidebar"):
                yield Label("yt-dlp TUI", classes="title")
                yield Button("Download", id="btn-download", variant="primary")
                yield Button("Config", id="btn-config")
                yield Button("Queue", id="btn-queue")
            
            with VerticalScroll(id="main-content"):
                yield Label("Enter URL:", id="url-label")
                yield Input(placeholder="https://youtube.com/watch?v=...", id="url-input")
                yield Button("Start Download", id="btn-start", variant="success")
                yield DownloadProgress(id="progress", classes="hidden")
                yield Static("", id="output-log")
        yield Footer()
    
    @on(Input.Changed, "#url-input")
    def on_url_changed(self, event: Input.Changed) -> None:
        self.current_url = event.value
    
    @on(Button.Pressed, "#btn-start")
    def on_start_download(self) -> None:
        url = self.query_one("#url-input", Input).value
        if url:
            self.start_download(url)
    
    def start_download(self, url: str) -> None:
        from yt_dlp import YoutubeDL
        
        progress = self.query_one("#progress", DownloadProgress)
        log = self.query_one("#output-log", Static)
        progress.remove_class("hidden")
        
        def progress_hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    self.call_from_thread(progress.update, downloaded / total)
            elif d["status"] == "finished":
                self.call_from_thread(progress.update, 1.0)
                self.call_from_thread(log.update, f"Finished: {d.get('filename')}")
        
        opts = self.config.get_yt_dlp_options(url)
        opts["progress_hooks"] = [progress_hook]
        
        def download():
            try:
                with YoutubeDL(opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                self.call_from_thread(log.update, f"Error: {e}")
        
        executor = ThreadPoolExecutor(max_workers=1)
        asyncio.get_event_loop().run_in_executor(executor, download)


class ConfigScreen(Screen):
    config: Config
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]
    
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
    
    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Label("Cookie Settings", classes="section-title")
            with RadioSet(id="cookie-mode"):
                yield RadioButton("No Cookies", value="none", id="cookie-none")
                yield RadioButton("From Browser", value="browser", id="cookie-browser")
                yield RadioButton("From File", value="file", id="cookie-file")
            
            with RadioSet(id="browser-select"):
                for browser in ["firefox", "chrome", "chromium", "edge", "opera", "brave", "vivaldi", "safari"]:
                    yield RadioButton(browser.capitalize(), value=browser)
            
            yield Input(
                placeholder="Cookie file path...",
                id="cookie-file-path",
            )
            
            yield Label("Format Settings", classes="section-title")
            with RadioSet(id="quality-select"):
                for q in ["best", "1080p", "720p", "480p", "360p", "audio"]:
                    yield RadioButton(q, value=q)
            
            with RadioSet(id="container-select"):
                for c in ["best", "mkv", "mp4", "webm"]:
                    yield RadioButton(c.upper(), value=c)
            
            yield Label("Download Settings", classes="section-title")
            yield Input(
                value=self.config.download.output_dir,
                placeholder="Output directory...",
                id="output-dir",
            )
            yield Input(
                value=self.config.download.output_template,
                placeholder="Filename template...",
                id="output-template",
            )
            
            with Horizontal():
                yield Label("Embed Thumbnail:")
                yield Switch(id="embed-thumb", value=self.config.download.embed_thumbnail)
            with Horizontal():
                yield Label("Embed Metadata:")
                yield Switch(id="embed-meta", value=self.config.download.embed_metadata)
            with Horizontal():
                yield Label("Extract Audio Only:")
                yield Switch(id="extract-audio", value=self.config.download.extract_audio)
            
            with RadioSet(id="audio-format"):
                for af in ["mp3", "flac", "m4a", "wav", "opus"]:
                    yield RadioButton(af.upper(), value=af)
            
            yield Button("Save Config", id="btn-save", variant="success")
        
        yield Footer()
    
    def on_mount(self) -> None:
        self._load_config_to_ui()
    
    def _load_config_to_ui(self) -> None:
        self.query_one(f"#cookie-{self.config.cookie.mode}", RadioButton).value = True
        self.query_one(f"#browser-{self.config.cookie.browser}", RadioButton).value = True
        self.query_one("#cookie-file-path", Input).value = self.config.cookie.file_path
        self.query_one(f"#quality-{self.config.format.quality}", RadioButton).value = True
        self.query_one(f"#container-{self.config.format.container}", RadioButton).value = True
        self.query_one(f"#audio-{self.config.download.audio_format.lower()}", RadioButton).value = True
    
    @on(Button.Pressed, "#btn-save")
    def on_save(self) -> None:
        cookie_mode = self.query_one("#cookie-mode", RadioSet).pressed[0].id.replace("cookie-", "") if self.query_one("#cookie-mode", RadioSet).pressed else "none"
        browser = self.query_one("#browser-select", RadioSet).pressed[0].value if self.query_one("#browser-select", RadioSet).pressed else "firefox"
        file_path = self.query_one("#cookie-file-path", Input).value
        quality = self.query_one("#quality-select", RadioSet).pressed[0].value if self.query_one("#quality-select", RadioSet).pressed else "best"
        container = self.query_one("#container-select", RadioSet).pressed[0].value if self.query_one("#container-select", RadioSet).pressed else "best"
        
        self.config.cookie.mode = cookie_mode
        self.config.cookie.browser = browser
        self.config.cookie.file_path = file_path
        self.config.format.quality = quality
        self.config.format.container = container
        self.config.download.output_dir = self.query_one("#output-dir", Input).value
        self.config.download.output_template = self.query_one("#output-template", Input).value
        self.config.download.embed_thumbnail = self.query_one("#embed-thumb", Switch).value
        self.config.download.embed_metadata = self.query_one("#embed-meta", Switch).value
        self.config.download.extract_audio = self.query_one("#extract-audio", Switch).value
        if self.query_one("#audio-format", RadioSet).pressed:
            self.config.download.audio_format = self.query_one("#audio-format", RadioSet).pressed[0].value
        
        self.config.save()
        self.app.pop_screen()


class YtDlpTUI(App):
    CSS = """
    Screen { layout: horizontal; }
    #sidebar { width: 30%; border: solid $primary; }
    .title { text-style: bold; margin: 1 0; }
    .section-title { text-style: bold; margin-top: 2; }
    .hidden { display: none; }
    RadioSet { margin-bottom: 1; }
    RadioButton { margin: 0 1; }
    Input { margin-bottom: 1; }
    """
    
    def __init__(self):
        super().__init__()
        self.config = Config.load()
    
    def on_mount(self) -> None:
        self.push_screen(MainScreen(self.config))
    
    def action_switch_mode(self, mode: str) -> None:
        if mode == "config":
            self.push_screen(ConfigScreen(self.config))


def run():
    app = YtDlpTUI()
    app.run()
