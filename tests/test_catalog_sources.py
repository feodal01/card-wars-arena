import json
import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cardwars.arena.catalog import make_catalog


@unittest.skipUnless(os.environ.get("CARDWARS_UNITY_PROJECT"), "requires the Unity source project")
class CatalogSourceTests(unittest.TestCase):
    def test_all_modes_render_native_english(self):
        project = Path(os.environ["CARDWARS_UNITY_PROJECT"])
        for mode, count in (("no_obsidian", 258), ("full", 272), ("sample40", 40)):
            with self.subTest(mode=mode):
                text, cards, heroes, factions = make_catalog(project, 3, mode)
                self.assertEqual(len(cards), count)
                self.assertEqual(set(cards), set(factions))
                self.assertEqual(len(heroes), 72)
                self.assertNotRegex(text, r"[А-Яа-яЁё]|<val\d+>|\{[^}]+\}|!!\w+")
                self.assertIn("## Cards", text)
                self.assertIn("## Heroes", text)

    def test_rebuild_rereads_blueprints_english_assets_enums_and_execution_literals(self):
        original = Path(os.environ["CARDWARS_UNITY_PROJECT"]) / "Assets"
        with TemporaryDirectory() as directory:
            project = Path(directory)
            assets = project / "Assets"
            tables = assets / "StreamingAssets/Blueprints"
            scripts = assets / "Scripts/Assembly-CSharp"
            language = assets / "Resources/languages"
            for folder in (tables, scripts, language):
                folder.mkdir(parents=True)
            for table in ("Creatures", "Spells", "Buildings", "Leaders"):
                name = f"db_{table}.json"
                shutil.copy2(original / "StreamingAssets/Blueprints" / name, tables / name)
            for file in (original / "Resources/languages").glob("EN_*.txt"):
                shutil.copy2(file, language / file.name)
            # Link unmodified source files and replace just the ones under test.
            for file in (original / "Scripts/Assembly-CSharp").glob("*.cs"):
                (scripts / file.name).symlink_to(file)

            creatures = json.loads((tables / "db_Creatures.json").read_text())
            ninja = next(row for row in creatures if row["ID"] == "Creature_WhiteNinja")
            ninja.update(val1="23", val2="29", Cost="11")
            (tables / "db_Creatures.json").write_text(json.dumps(creatures))
            for file in language.glob("EN_*.txt"):
                text = file.read_text()
                if ">White Ninja</entry>" in text:
                    file.write_text(text.replace(">White Ninja</entry>", ">Test Ninja</entry>"))

            def replace_local_source(name, before, after):
                path = scripts / name
                content = path.read_text()
                self.assertIn(before, content)
                path.unlink()
                path.write_text(content.replace(before, after))

            replace_local_source("ShuffleAndDraw.cs", "i < 5", "i < 6")
            replace_local_source("Faction.cs", "Corn = 0", "TestFaction = 0")
            text, *_ = make_catalog(project, 3, "no_obsidian")

            def line(card_id):
                return next(item for item in text.splitlines() if item.startswith(f"- `{card_id}` "))

            self.assertIn("Test Ninja", line("Creature_WhiteNinja"))
            self.assertIn("mana 11", line("Creature_WhiteNinja"))
            self.assertIn("23 damage", line("Creature_WhiteNinja"))
            self.assertIn("29 HP", line("Creature_WhiteNinja"))
            self.assertIn("draw up to 6 cards", line("Spell_CrystalBall"))
            self.assertIn("opposing TestFaction creature", line("Creature_FlySwatter"))
            replace_local_source("ShuffleAndDraw.cs", "i < 6", "i < drawLimit")
            with self.assertRaisesRegex(ValueError, r"ShuffleAndDraw\.cs.*draw_count"):
                make_catalog(project, 3, "no_obsidian")
