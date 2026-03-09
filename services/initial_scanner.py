# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Initial Scanner Service.
Handles the initial multi-phase scan of a directory to populate FileInfoRepositoryCache.

This scanner operates in 6 distinct phases:
1. FILE_CLASSIFICATION: Scan directory and classify files by type (very fast)
2. FILESYSTEM_METADATA: Read filesystem metadata for supported files (fast)
3. HASH: SHA256 hash calculation (requires FILESYSTEM_METADATA first)
4. EXIF_IMAGES: Image metadata extraction (requires FILESYSTEM_METADATA first)
5. EXIF_VIDEOS: Video metadata extraction (requires FILESYSTEM_METADATA first)
6. BEST_DATE: Calculate best available date for each file (requires EXIF)
"""
from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass
import logging

from config import Config
from utils.logger import get_logger
from utils.file_utils import validate_directory_exists, is_image_file, is_video_file
from utils.platform_utils import are_video_tools_available
from utils.i18n import tr
from services.file_metadata_repository_cache import FileInfoRepositoryCache, PopulationStrategy
from services.result_types import DirectoryScanResult


@dataclass
class PhaseProgress:
    """Progress information for a single phase."""
    phase_id: str
    phase_name: str
    current: int
    total: int
    message: str


class InitialScanner:
    """
    Handles multi-phase scanning of a directory to populate FileInfoRepositoryCache.
    
    The scan is performed in 6 distinct phases:
    1. FILE_CLASSIFICATION: Scan directory and classify files by type (very fast)
    2. FILESYSTEM_METADATA: Read filesystem metadata for supported files (fast)
    3. HASH: SHA256 hash calculation for duplicate detection (requires FILESYSTEM_METADATA)
    4. EXIF_IMAGES: Image metadata extraction (moderate cost, requires FILESYSTEM_METADATA)
    5. EXIF_VIDEOS: Video metadata extraction (expensive, requires FILESYSTEM_METADATA)
    6. BEST_DATE: Calculate best available date for each file (requires EXIF)
    """
    
    # Phase identifiers
    PHASE_FILE_CLASSIFICATION = "phase_file_classification"
    PHASE_FILESYSTEM_METADATA = "phase_filesystem_metadata"
    PHASE_HASH = "phase_hash"
    PHASE_EXIF_IMAGES = "phase_exif_images"
    PHASE_EXIF_VIDEOS = "phase_exif_videos"
    PHASE_BEST_DATE = "phase_best_date"
    
    def __init__(self):
        self.logger = get_logger('InitialScanner')
        self._should_stop = False
    
    def request_stop(self):
        """Request the scanner to stop processing."""
        self._should_stop = True
        self.logger.info("Stop requested for InitialScanner")
    
    def scan(
        self,
        directory: Path,
        phase_callback: Optional[Callable[[str, str], None]] = None,
        phase_completed_callback: Optional[Callable[[str], None]] = None,
        phase_skipped_callback: Optional[Callable[[str, str], None]] = None,
        progress_callback: Optional[Callable[[PhaseProgress], bool]] = None,
        calculate_hashes: bool = True,
        extract_image_exif: bool = True,
        extract_video_exif: bool = True
    ) -> DirectoryScanResult:
        """
        Performs multi-phase scan of a directory.
        
        Args:
            directory: Directory to scan
            phase_callback: Called when a phase starts: (phase_id, phase_message)
            phase_completed_callback: Called when a phase completes: (phase_id)
            phase_skipped_callback: Called when a phase is skipped: (phase_id, reason)
            progress_callback: Called with PhaseProgress for each file processed.
                             Returns False to cancel.
            calculate_hashes: Whether to calculate SHA256 hashes (Phase 2)
            extract_image_exif: Whether to extract image EXIF metadata (Phase 3)
            extract_video_exif: Whether to extract video EXIF metadata (Phase 4)
        
        Returns:
            DirectoryScanResult with classified files and statistics
        """
        # Validation
        validate_directory_exists(directory)
        self.logger.info(f"Starting initial scan: {directory}")
        self.logger.info(f"Scan configuration: calculate_hashes={calculate_hashes}, "
                        f"extract_image_exif={extract_image_exif}, extract_video_exif={extract_video_exif}")
        
        # Get repository instance
        repo = FileInfoRepositoryCache.get_instance()
        
        # ==================== PHASE 1: FILE CLASSIFICATION ====================
        phase_id = self.PHASE_FILE_CLASSIFICATION
        phase_msg = tr("services.phase.file_classification")
        
        if phase_callback:
            phase_callback(phase_id, phase_msg)
        
        self.logger.info(f"Phase 1: {phase_msg}")
        
        # Get all files
        all_files = self._get_file_list(directory)
        total_files = len(all_files)
        
        if total_files == 0:
            self.logger.warning("No files found in directory")
            return self._create_empty_result()
        
        self.logger.info(f"Found {total_files:,} files")
        
        # Emit initial progress (0/total) so UI knows the total before classification starts
        if progress_callback:
            phase_progress = PhaseProgress(
                phase_id=phase_id,
                phase_name=phase_msg,
                current=0,
                total=total_files,
                message=phase_msg
            )
            progress_callback(phase_progress)
        
        # Classify files
        images, videos, others = [], [], []
        image_extensions = {}
        video_extensions = {}
        unsupported_extensions = {}
        
        for idx, f in enumerate(all_files, 1):
            if self._should_stop:
                self.logger.warning("Scan cancelled during phase 1 (FILE_CLASSIFICATION)")
                break
            
            # Classify by type
            ext = f.suffix.lower() if f.suffix else '(no extension)'
            
            if is_image_file(f.name):
                images.append(f)
                image_extensions[ext] = image_extensions.get(ext, 0) + 1
            elif is_video_file(f.name):
                videos.append(f)
                video_extensions[ext] = video_extensions.get(ext, 0) + 1
            else:
                others.append(f)
                unsupported_extensions[ext] = unsupported_extensions.get(ext, 0) + 1
            
            # Report progress
            if progress_callback and idx % Config.UI_UPDATE_INTERVAL == 0:
                phase_progress = PhaseProgress(
                    phase_id=phase_id,
                    phase_name=phase_msg,
                    current=idx,
                    total=total_files,
                    message=phase_msg
                )
                if not progress_callback(phase_progress):
                    self.logger.warning("Scan cancelled by user")
                    self._should_stop = True
                    break
        
        # Final progress for phase 1
        if progress_callback and not self._should_stop:
            phase_progress = PhaseProgress(
                phase_id=phase_id,
                phase_name=phase_msg,
                current=total_files,
                total=total_files,
                message=phase_msg
            )
            progress_callback(phase_progress)
        
        supported_files = images + videos
        self.logger.info(
            f"Phase 1 complete: {len(images):,} images, "
            f"{len(videos):,} videos, {len(others):,} other files"
        )
        
        # Notify phase 1 completion
        if phase_completed_callback and not self._should_stop:
            phase_completed_callback(self.PHASE_FILE_CLASSIFICATION)
        
        if self._should_stop:
            self.logger.info(f"Scan cancelled after phase 1 (FILE_CLASSIFICATION) - Files classified: {total_files}")
            return self._create_result_from_data(
                total_files, images, videos, others,
                image_extensions, video_extensions, unsupported_extensions
            )
        
        # ==================== PHASE 2: FILESYSTEM METADATA ====================
        phase_id = self.PHASE_FILESYSTEM_METADATA
        phase_msg = tr("services.phase.filesystem_metadata")
        
        if phase_callback:
            phase_callback(phase_id, phase_msg)
        
        self.logger.info(f"Phase 2: {phase_msg}")
        
        # Update repository size
        repo.update_max_entries(len(supported_files))
        
        # Define progress callback for filesystem metadata population
        def filesystem_metadata_progress(current: int, total: int) -> bool:
            if self._should_stop:
                return False
            
            if progress_callback:
                phase_progress = PhaseProgress(
                    phase_id=phase_id,
                    phase_name=phase_msg,
                    current=current,
                    total=total,
                    message=phase_msg
                )
                return progress_callback(phase_progress)
            return True
        
        # Populate with FILESYSTEM_METADATA (filesystem only)
        repo.populate_from_scan(
            files=supported_files,
            strategy=PopulationStrategy.FILESYSTEM_METADATA,
            progress_callback=filesystem_metadata_progress,
            stop_check_callback=lambda: self._should_stop
        )
        
        if self._should_stop:
            self.logger.info("Phase 2 (FILESYSTEM_METADATA) cancelled by user")
        else:
            self.logger.info("Phase 2 (FILESYSTEM_METADATA) complete: Metadata collected")
        
        # Notify phase 2 completion
        if phase_completed_callback and not self._should_stop:
            phase_completed_callback(self.PHASE_FILESYSTEM_METADATA)
        
        # Log repository stats after Phase 2 (DEBUG)
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("=== Repository Stats after Phase 2 (FILESYSTEM_METADATA) ===")
            repo.log_cache_statistics(level=logging.DEBUG)  # DEBUG
        
        # ==================== PHASE 3: HASH CALCULATION ====================
        if calculate_hashes and supported_files and not self._should_stop:
            phase_id = self.PHASE_HASH
            phase_msg = tr("services.phase.hash")
            
            if phase_callback:
                phase_callback(phase_id, phase_msg)
            
            self.logger.info(f"Phase 3: {phase_msg}")
            
            # Track percentage for logging
            last_logged_percentage = 0
            
            def hash_progress(current: int, total: int) -> bool:
                nonlocal last_logged_percentage
                if self._should_stop:
                    return False
                
                # Log progress every 10% at INFO level
                current_percentage = (current * 100) // total
                if current_percentage >= last_logged_percentage + 10 and current_percentage < 100:
                    self.logger.info(f"Phase 3 (HASH) progress: {current_percentage}% ({current:,}/{total:,} files)")
                    last_logged_percentage = current_percentage
                
                if progress_callback:
                    phase_progress = PhaseProgress(
                        phase_id=phase_id,
                        phase_name=phase_msg,
                        current=current,
                        total=total,
                        message=phase_msg
                    )
                    return progress_callback(phase_progress)
                return True
            
            repo.populate_from_scan(
                files=supported_files,
                strategy=PopulationStrategy.HASH,
                progress_callback=hash_progress,
                stop_check_callback=lambda: self._should_stop
            )
            
            if self._should_stop:
                self.logger.info("Phase 3 (HASH) cancelled by user")
            else:
                self.logger.info("Phase 3 (HASH) complete: Hashes calculated")
            
            # Notify phase 3 completion
            if phase_completed_callback and not self._should_stop:
                phase_completed_callback(self.PHASE_HASH)
            
            # Log repository stats after Phase 3 (DEBUG)
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("=== Repository Stats after Phase 3 (HASH) ===")
                repo.log_cache_statistics(level=logging.DEBUG)  # DEBUG
        
        # ==================== PHASE 4: IMAGE EXIF ====================
        if extract_image_exif and images and not self._should_stop:
            phase_id = self.PHASE_EXIF_IMAGES
            phase_msg = tr("services.phase.exif_images")
            
            if phase_callback:
                phase_callback(phase_id, phase_msg)
            
            self.logger.info(f"Phase 4: {phase_msg}")
            
            # Track percentage for logging
            last_logged_percentage = 0
            
            def image_exif_progress(current: int, total: int) -> bool:
                nonlocal last_logged_percentage
                if self._should_stop:
                    return False
                
                # Log progress every 10% at INFO level
                current_percentage = (current * 100) // total
                if current_percentage >= last_logged_percentage + 10 and current_percentage < 100:
                    self.logger.info(f"Phase 4 (EXIF_IMAGES) progress: {current_percentage}% ({current:,}/{total:,} images)")
                    last_logged_percentage = current_percentage
                
                if progress_callback:
                    phase_progress = PhaseProgress(
                        phase_id=phase_id,
                        phase_name=phase_msg,
                        current=current,
                        total=total,
                        message=phase_msg
                    )
                    return progress_callback(phase_progress)
                return True
            
            repo.populate_from_scan(
                files=images,
                strategy=PopulationStrategy.EXIF_IMAGES,
                progress_callback=image_exif_progress,
                stop_check_callback=lambda: self._should_stop
            )
            
            if self._should_stop:
                self.logger.info("Phase 4 (EXIF_IMAGES) cancelled by user")
            else:
                self.logger.info("Phase 4 (EXIF_IMAGES) complete: Image EXIF extracted")
            
            # Notify phase 4 completion
            if phase_completed_callback and not self._should_stop:
                phase_completed_callback(self.PHASE_EXIF_IMAGES)
            
            # Log repository stats after Phase 4 (DEBUG)
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("=== Repository Stats after Phase 4 (EXIF_IMAGES) ===")
                repo.log_cache_statistics(level=logging.DEBUG)  # DEBUG
        
        # ==================== PHASE 5: VIDEO EXIF ====================
        if extract_video_exif and videos and not self._should_stop:
            phase_id = self.PHASE_EXIF_VIDEOS
            
            # Check if video tools are available (using unified function from platform_utils)
            if not are_video_tools_available():
                self.logger.warning("Phase 5 (EXIF_VIDEOS) SKIPPED: ffprobe/exiftool not installed")
                if phase_skipped_callback:
                    phase_skipped_callback(phase_id, tr("services.phase.video_tools_missing"))
            else:
                phase_msg = tr("services.phase.exif_videos")
                
                if phase_callback:
                    phase_callback(phase_id, phase_msg)
                
                self.logger.info(f"Phase 5: {phase_msg}")
                
                # Track percentage for logging
                last_logged_percentage = 0
                
                def video_exif_progress(current: int, total: int) -> bool:
                    nonlocal last_logged_percentage
                    if self._should_stop:
                        return False
                    
                    # Log progress every 10% at INFO level
                    current_percentage = (current * 100) // total
                    if current_percentage >= last_logged_percentage + 10 and current_percentage < 100:
                        self.logger.info(f"Phase 5 (EXIF_VIDEOS) progress: {current_percentage}% ({current:,}/{total:,} videos)")
                        last_logged_percentage = current_percentage
                    
                    if progress_callback:
                        phase_progress = PhaseProgress(
                            phase_id=phase_id,
                            phase_name=phase_msg,
                            current=current,
                            total=total,
                            message=phase_msg
                        )
                        return progress_callback(phase_progress)
                    return True
                
                repo.populate_from_scan(
                    files=videos,
                    strategy=PopulationStrategy.EXIF_VIDEOS,
                    progress_callback=video_exif_progress,
                    stop_check_callback=lambda: self._should_stop
                )
                
                if self._should_stop:
                    self.logger.info("Phase 5 (EXIF_VIDEOS) cancelled by user")
                else:
                    self.logger.info("Phase 5 (EXIF_VIDEOS) complete: Video EXIF extracted")
                
                # Notify phase 5 completion
                if phase_completed_callback and not self._should_stop:
                    phase_completed_callback(self.PHASE_EXIF_VIDEOS)
                
                # Log repository stats after Phase 5 (DEBUG)
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("=== Repository Stats after Phase 5 (EXIF_VIDEOS) ===")
                    repo.log_cache_statistics(level=logging.DEBUG)  # DEBUG
        
        # ==================== PHASE 6: BEST DATE CALCULATION ====================
        if supported_files and not self._should_stop:
            phase_id = self.PHASE_BEST_DATE
            phase_msg = tr("services.phase.best_date")
            
            if phase_callback:
                phase_callback(phase_id, phase_msg)
            
            self.logger.info(f"Phase 6: {phase_msg}")
            
            # Track percentage for logging
            last_logged_percentage = 0
            
            def best_date_progress(current: int, total: int) -> bool:
                nonlocal last_logged_percentage
                if self._should_stop:
                    return False
                
                # Log progress every 10% at INFO level
                current_percentage = (current * 100) // total
                if current_percentage >= last_logged_percentage + 10 and current_percentage < 100:
                    self.logger.info(f"Phase 6 (BEST_DATE) progress: {current_percentage}% ({current:,}/{total:,} files)")
                    last_logged_percentage = current_percentage
                
                if progress_callback:
                    phase_progress = PhaseProgress(
                        phase_id=phase_id,
                        phase_name=phase_msg,
                        current=current,
                        total=total,
                        message=phase_msg
                    )
                    return progress_callback(phase_progress)
                return True
            
            repo.populate_from_scan(
                files=supported_files,
                strategy=PopulationStrategy.BEST_DATE,
                progress_callback=best_date_progress,
                stop_check_callback=lambda: self._should_stop
            )
            
            if self._should_stop:
                self.logger.info("Phase 6 (BEST_DATE) cancelled by user")
            else:
                self.logger.info("Phase 6 (BEST_DATE) complete: Best dates calculated")
            
            # Notify phase 6 completion
            if phase_completed_callback and not self._should_stop:
                phase_completed_callback(self.PHASE_BEST_DATE)
            
            # Log repository stats after Phase 6 (DEBUG)
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("=== Repository Stats after Phase 6 (BEST_DATE) ===")
                repo.log_cache_statistics(level=logging.DEBUG)
        
        # ==================== FINALIZATION ====================
        result = self._create_result_from_data(
            total_files, images, videos, others,
            image_extensions, video_extensions, unsupported_extensions
        )
        
        # Log statistics

        scan_status = "cancelled" if self._should_stop else "completed"
        self.logger.info(
            f"Scan {scan_status}")
        repo.log_cache_statistics(level=logging.DEBUG)

        # Log detailed metadata information (DEBUG level)
        if self.logger.isEnabledFor(10):  # DEBUG = 10
            self.logger.debug("=== FileMetadata Repository Contents ===")
            all_metadata = repo.get_all_files()
            for idx, metadata in enumerate(all_metadata, 1):
                self.logger.debug(f"[{idx}/{len(all_metadata)}] {metadata.get_summary(verbose=True)}")
            self.logger.debug("=== End Repository Contents ===")
        
        return result
    
    def _get_file_list(self, directory: Path) -> List[Path]:
        """
        Get complete list of files in directory.
        
        Args:
            directory: Directory to scan
            
        Returns:
            List of Path objects for all files
        """
        all_files = [
            f for f in directory.rglob("*") 
            if f.is_file()
        ]
        return all_files
    
    def _create_empty_result(self) -> DirectoryScanResult:
        """Create an empty scan result."""
        return DirectoryScanResult(
            total_files=0,
            images=[],
            videos=[],
            others=[],
            total_size=0,
            image_extensions={},
            video_extensions={},
            unsupported_extensions={},
            unsupported_files=[]
        )
    
    def _create_result_from_data(
        self,
        total_files: int,
        images: List[Path],
        videos: List[Path],
        others: List[Path],
        image_extensions: dict,
        video_extensions: dict,
        unsupported_extensions: dict
    ) -> DirectoryScanResult:
        """Create a DirectoryScanResult from collected data."""
        # Calculate total size of all files
        total_size = 0
        all_paths = images + videos + others
        for path in all_paths:
            try:
                if path.exists():
                    total_size += path.stat().st_size
            except (OSError, PermissionError) as e:
                self.logger.warning(f"Could not get size for {path}: {e}")
        
        self.logger.debug(f"Total size calculated: {total_size:,} bytes for {len(all_paths):,} files")
        
        return DirectoryScanResult(
            total_files=total_files,
            images=images,
            videos=videos,
            others=others,
            total_size=total_size,
            image_extensions=image_extensions,
            video_extensions=video_extensions,
            unsupported_extensions=unsupported_extensions,
            unsupported_files=others
        )
