# Changelog

All notable changes to SafeTool Pix will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-beta] - 2026-03-23

### Fixed
- **Build**: Explained properly how to install in Windows and macOS. 


## [0.9.8-beta] - 2026-03-09

### Fixed
- **Build**: Fixed an issue in the visualization of images under windows. 


## [0.9.7-beta] - 2026-03-09

### Fixed
- **Build**: Fixed an issue in the creation of distribution binaries that would make certain functionalities not work properly. Adjusted packaging scripts and PyInstaller spec handling to ensure proper binary creation across build environments.


## [0.9.4-beta] - 2026-03-05

### Fixed
- **AppImage**: "Open logs" and "Change logs folder" buttons now work correctly. Fixed by cleaning AppImage-injected environment variables (`LD_LIBRARY_PATH`, etc.) before spawning host OS utilities (`xdg-open`, `nautilus`).
- **RPM (Fedora/openSUSE)**: Fixed crash on transition to Stage 3 caused by `libscipy_openblas64_` ELF page-alignment error. Removed unused top-level `import numpy` from `video_thumbnail.py` that eagerly loaded numpy/scipy at Stage 3 import time.
- **Internationalization**: Qt standard widget labels (Yes/No, Cancel, Open buttons in QMessageBox and QFileDialog) now display in the correct language. Added `QTranslator` loading for `qtbase_*.qm` translations.
- **File Organizer**: Cache is now updated for ALL file types (including unsupported/OTHER) after move operations, preventing potential stale cache entries on subsequent runs.

## [0.9-beta] - 2026-02-23

### Added
- **8 analysis tools** organized in 3 categories:
  - **Cleanup & Space**: Zero-byte files, Live Photos, HEIC/JPG duplicates, Exact copies (SHA256)
  - **Visual Detection**: Visually identical copies (perceptual hash), Similar files (70-95% similarity slider)
  - **Organization**: Smart file organizer (date-based structure), Complete file renamer (YYYYMMDD_HHMMSS)
- **Multi-phase scanner** with 6 incremental stages (file classification, filesystem metadata, SHA256 hashing, image EXIF, video EXIF, best date calculation)
- **FileMetadata singleton cache** with LRU eviction, thread-safe access, and optional disk persistence
- **3-stage UI workflow**: Folder selection → Analysis progress → Tools grid
- **Internationalization**: Full Spanish and English support (898+ translation keys each) with runtime language switching
- **Cross-platform support**: Linux, Windows, macOS with platform-specific file operations
- **Privacy-first architecture**: 100% local processing, no cloud, no telemetry, no external connections
- **Backup-first policy**: All destructive operations offer backup creation and dry-run simulation
- **Settings system**: Configurable analysis options, log levels, language, worker threads
- **Adaptive performance**: Dynamic worker allocation based on CPU cores and available RAM
- **Perceptual hash engine**: phash/dhash/ahash algorithms with configurable hash size and real-time re-clustering
- **Professional logging**: Dual-log system (main + warnings-only), grep-friendly FILE_DELETED tracking

### Technical
- PyQt6 desktop application with strict UI/logic separation
- 713+ passing tests (unit, integration, performance)
- Python 3.12+ with comprehensive type hints
- Automated release pipeline with GitHub Actions (Linux .deb/.rpm, Windows installer, macOS .dmg)

[Unreleased]: https://github.com/safetoolhub/safetool-pix/compare/v0.9.4-beta...HEAD
[0.9.4-beta]: https://github.com/safetoolhub/safetool-pix/compare/v0.9-beta...v0.9.4-beta
[0.9-beta]: https://github.com/safetoolhub/safetool-pix/releases/tag/v0.9-beta
