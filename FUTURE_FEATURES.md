# Future Features Roadmap

This document tracks potential features and enhancements for the `ytdownloads` project, specifically the `yt-dlp-tui` application.

## 🟢 Low-Hanging Fruit (Easy to Add)

- [x] **Subtitle Support**: Toggles for `--embed-subs`, `--write-auto-subs`, and language selection (e.g., `en,es`).
- [ ] **SponsorBlock Integration**: Built-in support for removing sponsor segments (`--sponsorblock-remove all`).
- [ ] **Custom CLI Arguments**: A text field in Config for advanced users to add arbitrary `yt-dlp` flags.
- [ ] **Rate Limiting**: Option to limit download speed (`--limit-rate`) to save bandwidth.
- [ ] **Playlist Controls**: Toggles for `--yes-playlist` / `--no-playlist` and range selection (e.g., items 1-10).

## 🟡 Medium Complexity

- [ ] **Download Queue & History**: A dedicated screen to manage multiple pending and completed downloads.
- [ ] **Search Functionality**: Support for `ytsearch:` to find and select videos directly within the TUI.
- [x] **External Downloader Support**: Integration with `aria2c` for multi-connection speed boosts.
- [ ] **Authentication Support**: Input fields for `--username`, `--password`, and `--twofactor`.
- [ ] **Proxy Support**: Configuration for `--proxy URL` to bypass geo-restrictions.

## 🔴 High Complexity / Polished Experience

- [x] **Metadata Preview**: Fetch and display title, uploader, and duration *before* starting the download.
- [ ] **Parallel Downloads**: Ability to download multiple items from the queue simultaneously.
- [x] **Desktop Notifications**: System-level alerts when long downloads or conversions finish.
- [ ] **TUI Theming**: Custom color schemes and light/dark mode support using Textual features.
- [ ] **Auto-Update**: A mechanism to check for and apply updates to `yt-dlp` itself.
