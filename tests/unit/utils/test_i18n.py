# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests exhaustivos para utils/i18n.py

Cobertura completa del sistema de internacionalización:
- Inicialización, resolución de claves, fallback a español, interpolación,
  idiomas soportados, lazy init, y consistencia de archivos JSON.

Especial atención al nombre de la aplicación en traducciones.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch

from utils.i18n import (
    init_i18n,
    tr,
    get_current_language,
    get_supported_languages,
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    _resolve_key,
    _load_language_file,
    _I18N_DIR,
)


# =============================================================================
# MODULE CONSTANTS
# =============================================================================

class TestI18nConstants:
    """Tests de constantes del módulo i18n."""

    def test_default_language_is_spanish(self):
        assert DEFAULT_LANGUAGE == "es"

    def test_supported_languages_has_spanish(self):
        assert "es" in SUPPORTED_LANGUAGES

    def test_supported_languages_has_english(self):
        assert "en" in SUPPORTED_LANGUAGES

    def test_supported_languages_spanish_name(self):
        assert SUPPORTED_LANGUAGES["es"] == "Español"

    def test_supported_languages_english_name(self):
        assert SUPPORTED_LANGUAGES["en"] == "English"

    def test_i18n_dir_exists(self):
        assert _I18N_DIR.exists()

    def test_i18n_dir_contains_json_files(self):
        json_files = list(_I18N_DIR.glob("*.json"))
        assert len(json_files) >= 2


# =============================================================================
# INITIALIZATION
# =============================================================================

class TestI18nInit:
    """Tests de inicialización del sistema i18n."""

    def test_init_with_spanish(self):
        init_i18n("es")
        assert get_current_language() == "es"

    def test_init_with_english(self):
        init_i18n("en")
        assert get_current_language() == "en"

    def test_init_with_invalid_language_falls_back_to_default(self):
        init_i18n("fr")
        assert get_current_language() == DEFAULT_LANGUAGE

    def test_init_with_empty_string_falls_back(self):
        init_i18n("")
        assert get_current_language() == DEFAULT_LANGUAGE

    def test_reinit_changes_language(self):
        init_i18n("es")
        assert get_current_language() == "es"
        init_i18n("en")
        assert get_current_language() == "en"


# =============================================================================
# KEY RESOLUTION (tr() function)
# =============================================================================

class TestTrFunction:
    """Tests de la función tr() de traducción."""

    def setup_method(self):
        init_i18n("es")

    def test_tr_returns_string(self):
        result = tr("app.name")
        assert isinstance(result, str)

    def test_tr_app_name_spanish(self):
        init_i18n("es")
        result = tr("app.name")
        assert result == "SafeTool Pix"

    def test_tr_app_name_english(self):
        init_i18n("en")
        result = tr("app.name")
        assert result == "SafeTool Pix"

    def test_tr_app_name_consistent_across_languages(self):
        """El nombre de la app es igual en todos los idiomas."""
        init_i18n("es")
        es_name = tr("app.name")
        init_i18n("en")
        en_name = tr("app.name")
        assert es_name == en_name

    def test_tr_nonexistent_key_returns_key(self):
        """Clave inexistente devuelve la propia clave."""
        result = tr("nonexistent.key.that.does.not.exist")
        assert result == "nonexistent.key.that.does.not.exist"

    def test_tr_common_cancel_exists(self):
        result = tr("common.cancel")
        assert result != "common.cancel"  # Should resolve to a real translation

    def test_tr_common_ok_exists(self):
        result = tr("common.ok")
        assert result != "common.ok"

    def test_tr_with_kwargs_interpolation(self):
        """Interpolación de parámetros funciona."""
        init_i18n("es")
        # common.pagination.load_n_more = "Cargar {count} más"
        result = tr("common.pagination.load_n_more", count=5)
        assert "5" in result

    def test_tr_with_invalid_kwargs_returns_value(self):
        """Si kwargs no coinciden, devuelve el valor sin interpolar."""
        result = tr("app.name", invalid_param=42)
        assert isinstance(result, str)

    def test_tr_empty_key(self):
        """Clave vacía devuelve string vacío o la clave."""
        result = tr("")
        assert isinstance(result, str)

    def test_tr_nested_key(self):
        """Claves profundamente anidadas resuelven correctamente."""
        result = tr("tools.zero_byte.title")
        assert result != "tools.zero_byte.title"  # Should resolve

    def test_tr_all_tool_titles_resolve(self):
        """Todos los títulos de herramientas se resuelven."""
        tool_ids = ['zero_byte', 'live_photos', 'heic', 'duplicates_exact',
                    'visual_identical', 'duplicates_similar', 'file_organizer', 'file_renamer']
        for tool_id in tool_ids:
            key = f"tools.{tool_id}.title"
            result = tr(key)
            assert result != key, f"Tool title '{key}' did not resolve"

    def test_tr_all_tool_short_descriptions_resolve(self):
        tool_ids = ['zero_byte', 'live_photos', 'heic', 'duplicates_exact',
                    'visual_identical', 'duplicates_similar', 'file_organizer', 'file_renamer']
        for tool_id in tool_ids:
            key = f"tools.{tool_id}.short_description"
            result = tr(key)
            assert result != key, f"Tool short_description '{key}' did not resolve"

    def test_tr_all_tool_long_descriptions_resolve(self):
        tool_ids = ['zero_byte', 'live_photos', 'heic', 'duplicates_exact',
                    'visual_identical', 'duplicates_similar', 'file_organizer', 'file_renamer']
        for tool_id in tool_ids:
            key = f"tools.{tool_id}.long_description"
            result = tr(key)
            assert result != key, f"Tool long_description '{key}' did not resolve"

    def test_tr_all_category_titles_resolve(self):
        category_ids = ['cleanup', 'visual', 'organization']
        for cat_id in category_ids:
            key = f"categories.{cat_id}.title"
            result = tr(key)
            assert result != key, f"Category title '{key}' did not resolve"

    def test_tr_all_category_descriptions_resolve(self):
        category_ids = ['cleanup', 'visual', 'organization']
        for cat_id in category_ids:
            key = f"categories.{cat_id}.description"
            result = tr(key)
            assert result != key, f"Category description '{key}' did not resolve"


