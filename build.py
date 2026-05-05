#!/usr/bin/env python3
"""Build a Checkmk MKP package from the local/ directory tree.

Usage:
    python build.py --version 1.0.0
    python build.py --version 1.0.0 --config .mkp-builder.ini --output-dir dist/
"""

import argparse
import ast
import configparser
import io
import json
import pprint
import sys
import tarfile
from pathlib import Path
from typing import Dict, List, Tuple


# Maps (subdirectory under local/, section enum key in info["files"]).
# Order matters: more specific paths must come before less specific ones so
# that each file is claimed by the most specific section.
_PATH_MAP: List[Tuple[str, str]] = [
    ("lib/python3/cmk_addons/plugins",  "cmk_addons_plugins"),
    ("lib/python3/cmk/plugins",         "cmk_plugins"),
    ("share/check_mk/agents",           "agents"),
    ("share/check_mk/checks",           "checks"),
    ("share/check_mk/web",              "web"),
    ("share/check_mk/notifications",    "notifications"),
    ("share/check_mk/alert_handlers",   "alert_handlers"),
    ("share/check_mk/pnp-templates",    "pnp-templates"),
    ("share/check_mk/mibs",             "mibs"),
    ("share/doc",                       "doc"),
    ("share/check_mk/locale",           "locales"),
    ("bin",                             "bin"),
    ("lib",                             "lib"),
]


def _discover_files(local_dir: Path) -> Dict[str, List[str]]:
    """Walk local/ and classify each file into a section.

    Returns section key → sorted list of paths relative to that section's
    base directory. Each file is claimed by the most specific matching section.
    """
    section_files: Dict[str, List[str]] = {}

    for p in sorted(local_dir.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        rel = str(p.relative_to(local_dir)).replace("\\", "/")
        for local_subdir, section in _PATH_MAP:
            if rel.startswith(local_subdir + "/"):
                section_files.setdefault(section, []).append(rel[len(local_subdir) + 1:])
                break

    return section_files


def _build_manifest(
    pkg: configparser.SectionProxy,
    version: str,
    section_files: Dict[str, List[str]],
) -> dict:
    """Return the manifest dict shared by both info and info.json."""
    num_files = sum(len(v) for v in section_files.values())
    return {
        "author":               pkg.get("author", ""),
        "description":          pkg.get("description", ""),
        "download_url":         pkg.get("url", ""),
        "files":                section_files,
        "name":                 pkg["name"],
        "num_files":            num_files,
        "title":                pkg.get("title", pkg["name"]),
        "version":              version,
        "version.min_required": pkg.get("min-version", "2.4.0"),
        "version.packaged":     pkg.get("min-version", "2.4.0"),
        "version.usable_until": None,
    }


def build(config_path: Path, version: str, output_dir: Path) -> Path:
    cfg = configparser.ConfigParser()
    cfg.read(config_path, encoding="utf-8")

    if "package" not in cfg:
        sys.exit(f"ERROR: [package] section missing in {config_path}")

    pkg = cfg["package"]
    name = pkg.get("name", "").strip()
    if not name:
        sys.exit("ERROR: 'name' is required in [package]")

    local_dir = config_path.parent / "local"
    if not local_dir.is_dir():
        sys.exit(f"ERROR: local/ directory not found: {local_dir}")

    section_files = _discover_files(local_dir)
    if not section_files:
        sys.exit("ERROR: No plugin files found under local/")

    manifest = _build_manifest(pkg, version, section_files)
    info_str = pprint.pformat(manifest) + "\n"

    # Guard: info must be a valid Python literal (Checkmk reads it with ast.literal_eval)
    ast.literal_eval(info_str)

    info_json_bytes = json.dumps(manifest, indent=2).encode("utf-8")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}-{version}.mkp"

    subdir_for_section = {section: subdir for subdir, section in _PATH_MAP}

    with tarfile.open(output_path, "w:gz") as outer_tar:
        info_bytes = info_str.encode("utf-8")
        ti = tarfile.TarInfo(name="info")
        ti.size = len(info_bytes)
        outer_tar.addfile(ti, io.BytesIO(info_bytes))

        ti_json = tarfile.TarInfo(name="info.json")
        ti_json.size = len(info_json_bytes)
        outer_tar.addfile(ti_json, io.BytesIO(info_json_bytes))

        for section, rel_files in section_files.items():
            local_subdir = subdir_for_section[section]
            inner_buf = io.BytesIO()
            with tarfile.open(fileobj=inner_buf, mode="w") as inner_tar:
                for rel_file in rel_files:
                    inner_tar.add(local_dir / local_subdir / rel_file, arcname=rel_file)
            inner_bytes = inner_buf.getvalue()
            inner_ti = tarfile.TarInfo(name=f"{section}.tar")
            inner_ti.size = len(inner_bytes)
            outer_tar.addfile(inner_ti, io.BytesIO(inner_bytes))

    num_files = sum(len(v) for v in section_files.values())
    print(f"Built {output_path}  ({num_files} file(s))")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Checkmk MKP package")
    parser.add_argument("--version",    required=True, help="Package version, e.g. 1.2.3")
    parser.add_argument("--config",     default=".mkp-builder.ini", help="Config file path")
    parser.add_argument("--output-dir", default=".",               help="Directory for the .mkp file")
    args = parser.parse_args()

    build(Path(args.config), args.version, Path(args.output_dir))


if __name__ == "__main__":
    main()
