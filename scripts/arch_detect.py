#!/usr/bin/env python3
"""Определяет архитектуру React и NestJS пакетов по каталогам и импортам и печатает JSON для /arch detect.

Признаки архитектур берутся из блока json в разделе «Признаки» каждого refs/arch/<id>.md.
Итог 0.6 доли выполненных структурных условий плюс 0.4 доли импортов между слоями по правилам.
Это эвристика для подсказки человеку. Точные правила проверяет dependency-cruiser.
"""
import argparse
import glob
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

REFS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "refs", "arch")
SKIP_DIRS = {"node_modules", "dist", "build", ".next", ".git", "coverage"}
SOURCE_EXT = (".ts", ".tsx", ".js", ".jsx")
SAMPLE = 300
PICK_SCORE = 0.6
PICK_GAP = 0.15
BONUS = 0.2
STRUCTURE_WEIGHT = 0.6
DEFAULT_GLOBS = ["apps/*", "packages/*", "libs/*"]
# Слои сверху вниз. Импорт разрешен в свой ярус и ниже. Детект видит только направление, не слайсы
LAYERS = {
    "react-fsd": [["app"], ["pages"], ["widgets"], ["features"], ["entities"], ["shared"]],
    "react-feod": [["app"], ["pages"], ["modules"], ["common"]],
    "react-evolution": [["app"], ["features"], ["services"], ["shared"]],
    "react-feature": [["app"], ["features"], ["components", "hooks", "lib", "utils"]],
    "react-clean": [["ui", "presentation"], ["infrastructure"], ["application"], ["domain"]],
    "nest-standard": [],
    "nest-modular-clean": [["presentation"], ["infrastructure"], ["application"], ["domain"]],
    "nest-ddd-cqrs": [["presentation"], ["infrastructure"], ["application"], ["domain"]],
}
IMPORT_RE = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)['"]([^'"]+)['"]""")
SIGNATURE_RE = re.compile(r"^## Признаки\s*\n.*?```json\n(.*?)\n```", re.S | re.M)
PNPM_RE = re.compile(r"""^\s*-\s*['"]?([^'"\n#]+?)['"]?\s*$""", re.M)

Signature = Dict[str, Any]
Candidate = Dict[str, Any]


def _read_json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _read_jsonc(path: str) -> Any:
    # tsconfig из Vite и Nest CLI содержит комментарии и висячие запятые
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    text = re.sub(r"^\s*/\*.*?\*/", "", text, flags=re.M | re.S)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        return json.loads(text)
    except ValueError:
        return None


def deps(package_dir: str) -> Set[str]:
    pkg = _read_json(os.path.join(package_dir, "package.json")) or {}
    found: Set[str] = set()
    for key in ("dependencies", "devDependencies"):
        if isinstance(pkg.get(key), dict):
            found |= set(pkg[key])
    return found


def stack(dep_names: Set[str]) -> Optional[str]:
    if "@nestjs/core" in dep_names:
        return "nest"
    if dep_names & {"react", "next"}:
        return "react"
    return None


def source_root(package_dir: str) -> str:
    src = os.path.join(package_dir, "src")
    return src if os.path.isdir(src) else package_dir


def _workspace_globs(root: str) -> List[str]:
    pkg = _read_json(os.path.join(root, "package.json")) or {}
    workspaces = pkg.get("workspaces")
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages")
    if isinstance(workspaces, list):
        return [w for w in workspaces if isinstance(w, str)]
    pnpm = os.path.join(root, "pnpm-workspace.yaml")
    if os.path.isfile(pnpm):
        with open(pnpm, encoding="utf-8") as f:
            found = PNPM_RE.findall(f.read())
        if found:
            return found
    if any(os.path.isfile(os.path.join(root, name)) for name in ("nx.json", "turbo.json")):
        return list(DEFAULT_GLOBS)
    return []


def find_roots(path: str) -> List[str]:
    root = os.path.abspath(path)
    packages = [root]
    for pattern in _workspace_globs(root):
        if pattern.startswith("!"):
            continue
        for match in glob.glob(os.path.join(root, pattern)):
            parts = set(os.path.relpath(match, root).split(os.sep))
            if os.path.isfile(os.path.join(match, "package.json")) and not parts & SKIP_DIRS:
                packages.append(os.path.abspath(match))
    unique = sorted(set(packages) - {root})
    return [p for p in ([root] + unique) if stack(deps(p))]


def load_signatures(refs_dir: str = REFS) -> Dict[str, Signature]:
    signatures: Dict[str, Signature] = {}
    for path in sorted(glob.glob(os.path.join(refs_dir, "*.md"))):
        arch = os.path.basename(path)[:-3]
        if arch not in LAYERS:
            continue
        with open(path, encoding="utf-8") as f:
            match = SIGNATURE_RE.search(f.read())
        if match:
            signatures[arch] = json.loads(match.group(1))
    return signatures


def _matches(base: str, pattern: str, want_dir: bool) -> List[str]:
    found = []
    for path in glob.glob(os.path.join(base, pattern)):
        if os.path.isdir(path) if want_dir else os.path.isfile(path):
            found.append(os.path.relpath(path, base))
    return sorted(found)


def structure_score(package_dir: str, src: str, dep_names: Set[str], sig: Signature) -> Tuple[float, List[str], List[str]]:
    evidence: List[str] = []
    required = sig.get("requires_dep") or []
    if required and not dep_names & set(required):
        return 0.0, evidence, ["нет зависимости %s" % " или ".join(required)]
    conflicts = ["лишний каталог %s" % hit for pattern in sig.get("dirs_none") or []
                 for hit in _matches(src, pattern, True)]
    if conflicts:
        return 0.0, evidence, conflicts
    total = done = 0
    for pattern in sig.get("dirs_all") or []:
        total += 1
        if _matches(src, pattern, True):
            done += 1
            evidence.append("каталог %s" % pattern)
    for key, want_dir, label in (("dirs_any", True, "каталог"), ("files_any", False, "файл")):
        patterns = sig.get(key) or []
        if not patterns:
            continue
        total += 1
        hits = [hit for pattern in patterns for hit in _matches(src, pattern, want_dir)]
        if hits:
            done += 1
            evidence.append("%s %s" % (label, ", ".join(hits[:3])))
    score = done / total if total else 0.0
    bonus = [hit for pattern in sig.get("bonus_files") or [] for hit in _matches(package_dir, pattern, False)]
    if bonus and score > 0:
        score = min(1.0, score + BONUS)
        evidence.append("конфиг %s" % ", ".join(bonus))
    return score, evidence, []


def source_files(src: str) -> List[str]:
    found: List[str] = []
    for folder, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(SOURCE_EXT) and not name.endswith(".d.ts"):
                found.append(os.path.join(folder, name))
                if len(found) >= SAMPLE:
                    return found
    return found


def _has_paths(path: str) -> bool:
    config = _read_jsonc(path) or {}
    return bool((config.get("compilerOptions") or {}).get("paths"))


def tsconfig_for(package_dir: str) -> Optional[str]:
    # Vite держит paths не в tsconfig.json, а в файле из references, например tsconfig.app.json
    root = os.path.join(package_dir, "tsconfig.json")
    if not os.path.isfile(root):
        return None
    if _has_paths(root):
        return "tsconfig.json"
    for ref in (_read_jsonc(root) or {}).get("references") or []:
        target = os.path.normpath(os.path.join(package_dir, str((ref or {}).get("path", ""))))
        if os.path.isdir(target):
            target = os.path.join(target, "tsconfig.json")
        if os.path.isfile(target) and _has_paths(target):
            return os.path.relpath(target, package_dir)
    return "tsconfig.json"


def _aliases(package_dir: str) -> List[Tuple[str, str]]:
    name = tsconfig_for(package_dir)
    if not name:
        return []
    config_path = os.path.join(package_dir, name)
    config = _read_jsonc(config_path) or {}
    options = config.get("compilerOptions") or {}
    base = os.path.join(os.path.dirname(config_path), options.get("baseUrl") or ".")
    found = []
    for key, targets in (options.get("paths") or {}).items():
        if key.endswith("/*") and targets and str(targets[0]).endswith("/*"):
            found.append((key[:-1], os.path.normpath(os.path.join(base, targets[0][:-1]))))
    return found


def _resolve(spec: str, path: str, aliases: List[Tuple[str, str]]) -> Optional[str]:
    if spec.startswith("."):
        return os.path.normpath(os.path.join(os.path.dirname(path), spec))
    for prefix, target in aliases:
        if spec.startswith(prefix):
            return os.path.normpath(os.path.join(target, spec[len(prefix):]))
    return None


def _layer(rel: str, tiers: List[List[str]]) -> Optional[Tuple[int, str]]:
    for part in rel.split(os.sep):
        for index, tier in enumerate(tiers):
            if part in tier:
                return index, part
    return None


def import_score(package_dir: str, src: str, arch: str, files: List[str]) -> Tuple[float, int]:
    tiers = LAYERS[arch]
    if not tiers:
        return 0.5, 0
    aliases = _aliases(package_dir)
    good = total = 0
    for path in files:
        source = _layer(os.path.relpath(path, src), tiers)
        if source is None:
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        for spec in IMPORT_RE.findall(text):
            target_path = _resolve(spec, path, aliases)
            if target_path is None:
                continue
            rel = os.path.relpath(target_path, src)
            if rel.startswith(".."):
                continue
            target = _layer(rel, tiers)
            if target is None or target[1] == source[1]:
                continue
            total += 1
            if target[0] >= source[0]:
                good += 1
    return (good / total if total else 0.5), total


def pick(candidates: List[Candidate]) -> Optional[str]:
    if not candidates or candidates[0]["score"] < PICK_SCORE:
        return None
    if len(candidates) > 1 and round(candidates[0]["score"] - candidates[1]["score"], 2) < PICK_GAP:
        return None
    return candidates[0]["arch"]


def analyze(package_dir: str, sigs: Dict[str, Signature]) -> Dict[str, Any]:
    dep_names = deps(package_dir)
    kind = stack(dep_names)
    src = source_root(package_dir)
    files = source_files(src)
    candidates: List[Candidate] = []
    for arch, sig in sorted(sigs.items()):
        if not kind or not arch.startswith(kind + "-"):
            continue
        structure, evidence, conflicts = structure_score(package_dir, src, dep_names, sig)
        score = 0.0
        if structure > 0:
            imports, count = import_score(package_dir, src, arch, files)
            if count:
                evidence.append("импортов между слоями %d, по правилам %d%%" % (count, round(imports * 100)))
            weight = float(sig.get("weight", 1.0))
            score = round((STRUCTURE_WEIGHT * structure + (1 - STRUCTURE_WEIGHT) * imports) * weight, 2)
        candidates.append({"arch": arch, "score": score, "evidence": evidence, "conflicts": conflicts})
    candidates.sort(key=lambda c: (-c["score"], c["arch"]))
    return {"root": package_dir, "stack": kind, "src": os.path.relpath(src, package_dir),
            "pick": pick(candidates), "candidates": candidates}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--refs", default=REFS)
    args = parser.parse_args(argv)
    base = os.path.abspath(args.path)
    sigs = load_signatures(args.refs)
    roots = []
    for package_dir in find_roots(base):
        found = analyze(package_dir, sigs)
        found["root"] = os.path.relpath(package_dir, base)
        roots.append(found)
    print(json.dumps({"roots": roots}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
