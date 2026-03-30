import json
import shlex
import subprocess
import threading
from pathlib import Path

from plyer import notification
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
    Switch,
)

from .config import (
    ARIA2_CONNECTIONS,
    AUDIO_FORMATS,
    BROWSERS,
    CODECS,
    CONTAINERS,
    QUALITIES,
    Config,
)

# ---------------------------------------------------------------------------
# Helpers for RadioSet
# ---------------------------------------------------------------------------


def _radio_id(prefix: str, key: str) -> str:
    return f"{prefix}-{key}"


def _selected_key(rs: RadioSet, prefix: str) -> str | None:
    btn = rs.pressed_button
    if btn and btn.id and btn.id.startswith(prefix + "-"):
        return btn.id[len(prefix) + 1 :]
    return None


def _select_key(rs: RadioSet, prefix: str, key: str) -> None:
    target_id = _radio_id(prefix, key)
    for btn in rs.query(RadioButton):
        if btn.id == target_id:
            btn.value = True
            return


# ---------------------------------------------------------------------------
# Main download screen
# ---------------------------------------------------------------------------


class MainScreen(Screen):
    BINDINGS = [
        Binding("q", "app.quit", "Quit", priority=True),
        Binding("v", "show_convert", "Convert", priority=True),
        Binding("c", "show_config", "Config", priority=True),
    ]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._proc: subprocess.Popen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with VerticalScroll(id="sidebar"):
                yield Label("yt-dlp TUI", classes="title")
                yield Button("Convert", id="btn-convert")
                yield Button("Config", id="btn-config")
                yield Static("", id="config-summary", classes="config-summary")
            with VerticalScroll(id="main-content"):
                yield Label("Enter URL:")
                with Horizontal(id="url-row"):
                    yield Input(
                        placeholder="Enter URL (YouTube, Facebook, etc.)",
                        id="url-input",
                    )
                    yield Button("Fetch Info", id="btn-fetch", variant="primary")

                with VerticalScroll(id="preview-area", classes="hidden"):
                    yield Label("Video Details:", classes="section-title")
                    yield Static("", id="preview-details")

                yield Button("Start Download", id="btn-start", variant="success")
                yield Static("", id="status-line")
                yield Static("", id="output-log")
        yield Footer()

    def update_config_summary(self) -> None:
        summary = self.query_one("#config-summary", Static)
        text = f"Quality: {self.config.format.quality}\n"
        text += f"Container: {self.config.format.container}\n"
        text += f"Codec: {self.config.format.codec}\n"
        if self.config.download.extract_audio:
            text += f"Audio: {self.config.download.audio_format}\n"
        if self.config.download.use_aria2c:
            text += f"Aria2: {self.config.download.aria2_connections} conn\n"
        text += f"Dir: {self.config.download.output_dir}"
        summary.update(text)

    def on_mount(self) -> None:
        self.update_config_summary()

    def on_screen_resume(self) -> None:
        self.update_config_summary()

    def action_show_convert(self) -> None:
        self.app.push_screen(ConvertScreen(self.config))

    @on(Button.Pressed, "#btn-convert")
    def on_convert_pressed(self) -> None:
        self.action_show_convert()

    def action_show_config(self) -> None:
        self.app.push_screen(ConfigScreen(self.config))

    @on(Button.Pressed, "#btn-config")
    def on_config_pressed(self) -> None:
        self.action_show_config()

    @on(Button.Pressed, "#btn-fetch")
    def on_fetch_info(self) -> None:
        url = self.query_one("#url-input", Input).value.strip()
        if not url:
            return

        status = self.query_one("#status-line", Static)
        status.update("Fetching metadata...")

        def _fetch() -> None:
            try:
                # Use --dump-json to get metadata without downloading
                cmd = ["yt-dlp", "--dump-json", "--simulate", url]
                # Pass cookies if configured
                if self.config.cookie.mode == "browser":
                    cmd.extend(["--cookies-from-browser", self.config.cookie.browser])
                elif self.config.cookie.mode == "file" and self.config.cookie.file_path:
                    cmd.extend(["--cookies", self.config.cookie.file_path])

                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                stdout, stderr = proc.communicate()

                if proc.returncode == 0:
                    data = json.loads(stdout)
                    title = data.get("title", "Unknown")
                    uploader = data.get("uploader", "Unknown")
                    duration_sec = data.get("duration", 0)
                    views = data.get("view_count", 0)
                    upload_date = data.get("upload_date", "Unknown")

                    # Format duration
                    m, s = divmod(duration_sec, 60)
                    h, m = divmod(m, 60)
                    dur_str = (
                        f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
                    )

                    # Format view count
                    if views >= 1_000_000:
                        view_str = f"{views / 1_000_000:.1f}M"
                    elif views >= 1_000:
                        view_str = f"{views / 1_000:.1f}K"
                    else:
                        view_str = str(views)

                    # Format date (YYYYMMDD to YYYY-MM-DD)
                    if len(upload_date) == 8:
                        date_str = (
                            f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
                        )
                    else:
                        date_str = upload_date

                    preview_text = (
                        f"[bold]{title}[/bold]\n"
                        f"Uploader: {uploader}\n"
                        f"Duration: {dur_str} | Views: {view_str} | Date: {date_str}"
                    )

                    def update_ui() -> None:
                        details = self.query_one("#preview-details", Static)
                        area = self.query_one("#preview-area", VerticalScroll)
                        details.update(preview_text)
                        area.remove_class("hidden")
                        status.update("Metadata loaded.")

                    self.app.call_from_thread(update_ui)
                else:
                    self.app.call_from_thread(
                        status.update, f"Metadata fetch failed: {stderr.strip()[:100]}"
                    )
            except Exception as e:
                self.app.call_from_thread(status.update, f"Error: {str(e)}")

        threading.Thread(target=_fetch, daemon=True).start()

    @on(Button.Pressed, "#btn-start")
    def on_start_download(self) -> None:
        if self._proc and self._proc.poll() is None:
            return  # already running

        url = self.query_one("#url-input", Input).value.strip()
        if not url:
            return

        status = self.query_one("#status-line", Static)
        log = self.query_one("#output-log", Static)
        status.update("Starting...")
        log.update("")

        self.app.notify_desktop("Download Started", f"Processing: {url}")

        cmd = self.config.build_cli_args(url)
        app = self.app

        def _stream() -> None:
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self._proc = proc

                lines: list[str] = []
                assert proc.stdout is not None
                for raw_line in proc.stdout:
                    line = raw_line.rstrip()
                    if not line:
                        continue

                    # Show latest line as status
                    app.call_from_thread(status.update, line)

                    # Collect all lines for the log area (last 20)
                    lines.append(line)
                    tail = "\n".join(lines[-20:])
                    app.call_from_thread(log.update, tail)

                proc.wait()
                if proc.returncode == 0:
                    app.call_from_thread(status.update, "Done!")
                    app.notify_desktop(
                        "Download Finished", f"Successfully downloaded: {url}"
                    )
                else:
                    app.call_from_thread(
                        status.update, f"Failed (exit {proc.returncode})"
                    )
                    app.notify_desktop(
                        "Download Failed", f"Error code {proc.returncode} for: {url}"
                    )
            except Exception as e:
                app.call_from_thread(status.update, "Failed!")
                app.call_from_thread(log.update, str(e))
                app.notify_desktop("Download Error", f"Unexpected error: {str(e)}")

        t = threading.Thread(target=_stream, daemon=True)
        t.start()


