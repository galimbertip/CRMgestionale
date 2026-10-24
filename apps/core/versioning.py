"""Versione dell'applicazione (file VERSION) e registro versioni (CHANGELOG.md).

Formato versione: maior.minor.patch, mostrata come "V0.1.0".
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache

from django.conf import settings

VERSION_FILE = settings.BASE_DIR / "VERSION"
CHANGELOG_FILE = settings.BASE_DIR / "CHANGELOG.md"
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def read_version():
    raw = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not SEMVER_RE.match(raw):
        raise ValueError(f"VERSION non valido: {raw!r} (atteso maior.minor.patch)")
    return raw


@lru_cache(maxsize=1)
def get_version():
    return read_version()


def display_version(version=None):
    return f"V{version or get_version()}"


def bump(version, part):
    m = SEMVER_RE.match(version)
    if not m:
        raise ValueError(f"Versione non valida: {version}")
    major, minor, patch = map(int, m.groups())
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError("part deve essere major, minor o patch")


@dataclass
class Release:
    version: str
    date: str = ""
    sections: dict = field(default_factory=dict)  # titolo -> [voci]

    @property
    def label(self):
        return display_version(self.version) if SEMVER_RE.match(self.version) else self.version


HEADER_RE = re.compile(r"^##\s+\[?([^\]\s]+)\]?(?:\s*-\s*(.+))?$")


def parse_changelog(text):
    releases, current, section = [], None, None
    for line in text.splitlines():
        h = HEADER_RE.match(line.strip())
        if h:
            current = Release(version=h.group(1), date=(h.group(2) or "").strip())
            releases.append(current)
            section = None
            continue
        if current is None:
            continue
        if line.startswith("### "):
            section = line[4:].strip()
            current.sections.setdefault(section, [])
        elif re.match(r"^\s*[-*]\s+", line):
            item = re.sub(r"^\s*[-*]\s+", "", line).strip()
            current.sections.setdefault(section or "Note", []).append(item)
        elif line.startswith("  ") and line.strip() and current.sections:
            # continuazione della voce precedente
            key = section or "Note"
            if current.sections.get(key):
                current.sections[key][-1] += " " + line.strip()
    return releases


def get_changelog():
    if not CHANGELOG_FILE.exists():
        return []
    return parse_changelog(CHANGELOG_FILE.read_text(encoding="utf-8"))
