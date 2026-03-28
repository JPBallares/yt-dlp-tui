from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import (
    Button,
    Header,
    Footer,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
    Switch,
)
from textual import on
from textual.screen import Screen

import subprocess
import threading
from pathlib import Path

from .config import Config, BROWSERS, QUALITIES, CONTAINERS, CODECS, AUDIO_FORMATS


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
                yield Button("Config", id="btn-config")
                yield Static("", id="config-summary", classes="config-summary")
            with VerticalScroll(id="main-content"):
                yield Label("Enter URL:")
                yield Input(
                    placeholder="https://youtube.com/watch?v=...", id="url-input"
                )
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
        text += f"Dir: {self.config.download.output_dir}"
        summary.update(text)

    def on_mount(self) -> None:
        self.update_config_summary()

    def on_screen_resume(self) -> None:
        self.update_config_summary()

    def action_show_config(self) -> None:
        self.app.push_screen(ConfigScreen(self.config))

    @on(Button.Pressed, "#btn-config")
    def on_config_pressed(self) -> None:
        self.action_show_config()

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
                actual_filename: str | None = None
                assert proc.stdout is not None
                for raw_line in proc.stdout:
                    line = raw_line.rstrip()
                    if not line:
                        continue

                    # Capture filename if possible
                    if "[download] Destination: " in line:
                        actual_filename = line.split("[download] Destination: ")[1]
                    elif "[download] " in line and " has already been downloaded" in line:
                        actual_filename = line.split("[download] ")[1].split(" has already been downloaded")[0]
                    elif "[Merger] Merging formats into \"" in line:
                        # Extract between quotes
                        actual_filename = line.split("[Merger] Merging formats into \"")[1].split("\"")[0]
                    elif "[VideoConvertor] Converting video from " in line and " to " in line:
                        # Sometimes yt-dlp converts after download
                        actual_filename = line.split(" to ")[1].strip()

                    # Show latest line as status
                    app.call_from_thread(status.update, line)

                    # Collect all lines for the log area (last 20)
                    lines.append(line)
                    tail = "\n".join(lines[-20:])
                    app.call_from_thread(log.update, tail)

                proc.wait()
                if proc.returncode == 0:
                    app.call_from_thread(status.update, "Done!")

                    if self.config.format.codec == "none":
                        app.call_from_thread(status.update, "Done! (No conversion requested)")
                        return

                    if not actual_filename:
                        app.call_from_thread(status.update, "Could not determine filename for conversion")
                        return

                    downloaded_file = Path(actual_filename)
                    if not downloaded_file.exists():
                        # Sometimes it might be a relative path based on CWD or output_dir
                        downloaded_file = Path(self.config.download.output_dir) / actual_filename

                    if not downloaded_file.exists():
                        app.call_from_thread(status.update, f"File not found: {actual_filename}")
                        return

                    compatible_file = downloaded_file.with_suffix(".mp4")
                    # If already MP4, use a different name to avoid overwriting input while reading
                    if downloaded_file.suffix == ".mp4":
                        compatible_file = downloaded_file.with_stem(downloaded_file.stem + "-compatible").with_suffix(".mp4")

                    codec_map = {
                        "h264": "libx264",
                        "h265": "libx265",
                        "vp9": "libvpx-vp9",
                    }
                    vcodec = codec_map.get(self.config.format.codec, "libx264")

                    try:
                        ffmpeg_cmd = [
                            "ffmpeg",
                            "-y", # Overwrite output if it exists
                            "-i",
                            str(downloaded_file),
                            "-c:v",
                            vcodec,
                        ]

                        if vcodec == "libx264":
                            ffmpeg_cmd.extend(["-preset", "slow", "-crf", "22"])

                        ffmpeg_cmd.extend(["-c:a", "aac", str(compatible_file)])

                        app.call_from_thread(status.update, f"Converting to {vcodec}...")
                        ffmpeg_proc = subprocess.Popen(
                            ffmpeg_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            bufsize=1,
                        )
                        self._proc = ffmpeg_proc

                        assert ffmpeg_proc.stdout is not None
                        for raw_line in ffmpeg_proc.stdout:
                            line = raw_line.rstrip()
                            if not line:
                                continue
                            app.call_from_thread(status.update, "Converting...")
                            lines.append(line)
                            tail = "\n".join(lines[-20:])
                            app.call_from_thread(log.update, tail)

                        ffmpeg_proc.wait()
                        if ffmpeg_proc.returncode == 0:
                            app.call_from_thread(
                                status.update, f"Converted to compatible MP4 ({self.config.format.codec})"
                            )
                        else:
                            app.call_from_thread(status.update, f"FFmpeg conversion failed (exit {ffmpeg_proc.returncode})!")
                    except Exception as e:
                        app.call_from_thread(status.update, "FFmpeg conversion exception!")
                        app.call_from_thread(log.update, str(e))
                else:
                    app.call_from_thread(
                        status.update, f"Failed (exit {proc.returncode})"
                    )
            except Exception as e:
                app.call_from_thread(status.update, "Failed!")
                app.call_from_thread(log.update, str(e))

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
                yield Label("Extract Audio Only:")
                yield Switch(id="extract-audio")

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
        self.query_one(
            "#extract-audio", Switch
        ).value = self.config.download.extract_audio
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
            _selected_key(self.query_one("#codec-select", RadioSet), "codec")
            or "h264"
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
        self.config.download.extract_audio = self.query_one(
            "#extract-audio", Switch
        ).value
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
    #sidebar { width: 20; border: solid $primary; padding: 1; }
    #main-content { padding: 1; }
    #config-scroll { padding: 1; }
    .title { text-style: bold; margin-bottom: 1; }
    .section-title { text-style: bold; margin-top: 2; margin-bottom: 1; }
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

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self.config))


def run() -> None:
    app = YtDlpTUI()
    app.run()
