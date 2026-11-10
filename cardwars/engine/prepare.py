"""Create an isolated arena project from a recovered Card Wars Unity 2022 project."""

import re
import shutil
import tempfile
from pathlib import Path

from cardwars.arena.catalog_audit import check_sources
from cardwars.engine.unity.install import install


def prepare_project(source: Path, destination: Path) -> int:
    source, destination = source.resolve(), destination.resolve()
    if destination.exists() or destination.is_relative_to(source):
        raise ValueError("Choose a new destination outside the source project.")
    version = source / "ProjectSettings/ProjectVersion.txt"
    if not version.is_file() or "m_EditorVersion: 2022.3.62f3" not in version.read_text().splitlines():
        raise ValueError("Supply a recovered Unity 2022.3.62f3 project containing Assets, Packages and ProjectSettings.")
    for required in ("Assets/Scripts/Assembly-CSharp/GameState.cs", "Assets/Scenes/StartupScene.unity",
                     "Assets/StreamingAssets/Blueprints/db_Leaders.json", "Packages/manifest.json"):
        if not (source / required).is_file():
            raise ValueError(f"The recovered project is missing {required}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        project = Path(temporary) / "arena"
        for folder in ("Assets", "Packages", "ProjectSettings"):
            shutil.copytree(source / folder, project / folder)
        settings = project / "ProjectSettings/ProjectSettings.asset"
        text = settings.read_text()
        # Standalone also occurs under unrelated settings. Edit only the bundle identifier map.
        for pattern, replacement in (
            (r"(?m)^  companyName:.*$", "  companyName: CardWarsArena"),
            (r"(?m)^  productName:.*$", "  productName: Card Wars Arena"),
            (r"(?m)(^  applicationIdentifier:\n(?:    [^\n]*\n)*?)^    Standalone:.*$",
             r"\g<1>    Standalone: local.cardwars.arena"),
        ):
            text, count = re.subn(pattern, replacement, text)
            if count != 1:
                raise ValueError("Unrecognized Unity PlayerSettings format")
        settings.write_text(text)
        (project / "Assets/Editor").mkdir(exist_ok=True)
        install(project)
        checked = check_sources(project)
        project.rename(destination)
    return checked
