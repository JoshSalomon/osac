"""Check that shared developer tools resolve inside the repository.

Run: python3 tools/test/test_repo_tools.py
"""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RepoToolsTest(unittest.TestCase):
    def test_golangci_lint_lives_in_the_ignored_tools_bin(self):
        """A repo-root bin/ is not gitignored; the shared cache is tools/bin."""
        result = subprocess.run(
            ["make", "-f", "tools/golangci-lint.mk", "-p", "-n"],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
        tools_dir = re.search(r"^GOLANGCI_LINT_TOOLS_DIR := (.+)$", result.stdout, re.M)
        self.assertIsNotNone(tools_dir, result.stdout[-2000:] + result.stderr[-2000:])
        self.assertEqual(tools_dir.group(1).strip(), str(ROOT / "tools"))
        binary = re.search(r"^GOLANGCI_LINT_BIN = (.+)$", result.stdout, re.M)
        self.assertIsNotNone(binary)
        self.assertEqual(binary.group(1).strip(), "$(GOLANGCI_LINT_TOOLS_DIR)/bin")


if __name__ == "__main__":
    unittest.main()
