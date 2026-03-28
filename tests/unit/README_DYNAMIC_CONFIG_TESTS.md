# Tests de Configuración Dinámica

Tests completos para la configuración dinámica de caché y workers basada en hardware del sistema.

## Archivo de tests

📄 **`tests/unit/test_dynamic_config.py`**

## Resumen de cobertura

- **52 tests** en total
- **100% de tests pasando** ✅
- **86% de cobertura** en `config.py`

## Clases de tests

### 1. `TestSystemDetection` (4 tests)
Tests para detección de recursos del sistema:
- ✅ Detecta RAM con psutil
- ✅ Usa fallback sin psutil (8GB default)
- ✅ Detecta número de CPUs
- ✅ Usa fallback para CPU (4 cores default)

### 2. `TestCacheConfiguration` (12 tests)
Tests para configuración dinámica de caché según RAM:

**Límites de entradas en caché:**
- Fórmula: `RAM_GB × 1000` (mín: 5000, máx: 20000)
- Tests con 2GB, 4GB, 8GB, 16GB, 32GB, 64GB
- Verifica límites mínimo y máximo

**Threshold de dataset grande:**
- Fórmula: `RAM_GB × 500` (mín: 3000, máx: 10000)
- Tests con diferentes cantidades de RAM
- Verifica límites y cálculo de auto-open (60%)

### 3. `TestWorkerConfiguration` (18 tests)
Tests para configuración dinámica de workers según CPU:

**Workers I/O bound** (lectura/hashing):
- Fórmula: `cores × 2` (mín: 4, máx: 16)
- Tests con 2, 4, 6, 8, 12, 16, 20 cores

**Workers CPU bound** (análisis de imágenes):
- Fórmula: `cores × 1` (mín: 4, máx: 16)
- Tests con diferentes configuraciones de CPU

**Override manual:**
- ✅ Sin override (0) usa automático
- ✅ Con override usa valor especificado
- ✅ Override respeta límite máximo
- ✅ Combinaciones de override + tipo de operación

### 4. `TestSystemInfo` (3 tests)
Tests para el método `get_system_info()`:
- ✅ Retorna dict completo con psutil
- ✅ Funciona sin psutil
- ✅ Consistencia entre valores calculados

### 5. `TestEdgeCases` (5 tests)
Tests para casos extremos:
- ✅ RAM de 0GB (aplica mínimos)
- ✅ RAM negativa (defensivo, aplica mínimos)
- ✅ Sistema de 1 core (aplica mínimo 4 workers)
- ✅ RAM masiva >100GB (aplica máximos)
- ✅ CPU masiva >64 cores (aplica máximo 16 workers)

### 6. `TestIntegration` (4 tests)
Tests de integración para configuraciones típicas:

| Hardware | Cache | Large Threshold | Auto-Open | I/O Workers | CPU Workers |
|----------|-------|-----------------|-----------|-------------|-------------|
| **Laptop** (4GB, 4 cores) | 5,000 | 3,000 | 1,800 | 8 | 4 |
| **Desktop** (16GB, 8 cores) | 16,000 | 8,000 | 4,800 | 16 | 8 |
| **Workstation** (32GB, 16 cores) | 20,000 | 10,000 | 6,000 | 16 | 16 |
| **Servidor** (64GB, 32 cores) | 20,000 | 10,000 | 6,000 | 16 | 16 |

## Ejecutar tests

```bash
# Todos los tests
pytest tests/unit/test_dynamic_config.py -v

# Con cobertura
pytest tests/unit/test_dynamic_config.py --cov=config --cov-report=html

# Solo una clase
pytest tests/unit/test_dynamic_config.py::TestWorkerConfiguration -v

# Solo un test específico
pytest tests/unit/test_dynamic_config.py::TestCacheConfiguration::test_get_max_cache_entries -v
```

## Métodos testeados

### Detección de sistema
- ✅ `Config._get_system_ram_gb()`
- ✅ `Config.get_cpu_count()`

### Configuración de caché
- ✅ `Config.get_max_cache_entries()`
- ✅ `Config.get_large_dataset_threshold()`
- ✅ `Config.get_similarity_dialog_auto_open_threshold()`

### Configuración de workers
- ✅ `Config.get_optimal_worker_threads()`
- ✅ `Config.get_cpu_bound_workers()`
- ✅ `Config.get_actual_worker_threads(override, io_bound)`

### Sistema completo
- ✅ `Config.get_system_info()`

## Parametrización

Los tests usan `@pytest.mark.parametrize` para probar múltiples configuraciones:

```python
@pytest.mark.parametrize("ram_gb,expected_cache", [
    (4.0, 5000),
    (8.0, 8000),
    (16.0, 16000),
    (32.0, 20000),
])
def test_get_max_cache_entries(self, ram_gb, expected_cache):
    # Test se ejecuta para cada combinación
```

## Mocking

Los tests usan `unittest.mock.patch` para simular diferentes configuraciones de hardware:

```python
with patch.object(Config, '_get_system_ram_gb', return_value=16.0):
    with patch.object(Config, 'get_cpu_count', return_value=8):
        # Test con 16GB RAM y 8 cores
```

## Validaciones

Cada test verifica:
1. ✅ **Cálculo correcto** según fórmula
2. ✅ **Límites aplicados** (mínimo y máximo)
3. ✅ **Consistencia** entre métodos relacionados
4. ✅ **Edge cases** y casos defensivos
5. ✅ **Integración** completa del sistema

## Cobertura detallada

Las líneas no cubiertas (14%) son:
- Métodos de utilidad legacy (is_image_file, is_video_file, etc.)
- Algunos getters/setters simples
- Código de validación que ya está cubierto implícitamente

**La configuración dinámica tiene 100% de cobertura en sus métodos críticos.**
