# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Crea la card de Copias Visuales Idénticas para el grid de herramientas.
"""

from ui.screens.tool_card import ToolCard
from ui.tools_definitions import TOOL_VISUAL_IDENTICAL
from utils.format_utils import format_size
from utils.i18n import tr


def create_visual_identical_card(analysis_results, on_click_callback) -> ToolCard:
    """
    Crea la card de Copias visuales idénticas

    Args:
        analysis_results: Objeto con los resultados del análisis
        on_click_callback: Callback para manejar el clic en la card

    Returns:
        ToolCard configurada
    """
    # Verificar si hay análisis disponible
    has_analysis = (hasattr(analysis_results, 'visual_identical') and 
                   analysis_results.visual_identical is not None)
    
    card = ToolCard(
        icon_name=TOOL_VISUAL_IDENTICAL.icon_name,
        title=TOOL_VISUAL_IDENTICAL.title,
        description=TOOL_VISUAL_IDENTICAL.long_description,
        action_text=tr("cards.action_manage") if has_analysis else tr("cards.action_analyze")
    )
    
    # Configurar estado según datos
    if has_analysis:
        vi_data = analysis_results.visual_identical
        if vi_data.total_groups > 0:
            size_text = tr("cards.space_recoverable", size=format_size(vi_data.space_recoverable))
            card.set_status_with_results(
                tr("cards.groups_detected", count=vi_data.total_groups),
                size_text,
                badge_count=vi_data.total_duplicates
            )
        else:
            card.set_status_no_results(tr("cards.no_visual_identical_found"))
    else:
        # Estado pendiente de análisis
        card.set_status_pending(tr("cards.pending_visual_identical"))
    
    card.clicked.connect(lambda: on_click_callback('visual_identical'))
    return card