# ---------------------------------------------------------------------------
# Convert screen
# ---------------------------------------------------------------------------


class ConvertScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
    ]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._proc: subprocess.Popen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with VerticalScroll(id="sidebar"):
                yield Label("Convert Media", classes="title")
                yield Static("", id="convert-config-summary", classes="config-summary")
            with VerticalScroll(id="main-content"):
                yield Label("Enter or drop file path:")
                yield Input(placeholder="/path/to/file.webm", id="file-input")
                yield Button(
                    "Start Conversion", id="btn-start-convert", variant="success"
                )
                yield Static("", id="convert-status-line")
                yield Static("", id="convert-output-log")
        yield Footer()

    def update_config_summary(self) -> None:
        summary = self.query_one("#convert-config-summary", Static)
        text = f"Target Codec: {self.config.format.codec}\n"
        if self.config.download.extract_audio:
            text += f"Audio: {self.config.download.audio_format}\n"
        summary.update(text)

    def on_mount(self) -> None:
        self.update_config_summary()
        self.query_one("#file-input", Input).focus()

    def on_paste(self, event: events.Paste) -> None:
        """Handle files being dropped (pasted) onto the terminal."""
        if event.text:
            # Set the pasted text (often a file path) as the input value
            self.query_one("#file-input", Input).value = event.text.strip().strip("'\"")

    def action_go_back(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._proc.wait()
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-start-convert")
    def on_start_convert(self) -> None:
        if self._proc and self._proc.poll() is None:
            return

        file_path_str = self.query_one("#file-input", Input).value.strip()
        # Remove quotes if dragged and dropped in some terminals
        file_path_str = file_path_str.strip("'\"")

        # Unescape backslashes (common in some terminals when dropping
        # files with spaces)
        if "\\" in file_path_str:
            try:
                # Use shlex to handle shell-style escapes (common on Mac)
                parts = shlex.split(file_path_str)
                if parts:
                    file_path_str = parts[0]
            except Exception:
                # Fallback to simple replacement if shlex fails
                file_path_str = file_path_str.replace("\\ ", " ")

        if not file_path_str:
            return

        status = self.query_one("#convert-status-line", Static)
        log = self.query_one("#convert-output-log", Static)
        status.update("Starting conversion...")
        log.update("")

        downloaded_file = Path(file_path_str)
        self.app.notify_desktop(
            "Conversion Started", f"Processing: {downloaded_file.name}"
        )

        if not downloaded_file.exists():
            status.update("File does not exist.")
            return

        compatible_file = downloaded_file.with_suffix(".mp4")
        if downloaded_file.suffix == ".mp4":
            compatible_file = downloaded_file.with_stem(
                downloaded_file.stem + "-converted"
            ).with_suffix(".mp4")

        codec_map = {
            "h264": "libx264",
            "h265": "libx265",
            "vp9": "libvpx-vp9",
        }
        vcodec = codec_map.get(self.config.format.codec, "libx264")

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(downloaded_file),
            "-c:v",
            vcodec,
        ]

        if vcodec == "libx264":
            ffmpeg_cmd.extend(["-preset", "slow", "-crf", "22"])

        ffmpeg_cmd.extend(["-c:a", "aac", str(compatible_file)])

        app = self.app

        def _stream() -> None:
            try:
                proc = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self._proc = proc

                lines: list[str] = []
                assert proc.stdout is not None
                for raw_line in proc.stdout:
                    line = raw_line.rstrip()
                    if not line:
                        continue

                    lines.append(line)
                    tail = "\n".join(lines[-20:])
                    app.call_from_thread(log.update, tail)

                proc.wait()
                if proc.returncode == 0:
                    app.call_from_thread(
                        status.update, f"Done! Saved as {compatible_file.name}"
                    )
                    app.notify_desktop(
                        "Conversion Finished",
                        f"Successfully converted to {compatible_file.name}",
                    )
                else:
                    app.call_from_thread(
                        status.update, f"Failed (exit {proc.returncode})"
                    )
                    app.notify_desktop(
                        "Conversion Failed",
                        f"Error code {proc.returncode} for: {downloaded_file.name}",
                    )
            except Exception as e:
                app.call_from_thread(status.update, "Failed!")
                app.call_from_thread(log.update, str(e))
                app.notify_desktop("Conversion Error", f"Unexpected error: {str(e)}")

        t = threading.Thread(target=_stream, daemon=True)
        t.start()


