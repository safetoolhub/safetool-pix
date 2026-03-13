# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Crea la card de HEIC/JPG Duplicados para el grid de herramientas.
"""

from ui.screens.tool_card import ToolCard
from ui.tools_definitions import TOOL_HEIC
from utils.format_utils import format_size
from utils.i18n import tr


def create_heic_card(analysis_results, on_click_callback) -> ToolCard:
    """
    Crea la card de HEIC/JPG con información del análisis (si existe)

    Args:
        analysis_results: Objeto con los resultados del análisis
        on_click_callback: Callback para manejar el clic en la card

    Returns:
        ToolCard configurada
    """
    # Verificar si hay análisis disponible
    has_analysis = (hasattr(analysis_results, 'heic') and 
                   analysis_results.heic is not None)
    
    card = ToolCard(
        icon_name=TOOL_HEIC.icon_name,
        title=TOOL_HEIC.title,
        description=TOOL_HEIC.long_description,
        action_text=tr("cards.action_manage") if has_analysis else tr("cards.action_analyze")
    )
    
    if has_analysis:
        heic_data = analysis_results.heic
        if heic_data.items_count > 0:
            savings_jpg = heic_data.potential_savings_keep_jpg or 0
            savings_heic = heic_data.potential_savings_keep_heic or 0
            max_savings = max(savings_jpg, savings_heic)
            card.set_status_with_results(
                tr("cards.heic_groups_found", count=heic_data.items_count),
                tr("cards.space_recoverable", size=format_size(max_savings)),
                badge_count=heic_data.items_count
            )
        else:
            card.set_status_no_results(tr("cards.no_heic_pairs_found"))
    else:
        # Estado pendiente de análisis
        card.set_status_pending(tr("cards.pending_heic"))

    card.clicked.connect(lambda: on_click_callback('heic'))
    return card
