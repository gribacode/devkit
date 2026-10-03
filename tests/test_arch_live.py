import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import SCRIPTS

sys.path.insert(0, SCRIPTS)
import arch_contract  # noqa: E402

DEPCRUISE = os.environ.get("DEVKIT_DEPCRUISE", "")
TSCONFIG = '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}'

# arch: (файлы, вариант, правила, которые должны сработать, пары from -> to, которые не должны)
CASES = {
    "react-fsd": ({
        "src/app/index.tsx": "import {P} from '../pages/home'; export const A=P",
        "src/pages/home/index.ts": "import {W} from '@/widgets/header'; export const P=W",
        "src/widgets/header/index.ts": "import {F} from '../../features/auth'; import {deep} from '../../features/auth/model/store'; export const W=F+deep",
        "src/features/auth/index.ts": "import {C} from '../cart'; import {U} from '@/entities/user'; export const F=C+U",
        "src/features/auth/model/store.ts": "export const deep=1",
        "src/features/cart/index.ts": "export const C=1",
        "src/entities/user/index.ts": "import {O} from '../order/@x/user'; import {X} from '../order'; export const U=O+X",
        "src/entities/order/index.ts": "export const X=1",
        "src/entities/order/@x/user.ts": "export const O=1",
        "src/shared/ui/index.ts": "import {U} from '@/entities/user'; export const S=U",
    }, None, {"fsd-public-api", "fsd-cross-slice", "fsd-layers-shared"},
        {"src/entities/user/index.ts -> src/entities/order/@x/user.ts", "src/app/index.tsx -> src/pages/home/index.ts"}),
    "react-feod": ({
        "src/app/index.tsx": "import {P} from '../pages/home'; export const A=P",
        "src/pages/home/index.ts": "import {M} from '@/modules/cart'; import {D} from '@/modules/cart/model/d'; import {A} from '../../app'; export const P=M+D",
        "src/modules/cart/index.ts": "import {D} from './model/d'; import {Q} from '../user'; import {G} from '../../global/g'; export const M=D+Q+G",
        "src/modules/cart/model/d.ts": "export const D=1",
        "src/modules/user/index.ts": "import {C} from '@/common/x'; export const Q=C",
        "src/common/x.ts": "import {Q} from '../modules/user'; export const C=1",
        "src/global/g.ts": "export const G=1",
    }, None, {"feod-public-api", "feod-pages-up", "feod-no-global-import", "feod-common-isolated"},
        {"src/modules/cart/index.ts -> src/modules/user/index.ts"}),
    "react-evolution": ({
        "src/app/index.tsx": "import {T} from '@/features/tasks'; export const A=T",
        "src/features/tasks/index.ts": "import {S} from '@/services/session'; import {AU} from '../auth'; import {X} from '@/services/session/model/x'; export const T=S+AU+X",
        "src/features/auth/index.ts": "import {A} from '@/app'; export const AU=1",
        "src/services/session/index.ts": "import {T} from '@/features/tasks'; export const S=1",
        "src/services/session/model/x.ts": "export const X=1",
        "src/shared/lib/index.ts": "import {S} from '@/services/session'; export const L=S",
    }, "medium", {"ed-no-app", "ed-no-features", "ed-shared-no-services", "ed-public-api", "ed-cross-feature"},
        {"src/features/tasks/index.ts -> src/services/session/index.ts"}),
    "react-feature": ({
        "src/app/index.tsx": "import {T} from '@/features/tasks/components/list'; export const A=T",
        "src/features/tasks/components/list.tsx": "import {AU} from '@/features/auth/api/x'; import {B} from '@/components/button'; export const T=AU+B",
        "src/features/auth/api/x.ts": "import {A} from '@/app'; export const AU=1",
        "src/components/button.tsx": "import {T} from '@/features/tasks/components/list'; export const B=1",
    }, None, {"feature-cross", "feature-no-app", "feature-shared-up"},
        {"src/app/index.tsx -> src/features/tasks/components/list.tsx"}),
    "react-clean": ({
        "src/ui/page.tsx": "import {uc} from '@/application/uc'; export const P=uc",
        "src/application/uc.ts": "import {E} from '@/domain/e'; import {I} from '@/infrastructure/api'; export const uc=E+I",
        "src/domain/e.ts": "import React from 'react'; import {uc} from '@/application/uc'; export const E=1",
        "src/infrastructure/api.ts": "import {P} from '@/ui/page'; export const I=1",
    }, None, {"clean-application-inner", "clean-domain-inner", "clean-domain-no-libs", "clean-infrastructure-no-ui"},
        {"src/ui/page.tsx -> src/application/uc.ts"}),
    "nest-standard": ({
        "src/users/users.controller.ts": "import {S} from './users.service'; import {PrismaClient} from '@prisma/client'; import {R} from './users.repository'; export const C=S",
        "src/users/users.service.ts": "import {O} from '../orders/orders.service'; import {OC} from '../orders/orders.controller'; import {D} from '../orders/dto/create.dto'; import {E} from '../orders/entities/order.entity'; import {cfg} from '../config/x'; export const S=O",
        "src/users/users.repository.ts": "export const R=1",
        "src/orders/orders.service.ts": "export const O=1",
        "src/orders/orders.controller.ts": "export const OC=1",
        "src/orders/dto/create.dto.ts": "export const D=1",
        "src/orders/entities/order.entity.ts": "export const E=1",
        "src/config/x.ts": "import {S} from '../users/users.service'; export const cfg=1",
    }, None, {"nest-controller-no-orm", "nest-controller-no-repository", "nest-foreign-internals", "nest-common-no-features"},
        {"src/users/users.service.ts -> src/orders/dto/create.dto.ts", "src/users/users.service.ts -> src/orders/orders.service.ts"}),
    "nest-modular-clean": ({
        "src/modules/users/index.ts": "export * from './users.module'",
        "src/modules/users/users.module.ts": "import {C} from './presentation/c'; export const M=C",
        "src/modules/users/presentation/c.ts": "import {U} from '../application/u'; import {I} from '../infrastructure/repo'; export const C=U",
        "src/modules/users/application/u.ts": "import {E} from '../domain/e'; import {I} from '../infrastructure/repo'; import {O} from '../../orders'; import {X} from '../../orders/domain/x'; export const U=E",
        "src/modules/users/domain/e.ts": "import {Injectable} from '@nestjs/common'; import {U} from '../application/u'; export const E=1",
        "src/modules/users/infrastructure/repo.ts": "import {PrismaClient} from '@prisma/client'; export const I=1",
        "src/modules/orders/index.ts": "export const O=1",
        "src/modules/orders/domain/x.ts": "import {PrismaClient} from '@prisma/client'; export const X=1",
        "src/shared/s.ts": "import {O} from '../modules/orders'; export const S=1",
    }, None, {"nmc-public-api", "nmc-domain-inner", "nmc-domain-no-framework", "nmc-application-inner",
              "nmc-presentation-no-infrastructure", "nmc-orm-in-infrastructure", "nmc-shared-no-modules"},
        {"src/modules/users/application/u.ts -> src/modules/orders/index.ts"}),
    "nest-ddd-cqrs": ({
        "src/contexts/billing/application/h.ts": "import {E} from '../domain/e'; import {I} from '../infrastructure/r'; import {Ev} from '../../users/contracts/events'; import {UE} from '../../users/domain/user'; export const H=E",
        "src/contexts/billing/domain/e.ts": "import {Injectable} from '@nestjs/common'; import {H} from '../application/h'; export const E=1",
        "src/contexts/billing/infrastructure/r.ts": "export const I=1",
        "src/contexts/users/contracts/events.ts": "export const Ev=1",
        "src/contexts/users/domain/user.ts": "export const UE=1",
        "src/shared/s.ts": "import {Ev} from '../contexts/users/contracts/events'; export const S=1",
    }, None, {"ddd-context-contracts", "ddd-domain-inner", "ddd-domain-no-framework", "ddd-application-inner",
              "ddd-shared-no-contexts"},
        {"src/contexts/billing/application/h.ts -> src/contexts/users/contracts/events.ts"}),
}


