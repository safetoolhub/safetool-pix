# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
#!/usr/bin/env python3
"""
Translation validation script for SafeTool Pix i18n.

Compares all JSON translation files to find:
- Missing keys (present in one file but not another)
- Extra keys (present in one file but not in the base)
- Placeholder mismatches ({count}, {size}, etc.)
- Empty values

Usage:
    python dev-tools/validate_translations.py
"""

import json
import re
import sys
from pathlib import Path


I18N_DIR = Path(__file__).parent.parent / "i18n"
BASE_LANGUAGE = "es"
PLACEHOLDER_PATTERN = re.compile(r'\{(\w+)(?::[^}]*)?\}')


def flatten_dict(d: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested dict to dotted keys."""
    result = {}
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten_dict(value, full_key))
        else:
            result[full_key] = str(value)
    return result


def extract_placeholders(text: str) -> set[str]:
    """Extract placeholder names from a translation string."""
    return set(PLACEHOLDER_PATTERN.findall(text))


def load_translation(lang: str) -> dict[str, str]:
    """Load and flatten a translation file."""
    path = I18N_DIR / f"{lang}.json"
    if not path.exists():
        print(f"ERROR: Translation file not found: {path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return flatten_dict(data)


def validate() -> int:
    """Run all validations. Returns number of issues found."""
    issues = 0

    # Find all language files
    lang_files = sorted(I18N_DIR.glob("*.json"))
    if not lang_files:
        print("ERROR: No translation files found in i18n/")
        return 1

    languages = [f.stem for f in lang_files]
    print(f"Found {len(languages)} languages: {', '.join(languages)}")
    print()

    # Load base language
    base = load_translation(BASE_LANGUAGE)
    base_keys = set(base.keys())
    print(f"Base language ({BASE_LANGUAGE}): {len(base_keys)} keys")

    # Check for empty values in base
    empty_base = [k for k, v in base.items() if not v.strip()]
    if empty_base:
        print(f"\n[WARNING] Empty values in {BASE_LANGUAGE}.json:")
        for k in sorted(empty_base):
            print(f"  - {k}")
            issues += 1

    # Compare each language against base
    for lang in languages:
        if lang == BASE_LANGUAGE:
            continue

        print(f"\n--- Checking {lang}.json ---")
        target = load_translation(lang)
        target_keys = set(target.keys())

        # Missing keys
        missing = base_keys - target_keys
        if missing:
            print(f"\n[ERROR] Missing keys in {lang}.json ({len(missing)}):")
            for k in sorted(missing):
                print(f"  - {k}")
                issues += 1
        else:
            print(f"[OK] No missing keys")

        # Extra keys
        extra = target_keys - base_keys
        if extra:
            print(f"\n[WARNING] Extra keys in {lang}.json (not in {BASE_LANGUAGE}): ({len(extra)})")
            for k in sorted(extra):
                print(f"  + {k}")
                issues += 1
        else:
            print(f"[OK] No extra keys")

        # Placeholder mismatches
        placeholder_issues = []
        for key in base_keys & target_keys:
            base_ph = extract_placeholders(base[key])
            target_ph = extract_placeholders(target[key])
            if base_ph != target_ph:
                placeholder_issues.append((key, base_ph, target_ph))

        if placeholder_issues:
            print(f"\n[ERROR] Placeholder mismatches ({len(placeholder_issues)}):")
            for key, base_ph, target_ph in sorted(placeholder_issues):
                print(f"  {key}:")
                print(f"    {BASE_LANGUAGE}: {base_ph}")
                print(f"    {lang}: {target_ph}")
                issues += 1
        else:
            print(f"[OK] All placeholders match")

        # Empty values
        empty = [k for k in target_keys & base_keys if not target[k].strip()]
        if empty:
            print(f"\n[WARNING] Empty values in {lang}.json ({len(empty)}):")
            for k in sorted(empty):
                print(f"  - {k}")
                issues += 1
        else:
            print(f"[OK] No empty values")

    # Summary
    print("\n" + "=" * 50)
    if issues == 0:
        print("[OK] All translations are valid!")
    else:
        print(f"[ERROR] Found {issues} issue(s)")
    print("=" * 50)

    return issues


if __name__ == "__main__":
    issues = validate()
    sys.exit(1 if issues > 0 else 0)