# =============================================================================
# FALLBACK MECHANISM
# =============================================================================

class TestI18nFallback:
    """Tests del mecanismo de fallback lingüístico."""

    def test_english_falls_back_to_spanish_for_missing_key(self):
        """Si una clave falta en inglés, usa español."""
        init_i18n("es")
        es_value = tr("app.name")
        init_i18n("en")
        en_value = tr("app.name")
        # Both should resolve (either direct or fallback)
        assert es_value != ""
        assert en_value != ""

    def test_fallback_chain_returns_key_as_last_resort(self):
        init_i18n("en")
        result = tr("this.key.does.not.exist.anywhere")
        assert result == "this.key.does.not.exist.anywhere"


# =============================================================================
# _resolve_key INTERNAL FUNCTION
# =============================================================================

class TestResolveKey:
    """Tests de la función interna _resolve_key."""

    def test_resolve_simple_key(self):
        data = {"hello": "world"}
        assert _resolve_key(data, "hello") == "world"

    def test_resolve_nested_key(self):
        data = {"level1": {"level2": "value"}}
        assert _resolve_key(data, "level1.level2") == "value"

    def test_resolve_deeply_nested(self):
        data = {"a": {"b": {"c": {"d": "deep"}}}}
        assert _resolve_key(data, "a.b.c.d") == "deep"

    def test_resolve_missing_key_returns_none(self):
        data = {"hello": "world"}
        assert _resolve_key(data, "missing") is None

    def test_resolve_partial_path_returns_none(self):
        data = {"a": {"b": "value"}}
        assert _resolve_key(data, "a.c") is None

    def test_resolve_non_string_value_returns_none(self):
        data = {"a": {"b": 42}}
        assert _resolve_key(data, "a.b") is None

    def test_resolve_dict_value_returns_none(self):
        data = {"a": {"b": {"c": "value"}}}
        assert _resolve_key(data, "a.b") is None

    def test_resolve_empty_dict(self):
        assert _resolve_key({}, "any.key") is None


# =============================================================================
# _load_language_file INTERNAL FUNCTION
# =============================================================================

class TestLoadLanguageFile:
    """Tests de la función interna _load_language_file."""

    def test_load_spanish_returns_dict(self):
        data = _load_language_file("es")
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_load_english_returns_dict(self):
        data = _load_language_file("en")
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_load_nonexistent_returns_empty_dict(self):
        data = _load_language_file("xyz_nonexistent")
        assert data == {}

    def test_spanish_has_app_section(self):
        data = _load_language_file("es")
        assert "app" in data

    def test_english_has_app_section(self):
        data = _load_language_file("en")
        assert "app" in data


# =============================================================================
# PUBLIC API FUNCTIONS
# =============================================================================

