# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Crea la card de Duplicados Exactos (Copias Exactas) para el grid de herramientas.
"""

from ui.screens.tool_card import ToolCard
from ui.tools_definitions import TOOL_DUPLICATES_EXACT
from utils.format_utils import format_size
from utils.i18n import tr


def create_duplicates_exact_card(analysis_results, on_click_callback) -> ToolCard:
    """
    Crea la card de Duplicados Exactos

    Args:
        analysis_results: Objeto con los resultados del análisis
        on_click_callback: Callback para manejar el clic en la card

    Returns:
        ToolCard configurada
    """
    # Verificar si hay análisis disponible
    has_analysis = (hasattr(analysis_results, 'duplicates') and 
                   analysis_results.duplicates is not None)
    
    card = ToolCard(
        icon_name=TOOL_DUPLICATES_EXACT.icon_name,
        title=TOOL_DUPLICATES_EXACT.title,
        description=TOOL_DUPLICATES_EXACT.long_description,
        action_text=tr("cards.action_manage") if has_analysis else tr("cards.action_analyze")
    )


    # Configurar estado según datos
    if has_analysis:
        dup_data = analysis_results.duplicates
        if dup_data.total_duplicates > 0:
            size_text = tr("cards.space_wasted", size=format_size(dup_data.space_recoverable))
            card.set_status_with_results(
                tr("cards.duplicate_files_found", count=dup_data.total_duplicates),
                size_text,
                badge_count=dup_data.total_duplicates
            )
        else:
            card.set_status_no_results(tr("cards.no_duplicates_found"))
    else:
        # Estado pendiente de análisis
        card.set_status_pending(tr("cards.pending_exact_copies"))

    card.clicked.connect(lambda: on_click_callback('duplicates_exact'))
    return card
