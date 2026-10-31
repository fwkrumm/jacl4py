"""Keep requirements installations consistent with published dependencies."""

import unittest
from importlib.metadata import requires
from pathlib import Path


class TestRequirements(unittest.TestCase):
    """Detect drift between requirements.txt and installed package metadata."""

    def test_requirements_match_distribution_metadata(self):
        """Runtime requirements match the installed distribution metadata."""
        requirements_path = Path(__file__).resolve().parents[1] / "requirements.txt"
        requirements = requirements_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            sorted(requirement.strip() for requirement in requirements if requirement.strip()),
            sorted(requires("jacl4py") or []),
        )
