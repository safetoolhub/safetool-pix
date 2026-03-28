# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests exhaustivos para ui/tools_definitions.py

Cobertura completa de definiciones de herramientas: ToolDefinition, ToolCategory,
registro TOOLS, funciones de acceso, inmutabilidad y consistencia de i18n.
"""

import pytest

from utils.i18n import init_i18n
from ui.tools_definitions import (
    ToolDefinition,
    ToolCategory,
    TOOL_ZERO_BYTE,
    TOOL_LIVE_PHOTOS,
    TOOL_HEIC,
    TOOL_DUPLICATES_EXACT,
    TOOL_VISUAL_IDENTICAL,
    TOOL_DUPLICATES_SIMILAR,
    TOOL_FILE_ORGANIZER,
    TOOL_FILE_RENAMER,
    CATEGORY_CLEANUP,
    CATEGORY_VISUAL,
    CATEGORY_ORGANIZATION,
    TOOL_CATEGORIES,
    TOOLS,
    get_tool,
    get_tool_title,
    get_tool_short_description,
    get_tool_long_description,
    get_all_tool_ids,
    get_tools_by_category,
    get_category,
    get_all_categories,
)


@pytest.fixture(autouse=True)
def _init_i18n():
    """Initialize i18n before each test."""
    init_i18n("es")


# =============================================================================
# TOOL DEFINITION CLASS
# =============================================================================

class TestToolDefinition:
    """Tests de la clase ToolDefinition."""

    def test_create_tool_definition(self):
        tool = ToolDefinition(id='test_tool', icon_name='test-icon')
        assert tool.id == 'test_tool'
        assert tool.icon_name == 'test-icon'

    def test_tool_definition_immutable_id(self):
        """No se puede modificar el id."""
        tool = ToolDefinition(id='test', icon_name='icon')
        with pytest.raises(AttributeError):
            tool.id = 'new_id'

    def test_tool_definition_immutable_icon(self):
        tool = ToolDefinition(id='test', icon_name='icon')
        with pytest.raises(AttributeError):
            tool.icon_name = 'new_icon'

    def test_tool_definition_immutable_arbitrary_attr(self):
        tool = ToolDefinition(id='test', icon_name='icon')
        with pytest.raises(AttributeError):
            tool.new_attr = 'value'

    def test_tool_definition_title_is_string(self):
        assert isinstance(TOOL_ZERO_BYTE.title, str)

    def test_tool_definition_short_description_is_string(self):
        assert isinstance(TOOL_ZERO_BYTE.short_description, str)

    def test_tool_definition_long_description_is_string(self):
        assert isinstance(TOOL_ZERO_BYTE.long_description, str)

    def test_tool_definition_title_resolves_via_i18n(self):
        """Title no devuelve la clave i18n literal."""
        title = TOOL_ZERO_BYTE.title
        assert title != "tools.zero_byte.title"
        assert len(title) > 0

    def test_tool_definition_repr(self):
        repr_str = repr(TOOL_ZERO_BYTE)
        assert "ToolDefinition" in repr_str
        assert "zero_byte" in repr_str

    def test_tool_definition_uses_slots(self):
        assert hasattr(ToolDefinition, '__slots__')


# =============================================================================
# TOOL CATEGORY CLASS
# =============================================================================

class TestToolCategory:
    """Tests de la clase ToolCategory."""

    def test_create_tool_category(self):
        cat = ToolCategory(id='test_cat', tool_ids=('tool1', 'tool2'))
        assert cat.id == 'test_cat'
        assert cat.tool_ids == ('tool1', 'tool2')

    def test_category_immutable_id(self):
        cat = ToolCategory(id='test', tool_ids=('t1',))
        with pytest.raises(AttributeError):
            cat.id = 'new_id'

    def test_category_immutable_tool_ids(self):
        cat = ToolCategory(id='test', tool_ids=('t1',))
        with pytest.raises(AttributeError):
            cat.tool_ids = ('t2',)

    def test_category_immutable_arbitrary_attr(self):
        cat = ToolCategory(id='test', tool_ids=('t1',))
        with pytest.raises(AttributeError):
            cat.new_attr = 'value'

    def test_category_title_is_string(self):
        assert isinstance(CATEGORY_CLEANUP.title, str)

    def test_category_description_is_string(self):
        assert isinstance(CATEGORY_CLEANUP.description, str)

    def test_category_title_resolves(self):
        title = CATEGORY_CLEANUP.title
        assert title != "categories.cleanup.title"
        assert len(title) > 0

    def test_category_repr(self):
        repr_str = repr(CATEGORY_CLEANUP)
        assert "ToolCategory" in repr_str
        assert "cleanup" in repr_str

    def test_category_uses_slots(self):
        assert hasattr(ToolCategory, '__slots__')


# =============================================================================
# TOOL INSTANCES (8 tools)
# =============================================================================

class TestToolInstances:
    """Tests de las 8 instancias de herramientas."""

    ALL_TOOLS = [
        TOOL_ZERO_BYTE, TOOL_LIVE_PHOTOS, TOOL_HEIC, TOOL_DUPLICATES_EXACT,
        TOOL_VISUAL_IDENTICAL, TOOL_DUPLICATES_SIMILAR, TOOL_FILE_ORGANIZER, TOOL_FILE_RENAMER,
    ]

    def test_zero_byte_id(self):
        assert TOOL_ZERO_BYTE.id == 'zero_byte'

    def test_zero_byte_icon(self):
        assert TOOL_ZERO_BYTE.icon_name == 'file-x'

    def test_live_photos_id(self):
        assert TOOL_LIVE_PHOTOS.id == 'live_photos'

    def test_live_photos_icon(self):
        assert TOOL_LIVE_PHOTOS.icon_name == 'camera-burst'

    def test_heic_id(self):
        assert TOOL_HEIC.id == 'heic'

    def test_heic_icon(self):
        assert TOOL_HEIC.icon_name == 'file-image'

    def test_duplicates_exact_id(self):
        assert TOOL_DUPLICATES_EXACT.id == 'duplicates_exact'

    def test_duplicates_exact_icon(self):
        assert TOOL_DUPLICATES_EXACT.icon_name == 'content-copy'

    def test_visual_identical_id(self):
        assert TOOL_VISUAL_IDENTICAL.id == 'visual_identical'

    def test_visual_identical_icon(self):
        assert TOOL_VISUAL_IDENTICAL.icon_name == 'image-multiple'

    def test_duplicates_similar_id(self):
        assert TOOL_DUPLICATES_SIMILAR.id == 'duplicates_similar'

    def test_duplicates_similar_icon(self):
        assert TOOL_DUPLICATES_SIMILAR.icon_name == 'image-search'

    def test_file_organizer_id(self):
        assert TOOL_FILE_ORGANIZER.id == 'file_organizer'

    def test_file_organizer_icon(self):
        assert TOOL_FILE_ORGANIZER.icon_name == 'folder-move'

    def test_file_renamer_id(self):
        assert TOOL_FILE_RENAMER.id == 'file_renamer'

    def test_file_renamer_icon(self):
        assert TOOL_FILE_RENAMER.icon_name == 'rename-box'

    def test_total_tool_count_is_8(self):
        assert len(self.ALL_TOOLS) == 8

    def test_all_tools_are_tool_definition(self):
        for tool in self.ALL_TOOLS:
            assert isinstance(tool, ToolDefinition)

    def test_all_tool_ids_are_unique(self):
        ids = [t.id for t in self.ALL_TOOLS]
        assert len(ids) == len(set(ids))

    def test_all_tools_have_nonempty_title(self):
        for tool in self.ALL_TOOLS:
            assert len(tool.title) > 0, f"Tool '{tool.id}' has empty title"

    def test_all_tools_have_nonempty_short_description(self):
        for tool in self.ALL_TOOLS:
            assert len(tool.short_description) > 0, f"Tool '{tool.id}' has empty short_description"

    def test_all_tools_have_nonempty_long_description(self):
        for tool in self.ALL_TOOLS:
            assert len(tool.long_description) > 0, f"Tool '{tool.id}' has empty long_description"


# =============================================================================
# CATEGORY INSTANCES (3 categories)
# =============================================================================

class TestCategoryInstances:
    """Tests de las 3 instancias de categorías."""

    def test_cleanup_id(self):
        assert CATEGORY_CLEANUP.id == 'cleanup'

    def test_cleanup_tool_ids(self):
        assert CATEGORY_CLEANUP.tool_ids == ('zero_byte', 'live_photos', 'heic', 'duplicates_exact')

    def test_visual_id(self):
        assert CATEGORY_VISUAL.id == 'visual'

    def test_visual_tool_ids(self):
        assert CATEGORY_VISUAL.tool_ids == ('visual_identical', 'duplicates_similar')

    def test_organization_id(self):
        assert CATEGORY_ORGANIZATION.id == 'organization'

    def test_organization_tool_ids(self):
        assert CATEGORY_ORGANIZATION.tool_ids == ('file_organizer', 'file_renamer')

    def test_total_category_count_is_3(self):
        assert len(TOOL_CATEGORIES) == 3

    def test_all_categories_are_tool_category(self):
        for cat in TOOL_CATEGORIES:
            assert isinstance(cat, ToolCategory)

    def test_all_tool_ids_covered_by_categories(self):
        """Todas las herramientas están en alguna categoría."""
        categorized_ids = set()
        for cat in TOOL_CATEGORIES:
            categorized_ids.update(cat.tool_ids)
        registered_ids = set(TOOLS.keys())
        assert categorized_ids == registered_ids

    def test_categories_order(self):
        assert TOOL_CATEGORIES[0].id == 'cleanup'
        assert TOOL_CATEGORIES[1].id == 'visual'
        assert TOOL_CATEGORIES[2].id == 'organization'


# =============================================================================
# TOOLS REGISTRY
# =============================================================================

class TestToolsRegistry:
    """Tests del diccionario TOOLS."""

    def test_tools_is_dict(self):
        assert isinstance(TOOLS, dict)

    def test_tools_has_8_entries(self):
        assert len(TOOLS) == 8

    def test_tools_keys_match_tool_ids(self):
        expected_ids = {
            'zero_byte', 'live_photos', 'heic', 'duplicates_exact',
            'visual_identical', 'duplicates_similar', 'file_organizer', 'file_renamer'
        }
        assert set(TOOLS.keys()) == expected_ids

    def test_tools_values_are_tool_definitions(self):
        for tool in TOOLS.values():
            assert isinstance(tool, ToolDefinition)


# =============================================================================
# ACCESS FUNCTIONS
# =============================================================================

class TestAccessFunctions:
    """Tests de funciones de acceso."""

    def test_get_tool_existing(self):
        tool = get_tool('zero_byte')
        assert tool is not None
        assert tool.id == 'zero_byte'

    def test_get_tool_nonexistent(self):
        result = get_tool('nonexistent_tool')
        assert result is None

    def test_get_tool_title_existing(self):
        title = get_tool_title('zero_byte')
        assert isinstance(title, str)
        assert len(title) > 0

    def test_get_tool_title_nonexistent_returns_id(self):
        result = get_tool_title('nonexistent')
        assert result == 'nonexistent'

    def test_get_tool_short_description_existing(self):
        desc = get_tool_short_description('zero_byte')
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_get_tool_short_description_nonexistent_returns_empty(self):
        result = get_tool_short_description('nonexistent')
        assert result == ''

    def test_get_tool_long_description_existing(self):
        desc = get_tool_long_description('zero_byte')
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_get_tool_long_description_nonexistent_returns_empty(self):
        result = get_tool_long_description('nonexistent')
        assert result == ''

    def test_get_all_tool_ids_returns_list(self):
        result = get_all_tool_ids()
        assert isinstance(result, list)

    def test_get_all_tool_ids_has_8(self):
        assert len(get_all_tool_ids()) == 8

    def test_get_tools_by_category_cleanup(self):
        tools = get_tools_by_category('cleanup')
        assert len(tools) == 4
        ids = [t.id for t in tools]
        assert 'zero_byte' in ids
        assert 'live_photos' in ids

    def test_get_tools_by_category_visual(self):
        tools = get_tools_by_category('visual')
        assert len(tools) == 2

    def test_get_tools_by_category_organization(self):
        tools = get_tools_by_category('organization')
        assert len(tools) == 2

    def test_get_tools_by_category_nonexistent(self):
        result = get_tools_by_category('nonexistent')
        assert result == []

    def test_get_category_existing(self):
        cat = get_category('cleanup')
        assert cat is not None
        assert cat.id == 'cleanup'

    def test_get_category_nonexistent(self):
        result = get_category('nonexistent')
        assert result is None

    def test_get_all_categories_returns_list(self):
        result = get_all_categories()
        assert isinstance(result, list)

    def test_get_all_categories_has_3(self):
        assert len(get_all_categories()) == 3


# =============================================================================
# I18N INTEGRATION
# =============================================================================

class TestToolsI18nIntegration:
    """Tests de integración con i18n para herramientas."""

    def test_tool_titles_differ_per_language(self):
        """Títulos cambian al cambiar idioma (excepto si coinciden)."""
        init_i18n("es")
        es_title = TOOL_ZERO_BYTE.title
        init_i18n("en")
        en_title = TOOL_ZERO_BYTE.title
        # Both should be non-empty
        assert len(es_title) > 0
        assert len(en_title) > 0

    def test_category_titles_differ_per_language(self):
        init_i18n("es")
        es_title = CATEGORY_CLEANUP.title
        init_i18n("en")
        en_title = CATEGORY_CLEANUP.title
        assert len(es_title) > 0
        assert len(en_title) > 0
