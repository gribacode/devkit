import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import SCRIPTS
from tests.test_arch_refs import ARCH, IDS, section

sys.path.insert(0, SCRIPTS)
import arch_detect  # noqa: E402

REACT = {"dependencies": {"react": "^19.0.0"}}
NEST = {"dependencies": {"@nestjs/core": "^11.0.0"}}
NEST_CQRS = {"dependencies": {"@nestjs/core": "^11.0.0", "@nestjs/cqrs": "^11.0.0"}}


class DetectCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self._tmp.name)
        self.sigs = arch_detect.load_signatures()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, rel: str, body: str = "export {}\n") -> None:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)

    def package(self, rel: str, pkg: dict) -> None:
        self.write(os.path.join(rel, "package.json"), json.dumps(pkg))

    def tree(self, rel: str, files: dict) -> None:
        for name, body in files.items():
            self.write(os.path.join(rel, name), body)

    def result(self, rel: str = "") -> dict:
        return arch_detect.analyze(os.path.join(self.root, rel), self.sigs)


FSD = {
    "src/app/index.tsx": "import {P} from '../pages/home'\n",
    "src/pages/home/index.ts": "import {W} from '../../widgets/header'\n",
    "src/widgets/header/index.ts": "import {F} from '../../features/auth'\n",
    "src/features/auth/index.ts": "import {U} from '../../entities/user'\n",
    "src/entities/user/index.ts": "import {B} from '../../shared/ui'\n",
    "src/shared/ui/index.ts": "export const B = 1\n",
}


class SignaturesTest(DetectCase):
    def test_all_refs_have_signatures(self) -> None:
        self.assertEqual(set(self.sigs), set(IDS))
        self.assertEqual(set(arch_detect.LAYERS), set(IDS))

    def test_layers_named_in_refs(self) -> None:
        for arch, tiers in arch_detect.LAYERS.items():
            with open(os.path.join(ARCH, arch + ".md"), encoding="utf-8") as f:
                imports = section(f.read(), "Импорты")
            for layer in (name for tier in tiers for name in tier):
                self.assertIn("`%s`" % layer, imports, "%s %s" % (arch, layer))


class PickTest(DetectCase):
    def check(self, files: dict, pkg: dict, expected: str) -> dict:
        self.package("", pkg)
        self.tree("", files)
        found = self.result()
        self.assertEqual(found["pick"], expected, json.dumps(found["candidates"][:3], ensure_ascii=False))
        return found

    def test_fsd(self) -> None:
        found = self.check(FSD, REACT, "react-fsd")
        self.assertEqual(found["stack"], "react")
        self.assertEqual(found["src"], "src")

    def test_feod(self) -> None:
        self.check({"src/app/index.tsx": "", "src/pages/home/index.ts": "", "src/modules/cart/index.ts": "",
                    "src/common/x.ts": ""}, REACT, "react-feod")

    def test_evolution_medium(self) -> None:
        self.check({"src/app/index.tsx": "", "src/features/tasks/index.ts": "", "src/services/session/index.ts": "",
                    "src/shared/lib/index.ts": ""}, REACT, "react-evolution")

    def test_evolution_small(self) -> None:
        self.check({"src/app/index.tsx": "import {T} from '../features/tasks'\n", "src/features/tasks/index.ts": "",
                    "src/shared/lib/index.ts": ""}, REACT, "react-evolution")

    def test_feature(self) -> None:
        self.check({"src/app/index.tsx": "", "src/features/tasks/components/list.tsx": "",
                    "src/components/button.tsx": "", "src/hooks/use-x.ts": "", "src/lib/api.ts": ""},
                   REACT, "react-feature")

    def test_clean(self) -> None:
        self.check({"src/domain/cart.ts": "", "src/application/add.ts": "import {C} from '../domain/cart'\n",
                    "src/infrastructure/api.ts": "", "src/ui/page.tsx": ""}, REACT, "react-clean")

    def test_nest_new_is_standard(self) -> None:
        found = self.check({"src/main.ts": "", "src/app.module.ts": "", "src/app.controller.ts": "",
                            "src/app.service.ts": ""}, NEST, "nest-standard")
        self.assertEqual(found["stack"], "nest")

    def test_nest_standard_with_modules(self) -> None:
        self.check({"src/app.module.ts": "", "src/users/users.module.ts": "", "src/users/dto/x.dto.ts": "",
                    "src/orders/orders.module.ts": ""}, NEST, "nest-standard")

    def test_nest_modular_clean(self) -> None:
        self.check({"src/app.module.ts": "", "src/modules/users/index.ts": "",
                    "src/modules/users/domain/user.ts": "", "src/modules/users/application/x.service.ts": "",
                    "src/modules/users/infrastructure/repo.ts": ""}, NEST, "nest-modular-clean")

    def test_nest_ddd(self) -> None:
        self.check({"src/app.module.ts": "", "src/contexts/billing/domain/invoice.ts": "",
                    "src/contexts/billing/application/commands/pay.handler.ts": "",
                    "src/contexts/billing/contracts/paid.event.ts": ""}, NEST_CQRS, "nest-ddd-cqrs")


