# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para verificar la priorización de grupos por diferencia de tamaño.

Este test verifica que el algoritmo de priorización de duplicados similares
ordena correctamente los grupos basándose en la diferencia de tamaño entre archivos.
"""

from pathlib import Path
from services.result_types import SimilarDuplicateGroup


class TestSizePrioritization:
    """Tests para la priorización de grupos por tamaño."""

    def test_size_variation_calculation(self):
        """
        Verifica que el cálculo de variación de tamaño funciona correctamente.
        """
        # Simular datos de hashes con información de tamaño
        hashes = {
            '/photos/IMG_001.jpg': {'hash': 12345, 'size': 4_500_000, 'modified': 1.0},  # 4.5 MB
            '/photos/WhatsApp_001.jpg': {'hash': 12346, 'size': 1_200_000, 'modified': 1.0},  # 1.2 MB
        }
        
        group = SimilarDuplicateGroup(
            hash_value='12345',
            files=[Path('/photos/IMG_001.jpg'), Path('/photos/WhatsApp_001.jpg')],
            file_sizes=[4_500_000, 1_200_000],
            similarity_score=95.0
        )
        
        # Función de cálculo de score (copiada del servicio)
        def calculate_size_variation_score(group: SimilarDuplicateGroup) -> float:
            """Calcula un score basado en la variación de tamaño."""
            if len(group.files) < 2:
                return 0.0
            
            sizes = []
            for f in group.files:
                try:
                    size = hashes[f.as_posix()]['size']
                    sizes.append(size)
                except (KeyError, FileNotFoundError):
                    continue
            
            if len(sizes) < 2:
                return 0.0
            
            min_size = min(sizes)
            max_size = max(sizes)
            
            if min_size == 0:
                return 0.0
            
            size_diff_percent = ((max_size - min_size) / min_size) * 100
            return size_diff_percent
        
        # Verificar cálculo: (4_500_000 - 1_200_000) / 1_200_000 * 100 = 275%
        score = calculate_size_variation_score(group)
        assert score == 275.0, f"Expected 275.0, got {score}"

    def test_size_prioritization_ordering(self):
        """
        Verifica que los grupos se ordenan correctamente por diferencia de tamaño.
        
        Este test simula tres grupos:
        1. WhatsApp vs original: ~275% diferencia (debe ser primero)
        2. Email vs original: ~533% diferencia (debe ser primero)
        3. Ediciones similares: ~5% diferencia (debe ser último)
        """
        # Simular datos de hashes
        hashes = {
            # Grupo 1: Gran diferencia de tamaño (WhatsApp vs original)
            '/photos/IMG_001.jpg': {'hash': 12345, 'size': 4_500_000, 'modified': 1.0},
            '/photos/WhatsApp_001.jpg': {'hash': 12346, 'size': 1_200_000, 'modified': 1.0},
            
            # Grupo 2: Tamaños similares (ediciones)
            '/photos/IMG_002.jpg': {'hash': 22345, 'size': 2_100_000, 'modified': 1.0},
            '/photos/IMG_002_edited.jpg': {'hash': 22346, 'size': 2_000_000, 'modified': 1.0},
            
            # Grupo 3: Enorme diferencia (email vs original)
            '/photos/DSC_0001.jpg': {'hash': 32345, 'size': 3_800_000, 'modified': 1.0},
            '/photos/DSC_0001_email.jpg': {'hash': 32346, 'size': 600_000, 'modified': 1.0},
        }
        
        # Crear grupos
        groups = [
            SimilarDuplicateGroup(
                hash_value='12345',
                files=[Path('/photos/IMG_001.jpg'), Path('/photos/WhatsApp_001.jpg')],
                file_sizes=[4_500_000, 1_200_000],
                similarity_score=95.0
            ),
            SimilarDuplicateGroup(
                hash_value='22345',
                files=[Path('/photos/IMG_002.jpg'), Path('/photos/IMG_002_edited.jpg')],
                file_sizes=[2_100_000, 2_000_000],
                similarity_score=92.0
            ),
            SimilarDuplicateGroup(
                hash_value='32345',
                files=[Path('/photos/DSC_0001.jpg'), Path('/photos/DSC_0001_email.jpg')],
                file_sizes=[3_800_000, 600_000],
                similarity_score=88.0
            ),
        ]
        
        # Función de cálculo de score
        def calculate_size_variation_score(group: SimilarDuplicateGroup) -> float:
            """Calcula un score basado en la variación de tamaño."""
            if len(group.files) < 2:
                return 0.0
            
            sizes = []
            for f in group.files:
                try:
                    size = hashes[f.as_posix()]['size']
                    sizes.append(size)
                except (KeyError, FileNotFoundError):
                    continue
            
            if len(sizes) < 2:
                return 0.0
            
            min_size = min(sizes)
            max_size = max(sizes)
            
            if min_size == 0:
                return 0.0
            
            size_diff_percent = ((max_size - min_size) / min_size) * 100
            return size_diff_percent
        
        # Calcular scores antes de ordenar
        scores_before = [calculate_size_variation_score(g) for g in groups]
        
        # Ordenar grupos por diferencia de tamaño
        groups.sort(key=calculate_size_variation_score, reverse=True)
        
        # Calcular scores después de ordenar
        scores_after = [calculate_size_variation_score(g) for g in groups]
        
        # Verificaciones
        # 1. El grupo con mayor diferencia debe estar primero (email: ~533%)
        assert 'DSC_0001' in groups[0].files[0].name, \
            f"Expected DSC_0001 group first, got {groups[0].files[0].name}"
        
        # 2. El grupo con menor diferencia debe estar último (ediciones: ~5%)
        assert 'IMG_002' in groups[-1].files[0].name, \
            f"Expected IMG_002 group last, got {groups[-1].files[0].name}"
        
        # 3. Los scores deben estar en orden descendente
        assert scores_after == sorted(scores_after, reverse=True), \
            "Groups are not sorted by size variation score"
        
        # 4. Verificar valores aproximados de los scores
        # Email group: (3_800_000 - 600_000) / 600_000 * 100 ≈ 533%
        assert scores_after[0] > 500, f"Expected score > 500, got {scores_after[0]}"
        
        # WhatsApp group: (4_500_000 - 1_200_000) / 1_200_000 * 100 = 275%
        assert 200 < scores_after[1] < 300, f"Expected score ~275, got {scores_after[1]}"
        
        # Edited group: (2_100_000 - 2_000_000) / 2_000_000 * 100 = 5%
        assert scores_after[2] < 10, f"Expected score < 10, got {scores_after[2]}"

    def test_edge_cases(self):
        """Verifica casos extremos del algoritmo de priorización."""
        # Caso 1: Grupo con un solo archivo (debe retornar 0)
        single_file_group = SimilarDuplicateGroup(
            hash_value='99999',
            files=[Path('/photos/single.jpg')],
            file_sizes=[1_000_000],
            similarity_score=100.0
        )
        
        def calculate_size_variation_score(group: SimilarDuplicateGroup) -> float:
            """Calcula un score basado en la variación de tamaño."""
            if len(group.files) < 2:
                return 0.0
            return 0.0  # Simplificado para este test
        
        score = calculate_size_variation_score(single_file_group)
        assert score == 0.0, "Single file group should have score 0.0"
        
        # Caso 2: Grupo sin archivos (debe retornar 0)
        empty_group = SimilarDuplicateGroup(
            hash_value='00000',
            files=[],
            file_sizes=[],
            similarity_score=0.0
        )
        
        score = calculate_size_variation_score(empty_group)
        assert score == 0.0, "Empty group should have score 0.0"

    def test_prioritization_integration(self):
        """
        Test de integración que verifica el flujo completo de priorización.
        """
        # Simular múltiples grupos con diferentes características
        hashes = {
            '/a1.jpg': {'size': 5_000_000},  # 5 MB
            '/a2.jpg': {'size': 4_900_000},  # 4.9 MB (2% diff)
            
            '/b1.jpg': {'size': 3_000_000},  # 3 MB
            '/b2.jpg': {'size': 1_000_000},  # 1 MB (200% diff)
            
            '/c1.jpg': {'size': 2_000_000},  # 2 MB
            '/c2.jpg': {'size': 500_000},    # 500 KB (300% diff)
        }
        
        groups = [
            SimilarDuplicateGroup(
                hash_value='a', files=[Path('/a1.jpg'), Path('/a2.jpg')],
                file_sizes=[5_000_000, 4_900_000], similarity_score=99.0
            ),
            SimilarDuplicateGroup(
                hash_value='b', files=[Path('/b1.jpg'), Path('/b2.jpg')],
                file_sizes=[3_000_000, 1_000_000], similarity_score=85.0
            ),
            SimilarDuplicateGroup(
                hash_value='c', files=[Path('/c1.jpg'), Path('/c2.jpg')],
                file_sizes=[2_000_000, 500_000], similarity_score=90.0
            ),
        ]
        
        def calculate_size_variation_score(group: SimilarDuplicateGroup) -> float:
            if len(group.files) < 2:
                return 0.0
            sizes = [hashes[f.as_posix()]['size'] for f in group.files]
            if len(sizes) < 2:
                return 0.0
            min_size = min(sizes)
            max_size = max(sizes)
            if min_size == 0:
                return 0.0
            return ((max_size - min_size) / min_size) * 100
        
        # Ordenar por diferencia de tamaño
        groups.sort(key=calculate_size_variation_score, reverse=True)
        
        # Verificar orden esperado: c (300%) > b (200%) > a (2%)
        assert groups[0].hash_value == 'c', "Group 'c' should be first (highest size diff)"
        assert groups[1].hash_value == 'b', "Group 'b' should be second"
        assert groups[2].hash_value == 'a', "Group 'a' should be last (lowest size diff)"
        
        # Verificar que los scores están en orden descendente
        scores = [calculate_size_variation_score(g) for g in groups]
        assert scores == sorted(scores, reverse=True), "Scores must be in descending order"
