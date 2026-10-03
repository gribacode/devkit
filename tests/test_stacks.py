import os
import sys
import unittest

from tests.helpers import HOOKS, HookTestCase

sys.path.insert(0, HOOKS)
import _stacks  # noqa: E402

KINDS = {
    "src/a.ts": "js", "src/a.tsx": "js", "x.mjs": "js", "x.cjs": "js",
    "app/main.py": "python", "stubs/x.pyi": "python",
    "Dockerfile": "dockerfile", "Dockerfile.dev": "dockerfile", "api.Dockerfile": "dockerfile",
    "Containerfile": "dockerfile",
    "compose.yaml": "compose", "compose.prod.yml": "compose", "docker-compose.yml": "compose",
    "docker-compose.override.yml": "compose",
    "nginx.conf": "nginx", "deploy/nginx/site.conf": "nginx", "etc/conf.d/app.conf": "nginx",
    "sites-enabled/default.conf": "nginx",
    "README.md": None, "data.json": None, "client.conf": None, "values.yaml": None,
}


class KindTest(unittest.TestCase):
    def test_kind_table(self) -> None:
        for rel, expected in KINDS.items():
            self.assertEqual(_stacks.kind(os.path.join("/repo", rel)), expected, rel)


class ToolsTest(HookTestCase):
    def test_biome_needs_config_and_binary(self) -> None:
        path = self.write("p/src/a.ts", "x\n")
        self.assertIsNone(_stacks.biome(path))
        self.write("p/biome.json", "{}")
        self.assertIsNone(_stacks.biome(path))
        binary = self.write("p/node_modules/.bin/biome", "#!/bin/sh\n", executable=True)
        self.assertEqual(_stacks.biome(path), (binary, os.path.join(self.home, "p")))

    def test_oxlint_needs_config_and_binary(self) -> None:
        path = self.write("p/src/a.ts", "x\n")
        self.write("p/node_modules/.bin/oxlint", "#!/bin/sh\n", executable=True)
        self.assertIsNone(_stacks.oxlint(path))
        self.write("p/.oxlintrc.json", "{}")
        self.assertEqual(_stacks.oxlint(path)[1], os.path.join(self.home, "p"))

    def test_python_bin_prefers_venv(self) -> None:
        path = self.write("p/app/a.py", "x\n")
        venv = self.write("p/.venv/bin/ruff", "#!/bin/sh\n", executable=True)
        self.assertEqual(_stacks.python_bin(path, "ruff"), venv)

    def test_ruff_root(self) -> None:
        path = self.write("p/app/a.py", "x\n")
        self.write("p/pyproject.toml", "[project]\nname = 'x'\n")
        self.assertIsNone(_stacks.ruff_root(path))
        self.write("p/pyproject.toml", "[project]\nname = 'x'\n\n[tool.ruff.lint]\nselect = ['E']\n")
        self.assertEqual(_stacks.ruff_root(path), os.path.join(self.home, "p"))
        other = self.write("q/a.py", "x\n")
        self.write("q/ruff.toml", "")
        self.assertEqual(_stacks.ruff_root(other), os.path.join(self.home, "q"))

    def test_python_typechecker(self) -> None:
        path = self.write("p/app/a.py", "x\n")
        self.assertIsNone(_stacks.python_typechecker(path))
        self.write("p/pyproject.toml", "[tool.mypy]\nstrict = true\n")
        self.assertEqual(_stacks.python_typechecker(path), "mypy")
        self.write("p/pyrightconfig.json", "{}")
        self.assertEqual(_stacks.python_typechecker(path), "pyright")

    def test_python_root(self) -> None:
        path = self.write("p/app/a.py", "x\n")
        self.assertEqual(_stacks.python_root(path), os.path.join(self.home, "p", "app"))
        self.write("p/pyproject.toml", "")
        self.assertEqual(_stacks.python_root(path), os.path.join(self.home, "p"))

    def test_compose_files_pairs_override_with_base(self) -> None:
        base = self.write("c/docker-compose.yml", "services: {}\n")
        override = self.write("c/docker-compose.override.yml", "services: {}\n")
        self.assertEqual(_stacks.compose_files(base), [base])
        self.assertEqual(_stacks.compose_files(override), [base, override])
        lone = self.write("d/compose.prod.yaml", "services: {}\n")
        self.assertEqual(_stacks.compose_files(lone), [lone])


    def test_compose_files_finds_base_up_to_repo_root(self) -> None:
        os.makedirs(os.path.join(self.home, "repo", ".git"))
        base = self.write("repo/docker-compose.yml", "services: {}\n")
        override = self.write("repo/deploy/docker-compose.prod.yml", "services: {}\n")
        self.assertEqual(_stacks.compose_files(override), [base, override])

    def test_compose_files_stops_at_repo_root(self) -> None:
        self.write("docker-compose.yml", "services: {}\n")
        os.makedirs(os.path.join(self.home, "repo", ".git"))
        override = self.write("repo/deploy/compose.prod.yaml", "services: {}\n")
        self.assertEqual(_stacks.compose_files(override), [override])


if __name__ == "__main__":
    unittest.main()
