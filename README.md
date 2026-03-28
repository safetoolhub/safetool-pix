<p align="center">
  <img src="assets/icon.png" alt="SafeTool Pix" width="128" height="128">
</p>

<h1 align="center">SafeTool Pix</h1>

<p align="center">
  <strong>Privacy-first photo & video management. 100% local, no cloud.</strong>
</p>

<p align="center">
  <a href="https://github.com/safetoolhub/safetool-pix/releases"><img src="https://img.shields.io/github/v/release/safetoolhub/safetool-pix?include_prereleases&label=version&color=blue" alt="Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPLv3-green" alt="License GPLv3"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey" alt="Platforms">
  <img src="https://img.shields.io/badge/privacy-100%25%20offline-brightgreen" alt="100% Offline">
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#build-from-source">Build from Source</a> •
  <a href="#license">License</a> •
  <a href="#español">Español</a>
</p>

---

## What is SafeTool Pix?

SafeTool Pix is a desktop application for managing, organizing, and optimizing photo and video collections with **absolute privacy**. All processing happens 100% locally on your machine — no cloud, no telemetry, no external connections. Ever.

## Features

### 🧹 Cleanup & Space

| Tool | Description |
|------|-------------|
| **Zero-byte files** | Detect and safely remove empty (0-byte) files |
| **Live Photos** | Find iPhone Live Photo pairs (image + MOV) and choose what to keep |
| **HEIC/JPG duplicates** | Identify HEIC/JPG duplicate pairs from iPhone conversions |
| **Exact copies** | Find 100% identical files using SHA256 hash comparison |

### 🔍 Visual Detection

| Tool | Description |
|------|-------------|
| **Visually identical** | Detect images that look exactly the same using perceptual hashing |
| **Similar files** | Find 70–95% similar images (edits, crops, different resolutions) with an adjustable sensitivity slider |

### 📁 Organization

| Tool | Description |
|------|-------------|
| **Smart organizer** | Reorganize files into a clean date-based folder structure |
| **Complete renamer** | Standardize filenames to `YYYYMMDD_HHMMSS_TYPE.ext` format |

### Core Principles

- **🔒 Privacy First** — All operations are offline and local. No data ever leaves your machine.
- **💾 Backup-First Policy** — Every destructive operation offers backup creation and dry-run simulation before making changes.
- **🌍 Multilingual** — Full Spanish and English interface (898+ translation keys).
- **🖥️ Cross-Platform** — Native experience on Linux, Windows, and macOS.

## Installation

