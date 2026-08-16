"""Per-waveform annotation sidecars: <source>.annotations.json.

A single source file can produce several waveforms -- WaveformLoader.load()
returns a list, and CSV/npz/HDF5 captures routinely carry multiple channels --
so the sidecar is keyed by channel rather than being a flat list.

Loading is deliberately NOT wired into WaveformLoader.load(). The library loader
stays free of surprise disk reads for scripts that never wanted a sidecar; the
GUI calls these functions explicitly at import and at section-build time.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from scpi_control.report_generator.models.annotations import PlotAnnotation
from scpi_control.report_generator.models.report_data import WaveformData

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def _atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` atomically.

    A plain write_text() truncates the destination before writing, so an
    interrupted write can leave a half-written (or empty) file. Since a save
    now read-merge-writes the whole sidecar (Finding 1), that file carries
    every channel's annotations, not just the ones being saved -- an
    interrupted plain write would destroy more than before. Writing to a
    temp file in the same directory and os.replace()-ing it over the target
    is atomic on both Windows and POSIX: readers see either the old file or
    the fully-written new one, never a partial one.
    """
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


def sidecar_path_for(source_file: Path) -> Path:
    """The sidecar beside `source_file`.

    The suffix is APPENDED, not replaced: capture.csv and capture.npz in one
    directory would otherwise both claim capture.annotations.json and silently
    overwrite each other's annotations.
    """
    source_file = Path(source_file)
    return source_file.with_name(source_file.name + ".annotations.json")


def save_annotations(
    waveforms: Iterable[WaveformData],
    *,
    fft: Optional[Dict[str, Tuple[Optional[str], List[PlotAnnotation]]]] = None,
) -> Path:
    """Write every waveform's annotations to the sidecar beside their source file.

    This is a read-merge-write: the existing sidecar is read first, and only the
    channels in `waveforms` are replaced. A channel already on disk but absent
    from `waveforms` keeps whatever it held. This matters because a save can be
    for a single waveform (as the annotation dialog does) even though the
    source file carries several channels -- overwriting the whole sidecar with
    only the passed-in channels would silently erase every sibling channel's
    annotations.

    Args:
        waveforms: waveforms sharing one source file. Not required to be every
            channel the source file carries.
        fft: optional {channel: (caption, annotations)}. FFT annotations hang off
            a TestSection, not off a waveform, so the caller must supply them --
            this function cannot reach them from the waveform list alone.

    Returns:
        The path written.

    Raises:
        ValueError: if a waveform has no source_file. Silently writing nothing
            would look like success.
    """
    waveforms = list(waveforms)
    if not waveforms:
        raise ValueError("save_annotations needs at least one waveform")

    sources = {w.source_file for w in waveforms}
    if None in sources:
        missing = [w.channel for w in waveforms if w.source_file is None]
        raise ValueError(f"Cannot save annotations for waveforms with no source_file: {missing}")
    if len(sources) > 1:
        raise ValueError(f"All waveforms must share one source_file; got {sorted(str(s) for s in sources)}")

    source_file = waveforms[0].source_file
    fft = fft or {}

    # Start from whatever is already on disk so channels not present in this
    # save are preserved rather than dropped.
    entries: Dict[str, Any] = dict(_read_sidecar(source_file))
    for waveform in waveforms:
        entry: Dict[str, Any] = {
            "caption": waveform.caption,
            "annotations": [a.to_dict() for a in waveform.annotations],
        }
        if waveform.channel in fft:
            caption, annotations = fft[waveform.channel]
            entry["fft"] = {"caption": caption, "annotations": [a.to_dict() for a in annotations]}
        else:
            # `caption`/`annotations` come straight from the WaveformData the
            # caller holds, so they are authoritative -- if the user cleared
            # them, that clearing must persist. `fft` is different: it is NOT
            # reachable from a waveform (it lives on a TestSection), so a
            # caller with no `fft` kwarg -- e.g. Task 9's annotation dialog,
            # which only ever holds a WaveformData -- has nothing to say
            # about FFT, not "clear the FFT data". Carry the prior on-disk
            # entry forward so this save cannot delete it.
            existing_entry = entries.get(waveform.channel)
            if existing_entry and "fft" in existing_entry:
                entry["fft"] = existing_entry["fft"]
        entries[waveform.channel] = entry

    path = sidecar_path_for(source_file)
    _atomic_write_text(path, json.dumps({"schema": SCHEMA_VERSION, "waveforms": entries}, indent=2))
    logger.info(f"Saved annotations for {len(entries)} channel(s) to {path}")
    return path


