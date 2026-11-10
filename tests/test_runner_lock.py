import fcntl
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from cardwars.arena.runner import run


class MatchOwnershipTest(unittest.TestCase):
    def test_busy_unity_project_does_not_create_or_modify_a_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "arena"
            settings = project / "ProjectSettings"
            settings.mkdir(parents=True)
            (settings / "ProjectSettings.asset").write_text("companyName: CardWarsArena\n")
            output = project.parent / "out"
            with (project / "CardWarsArena.host.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                with self.assertRaisesRegex(ValueError, "already in use"):
                    run(SimpleNamespace(project=project), output)
            self.assertFalse(output.exists())
