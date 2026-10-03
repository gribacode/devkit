#!/usr/bin/env python3
"""Собирает контракт архитектуры для /arch. Конфиг dependency-cruiser, парсер под версию TypeScript,
счет модулей и нарушений baseline, долг steiger и скрипт lint:arch. Только stdlib, чтобы работать без зависимостей плагина.
"""
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from arch_detect import tsconfig_for

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "refs", "arch", "depcruise")
ARCHS = ["react-fsd", "react-feod", "react-evolution", "react-feature", "react-clean",
         "nest-standard", "nest-modular-clean", "nest-ddd-cqrs"]
ROOT_TOKEN = "__ROOT__/"
# Нерезолвленный импорт с таким началом это свой код, значит алиас или путь сломан и правила его не видят
LOCAL_PREFIXES = (".", "/", "@/", "~/", "#")
# dependency-cruiser 18 разбирает TS через typescript <7. С 7 он молча не видит .ts, нужен swc
SWC_FROM_TS_MAJOR = 7
EXPORT_PREFIX = "module.exports = "


def _load(name: str, templates: str) -> Dict[str, Any]:
    with open(os.path.join(templates, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def _clean_root(root: str) -> str:
    clean = root.strip()
    while clean.startswith("./"):
        clean = clean[2:]
    return clean.strip("/")


def _root_prefix(root: str) -> str:
    clean = _clean_root(root)
    if clean in ("", "."):
        return ""
    # Префикс вставляется внутрь JSON-строки, поэтому экранируем и для регулярки, и для JSON
    return json.dumps(re.escape(clean) + "/")[1:-1]


def glob_regex(pattern: str) -> str:
    # Поле ignore из ARCHITECTURE.md пишут глобами, а depcruise exclude ждет регулярку
    out, i = "^", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return out if out.endswith(".*") else out + "$"


def render_depcruise(arch: str, variant: Optional[str] = None, root: str = "src",
                     tsconfig: Optional[str] = None, templates: str = TEMPLATES, parser: Optional[str] = None,
                     ignore: Optional[List[str]] = None) -> str:
    base = _load("base", templates)
    rules = list(base["forbidden"]) + _load(arch, templates)["forbidden"]
    if variant:
        rules += _load("%s.%s" % (arch, variant), templates)["forbidden"]
    options = dict(base["options"])
    if tsconfig:
        options["tsConfig"] = {"fileName": tsconfig}
    if parser:
        options["parser"] = parser
    if ignore:
        options["exclude"] = {"path": [options["exclude"]["path"]] + [glob_regex(p) for p in ignore]}
    body = json.dumps({"forbidden": rules, "options": options}, ensure_ascii=False, indent=2)
    body = body.replace(ROOT_TOKEN, _root_prefix(root))
    name = arch + ("." + variant if variant else "")
    return ("// Сгенерировано devkit /arch для %s. Правила описаны в ARCHITECTURE.md.\n"
            "/** @type {import('dependency-cruiser').IConfiguration} */\n%s%s;\n" % (name, EXPORT_PREFIX, body))


def config_json(cjs: str) -> Dict[str, Any]:
    start = cjs.index(EXPORT_PREFIX) + len(EXPORT_PREFIX)
    return json.loads(cjs[start:].rstrip().rstrip(";"))


def _json_list(text: str) -> List[Any]:
    if not text.strip():
        return []
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("ожидался JSON-список, пришел %s" % type(data).__name__)
    return data


def parser_for(package_dir: str) -> Optional[str]:
    folder = os.path.abspath(package_dir)
    while True:
        manifest = os.path.join(folder, "node_modules", "typescript", "package.json")
        if os.path.isfile(manifest):
            try:
                with open(manifest, encoding="utf-8") as f:
                    major = int(str(json.load(f).get("version", "0")).split(".")[0])
            except (OSError, ValueError):
                return None
            return "swc" if major >= SWC_FROM_TS_MAJOR else None
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def count_modules(text: str) -> int:
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("modules"), list):
        raise ValueError("ожидался JSON depcruise --output-type json")
    return len(data["modules"])


def unresolved_local(text: str) -> List[str]:
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("modules"), list):
        raise ValueError("ожидался JSON depcruise --output-type json")
    found = []
    for module in data["modules"]:
        for dep in module.get("dependencies") or []:
            spec = str(dep.get("module", ""))
            if dep.get("couldNotResolve") and spec.startswith(LOCAL_PREFIXES):
                found.append("%s -> %s" % (module.get("source"), spec))
    return found


def count_violations(text: str) -> int:
    return len(_json_list(text))


def steiger_debt(text: str) -> List[str]:
    return sorted({item["ruleName"] for item in _json_list(text)
                   if isinstance(item, dict) and item.get("severity") == "error" and item.get("ruleName")})


def lint_script(arch: str, root: str = "src", evo: bool = False) -> str:
    target = _clean_root(root) or "."
    parts = ["depcruise %s --ignore-known" % target]
    if arch == "react-fsd":
        parts.append("steiger %s" % target)
    if evo:
        parts.append("edlint lint")
    return " && ".join(parts)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    dep = sub.add_parser("depcruise")
    dep.add_argument("--arch", required=True)
    dep.add_argument("--variant")
    dep.add_argument("--root", default="src")
    dep.add_argument("--tsconfig")
    dep.add_argument("--parser", choices=["swc"])
    dep.add_argument("--ignore", action="append", default=[])
    sub.add_parser("count")
    sub.add_parser("modules")
    sub.add_parser("unresolved")
    tsconfig_cmd = sub.add_parser("tsconfig")
    tsconfig_cmd.add_argument("package", nargs="?", default=".")
    parser_cmd = sub.add_parser("parser")
    parser_cmd.add_argument("package", nargs="?", default=".")
    sub.add_parser("steiger-debt")
    lint = sub.add_parser("lint-script")
    lint.add_argument("--arch", required=True)
    lint.add_argument("--root", default="src")
    lint.add_argument("--evo", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "depcruise":
            sys.stdout.write(render_depcruise(args.arch, args.variant, args.root, args.tsconfig,
                                              parser=args.parser, ignore=args.ignore))
        elif args.command == "count":
            print(count_violations(sys.stdin.read()))
        elif args.command == "modules":
            print(count_modules(sys.stdin.read()))
        elif args.command == "unresolved":
            found = unresolved_local(sys.stdin.read())
            print(len(found))
            for line in found:
                print(line)
        elif args.command == "tsconfig":
            print(tsconfig_for(args.package) or "")
        elif args.command == "parser":
            print(parser_for(args.package) or "")
        elif args.command == "steiger-debt":
            for rule in steiger_debt(sys.stdin.read()):
                print(rule)
        else:
            print(lint_script(args.arch, args.root, args.evo))
    except FileNotFoundError as error:
        sys.stderr.write("нет шаблона %s\n" % os.path.basename(str(error.filename or error)))
        return 2
    except ValueError as error:
        sys.stderr.write("%s\n" % error)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
