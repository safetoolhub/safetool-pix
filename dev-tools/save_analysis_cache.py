# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
#!/usr/bin/env python3
"""
Save Analysis Cache Tool

Runs a complete analysis (Structure + Hash + Image EXIF) on a directory and saves
the resulting cache repository to disk. This allows for reloading the analysis state
later for testing or development purposes without re-scanning.

Usage:    
    source .venv/bin/activate && python dev-tools/save_analysis_cache.py --folder <PATH_TO_FOLDER_WITH_PHOTOS>
    source .venv/bin/activate && python dev-tools/save_analysis_cache.py --folder /path/to/your/photos
    source .venv/bin/activate && python dev-tools/save_analysis_cache.py --folder /path/to/another/folder
    
The cache file will be saved in the configured DEFAULT_CACHE_SAVED_DIR.
"""

import sys
import argparse
import logging
from pathlib import Path
import time

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from utils.logger import configure_logging, get_logger
from utils.settings_manager import settings_manager
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from services.initial_scanner import InitialScanner, PhaseProgress

def setup_environment():
    """Configure logging and environment"""
    # Configure logging using the same directory as the main app
    log_file, logs_dir = configure_logging(
        logs_dir=Config.DEFAULT_LOG_DIR,
        level="INFO",
        dual_log_enabled=True
    )
    logger = get_logger("SaveAnalysisCache")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Logs directory: {logs_dir}")
    
    # Log Python executable to verify we're using the right one
    logger.info(f"Python executable: {sys.executable}")
    logger.info(f"Python version: {sys.version}")
    
    return logger

def run_analysis_and_save(folder_path, logger):
    """Run full analysis and save cache to disk"""
    folder = Path(folder_path).resolve()
    
    if not folder.exists():
        logger.error(f"Folder not found: {folder}")
        return False
    
    logger.info(f"Starting analysis for: {folder}")
    
    # Initialize repository
    repo = FileInfoRepositoryCache.get_instance()
    repo.clear()
    
    # Initialize scanner
    scanner = InitialScanner()
    
    # Callbacks for progress
    def phase_callback(phase_id, phase_message):
        logger.info(f"Starting Phase: {phase_id} - {phase_message}")
        
    def phase_completed_callback(phase_id):
        logger.info(f"Completed Phase: {phase_id}")
        
    def progress_callback(progress: PhaseProgress):
        # Log every 500 items or 5% to avoid spam
        if progress.total > 0 and (progress.current % 500 == 0 or progress.current == progress.total):
            percent = (progress.current / progress.total) * 100
            logger.info(f"[{progress.phase_id}] {percent:.1f}% ({progress.current}/{progress.total})")
        return True
    
    # Run scan
    try:
        start_time = time.time()
        
        # Read settings from user configuration (same as main app)
        calculate_hashes = settings_manager.get_precalculate_hashes()
        extract_image_exif = settings_manager.get_precalculate_image_exif()
        extract_video_exif = settings_manager.get_precalculate_video_exif()
        
        logger.info("="*60)
        logger.info(f"CONFIGURATION LOADED FROM SETTINGS:")
        logger.info(f"  - Hashes: {calculate_hashes}")
        logger.info(f"  - Image EXIF: {extract_image_exif}")
        logger.info(f"  - Video EXIF: {extract_video_exif} <-- CHECK THIS")
        logger.info("="*60)
        
        # Configure what to scan (respecting user settings)
        result = scanner.scan(
            directory=folder,
            phase_callback=phase_callback,
            phase_completed_callback=phase_completed_callback,
            progress_callback=progress_callback,
            calculate_hashes=calculate_hashes,
            extract_image_exif=extract_image_exif,
            extract_video_exif=extract_video_exif
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Analysis completed in {elapsed:.2f} seconds")
        logger.info(f"Found: {result.total_files} files ({len(result.images)} images, {len(result.videos)} videos)")
        
        # Define output path
        # Sanitizar nombre de carpeta para el archivo
        safe_name = folder.name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        # Asegurar directorio de destino
        save_dir = Config.DEFAULT_CACHE_SAVED_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = save_dir / f"{safe_name}.json"
        
        # Save cache
        logger.info(f"Saving cache to: {output_file}")
        repo.save_to_disk(output_file)
        
        logger.info("Cache saved successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error during analysis or saving: {e}", exc_info=True)
        return False

def main():
    parser = argparse.ArgumentParser(description="Run analysis and save cache to disk")
    parser.add_argument("--folder", required=True, help="Path to the folder to analyze")
    
    args = parser.parse_args()
    
    logger = setup_environment()
    success = run_analysis_and_save(args.folder, logger)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