Download the latest release for your platform from the [Releases page](https://github.com/safetoolhub/safetool-pix/releases).

| Platform | Format | Notes |
|----------|--------|-------|
| **Linux** | `.deb`, `.rpm`, `appImage`, `flatpak`| All |
| **Windows** | `.exe` installer | Windows 10/11 |
| **macOS** | `.dmg` | macOS 12+ |

### Linux .deb

```bash
# Debian/Ubuntu
sudo dpkg -i safetool-pix_0.9-beta_amd64.deb
```

### Linux .rpm

```bash
# Fedora/RHEL
sudo rpm -i safetool-pix-0.9.beta-1.x86_64.rpm
```

### Linux AppImage

Download the `.AppImage` file, make it executable, and run:

```bash
chmod +x safetool-pix_0.9-beta.AppImage
./safetool-pix_0.9-beta.AppImage
```

### Linux Flatpak

```bash
# Install from the provided .flatpakref file
flatpak install safetool-pix.flatpakref

# Or from Flathub (if available)
flatpak install flathub org.safetoolhub.safetoolpix
```

**Security Note**: Your system may warn that SafeTool Pix is from an unknown developer or untrusted source. This is normal for open-source software. SafeTool Pix is completely safe and open-source — you can verify the code on GitHub.

### Windows

Run the installer and follow the setup wizard. A Start Menu shortcut will be created automatically.

### macOS

Open the `.dmg` file and drag SafeTool Pix to your Applications folder.

## Build from Source

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Setup

```bash
git clone https://github.com/safetoolhub/safetool-pix.git
cd safetool-pix

# Create virtual environment
uv venv --python 3.12
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Install dependencies
uv pip install -r requirements.txt

# Run the application
python main.py
```

### Running Tests

```bash
uv pip install -r requirements-dev.txt
pytest --ignore=tests/performance
```

### Optional System Tools

Some video analysis features require external tools:

- **ffprobe** (from FFmpeg) — for video metadata extraction
- **exiftool** — for advanced EXIF reading

These are optional. The application works fully without them but will skip video metadata phases during scanning.

## Tech Stack

- **Language**: Python 3.12+
- **UI Framework**: PyQt6
- **Testing**: pytest (713+ tests)
- **Architecture**: Strict UI/logic separation — services are PyQt6-free for future portability

## Contributing

Contributions are welcome! Please read the [Contributing Guide](CONTRIBUTING.md) before submitting a pull request.

## License

SafeTool Pix is licensed under the [GNU General Public License v3.0](LICENSE) with additional attribution requirements under Section 7:

- **Attribution Required**: Any derivative work must retain visible attribution to [SafeToolHub](https://safetoolhub.org) with a clickable link.
- See [LICENSE](LICENSE) for full details.

## Links

- **Website**: [safetoolhub.org](https://safetoolhub.org)
- **Releases**: [GitHub Releases](https://github.com/safetoolhub/safetool-pix/releases)
- **Issues**: [Report a bug](https://github.com/safetoolhub/safetool-pix/issues)

---

## Español

### ¿Qué es SafeTool Pix?

SafeTool Pix es una aplicación de escritorio para gestionar, organizar y optimizar colecciones de fotos y vídeos con **privacidad absoluta**. Todo el procesamiento ocurre 100% en local en tu máquina — sin nube, sin telemetría, sin conexiones externas. Nunca.

### Características

#### 🧹 Limpieza y espacio

| Herramienta | Descripción |
|-------------|-------------|
| **Archivos de cero bytes** | Detecta y elimina de forma segura archivos vacíos (0 bytes) |
| **Live Photos** | Encuentra pares de Live Photos de iPhone (imagen + MOV) y elige qué mantener |
| **Duplicados HEIC/JPG** | Identifica pares duplicados HEIC/JPG de conversiones de iPhone |
| **Copias exactas** | Encuentra archivos 100% idénticos usando comparación de hash SHA256 |

#### 🔍 Detección visual

| Herramienta | Descripción |
|-------------|-------------|
| **Visualmente idénticos** | Detecta imágenes que se ven exactamente iguales usando hash perceptual |
| **Archivos similares** | Encuentra imágenes 70–95% similares (ediciones, recortes, diferentes resoluciones) con un slider de sensibilidad ajustable |

#### 📁 Organización

| Herramienta | Descripción |
|-------------|-------------|
| **Organizador inteligente** | Reorganiza archivos en una estructura de carpetas limpia basada en fechas |
| **Renombrado completo** | Estandariza nombres de archivo al formato `YYYYMMDD_HHMMSS_TYPE.ext` |

#### Principios clave

- **🔒 Privacidad ante todo** — Todas las operaciones son offline y locales. Ningún dato sale de tu máquina.
- **💾 Política de backups primero** — Toda operación destructiva ofrece creación de backup y simulación en seco antes de hacer cambios.
- **🌍 Multilingüe** — Interfaz completa en español e inglés (898+ claves de traducción).
- **🖥️ Multiplataforma** — Experiencia nativa en Linux, Windows y macOS.

### Instalación

Descarga la última versión para tu plataforma desde la [página de Releases](https://github.com/safetoolhub/safetool-pix/releases).

| Plataforma | Formato | Notas |
|------------|---------|-------|
| **Linux** | `.deb`, `.rpm`, `appImage`, `flatpak` | Todos |
| **Windows** | Instalador `.exe` | Windows 10/11 |
| **macOS** | `.dmg` | macOS 12+ |

#### Linux .deb

```bash
# Debian/Ubuntu
sudo dpkg -i safetool-pix_0.9-beta_amd64.deb
```

#### Linux .rpm
```bash
# Fedora/RHEL
sudo rpm -i safetool-pix-0.9.beta-1.x86_64.rpm
```

#### AppImage

Descarga el archivo `.AppImage`, hazlo ejecutable y ejecútalo:

```bash
chmod +x safetool-pix_0.9-beta.AppImage
./safetool-pix_0.9-beta.AppImage
```

#### Flatpak

```bash
# Instalar desde el archivo .flatpakref proporcionado
flatpak install safetool-pix.flatpakref

# O desde Flathub (si está disponible)
flatpak install flathub org.safetoolhub.safetoolpix
```

**Nota de seguridad**: Tu sistema puede advertir que SafeTool Pix proviene de un desarrollador desconocido o fuente no confiable. Esto es normal para software de código abierto. SafeTool Pix es completamente seguro y de código abierto — puedes verificar el código en GitHub.

#### Windows

Ejecuta el instalador y sigue el asistente de configuración. Se creará automáticamente un acceso directo en el Menú Inicio.

#### macOS

Abre el archivo `.dmg` y arrastra SafeTool Pix a tu carpeta de Aplicaciones.

### Compilar desde código fuente

#### Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recomendado) o pip

#### Configuración

```bash
git clone https://github.com/safetoolhub/safetool-pix.git
cd safetool-pix

# Crear entorno virtual
uv venv --python 3.12
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Instalar dependencias
uv pip install -r requirements.txt

# Ejecutar la aplicación
python main.py
```

#### Ejecutar pruebas

```bash
uv pip install -r requirements-dev.txt
pytest --ignore=tests/performance
```

#### Herramientas del sistema opcionales

Algunas funciones de análisis de vídeo requieren herramientas externas:

- **ffprobe** (de FFmpeg) — para extracción de metadatos de vídeo
- **exiftool** — para lectura avanzada de EXIF

Estas son opcionales. La aplicación funciona completamente sin ellas, pero omitirá fases de metadatos de vídeo durante el escaneo.

### Stack tecnológico

- **Lenguaje**: Python 3.12+
- **Framework de UI**: PyQt6
- **Pruebas**: pytest (713+ pruebas)
- **Arquitectura**: Separación estricta UI/lógica — los servicios están libres de PyQt6 para futura portabilidad

### Contribucionesthisis

¡Las contribuciones son bienvenidas! Por favor lee la [Guía de Contribución](CONTRIBUTING.md) antes de enviar una pull request.

### Licencia

SafeTool Pix está licenciado bajo la [Licencia Pública General de GNU v3.0](LICENSE) con requisitos adicionales de atribución bajo la Sección 7:

- **Atribución requerida**: Cualquier trabajo derivado debe retener atribución visible a [SafeToolHub](https://safetoolhub.org) con un enlace clickeable.
- Ver [LICENSE](LICENSE) para detalles completos.

### Enlaces

- **Sitio web**: [safetoolhub.org](https://safetoolhub.org)
- **Versiones**: [Releases de GitHub](https://github.com/safetoolhub/safetool-pix/releases)
- **Problemas**: [Reportar un error](https://github.com/safetoolhub/safetool-pix/issues)

---

<p align="center">
  Made with ❤️ by <a href="https://safetoolhub.org">SafeToolHub</a>
</p>
