# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Clase base abstracta para todos los servicios de SafeTool Pix.

Proporciona funcionalidad común: logging estandarizado, gestión de backup,
y métodos template para operaciones consistentes.
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Iterable, Callable, Union, Any, TypeAlias
from contextlib import contextmanager
from utils.logger import get_logger
from utils.i18n import tr


# Type alias para callbacks de progreso estandarizados
ProgressCallback: TypeAlias = Callable[[int, int, str], Optional[bool]]
"""
Callback de progreso estandarizado para todas las operaciones.

Firma:
    callback(current: int, total: int, message: str) -> Optional[bool]

Args:
    current: Número de elementos procesados hasta ahora
    total: Total de elementos a procesar
    message: Mensaje descriptivo del progreso actual

Returns:
    - True o None: Continuar con la operación
    - False: Cancelar la operación inmediatamente

Example:
    >>> def my_progress(current: int, total: int, message: str) -> bool:
    ...     print(f"[{current}/{total}] {message}")
    ...     return True  # Continuar
    ...
    >>> service.execute(plan, progress_callback=my_progress)
"""


class BackupCreationError(Exception):
    """
    Excepción lanzada cuando falla la creación de backup.
    
    Esta excepción permite diferenciar entre errores de backup
    y otros tipos de errores en la ejecución de operaciones.
    """
    pass


