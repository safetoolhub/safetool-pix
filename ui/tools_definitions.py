# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Centralized definitions of all SafeTool Pix tools.

This file is the single source of truth for tool names, descriptions and icons.
Any naming changes should be made here.

Text is resolved via i18n (tr()) for internationalization support.
"""

from typing import Dict, List, Optional

from utils.i18n import tr


class ToolDefinition:
    """Immutable tool definition with i18n-resolved text properties."""

    __slots__ = ('_id', '_icon_name')

    def __init__(self, id: str, icon_name: str) -> None:
        object.__setattr__(self, '_id', id)
        object.__setattr__(self, '_icon_name', icon_name)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("ToolDefinition instances are immutable")

    @property
    def id(self) -> str:
        return self._id

    @property
    def icon_name(self) -> str:
        return self._icon_name

    @property
    def title(self) -> str:
        return tr(f"tools.{self._id}.title")

    @property
    def short_description(self) -> str:
        return tr(f"tools.{self._id}.short_description")

    @property
    def long_description(self) -> str:
        return tr(f"tools.{self._id}.long_description")

    def __repr__(self) -> str:
        return f"ToolDefinition(id={self._id!r}, icon_name={self._icon_name!r})"


class ToolCategory:
    """Immutable tool category definition with i18n-resolved text properties."""

    __slots__ = ('_id', '_tool_ids')

    def __init__(self, id: str, tool_ids: tuple) -> None:
        object.__setattr__(self, '_id', id)
        object.__setattr__(self, '_tool_ids', tool_ids)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("ToolCategory instances are immutable")

    @property
    def id(self) -> str:
        return self._id

    @property
    def title(self) -> str:
        return tr(f"categories.{self._id}.title")

    @property
    def description(self) -> str:
        return tr(f"categories.{self._id}.description")

    @property
    def tool_ids(self) -> tuple:
        return self._tool_ids

    def __repr__(self) -> str:
        return f"ToolCategory(id={self._id!r}, tool_ids={self._tool_ids!r})"


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

TOOL_ZERO_BYTE = ToolDefinition(id='zero_byte', icon_name='file-x')
TOOL_LIVE_PHOTOS = ToolDefinition(id='live_photos', icon_name='camera-burst')
TOOL_HEIC = ToolDefinition(id='heic', icon_name='file-image')
TOOL_DUPLICATES_EXACT = ToolDefinition(id='duplicates_exact', icon_name='content-copy')
TOOL_VISUAL_IDENTICAL = ToolDefinition(id='visual_identical', icon_name='image-multiple')
TOOL_DUPLICATES_SIMILAR = ToolDefinition(id='duplicates_similar', icon_name='image-search')
TOOL_FILE_ORGANIZER = ToolDefinition(id='file_organizer', icon_name='folder-move')
TOOL_FILE_RENAMER = ToolDefinition(id='file_renamer', icon_name='rename-box')


# =============================================================================
# TOOL CATEGORIES
# =============================================================================

CATEGORY_CLEANUP = ToolCategory(
    id='cleanup',
    tool_ids=('zero_byte', 'live_photos', 'heic', 'duplicates_exact')
)

CATEGORY_VISUAL = ToolCategory(
    id='visual',
    tool_ids=('visual_identical', 'duplicates_similar')
)

CATEGORY_ORGANIZATION = ToolCategory(
    id='organization',
    tool_ids=('file_organizer', 'file_renamer')
)

# Lista ordenada de categorías
TOOL_CATEGORIES: List[ToolCategory] = [
    CATEGORY_CLEANUP,
    CATEGORY_VISUAL,
    CATEGORY_ORGANIZATION,
]


# =============================================================================
# REGISTRO DE HERRAMIENTAS
# =============================================================================

# Diccionario con todas las herramientas indexadas por ID
TOOLS: Dict[str, ToolDefinition] = {
    tool.id: tool for tool in [
        TOOL_ZERO_BYTE,
        TOOL_LIVE_PHOTOS,
        TOOL_HEIC,
        TOOL_DUPLICATES_EXACT,
        TOOL_VISUAL_IDENTICAL,
        TOOL_DUPLICATES_SIMILAR,
        TOOL_FILE_ORGANIZER,
        TOOL_FILE_RENAMER,
    ]
}


# =============================================================================
# ACCESS FUNCTIONS
# =============================================================================

def get_tool(tool_id: str) -> Optional[ToolDefinition]:
    """
    Get a tool definition by its ID.

    Args:
        tool_id: Tool identifier (e.g. 'zero_byte', 'live_photos')

    Returns:
        ToolDefinition or None if not found
    """
    return TOOLS.get(tool_id)


def get_tool_title(tool_id: str) -> str:
    """
    Obtiene el título de una herramienta por su ID.
    
    Args:
        tool_id: Identificador de la herramienta
        
    Returns:
        Título de la herramienta o el ID si no existe
    """
    tool = TOOLS.get(tool_id)
    return tool.title if tool else tool_id


def get_tool_short_description(tool_id: str) -> str:
    """
    Obtiene la descripción corta de una herramienta por su ID.
    
    Args:
        tool_id: Identificador de la herramienta
        
    Returns:
        Descripción corta o string vacío si no existe
    """
    tool = TOOLS.get(tool_id)
    return tool.short_description if tool else ''


def get_tool_long_description(tool_id: str) -> str:
    """
    Obtiene la descripción larga de una herramienta por su ID.
    
    Args:
        tool_id: Identificador de la herramienta
        
    Returns:
        Descripción larga o string vacío si no existe
    """
    tool = TOOLS.get(tool_id)
    return tool.long_description if tool else ''


def get_all_tool_ids() -> list:
    """
    Obtiene la lista de todos los IDs de herramientas.
    
    Returns:
        Lista de IDs de herramientas
    """
    return list(TOOLS.keys())


def get_tools_by_category(category_id: str) -> List[ToolDefinition]:
    """
    Obtiene las herramientas de una categoría específica.
    
    Args:
        category_id: Identificador de la categoría ('cleanup', 'visual', 'organization')
        
    Returns:
        Lista de ToolDefinition de esa categoría
    """
    for category in TOOL_CATEGORIES:
        if category.id == category_id:
            return [TOOLS[tool_id] for tool_id in category.tool_ids if tool_id in TOOLS]
    return []


def get_category(category_id: str) -> Optional[ToolCategory]:
    """
    Obtiene una categoría por su ID.
    
    Args:
        category_id: Identificador de la categoría
        
    Returns:
        ToolCategory o None si no existe
    """
    for category in TOOL_CATEGORIES:
        if category.id == category_id:
            return category
    return None


def get_all_categories() -> List[ToolCategory]:
    """
    Obtiene todas las categorías de herramientas.
    
    Returns:
        Lista de ToolCategory ordenada
    """
    return TOOL_CATEGORIES