@unittest.skipUnless(DEPCRUISE and os.path.isfile(DEPCRUISE), "нет DEVKIT_DEPCRUISE")
class LiveRulesTest(unittest.TestCase):
    def cruise(self, folder: str, extra: list = None) -> subprocess.CompletedProcess:
        return subprocess.run([DEPCRUISE, "src"] + (extra or []), cwd=folder, capture_output=True, text=True, timeout=120)

    def make(self, folder: str, arch: str, files: dict, variant: str = None, parser: str = None) -> None:
        for rel, body in files.items():
            path = os.path.join(folder, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(body + "\n")
        with open(os.path.join(folder, "tsconfig.json"), "w", encoding="utf-8") as f:
            f.write(TSCONFIG)
        with open(os.path.join(folder, ".dependency-cruiser.cjs"), "w", encoding="utf-8") as f:
            f.write(arch_contract.render_depcruise(arch, variant, "src", "tsconfig.json", parser=parser))

    def test_every_rule_fires_and_allowed_pass(self) -> None:
        self.assertEqual(set(CASES), set(arch_contract.ARCHS))
        for arch, (files, variant, expected, allowed) in CASES.items():
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as folder:
                self.make(folder, arch, files, variant)
                proc = self.cruise(folder, ["--output-type", "json"])
                self.assertGreaterEqual(arch_contract.count_modules(proc.stdout), len(files), "depcruise не видит модули")
                errors = [v for v in json.loads(proc.stdout)["summary"]["violations"] if v["rule"]["severity"] == "error"]
                self.assertEqual({v["rule"]["name"] for v in errors}, expected)
                self.assertFalse(allowed & {"%s -> %s" % (v["from"], v["to"]) for v in errors})

    @unittest.skipUnless(os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(DEPCRUISE or "/x/y/z"))),
                                                 "node_modules", "@swc", "core")), "нет @swc/core рядом с depcruise")
    def test_swc_parser(self) -> None:
        for arch, (files, variant, expected, _) in CASES.items():
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as folder:
                self.make(folder, arch, files, variant, parser="swc")
                proc = self.cruise(folder, ["--output-type", "json"])
                self.assertGreaterEqual(arch_contract.count_modules(proc.stdout), len(files))
                errors = {v["rule"]["name"] for v in json.loads(proc.stdout)["summary"]["violations"]
                          if v["rule"]["severity"] == "error"}
                self.assertEqual(errors, expected)

    def install(self, folder: str, files: dict) -> None:
        # Настоящий проект держит пакеты в node_modules, depcruise резолвит их в node_modules/<pkg>/index.js
        for body in files.values():
            for spec in re.findall(r"from '([^'.][^']*)'", body):
                if spec.startswith("@/"):
                    continue
                name = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
                package = os.path.join(folder, "node_modules", name)
                os.makedirs(package, exist_ok=True)
                with open(os.path.join(package, "package.json"), "w") as f:
                    json.dump({"name": name, "version": "1.0.0", "main": "index.js"}, f)
                with open(os.path.join(package, "index.js"), "w") as f:
                    f.write("module.exports = {}\n")

    def test_rules_with_installed_packages(self) -> None:
        for arch, (files, variant, expected, _) in CASES.items():
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as folder:
                self.make(folder, arch, files, variant)
                self.install(folder, files)
                proc = self.cruise(folder, ["--output-type", "json"])
                errors = {v["rule"]["name"] for v in json.loads(proc.stdout)["summary"]["violations"]
                          if v["rule"]["severity"] == "error"}
                self.assertEqual(errors, expected)

    def test_dot_root_does_not_flag_packages(self) -> None:
        files = {
            "users/users.controller.ts": "import {Controller} from '@nestjs/common'; import {S} from './users.service'; export const C=S",
            "users/users.service.ts": "import {Injectable} from '@nestjs/common'; export const S=1",
            "common/guard.ts": "import {Injectable} from '@nestjs/common'; export const G=1",
        }
        with tempfile.TemporaryDirectory() as folder:
            for rel, body in files.items():
                path = os.path.join(folder, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(body + "\n")
            self.install(folder, files)
            with open(os.path.join(folder, ".dependency-cruiser.cjs"), "w") as f:
                f.write(arch_contract.render_depcruise("nest-standard", root="."))
            proc = subprocess.run([DEPCRUISE, "users", "common"], cwd=folder, capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_baseline_ratchet(self) -> None:
        files, variant, _, _ = CASES["react-fsd"]
        with tempfile.TemporaryDirectory() as folder:
            self.make(folder, "react-fsd", files, variant)
            self.assertNotEqual(self.cruise(folder, ["--ignore-known"]).returncode, 0, "без baseline должно падать")
            baseline = self.cruise(folder, ["--output-type", "baseline"]).stdout
            with open(os.path.join(folder, ".dependency-cruiser-known-violations.json"), "w") as f:
                f.write(baseline)
            self.assertGreater(arch_contract.count_violations(baseline), 0)
            self.assertEqual(self.cruise(folder, ["--ignore-known"]).returncode, 0, "старые нарушения не валят")
            with open(os.path.join(folder, "src/shared/ui/bad.ts"), "w") as f:
                f.write("import {F} from '@/features/auth'; export const Z=F\n")
            self.assertNotEqual(self.cruise(folder, ["--ignore-known"]).returncode, 0, "новое нарушение валит")


if __name__ == "__main__":
    unittest.main()
