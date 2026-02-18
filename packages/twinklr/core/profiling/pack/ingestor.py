"""Ingest zip/xsqz sequence packs and produce package manifests."""

from __future__ import annotations

import hashlib
import shutil
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from twinklr.core.profiling.models.enums import FileKind
from twinklr.core.profiling.models.pack import FileEntry, PackageManifest
from twinklr.core.utils.logging import get_logger

logger = get_logger(__name__)

ZIP_EXTENSIONS: frozenset[str] = frozenset({".zip", ".xsqz"})
SEQUENCE_EXTENSIONS: frozenset[str] = frozenset({".xsq", ".seq"})
RGB_EFFECTS_NAMES: frozenset[str] = frozenset({"xlights_rgbeffects.xml", "rgb_effects.xml"})

_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
_IGNORED_FILENAMES = {".ds_store"}


def _is_ignored_filename(filename: str) -> bool:
    name = filename.strip()
    lowered = name.lower()
    if not name:
        return True
    if lowered in _IGNORED_FILENAMES:
        return True
    # AppleDouble resource forks or hidden files should never be treated as assets/XSQ/XML.
    return name.startswith("._")


def sha256_bytes(data: bytes) -> str:
    """Return SHA-256 hex digest for raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return SHA-256 hex digest for a file on disk."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_asset_type(filename: str) -> str:
    """Classify simple media/shader asset type from file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".fs":
        return "shader"
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _IMAGE_EXTS:
        return "image"
    return "other"


def is_zip_like(path: Path) -> bool:
    """Return True when path uses a known archive extension."""
    return path.suffix.lower() in ZIP_EXTENSIONS


def extract_zip_flat(
    zip_path: Path,
    out_dir: Path,
    seen_hashes: set[str] | None = None,
    source_extensions: set[str] | None = None,
) -> None:
    """Extract archive recursively into a flat directory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    seen_hashes = seen_hashes or set()
    source_extensions = source_extensions if source_extensions is not None else set()

    archive_hash = sha256_file(zip_path)
    if archive_hash in seen_hashes:
        return
    seen_hashes.add(archive_hash)
    source_extensions.add(zip_path.suffix.lower())

    with ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = Path(info.filename).name
            if _is_ignored_filename(basename):
                continue
            dest = out_dir / basename
            data = archive.read(info.filename)
            if dest.exists() and dest.read_bytes() != data:
                logger.warning("filename collision during flat extraction: %s", basename)
            dest.write_bytes(data)
            if is_zip_like(dest):
                extract_zip_flat(dest, out_dir, seen_hashes, source_extensions)
                dest.unlink(missing_ok=True)


def _sniff_xsequence(path: Path) -> bool:
    """Return True if XML root tag is `xsequence` (case-insensitive)."""
    try:
        for _event, elem in ET.iterparse(path, events=["start"]):
            return elem.tag.lower() == "xsequence"
    except Exception:  # noqa: BLE001
        return False
    return False


def _classify_kind(filename: str, ext: str) -> FileKind:
    if ext in SEQUENCE_EXTENSIONS:
        return FileKind.SEQUENCE
    if filename.lower() in RGB_EFFECTS_NAMES:
        return FileKind.RGB_EFFECTS

    asset_type = infer_asset_type(filename)
    if asset_type == "shader":
        return FileKind.SHADER
    if asset_type in {"audio", "video", "image"}:
        return FileKind.ASSET
    return FileKind.OTHER


def _detect_rgb_effects_file(files: list[FileEntry]) -> str | None:
    for entry in sorted(files, key=lambda f: f.filename.lower()):
        if entry.filename.lower() in RGB_EFFECTS_NAMES:
            return entry.file_id
    return None


def _detect_sequence_file(files: list[FileEntry], extracted_dir: Path) -> str | None:
    for entry in sorted(files, key=lambda f: f.filename.lower()):
        if entry.ext in SEQUENCE_EXTENSIONS:
            return entry.file_id

    xml_entries = sorted((f for f in files if f.ext == ".xml"), key=lambda f: f.filename.lower())
    for entry in xml_entries:
        xml_path = extracted_dir / entry.filename
        if not _sniff_xsequence(xml_path):
            continue

        promoted_path = xml_path.with_suffix(".xsq")
        promoted_path.write_bytes(xml_path.read_bytes())
        promoted_entry = FileEntry(
            file_id=str(uuid.uuid4()),
            filename=promoted_path.name,
            ext=".xsq",
            size=promoted_path.stat().st_size,
            sha256=sha256_file(promoted_path),
            kind=FileKind.SEQUENCE,
            original_ext=".xml",
        )
        files.remove(entry)
        files.append(promoted_entry)
        return promoted_entry.file_id

    return None


def ingest_zip(zip_path: Path) -> tuple[PackageManifest, Path]:
    """Ingest zip/xsqz package into a manifest and extracted directory."""
    zip_path = Path(zip_path)
    extracted_dir = zip_path.parent / f"{zip_path.stem}_extracted"
    if extracted_dir.exists():
        shutil.rmtree(extracted_dir)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    source_extensions: set[str] = set()
    extract_zip_flat(
        zip_path, extracted_dir, seen_hashes=set(), source_extensions=source_extensions
    )

    files: list[FileEntry] = []
    for path in sorted(extracted_dir.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        if _is_ignored_filename(path.name):
            continue
        ext = path.suffix.lower()
        files.append(
            FileEntry(
                file_id=str(uuid.uuid4()),
                filename=path.name,
                ext=ext,
                size=path.stat().st_size,
                sha256=sha256_file(path),
                kind=_classify_kind(path.name, ext),
            )
        )

    sequence_file_id = _detect_sequence_file(files, extracted_dir)
    rgb_effects_file_id = _detect_rgb_effects_file(files)

    manifest = PackageManifest(
        package_id=str(uuid.uuid4()),
        zip_sha256=sha256_file(zip_path),
        source_extensions=frozenset(source_extensions or {zip_path.suffix.lower()}),
        files=tuple(sorted(files, key=lambda f: f.filename.lower())),
        sequence_file_id=sequence_file_id,
        rgb_effects_file_id=rgb_effects_file_id,
    )

    return manifest, extracted_dir
