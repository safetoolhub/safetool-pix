# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Crea la card de Live Photos para el grid de herramientas.
"""

from ui.screens.tool_card import ToolCard
from ui.tools_definitions import TOOL_LIVE_PHOTOS
from utils.format_utils import format_size
from utils.i18n import tr


def create_live_photos_card(analysis_results, on_click_callback) -> ToolCard:
    """
    Crea la card de Live Photos

    Args:
        analysis_results: Objeto con los resultados del análisis
        on_click_callback: Callback para manejar el clic en la card

    Returns:
        ToolCard configurada
    """
    # Verificar si hay análisis disponible
    has_analysis = (hasattr(analysis_results, 'live_photos') and 
                   analysis_results.live_photos is not None)
    
    card = ToolCard(
        icon_name=TOOL_LIVE_PHOTOS.icon_name,
        title=TOOL_LIVE_PHOTOS.title,
        description=TOOL_LIVE_PHOTOS.long_description,
        action_text=tr("cards.action_manage") if has_analysis else tr("cards.action_analyze")
    )

    # Configurar estado según datos
    if has_analysis:
        live_photo_data = analysis_results.live_photos
        if live_photo_data.items_count > 0:
            size_text = tr("cards.space_recoverable", size=format_size(live_photo_data.potential_savings))
            card.set_status_with_results(
                tr("cards.live_photo_groups_detected", count=live_photo_data.items_count),
                size_text,
                badge_count=live_photo_data.items_count
            )
        else:
            card.set_status_no_results(tr("cards.no_live_photos_found"))
    else:
        # Estado pendiente de análisis
        card.set_status_pending(tr("cards.pending_live_photos"))

    card.clicked.connect(lambda: on_click_callback('live_photos'))
    return card