# ---------------------------------------------------------------------------
# Config screen
# ---------------------------------------------------------------------------


class ConfigScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
    ]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="config-scroll"):
            yield Label("Cookie Settings", classes="section-title")
            with RadioSet(id="cookie-mode"):
                yield RadioButton("No Cookies", id=_radio_id("cookie", "none"))
                yield RadioButton("From Browser", id=_radio_id("cookie", "browser"))
                yield RadioButton("From File", id=_radio_id("cookie", "file"))

            yield Label("Browser:")
            with RadioSet(id="browser-select"):
                for b in BROWSERS:
                    yield RadioButton(b.capitalize(), id=_radio_id("browser", b))

            yield Label("Cookie file path:")
            yield Input(placeholder="/path/to/cookies.txt", id="cookie-file-path")

            yield Label("Format Settings", classes="section-title")
            yield Label("Quality:")
            with RadioSet(id="quality-select"):
                for q in QUALITIES:
                    yield RadioButton(q, id=_radio_id("quality", q))

            yield Label("Container:")
            with RadioSet(id="container-select"):
                for c in CONTAINERS:
                    yield RadioButton(c, id=_radio_id("container", c))

            yield Label("Post-Download Codec Conversion (to MP4):")
            with RadioSet(id="codec-select"):
                for codec in CODECS:
                    yield RadioButton(codec, id=_radio_id("codec", codec))

            yield Label("Download Settings", classes="section-title")
            yield Label("Output directory:")
            yield Input(id="output-dir")
            yield Label("Filename template:")
            yield Input(id="output-template")

            with Horizontal(classes="switch-row"):
                yield Label("Embed Thumbnail:")
                yield Switch(id="embed-thumb")
            with Horizontal(classes="switch-row"):
                yield Label("Embed Metadata:")
                yield Switch(id="embed-meta")
            with Horizontal(classes="switch-row"):
                yield Label("Embed Subtitles:")
                yield Switch(id="embed-subs")
            with Horizontal(classes="switch-row"):
                yield Label("Include Auto-generated Subtitles:")
                yield Switch(id="write-auto-subs")

            with Horizontal(classes="switch-row"):
                yield Label("SponsorBlock (remove segments):")
                yield Switch(id="sponsorblock-remove")

            yield Label("Subtitle Languages (e.g., en,es or en.*):")
            yield Input(id="sub-langs")

            with Horizontal(classes="switch-row"):
                yield Label("Extract Audio Only:")
                yield Switch(id="extract-audio")
            with Horizontal(classes="switch-row"):
                yield Label("Desktop Notifications:")
                yield Switch(id="desktop-notifications")
            with Horizontal(classes="switch-row"):
                yield Label("Use aria2c (external downloader):")
                yield Switch(id="use-aria2c")

            yield Label("Aria2 Connections:")
            with RadioSet(id="aria2-conn-select"):
                for conn in ARIA2_CONNECTIONS:
                    yield RadioButton(conn, id=_radio_id("aria2conn", conn))

            yield Label("Audio Format:")
            with RadioSet(id="audio-format"):
                for af in AUDIO_FORMATS:
                    yield RadioButton(af.upper(), id=_radio_id("audio", af))

            yield Button("Save Config", id="btn-save", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        _select_key(
            self.query_one("#cookie-mode", RadioSet), "cookie", self.config.cookie.mode
        )
        _select_key(
            self.query_one("#browser-select", RadioSet),
            "browser",
            self.config.cookie.browser,
        )
        self.query_one("#cookie-file-path", Input).value = self.config.cookie.file_path
        _select_key(
            self.query_one("#quality-select", RadioSet),
            "quality",
            self.config.format.quality,
        )
        _select_key(
            self.query_one("#container-select", RadioSet),
            "container",
            self.config.format.container,
        )
        _select_key(
            self.query_one("#codec-select", RadioSet),
            "codec",
            self.config.format.codec,
        )
        self.query_one("#output-dir", Input).value = self.config.download.output_dir
        self.query_one(
            "#output-template", Input
        ).value = self.config.download.output_template
        self.query_one(
            "#embed-thumb", Switch
        ).value = self.config.download.embed_thumbnail
        self.query_one(
            "#embed-meta", Switch
        ).value = self.config.download.embed_metadata
        self.query_one("#embed-subs", Switch).value = self.config.download.embed_subs
        self.query_one(
            "#write-auto-subs", Switch
        ).value = self.config.download.write_auto_subs
        self.query_one(
            "#sponsorblock-remove", Switch
        ).value = self.config.download.sponsorblock_remove
        self.query_one("#sub-langs", Input).value = self.config.download.sub_langs
        self.query_one(
            "#extract-audio", Switch
        ).value = self.config.download.extract_audio
        self.query_one(
            "#desktop-notifications", Switch
        ).value = self.config.download.desktop_notifications
        self.query_one("#use-aria2c", Switch).value = self.config.download.use_aria2c
        _select_key(
            self.query_one("#aria2-conn-select", RadioSet),
            "aria2conn",
            str(self.config.download.aria2_connections),
        )
        _select_key(
            self.query_one("#audio-format", RadioSet),
            "audio",
            self.config.download.audio_format,
        )

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-save")
    def on_save(self) -> None:
        self.config.cookie.mode = (
            _selected_key(self.query_one("#cookie-mode", RadioSet), "cookie") or "none"
        )
        self.config.cookie.browser = (
            _selected_key(self.query_one("#browser-select", RadioSet), "browser")
            or "firefox"
        )
        self.config.cookie.file_path = self.query_one("#cookie-file-path", Input).value
        self.config.format.quality = (
            _selected_key(self.query_one("#quality-select", RadioSet), "quality")
            or "best"
        )
        self.config.format.container = (
            _selected_key(self.query_one("#container-select", RadioSet), "container")
            or "best"
        )
        self.config.format.codec = (
            _selected_key(self.query_one("#codec-select", RadioSet), "codec") or "h264"
        )
        self.config.download.output_dir = self.query_one("#output-dir", Input).value
        self.config.download.output_template = self.query_one(
            "#output-template", Input
        ).value
        self.config.download.embed_thumbnail = self.query_one(
            "#embed-thumb", Switch
        ).value
        self.config.download.embed_metadata = self.query_one(
            "#embed-meta", Switch
        ).value
        self.config.download.embed_subs = self.query_one("#embed-subs", Switch).value
        self.config.download.write_auto_subs = self.query_one(
            "#write-auto-subs", Switch
        ).value
        self.config.download.sponsorblock_remove = self.query_one(
            "#sponsorblock-remove", Switch
        ).value
        self.config.download.sub_langs = self.query_one("#sub-langs", Input).value
        self.config.download.extract_audio = self.query_one(
            "#extract-audio", Switch
        ).value
        self.config.download.desktop_notifications = self.query_one(
            "#desktop-notifications", Switch
        ).value
        self.config.download.use_aria2c = self.query_one("#use-aria2c", Switch).value
        self.config.download.aria2_connections = int(
            _selected_key(self.query_one("#aria2-conn-select", RadioSet), "aria2conn")
            or "8"
        )
        self.config.download.audio_format = (
            _selected_key(self.query_one("#audio-format", RadioSet), "audio") or "mp3"
        )

        self.config.save()
        self.app.pop_screen()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


class YtDlpTUI(App):
    CSS = """
    Screen { layout: horizontal; }
    #sidebar { width: 25; border: solid $primary; padding: 1; }
    #main-content { padding: 1; }
    #url-row { height: 3; margin-bottom: 1; }
    #url-input { width: 1fr; }
    #btn-fetch { width: 15; margin-left: 1; }
    #preview-area {
        height: auto;
        max-height: 12;
        border: double $accent;
        padding: 1;
        margin-bottom: 1;
        background: $surface;
    }
    #preview-details { height: auto; }
    #config-scroll { padding: 1; }
    .title { text-style: bold; margin-bottom: 1; }
    .section-title { text-style: bold; margin-bottom: 1; color: $accent; }
    .config-summary { margin-top: 2; border: solid $secondary; padding: 1; }
    .hidden { display: none; }
    .switch-row { height: 3; }
    RadioSet { margin-bottom: 1; }
    Input { margin-bottom: 1; }
    #status-line { margin-top: 1; }
    #output-log { margin-top: 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.config = Config.load()

    def notify_desktop(self, title: str, message: str) -> None:
        """Send a desktop notification if enabled in config."""
        if self.config.download.desktop_notifications:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    app_name="yt-dlp-tui",
                )
            except Exception:
                pass  # Ignore notification failures

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self.config))


def run() -> None:
    app = YtDlpTUI()
    app.run()


if __name__ == "__main__":
    run()
