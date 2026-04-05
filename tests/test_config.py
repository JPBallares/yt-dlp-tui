import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "yt-dlp-tui" / "src"))

from yt_dlp_tui.config import Config, DownloadTask, DownloadSettings

def test_build_cli_args_basic():
    config = Config()
    args = config.build_cli_args("https://example.com/video")
    assert "https://example.com/video" in args
    assert "-f" in args
    print("test_build_cli_args_basic passed")

def test_build_cli_args_with_sections():
    config = Config()
    task = DownloadTask(url="https://example.com/video", download_sections="*00:01:00-00:02:00")
    args = config.build_cli_args(task.url, task=task)
    assert "--download-sections" in args
    idx = args.index("--download-sections")
    assert args[idx+1] == "*00:01:00-00:02:00"
    print("test_build_cli_args_with_sections passed")

def test_build_cli_args_with_split_chapters():
    config = Config()
    task = DownloadTask(url="https://example.com/video", split_chapters=True)
    args = config.build_cli_args(task.url, task=task)
    assert "--split-chapters" in args
    print("test_build_cli_args_with_split_chapters passed")

def test_build_cli_args_global_config():
    config = Config()
    config.download.split_chapters = True
    args = config.build_cli_args("https://example.com/video")
    assert "--split-chapters" in args
    
    # Task override
    task = DownloadTask(url="https://example.com/video", split_chapters=False)
    args = config.build_cli_args(task.url, task=task)
    assert "--split-chapters" not in args
    print("test_build_cli_args_global_config passed")

def test_backward_compatibility():
    # Old task data without new fields
    old_data = {
        "url": "https://example.com/video",
        "id": "123",
        "title": "Old Video",
        "status": "finished",
        "progress": "100%",
        "eta": "",
        "speed": "",
        "error_msg": "",
        "timestamp": "2023-01-01T00:00:00"
    }
    task = DownloadTask.from_dict(old_data)
    assert task.download_sections == ""
    assert task.split_chapters == False
    print("test_backward_compatibility passed")

if __name__ == "__main__":
    try:
        test_build_cli_args_basic()
        test_build_cli_args_with_sections()
        test_build_cli_args_with_split_chapters()
        test_build_cli_args_global_config()
        test_backward_compatibility()
        print("All tests passed!")
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