class EdgeTest(DetectCase):
    def test_mixed_has_no_pick_and_explains(self) -> None:
        self.package("", REACT)
        self.tree("", {"src/modules/a/index.ts": "", "src/common/x.ts": "", "src/features/b/index.ts": "",
                       "src/entities/c/index.ts": "", "src/shared/ui/index.ts": ""})
        found = self.result()
        self.assertIsNone(found["pick"])
        fsd = next(c for c in found["candidates"] if c["arch"] == "react-fsd")
        self.assertTrue(any("modules" in item for item in fsd["conflicts"]), fsd)

    def test_empty_react_has_no_pick(self) -> None:
        self.package("", REACT)
        found = self.result()
        self.assertIsNone(found["pick"])
        self.assertEqual(found["src"], ".")

    def test_without_src_uses_package_root(self) -> None:
        self.package("", REACT)
        self.tree("", {name[len("src/"):]: body for name, body in FSD.items()})
        found = self.result()
        self.assertEqual(found["src"], ".")
        self.assertEqual(found["pick"], "react-fsd")

    def test_next_router_app_ignored(self) -> None:
        self.package("", {"dependencies": {"next": "15.0.0", "react": "19.0.0"}})
        self.tree("", dict(FSD, **{"app/page.tsx": "export {}\n", "app/layout.tsx": "export {}\n"}))
        self.assertEqual(self.result()["pick"], "react-fsd")

    def test_only_candidates_of_own_stack(self) -> None:
        self.package("", NEST)
        self.write("src/app.module.ts")
        self.assertTrue(all(c["arch"].startswith("nest-") for c in self.result()["candidates"]))

    def test_bonus_file(self) -> None:
        self.package("", REACT)
        self.tree("", {"src/shared/ui/index.ts": "", "src/features/a/index.ts": "", "steiger.config.ts": ""})
        fsd = next(c for c in self.result()["candidates"] if c["arch"] == "react-fsd")
        self.assertTrue(any("steiger.config.ts" in item for item in fsd["evidence"]), fsd)

    def test_imports_against_layers_lower_score(self) -> None:
        self.package("good", REACT)
        self.tree("good", FSD)
        self.package("bad", REACT)
        self.tree("bad", dict(FSD, **{
            "src/shared/ui/index.ts": "import {F} from '../../features/auth'\nimport {W} from '../../widgets/header'\n",
            "src/entities/user/index.ts": "import {P} from '../../pages/home'\n"}))
        score = lambda rel: next(c["score"] for c in self.result(rel)["candidates"] if c["arch"] == "react-fsd")
        self.assertGreater(score("good"), score("bad"))

    def test_tsconfig_with_comments_and_alias(self) -> None:
        self.package("", REACT)
        self.tree("", {
            "tsconfig.json": '{\n  // Vite\n  "compilerOptions": {\n    /* alias */\n    "baseUrl": ".",\n'
                             '    "paths": {"@/*": ["src/*"],},\n  },\n}\n',
            "src/shared/ui/index.ts": "import {F} from '@/features/auth'\n",
            "src/features/auth/index.ts": "", "src/entities/user/index.ts": "",
        })
        fsd = next(c for c in self.result()["candidates"] if c["arch"] == "react-fsd")
        self.assertTrue(any("0%" in item for item in fsd["evidence"]), fsd)

    def test_vite_tsconfig_references_alias(self) -> None:
        self.package("", REACT)
        self.tree("", {
            "tsconfig.json": '{"files": [], "references": [{"path": "./tsconfig.app.json"}]}',
            "tsconfig.app.json": '{"compilerOptions": {"paths": {"@/*": ["./src/*"]}}}',
            "src/shared/ui/index.ts": "import {F} from '@/features/auth'\n",
            "src/features/auth/index.ts": "", "src/entities/user/index.ts": "",
        })
        fsd = next(c for c in self.result()["candidates"] if c["arch"] == "react-fsd")
        self.assertTrue(any("0%" in item for item in fsd["evidence"]), fsd)