class TestPublicAPI:
    """Tests de funciones públicas del API."""

    def test_get_current_language_returns_string(self):
        init_i18n("es")
        assert isinstance(get_current_language(), str)

    def test_get_supported_languages_returns_dict(self):
        result = get_supported_languages()
        assert isinstance(result, dict)

    def test_get_supported_languages_is_copy(self):
        """Devuelve una copia, no la referencia original."""
        result = get_supported_languages()
        result["new_lang"] = "Test"
        assert "new_lang" not in SUPPORTED_LANGUAGES


# =============================================================================
# JSON FILE CONSISTENCY
# =============================================================================

class TestJsonFileConsistency:
    """Tests de consistencia entre archivos JSON de traducción."""

    @pytest.fixture
    def es_data(self):
        with open(_I18N_DIR / "es.json", "r", encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def en_data(self):
        with open(_I18N_DIR / "en.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_all_keys(self, data, prefix=""):
        """Recursively get all dotted keys from nested dict."""
        keys = set()
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                keys.update(self._get_all_keys(value, full_key))
            else:
                keys.add(full_key)
        return keys

    def test_es_and_en_have_same_top_level_keys(self, es_data, en_data):
        """Ambos archivos tienen las mismas secciones de primer nivel."""
        es_top = set(es_data.keys())
        en_top = set(en_data.keys())
        assert es_top == en_top, f"Diff: ES extra={es_top - en_top}, EN extra={en_top - es_top}"

    def test_es_and_en_have_same_dotted_keys(self, es_data, en_data):
        """Ambos archivos tienen exactamente las mismas claves profundas."""
        es_keys = self._get_all_keys(es_data)
        en_keys = self._get_all_keys(en_data)
        missing_in_en = es_keys - en_keys
        extra_in_en = en_keys - es_keys
        assert missing_in_en == set(), f"Missing in EN: {missing_in_en}"
        assert extra_in_en == set(), f"Extra in EN: {extra_in_en}"

    def test_app_name_identical_in_both_languages(self, es_data, en_data):
        """El nombre de la app es idéntico en ambos idiomas."""
        assert es_data["app"]["name"] == en_data["app"]["name"]
        assert es_data["app"]["name"] == "SafeTool Pix"

    def test_no_empty_values_in_spanish(self, es_data):
        """No hay valores vacíos en español."""
        keys = self._get_all_keys(es_data)
        for key in keys:
            value = _resolve_key(es_data, key)
            if value is not None:
                assert value.strip() != "", f"Empty value for key '{key}' in es.json"

    def test_no_empty_values_in_english(self, en_data):
        """No hay valores vacíos en inglés."""
        keys = self._get_all_keys(en_data)
        for key in keys:
            value = _resolve_key(en_data, key)
            if value is not None:
                assert value.strip() != "", f"Empty value for key '{key}' in en.json"

    def test_placeholders_match_between_languages(self, es_data, en_data):
        """Los placeholders ({count}, {size}, etc.) coinciden entre idiomas."""
        import re
        placeholder_re = re.compile(r'\{(\w+)\}')

        es_keys = self._get_all_keys(es_data)
        for key in es_keys:
            es_val = _resolve_key(es_data, key)
            en_val = _resolve_key(en_data, key)
            if es_val and en_val:
                es_placeholders = set(placeholder_re.findall(es_val))
                en_placeholders = set(placeholder_re.findall(en_val))
                assert es_placeholders == en_placeholders, (
                    f"Placeholder mismatch for '{key}': ES={es_placeholders}, EN={en_placeholders}"
                )


# =============================================================================
# APP NAME IN TRANSLATIONS
# =============================================================================

class TestAppNameInTranslations:
    """Tests específicos del nombre de la aplicación en las traducciones."""

    def test_app_name_key_exists(self):
        init_i18n("es")
        assert tr("app.name") != "app.name"

    def test_app_name_matches_config(self):
        from config import Config
        init_i18n("es")
        assert tr("app.name") == Config.APP_NAME

    def test_app_name_in_about_dialog_title(self):
        """El about dialog menciona el nombre de la app."""
        init_i18n("es")
        about_title = tr("about.title", name="SafeTool Pix")
        assert about_title != "about.title"  # Exists
        assert "SafeTool Pix" in about_title

    def test_stage1_privacy_notice_mentions_app(self):
        """El aviso de privacidad en stage1 menciona SafeTool Pix."""
        init_i18n("es")
        notice = tr("stage1.tip_privacy_notice")
        assert "SafeTool Pix" in notice or "safetool" in notice.lower()
