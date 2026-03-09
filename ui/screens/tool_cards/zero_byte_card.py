# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Crea la card de Archivos vacíos para el grid de herramientas.
"""

from ui.screens.tool_card import ToolCard
from ui.tools_definitions import TOOL_ZERO_BYTE
from utils.i18n import tr


def create_zero_byte_card(analysis_results, on_click_callback) -> ToolCard:
    """
    Crea la card de Archivos vacíos

    Args:
        analysis_results: Objeto con los resultados del análisis
        on_click_callback: Callback para manejar el clic en la card

    Returns:
        ToolCard configurada
    """
    # Verificar si hay análisis disponible
    has_analysis = (hasattr(analysis_results, 'zero_byte') and 
                   analysis_results.zero_byte is not None)
    
    card = ToolCard(
        icon_name=TOOL_ZERO_BYTE.icon_name,
        title=TOOL_ZERO_BYTE.title,
        description=TOOL_ZERO_BYTE.long_description,
        action_text=tr("cards.action_manage") if has_analysis else tr("cards.action_analyze")
    )

    # Configurar estado según datos
    if has_analysis:
        zero_byte_data = analysis_results.zero_byte
        if zero_byte_data.items_count > 0:
            size_text = tr("cards.n_files", count=zero_byte_data.items_count)
            card.set_status_with_results(
                tr("cards.empty_files_detected", count=zero_byte_data.items_count),
                size_text,
                badge_count=zero_byte_data.items_count
            )
        else:
            card.set_status_no_results(tr("cards.no_empty_files_found"))
    else:
        # Estado pendiente de análisis
        card.set_status_pending(tr("cards.pending_empty_files"))
        
    card.clicked.connect(lambda: on_click_callback('zero_byte'))
    return card