class RootsTest(DetectCase):
    def test_npm_workspaces(self) -> None:
        self.package("", {"workspaces": ["apps/*"]})
        self.package("apps/web", REACT)
        self.tree("apps/web", FSD)
        self.package("apps/api", NEST)
        self.write("apps/api/src/app.module.ts")
        self.package("apps/docs", {"dependencies": {"vitepress": "1"}})
        roots = [os.path.relpath(r, self.root) for r in arch_detect.find_roots(self.root)]
        self.assertEqual(roots, ["apps/api", "apps/web"])

    def test_pnpm_workspace_with_quotes_and_negation(self) -> None:
        self.package("", {"name": "mono"})
        self.write("pnpm-workspace.yaml", "packages:\n  - 'apps/*'\n  - \"libs/*\"\n  - '!**/test/**'\n")
        self.package("apps/web", REACT)
        self.package("libs/api", NEST)
        roots = [os.path.relpath(r, self.root) for r in arch_detect.find_roots(self.root)]
        self.assertEqual(roots, ["apps/web", "libs/api"])

    def test_turbo_without_workspaces(self) -> None:
        self.package("", {"name": "mono"})
        self.write("turbo.json", "{}")
        self.package("apps/web", REACT)
        self.package("packages/ui", {"dependencies": {"react": "19"}})
        roots = [os.path.relpath(r, self.root) for r in arch_detect.find_roots(self.root)]
        self.assertEqual(roots, ["apps/web", "packages/ui"])

    def test_single_package(self) -> None:
        self.package("", REACT)
        self.assertEqual(arch_detect.find_roots(self.root), [self.root])

    def test_no_react_or_nest(self) -> None:
        self.package("", {"dependencies": {"express": "5"}})
        self.assertEqual(arch_detect.find_roots(self.root), [])

    def test_cli(self) -> None:
        self.package("", REACT)
        self.tree("", FSD)
        proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "arch_detect.py"), self.root],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["roots"][0]["root"], ".")
        self.assertEqual(data["roots"][0]["pick"], "react-fsd")


class PickRuleTest(unittest.TestCase):
    def test_threshold_and_gap(self) -> None:
        cand = lambda *scores: [{"arch": "a%d" % i, "score": s} for i, s in enumerate(scores)]
        self.assertEqual(arch_detect.pick(cand(0.6)), "a0")
        self.assertIsNone(arch_detect.pick(cand(0.59)))
        self.assertEqual(arch_detect.pick(cand(0.8, 0.65)), "a0")
        self.assertIsNone(arch_detect.pick(cand(0.8, 0.66)))
        self.assertIsNone(arch_detect.pick([]))


if __name__ == "__main__":
    unittest.main()