class BaseService(ABC):
    r"""
    Clase base abstracta para todos los servicios.
    
    Arquitectura de 2 fases:
    1. Fase de Análisis: analyze() -> AnalysisResult
       - Accede a FileInfoRepositoryCache.get_instance() para metadatos
       - No recibe metadata_cache como parámetro (patrón singleton)
       - No realiza I/O intensivo si es posible
       - Retorna un plan de acción
       
    2. Fase de Ejecución: execute(analysis_result) -> ExecutionResult
       - Ejecuta las acciones del plan (delete, move, rename)
       - Maneja backups y dry-run
       - Retorna resultado de la operación
    """
    
    def __init__(self, service_name: str):
        self.logger = get_logger(service_name)
        self.backup_dir: Optional[Path] = None
        self._cancelled = False

    @abstractmethod
    def analyze(self, **kwargs) -> 'AnalysisResult':
        """
        Analiza usando FileInfoRepositoryCache como fuente de verdad.
        
        Args:
            **kwargs: Argumentos específicos del servicio
            
        Returns:
            AnalysisResult: El resultado del análisis / plan de acción
            
        Note:
            Los servicios NO reciben metadata_cache. Acceden directamente a
            FileInfoRepositoryCache.get_instance() para obtener metadatos.
        """
        pass

    @abstractmethod
    def execute(self, analysis_result: 'AnalysisResult', dry_run: bool = False, **kwargs) -> 'ExecutionResult':
        """
        Ejecuta la operación basada en el análisis previo.
        
        Args:
            analysis_result: El resultado obtenido de analyze()
            dry_run: Si True, solo simula las acciones
            **kwargs: Argumentos adicionales
            
        Returns:
            ExecutionResult: Resultado de la ejecución
        """
        pass

    
    def _report_progress(
        self,
        callback: Optional[ProgressCallback],
        current: int,
        total: int,
        message: str
    ) -> bool:
        """
        Helper estandarizado para reportar progreso de operaciones.
        
        Este método centraliza toda la lógica de callbacks de progreso,
        eliminando 3 patrones diferentes de manejo de callbacks.
        
        Características:
        - Verifica flag de cancelación antes de llamar al callback
        - Maneja excepciones en callbacks sin interrumpir operación
        - Soporta callbacks que retornan None (no cancelables)
        - Logging automático de cancelaciones
        
        Args:
            callback: Función de callback opcional (ver ProgressCallback)
            current: Número de elementos procesados
            total: Total de elementos a procesar
            message: Mensaje descriptivo del progreso
            
        Returns:
            True si debe continuar la operación, False si se canceló
            
        Example:
            >>> for i, file in enumerate(files):
            ...     if not self._report_progress(progress_callback, i, len(files), f"Procesando {file.name}"):
            ...         break  # Operación cancelada
            ...     # Procesar archivo...
        """
        # Si ya se canceló previamente, no continuar
        if self._cancelled:
            return False
        
        # Si no hay callback, continuar
        if callback is None:
            return True
        
        # Llamar al callback de forma segura
        try:
            result = callback(current, total, message)
            
            # Si el callback retorna explícitamente False, cancelar
            if result is False:
                self._cancelled = True
                self.logger.info(f"Operation cancelled by user at {current}/{total}")
                return False
            
            # None o True: continuar
            return True
            
        except Exception as e:
            # No interrumpir operación por errores en callback
            self.logger.warning(f"Error in progress callback: {e}")
            return True
    
    def cancel(self):
        """
        Solicita cancelación de operación en curso.
        
        Este método puede ser llamado desde otro thread (ej: UI)
        para detener una operación larga. La cancelación es cooperativa:
        la operación debe verificar _report_progress() periódicamente.
        
        Example:
            >>> # Desde UI thread
            >>> service.cancel()
            >>> # La operación se detendrá en el siguiente _report_progress()
        """
        self._cancelled = True
        self.logger.info("Cancellation requested")
    
    def _create_backup_for_operation(
        self,
        files: Iterable[Union[Path, dict, Any]],
        operation_name: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> Optional[Path]:
        """
        Crea backup estandarizado para cualquier operación.
        
        Este método centraliza la lógica de creación de backups,
        eliminando ~50 líneas de código duplicado por servicio.
        
        Características:
        - Encuentra automáticamente el directorio común entre archivos
        - Extrae rutas de diferentes estructuras (Path, dict, dataclass)
        - Genera nombres consistentes con metadata
        - Maneja errores de forma uniforme
        
        Args:
            files: Archivos a incluir en backup. Acepta:
                  - Path objects directamente
                  - Dicts con keys: 'original_path', 'path', 'source_path'
                  - Dataclasses con attrs: path, original_path, source_path
                  - Objetos con atributo 'heic_path' o 'jpg_path' (HEICDuplicatePair)
            operation_name: Nombre de la operación (ej: 'renaming', 'deletion', 'heic_removal')
            progress_callback: Callback opcional para reportar progreso
            
        Returns:
            Path del backup creado, o None si no hay archivos
            
        Raises:
            BackupCreationError: Si el backup falla de forma crítica
            
        Example:
            >>> # Con lista de Path
            >>> backup = self._create_backup_for_operation(
            ...     [Path('file1.jpg'), Path('file2.jpg')],
            ...     'deletion'
            ... )
            
            >>> # Con plan de renombrado (dicts)
            >>> backup = self._create_backup_for_operation(
            ...     [{'original_path': Path('old.jpg')}, ...],
            ...     'renaming'
            ... )
        """
        from utils.file_utils import launch_backup_creation, to_path
        
        # Convertir iterador a lista y extraer Paths
        file_list = []
        skipped_missing = []
        for item in files:
            try:
                # to_path maneja Path, dict, dataclass, HEICDuplicatePair, etc.
                file_path = to_path(
                    item, 
                    attr_names=('original_path', 'path', 'source_path', 'heic_path', 'jpg_path')
                )
                if file_path:
                    # Verificar que el archivo existe antes de incluirlo en backup
                    # Esto previene errores cuando otro servicio eliminó el archivo
                    if file_path.exists():
                        file_list.append(file_path)
                    else:
                        skipped_missing.append(file_path)
            except Exception as e:
                self.logger.warning(f"Could not extract path from {item}: {e}")
                continue
        
        # Log de archivos omitidos por no existir
        if skipped_missing:
            self.logger.warning(
                f"{len(skipped_missing)} files skipped from backup (no longer exist, "
                f"possibly deleted by another operation):"
            )
            for missing_path in skipped_missing[:10]:  # Show max 10
                self.logger.warning(f"   - {missing_path}")
            if len(skipped_missing) > 10:
                self.logger.warning(f"   ... and {len(skipped_missing) - 10} more")
        
        if not file_list:
            self.logger.warning("No files for backup (all were skipped or don't exist)")
            return None
        
        # Encontrar directorio común
        base_dir = file_list[0].parent
        for file_path in file_list[1:]:
            try:
                base_dir = Path(os.path.commonpath([base_dir, file_path.parent]))
            except ValueError:
                # No hay path común (ej: diferentes drives en Windows)
                self.logger.warning(
                    f"No common path between {base_dir} and {file_path.parent}, "
                    f"using {base_dir}"
                )
                break
        
        # Crear backup
        try:
            backup_path = launch_backup_creation(
                file_list,
                base_dir,
                backup_prefix=f'backup_{operation_name}',
                progress_callback=progress_callback,
                metadata_name=f'{operation_name}_metadata.txt'
            )
            self.backup_dir = backup_path
            self.logger.info(f"Backup created at: {backup_path}")
            return backup_path
        except Exception as e:
            error_msg = f"Failed creating backup for {operation_name}: {e}"
            self.logger.error(error_msg)
            raise BackupCreationError(error_msg) from e
    
    def _format_operation_summary(
        self,
        operation_name: str,
        files_count: int,
        space_amount: int = 0,
        dry_run: bool = False
    ) -> str:
        """
        Genera mensaje de resumen estandarizado para operaciones.
        
        Args:
            operation_name: Nombre de la operación (ej: "Renombrado", "Eliminación")
            files_count: Cantidad de archivos procesados
            space_amount: Espacio liberado en bytes (opcional)
            dry_run: Si es simulación
        
        Returns:
            Mensaje formateado
        
        Example:
            >>> self._format_operation_summary("Eliminación", 10, 5242880, True)
            'Eliminación completado: 10 archivos se procesarían, 5.00 MB se liberarían'
        """
        from utils.format_utils import format_size
        
        mode_verb = tr("services.result.would_be_processed") if dry_run else tr("services.result.processed")
        
        if space_amount > 0:
            space_verb = tr("services.result.would_be_freed") if dry_run else tr("services.result.freed")
            return (
                f"{operation_name} {tr('services.result.completed')}: "
                f"{files_count} {tr('services.unit.files')} {mode_verb}, "
                f"{format_size(space_amount)} {space_verb}"
            )
        else:
            return f"{operation_name} {tr('services.result.completed')}: {files_count} {tr('services.unit.files')} {mode_verb}"
    
    def _execute_operation(
        self,
        files: Iterable[Union[Path, dict, Any]],
        operation_name: str,
        execute_fn: Callable[[bool], Any],
        create_backup: bool,
        dry_run: bool,
        progress_callback: Optional[ProgressCallback] = None
    ) -> Any:
        """
        Template method para ejecutar operaciones con gestión automática de backup.
        
        Encapsula toda la lógica común de ejecución:
        - Decisión de crear backup según flags
        - Manejo de BackupCreationError
        - Población de backup_path en resultado
        - Logging de errores
        
        Este método elimina ~120 líneas de código duplicado en servicios.
        
        Args:
            files: Archivos para incluir en backup. Acepta Path, dict, dataclass, etc.
            operation_name: String para logs y nombre de backup (ej: 'renaming', 'deletion', 'organization')
            execute_fn: Función que realiza el trabajo real.
                       Firma: execute_fn(dry_run: bool) -> OperationResult
                       Debe retornar un resultado con campos success, message, etc.
            create_backup: Si True y dry_run=False, crea backup antes de ejecutar
            dry_run: Si True, simula operación sin modificar disco (no crea backup)
            progress_callback: Callback opcional de progreso
            
        Returns:
            Resultado de execute_fn con campo backup_path poblado si corresponde
            
        Raises:
            Las excepciones de execute_fn se propagan (excepto BackupCreationError)
            
        Example:
            >>> def execute(self, renaming_plan, create_backup=True, dry_run=False, progress_callback=None):
            ...     return self._execute_operation(
            ...         files=[item['original_path'] for item in renaming_plan],
            ...         operation_name='renaming',
            ...         execute_fn=lambda dry: self._do_renaming(renaming_plan, dry, progress_callback),
            ...         create_backup=create_backup,
            ...         dry_run=dry_run,
            ...         progress_callback=progress_callback
            ...     )
        """
        backup_path = None
        
        # Decisión: solo crear backup si create_backup=True AND dry_run=False
        should_create_backup = create_backup and not dry_run
        
        if should_create_backup:
            try:
                backup_path = self._create_backup_for_operation(
                    files=files,
                    operation_name=operation_name,
                    progress_callback=progress_callback
                )
            except BackupCreationError as e:
                # Error crítico de backup: retornar resultado de error sin ejecutar
                self.logger.error(f"Operation aborted due to backup failure: {e}")
                
                # Importar aquí para evitar dependencia circular
                from services.result_types import BaseResult
                
                # Retornar resultado de error genérico
                # El servicio específico debería manejar esto mejor con su tipo de resultado
                return BaseResult(
                    success=False,
                    message=tr("services.error.backup_failed_operation_aborted", error=str(e))
                )
        
        # Ejecutar operación real
        try:
            result = execute_fn(dry_run)
            
            # Poblar backup_path en resultado si tiene ese campo
            if hasattr(result, 'backup_path'):
                result.backup_path = backup_path
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing {operation_name}: {e}")
            raise
    
    def _get_max_workers(self, io_bound: bool = True) -> int:
        """
        Obtiene número óptimo de workers para ThreadPoolExecutor.
        
        Centraliza configuración de workers eliminando ~30 líneas duplicadas
        por servicio que usa ThreadPool.
        
        Considera:
        - Override del usuario desde settings
        - Tipo de operación (IO-bound vs CPU-bound)
        - Configuración por defecto del sistema
        
        Args:
            io_bound: Si True, operación es IO-bound (lectura disco, red, hashes).
                     Si False, operación es CPU-bound (cálculos intensivos, procesamiento imagen).
                     
                     IO-bound: Puede usar más workers que CPU cores (ej: 4x cores)
                     CPU-bound: Limitado a número de cores para evitar contención
        
        Returns:
            Número de workers a usar en ThreadPoolExecutor
            
        Example:
            >>> # Para lectura de archivos y cálculo de hashes (IO-bound)
            >>> max_workers = self._get_max_workers(io_bound=True)
            >>> 
            >>> # Para procesamiento intensivo de imágenes (CPU-bound)
            >>> max_workers = self._get_max_workers(io_bound=False)
        """
        from utils.settings_manager import settings_manager
        from config import Config
        
        # Obtener override del usuario (0 = usar default)
        user_override = settings_manager.get_max_workers(0)
        
        # Calcular workers según tipo de operación
        max_workers = Config.get_actual_worker_threads(
            override=user_override,
            io_bound=io_bound
        )
        
        self.logger.debug(
            f"Usando {max_workers} workers para operación "
            f"{'IO-bound' if io_bound else 'CPU-bound'}"
        )
        
        return max_workers
    
    @contextmanager
    def _parallel_processor(self, io_bound: bool = True):
        """
        Context manager para procesamiento paralelo con ThreadPoolExecutor.
        
        Configura ThreadPoolExecutor con max_workers apropiado según tipo de operación.
        Compatible con cancelación cooperativa.
        
        Este context manager elimina ~20 líneas duplicadas por uso de ThreadPool.
        
        Args:
            io_bound: Si True, operación es IO-bound (lectura disco, red).
                     Si False, operación es CPU-bound (cálculos intensivos).
        
        Yields:
            ThreadPoolExecutor configurado y listo para usar
            
        Example:
            >>> with self._parallel_processor(io_bound=True) as executor:
            ...     futures = {executor.submit(process_file, f): f for f in files}
            ...     for future in as_completed(futures):
            ...         if self._cancelled:
            ...             break
            ...         result = future.result()
            ...         # Procesar resultado...
        """
        from concurrent.futures import ThreadPoolExecutor
        
        max_workers = self._get_max_workers(io_bound)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            yield executor
    
    def _should_report_progress(self, counter: int, interval: int = None) -> bool:
        """
        Determina si debe reportarse progreso según intervalo configurado.
        
        Ayuda a evitar spam de logs/callbacks reportando solo cada N elementos.
        
        Args:
            counter: Número actual de elementos procesados
            interval: Intervalo de reporte (usa Config.UI_UPDATE_INTERVAL si es None)
        
        Returns:
            True si counter es múltiplo del intervalo
            
        Example:
            >>> for i, file in enumerate(files):
            ...     # Solo reportar cada 50 archivos
            ...     if self._should_report_progress(i):
            ...         self._report_progress(callback, i, len(files), f"Procesando...")
        """
        from config import Config
        
        if interval is None:
            interval = Config.UI_UPDATE_INTERVAL
        
        return counter % interval == 0
    
    def _validate_directory(self, directory: Path, must_exist: bool = True) -> None:
        """
        Valida que un path sea un directorio válido.
        
        Centraliza validación común eliminando ~10 líneas por servicio.
        
        Args:
            directory: Path a validar
            must_exist: Si True, verifica que existe
            
        Raises:
            ValueError: Si validación falla con mensaje descriptivo
            
        Example:
            >>> def analyze(self, directory: Path, ...):
            ...     self._validate_directory(directory)
            ...     # Continuar con análisis...
        """
        if must_exist and not directory.exists():
            raise ValueError(f"Directory does not exist: {directory}")
        
        if must_exist and not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")
    
    def _get_supported_files(
        self,
        directory: Path,
        recursive: bool = True,
        progress_callback: Optional[ProgressCallback] = None
    ) -> list[Path]:
        """
        Recopila archivos multimedia soportados en directorio.
        
        Usa utils.file_utils.is_supported_file() para filtrar.
        Puede reportar progreso y soporta cancelación.
        
        Este método elimina ~20 líneas de código duplicado por servicio.
        
        Args:
            directory: Directorio a escanear
            recursive: Si True, busca recursivamente con **/*
            progress_callback: Callback opcional para progreso de scan
            
        Returns:
            Lista de Paths de archivos soportados
            
        Example:
            >>> files = self._get_supported_files(
            ...     directory,
            ...     recursive=True,
            ...     progress_callback=progress_callback
            ... )
            >>> self.logger.info(f"Found {len(files)} supported files")
        """
        from config import Config
        
        files = []
        pattern = "**/*" if recursive else "*"
        processed = 0
        
        for filepath in directory.glob(pattern):
            from utils.file_utils import is_supported_file
            if filepath.is_file() and is_supported_file(filepath.name):
                files.append(filepath)
            
            processed += 1
            if progress_callback and self._should_report_progress(processed):
                if not self._report_progress(
                    progress_callback,
                    processed,
                    -1,  # Total desconocido en scan
                    tr("services.progress.scanning_file", name=filepath.name)
                ):
                    break  # Cancelado
        
        return files

    def _delete_file_with_logging(
        self,
        file_path: Path,
        file_size: int,
        file_type: str,
        dry_run: bool
    ) -> bool:
        """
        Elimina un archivo con logging estandarizado y actualización de caché.
        
        Centraliza el patrón repetido de:
        - Log FILE_DELETED o FILE_DELETED_SIMULATION
        - Llamada a delete_file_securely()
        - Actualización de FileInfoRepositoryCache
        
        Args:
            file_path: Ruta del archivo a eliminar
            file_size: Tamaño en bytes para el log
            file_type: Tipo de archivo para el log (ej: 'HEIC', 'MOV', 'visual_identical')
            dry_run: Si True, solo simula y loguea sin eliminar
            
        Returns:
            True si se eliminó/simuló exitosamente, False en caso de error
            
        Example:
            >>> success = self._delete_file_with_logging(
            ...     file_path=Path('/tmp/foto.jpg'),
            ...     file_size=1024,
            ...     file_type='JPG',
            ...     dry_run=False
            ... )
        """
        from utils.file_utils import delete_file_securely
        from utils.format_utils import format_size
        from services.file_metadata_repository_cache import FileInfoRepositoryCache
        
        log_type = "FILE_DELETED_SIMULATION" if dry_run else "FILE_DELETED"
        log_msg = f"{log_type}: {file_path} | Size: {format_size(file_size)} | Type: {file_type}"
        
        if dry_run:
            self.logger.info(log_msg)
            return True
        else:
            if delete_file_securely(file_path):
                self.logger.info(log_msg)
                # Actualizar caché eliminando el archivo
                repo = FileInfoRepositoryCache.get_instance()
                repo.remove_file(file_path)
                return True
            else:
                self.logger.error(f"Could not delete: {file_path}")
                return False