def _read_sidecar(source_file: Optional[Path]) -> Dict[str, Any]:
    """Read and parse one sidecar. Returns {} for missing, corrupt or unreadable
    files -- a bad sidecar must never fail a waveform import."""
    if source_file is None:
        return {}
    path = sidecar_path_for(source_file)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # ValueError covers json.JSONDecodeError (a subclass) AND
        # UnicodeDecodeError, which read_text() raises on bytes that are not
        # valid UTF-8 (a truncated write, or a genuinely binary file).
        # UnicodeDecodeError is a ValueError subclass, not an OSError or a
        # JSONDecodeError, so a narrower except here would let it escape and
        # fail the caller's waveform import -- exactly what a corrupt sidecar
        # must never do.
        logger.warning(f"Ignoring unreadable annotation sidecar {path}: {exc}")
        return {}
    if not isinstance(data, dict) or not isinstance(data.get("waveforms"), dict):
        logger.warning(f"Ignoring annotation sidecar {path}: expected an object with a 'waveforms' mapping")
        return {}
    return data["waveforms"]


def load_annotations_into(waveforms: Iterable[WaveformData]) -> int:
    """Apply saved annotations and captions to `waveforms`, matching by channel.

    Merges: annotations already on a waveform are kept, and saved ones are
    appended. A caption already set in memory is not overwritten by the sidecar.

    Idempotent, multiset-aware: an incoming annotation is matched against a
    *consumable* copy of what the target already holds, not a plain
    membership test. PlotAnnotation is a plain dataclass with no identity
    field, so two annotations a user deliberately created with identical
    kind/text/coordinates compare equal -- a plain `in` check would then
    treat the second one as "already present" and drop it even on the very
    first load, which is data loss, not deduplication. Matching against a
    copy that shrinks as matches are consumed means: a repeat load of the
    same sidecar appends nothing (each incoming annotation finds and
    consumes its own already-loaded twin), while two genuinely identical
    annotations in the sidecar both load into an empty target (there is
    nothing yet to consume, so neither is treated as a duplicate of the
    other).

    Returns:
        The number of annotations newly applied (duplicates already present
        are not counted).
    """
    applied = 0
    cache: Dict[Any, Dict[str, Any]] = {}

    for waveform in waveforms:
        key = str(waveform.source_file) if waveform.source_file else None
        if key not in cache:
            cache[key] = _read_sidecar(waveform.source_file)
        entry = cache[key].get(waveform.channel)
        if not entry:
            continue

        remaining = list(waveform.annotations)  # copy; consumed as matches are found
        for raw in entry.get("annotations", []):
            try:
                annotation = PlotAnnotation.from_dict(raw)
            except (ValueError, TypeError) as exc:
                logger.warning(f"Skipping invalid annotation for {waveform.channel}: {exc}")
                continue
            if annotation in remaining:
                remaining.remove(annotation)  # already present; consume one copy
                continue
            waveform.annotations.append(annotation)
            applied += 1

        if entry.get("caption") and not waveform.caption:
            waveform.caption = entry["caption"]

    return applied


def load_fft_annotations_into(section, waveforms: Iterable[WaveformData]) -> int:
    """Apply saved FFT annotations to `section`, routed by section.fft_channel.

    Separate from load_annotations_into because of timing: at waveform-import
    time no TestSection exists yet. The GUI builds sections much later, and calls
    this then.

    Idempotent, multiset-aware against section.fft_annotations, for the same
    reason and by the same consumable-copy mechanism as load_annotations_into
    -- see that function's docstring.

    Returns:
        The number of annotations newly applied (duplicates already present
        are not counted). 0 if the section names no fft_channel, or names one
        absent from `waveforms`.
    """
    channel = getattr(section, "fft_channel", None)
    if not channel:
        return 0

    match = next((w for w in waveforms if w.channel == channel), None)
    if match is None:
        logger.debug(f"No loaded waveform for fft_channel {channel!r}; leaving FFT annotations unset")
        return 0

    entry = _read_sidecar(match.source_file).get(channel, {})
    fft = entry.get("fft") or {}

    applied = 0
    remaining = list(section.fft_annotations)  # copy; consumed as matches are found
    for raw in fft.get("annotations", []):
        try:
            annotation = PlotAnnotation.from_dict(raw)
        except (ValueError, TypeError) as exc:
            logger.warning(f"Skipping invalid FFT annotation for {channel}: {exc}")
            continue
        if annotation in remaining:
            remaining.remove(annotation)  # already present; consume one copy
            continue
        section.fft_annotations.append(annotation)
        applied += 1

    if fft.get("caption") and not section.fft_caption:
        section.fft_caption = fft["caption"]

    return applied
