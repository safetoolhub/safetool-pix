# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
SafeTool Pix - Application entry point

Multimedia file management application with tools for organizing and cleaning duplicates
"""
import sys
import os
import traceback
from pathlib import Path

# Configure Qt to avoid Wayland warnings
os.environ['QT_LOGGING_RULES'] = 'qt.qpa.wayland=false'

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QPalette, QColor
from PyQt6.QtCore import QTranslator, QLocale, QLibraryInfo
from ui.screens.main_window import MainWindow
from ui.styles.design_system import DesignSystem
from config import Config
from utils.logger import configure_logging, get_logger
from utils import get_optimal_window_config
from utils.settings_manager import settings_manager
from utils.i18n import init_i18n
import logging


def _install_exception_hook():
    """Install a global exception hook to prevent PyQt6 from calling qFatal on unhandled exceptions.

    In PyQt6, unhandled Python exceptions inside signal/slot callbacks trigger
    pyqt6_err_print() which calls qFatal() -> abort() -> SIGABRT core dump.
    This hook logs the exception and prevents the crash.
    """
    def exception_hook(exc_type, exc_value, exc_tb):
        # Always log to the application logger if available
        try:
            logger = get_logger('ExceptionHook')
            logger.critical(
                "Unhandled exception in slot/callback:\n"
                + "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            )
        except Exception:
            pass

        # Also print to stderr (captured by systemd journal on Linux)
        sys.stderr.write("=" * 60 + "\n")
        sys.stderr.write("UNHANDLED EXCEPTION (caught by global hook):\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr)
        sys.stderr.write("=" * 60 + "\n")
        sys.stderr.flush()

    sys.excepthook = exception_hook


def _run_verify_mode():
    """Quick smoke test for build verification. No UI, just check critical imports."""
    errors = []

    # Core imports
    checks = [
        ("imagehash", "import imagehash"),
        ("scipy.fftpack", "import scipy.fftpack"),
        ("pywt", "import pywt"),
        ("numpy", "import numpy"),
        ("PIL.Image", "from PIL import Image"),
        ("PyQt6.QtWidgets", "from PyQt6.QtWidgets import QApplication"),
        ("sqlite3", "import sqlite3"),
    ]

    for name, code in checks:
        try:
            exec(code)
        except ImportError as e:
            errors.append(f"IMPORT_FAIL: {name}: {e}")

    # Functional: perceptual hash must work
    try:
        import imagehash
        from PIL import Image
        img = Image.new('RGB', (64, 64), 'red')
        h = imagehash.phash(img, hash_size=16)
        assert h is not None, "phash returned None"
    except Exception as e:
        errors.append(f"FUNC_FAIL: imagehash.phash: {e}")

    # i18n
    try:
        from utils.i18n import init_i18n, tr
        init_i18n('es')
        val = tr('app.name')
        assert val, "tr() returned empty"
    except Exception as e:
        errors.append(f"FUNC_FAIL: i18n: {e}")

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        print("VERIFY_FAIL")
        sys.exit(1)
    else:
        print("VERIFY_OK")
        sys.exit(0)


def main():
    """Main application entry point"""

    # Quick verification mode for build testing (no UI, just check imports)
    if "--verify" in sys.argv:
        _run_verify_mode()
        return

    # Install global exception hook FIRST to prevent qFatal crashes in PyQt6 slots
    _install_exception_hook()

    # Initialize internationalization before anything else
    language = settings_manager.get_language()
    init_i18n(language)

    if Config.DEVELOPMENT_MODE:
        print(f"DEVELOPMENT MODE ENABLED")
        if Config.SAVED_CACHE_DEV_MODE_PATH:
             print(f"Loading cache from: {Config.SAVED_CACHE_DEV_MODE_PATH}")

    # Read log level from persistent settings
    saved_log_level = settings_manager.get_log_level("INFO")  # INFO by default
    saved_dual_log = settings_manager.get_dual_log_enabled()  # True by default
    saved_disable_file_logging = settings_manager.get_disable_file_logging()  # False by default
    
    # Configure logging system with saved level
    log_file, logs_dir = configure_logging(
        logs_dir=Config.DEFAULT_LOG_DIR,
        level=saved_log_level,
        dual_log_enabled=saved_dual_log,
        disable_file_logging=saved_disable_file_logging,
    )
    
    # Read precalculation settings for log output
    precalc_hashes = settings_manager.get_precalculate_hashes()
    precalc_image_exif = settings_manager.get_precalculate_image_exif()
    precalc_video_exif = settings_manager.get_precalculate_video_exif()
    
    logger = get_logger()
    log_level = logging.getLevelName(logger.logger.level)
    
    # Get system info
    sys_info = Config.get_system_info()
    
    logger.info("=" * 80)
    logger.info(f"Starting {Config.APP_NAME} v{Config.get_full_version()}")
    logger.info("=" * 80)
    logger.info("")
    logger.info("SYSTEM CONFIGURATION:")
    logger.info(f"  • Total RAM: {sys_info['ram_total_gb']:.2f} GB")
    if sys_info['ram_available_gb']:
        logger.info(f"  • Available RAM: {sys_info['ram_available_gb']:.2f} GB")
    logger.info(f"  • CPU Cores: {sys_info['cpu_count']}")
    logger.info(f"  • I/O Workers (hashing): {sys_info['io_workers']}")
    logger.info(f"  • CPU Workers (images): {sys_info['cpu_workers']}")
    if not sys_info['psutil_available']:
        logger.info("  psutil not available, using default values")
    logger.info("")
    logger.info("MEMORY CONFIGURATION:")
    logger.info(f"  • Max cache entries (initial): {sys_info['max_cache_entries']:,}")
    logger.info(f"  • Large dataset threshold: {sys_info['large_dataset_threshold']:,} files")
    logger.info(f"  • Auto-open dialog threshold: {sys_info['auto_open_threshold']:,} files")
    logger.info("")
    logger.info("LOG CONFIGURATION:")
    if saved_disable_file_logging:
        logger.info(f"  • File logging: DISABLED (only WARNING/ERROR on console)")
    else:
        logger.info(f"  • Log level: {log_level}")
        logger.info(f"  • Log file: {log_file}")
        logger.info(f"  • Log directory: {logs_dir}")
        if saved_dual_log and saved_log_level in ('INFO', 'DEBUG'):
            logger.info(f"  • Dual logging: enabled (additional _WARNERROR file will be created)")
        else:
            logger.info(f"  • Dual logging: {'disabled' if not saved_dual_log else 'not applicable (WARNING/ERROR level)'}")
    logger.info("")
    logger.info("LANGUAGE:")
    logger.info(f"  • UI Language: {language}")
    logger.info("")
    logger.info("INITIAL ANALYSIS CONFIGURATION:")
    logger.info(f"  • SHA256 hash calculation: {'enabled' if precalc_hashes else 'disabled (on demand)'}")
    logger.info(f"  • Image metadata (EXIF): {'enabled' if precalc_image_exif else 'disabled (on demand)'}")
    logger.info(f"  • Video metadata (EXIF): {'enabled' if precalc_video_exif else 'disabled (on demand)'}")
    logger.info("=" * 80)
    logger.info("")
    
    app = QApplication(sys.argv)

    # Force light palette to ensure consistent appearance regardless of OS dark mode.
    # Without this, Linux users with dark GTK/KDE themes see dark backgrounds in
    # native dialogs (QFileDialog) and widgets without explicit background colors.
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(DesignSystem.COLOR_BACKGROUND))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(DesignSystem.COLOR_TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(DesignSystem.COLOR_SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(DesignSystem.COLOR_BACKGROUND))
    palette.setColor(QPalette.ColorRole.Text, QColor(DesignSystem.COLOR_TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(DesignSystem.COLOR_BACKGROUND))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(DesignSystem.COLOR_TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(DesignSystem.COLOR_PRIMARY))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2D3436"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#F5F6FA"))
    app.setPalette(palette)

    # Apply tooltip style at QApplication level so ALL tooltips inherit it,
    # even those on widgets with their own local stylesheets.
    app.setStyleSheet(DesignSystem.get_tooltip_style())

    # Load Qt's own translations for standard widgets (QMessageBox Yes/No, QFileDialog, etc.)
    qt_translator = QTranslator()
    # Map our language codes to Qt locale codes
    qt_locale_map = {'es': 'es', 'en': 'en'}
    qt_lang = qt_locale_map.get(language, 'es')
    qt_translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(f"qtbase_{qt_lang}", qt_translations_path):
        app.installTranslator(qt_translator)
        logger.debug(f"Qt translations loaded for '{qt_lang}' from {qt_translations_path}")
    else:
        logger.debug(f"Qt translations not found for '{qt_lang}' at {qt_translations_path}")

    # Configure the application
    app.setApplicationName(Config.APP_NAME)
    app.setApplicationVersion(Config.get_full_version())
    app.setOrganizationName("SafeToolPix")

    # Set application icon (taskbar, window title bar, alt-tab)
    icon_path = Config.APP_ICON_PATH
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        logger.debug(f"Application icon set from {icon_path}")
    else:
        logger.warning(f"Application icon not found at {icon_path}")

    # Windows-specific: set AppUserModelID so Windows shows our icon in taskbar
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                f"SafeToolHub.SafeToolPix.{Config.APP_VERSION}"
            )
        except Exception:
            pass

    # Create and show main window
    window = MainWindow()
    
    # Configure window size using decoupled utility
    action, window_size, center_pos = get_optimal_window_config()
    
    if action == 'resize' and window_size and center_pos:
        # 2K+ monitor: show in FullHD centered
        window.resize(window_size.width, window_size.height)
        window.move(center_pos[0], center_pos[1])
        logger.info(f"Window configured in FullHD ({window_size}) centered on screen")
    else:
        # FullHD or lower monitor: maximize
        window.showMaximized()
        logger.info("Window maximized")
    
    window.show()
    
    logger.debug("Main window shown")

    return app.exec()


import multiprocessing

if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
