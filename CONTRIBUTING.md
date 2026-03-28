# Contributing to SafeTool Pix

Thank you for your interest in contributing to SafeTool Pix! This guide will help you get started.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

1. Check the [existing issues](https://github.com/safetoolhub/safetool-pix/issues) to avoid duplicates.
2. Open a new issue using the **Bug Report** template.
3. Include your OS, app version, and clear steps to reproduce the problem.

### Suggesting Features

1. Open a new issue using the **Feature Request** template.
2. Describe the use case and why it would benefit users.

### Submitting Pull Requests

1. **Fork** the repository and create a branch from `main`.
2. Make your changes following the [code standards](#code-standards) below.
3. Add or update tests as needed.
4. Ensure all tests pass: `pytest --ignore=tests/performance`
5. Submit your PR with a clear description of the changes.

> **Note**: Only the maintainer can merge pull requests. All contributions are reviewed before merging.

## Development Setup

```bash
git clone https://github.com/safetoolhub/safetool-pix.git
cd safetool-pix

uv venv --python 3.12
source .venv/bin/activate   # Linux/macOS

uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt

# Run tests
pytest --ignore=tests/performance

# Run the app
python main.py
```

## Code Standards

### Style

- **PEP 8** compliance
- **Type hints** on all public functions and methods
- **Docstrings** for classes and non-trivial functions
- Use `black` for formatting and `isort` for import ordering

### Architecture Rules

- **Services** (`services/`) contain business logic only — **no PyQt6 imports**.
- **UI code** (`ui/`) handles rendering and user interaction only.
- All service outputs must be **dataclasses** (never dicts or tuples) — see `services/result_types.py`.
- Use the singleton `FileInfoRepositoryCache.get_instance()` — never pass the repository as a parameter.

### Internationalization (i18n)

All user-facing strings must use the `tr()` function:

```python
from utils.i18n import tr

title = tr("tools.zero_byte.title")
message = tr("services.error.directory_not_found", path="/tmp/foo")
```

When adding new strings:
1. Add the key to `i18n/es.json` (Spanish, base language).
2. Add the translation to `i18n/en.json`.
3. Run `python dev-tools/validate_translations.py` to verify.

### Testing

- Write tests for all new services and utilities.
- Follow the pattern: `test_<behavior>_when_<condition>` or `test_<behavior>_<scenario>`.
- Tests must run offline — mock all external I/O.
- Unit tests should complete in milliseconds.

### Logging

- Use `get_logger('ModuleName')` — never `print()`.
- Log messages are always in **English** (logs are for developers).
- User-facing progress messages use `tr()`.

### Commit Messages

Use clear, descriptive commit messages:

```
Add visual similarity threshold slider to settings

- Add slider widget to settings dialog
- Connect slider value to DuplicatesSimilarService config
- Add translation keys for slider labels
- Add unit tests for threshold validation
```

## What Not to Do

- Don't add cloud connectivity, telemetry, or any external network calls.
- Don't add dependencies without discussion — the app is 100% offline.
- Don't use bare `except: pass` — always handle or log errors.
- Don't use `print()` — use the logging system.

## Questions?

Open an issue or contact us at safetoolhub@protonmail.com.

---

Thank you for helping make SafeTool Pix better! 🙏
