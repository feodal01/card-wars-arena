import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from cardwars.arena import catalog_audit


class CatalogAuditTests(TestCase):
    def test_changed_new_and_removed_effects_are_reported_by_name(self):
        with TemporaryDirectory() as tmp:
            project = Path(tmp)
            scripts = project / "Assets/Scripts/Assembly-CSharp"
            tables = project / "Assets/StreamingAssets/Blueprints"
            scripts.mkdir(parents=True)
            tables.mkdir(parents=True)
            for table in catalog_audit.TABLES:
                (tables / f"db_{table}.json").write_text("[]")
            leaders = tables / "db_Leaders.json"
            leaders.write_text('[{"ScriptName":"OldEffect"}]')
            for name in ("Shared", "OldEffect", "NewEffect"):
                (scripts / f"{name}.cs").write_text(f"class {name} {{}}")
            baseline = project / "reviewed.json"
            with patch.object(catalog_audit, "SHARED", {"Shared"}), patch.object(catalog_audit, "BASELINE", baseline):
                baseline.write_text(json.dumps(catalog_audit.source_hashes(project)))
                self.assertEqual(catalog_audit.check_sources(project), 2)
                leaders.write_text('[{"ScriptName":"NewEffect"}]')
                (scripts / "Shared.cs").write_text("class Shared { int damage; }")
                with self.assertRaisesRegex(ValueError, "NewEffect, OldEffect, Shared"):
                    catalog_audit.check_sources(project)
