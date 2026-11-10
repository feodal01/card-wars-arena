# Preparing the native engine

The live arena runs inside a recovered, functioning Card Wars project ported to Unity Editor 2022.3.62f3 (revision 96770f904ca7). This repository contains the Python host and the Unity additions. Its supported starting point for new games is the recovered editor project. Recovery of a retail APK, migration from the original Unity version, and device signing are outside this installer.

The input needs the original scripts under `Assets/Scripts/Assembly-CSharp`, the `StartupScene` and battle scenes, the English files under `Assets/Resources/languages`, and the original art and `StreamingAssets/Blueprints` tables. The installer checks the project version and the prepared effect sources. For the recorded build it verifies 222 files. The arena does its work on a new copy, with company name `CardWarsArena` and standalone identifier `local.cardwars.arena`.

```sh
export CARDWARS_UNITY_PROJECT="$PWD/local/arena-unity"
uv run --locked cardwars prepare-engine /path/to/recovered-card-wars "$CARDWARS_UNITY_PROJECT"
UNITY_EDITOR="/Applications/Unity/Hub/Editor/2022.3.62f3/Unity.app/Contents/MacOS/Unity"
"$UNITY_EDITOR" -batchmode -quit -buildTarget StandaloneOSX -projectPath "$CARDWARS_UNITY_PROJECT" -logFile "$CARDWARS_UNITY_PROJECT/import.log"
uv run --locked cardwars match results/2026-11-10-random-baseline/match.toml --output runs/baseline-42
uv run --locked cardwars verify runs/baseline-42/trace.jsonl
```

The prepared project may be reused for future matches. The host takes an exclusive lock while using it. Inspect `import.log` if Unity fails on first import, and the corresponding run’s `game-N/unity.log` for a battle startup failure. Use [the archived baseline](../results/2026-11-10-random-baseline/trace.html) to compare the five-game result. The [catalog audit](rules-review.md) explains the source hashes and generated card descriptions.

## Starting from your own Android copy

The recovery used for these recordings combined the Android v1.11.0 application with its matching expansion data. The APK contains the managed assemblies under `assets/bin/Data/Managed/`. The `main.92.com.turner.cardwars.obb` expansion contains the bulk of the serialized game assets. Keep the two archives from the same build together and work in a separate directory.

1. Extract the two archives locally, retaining the `assets/` directory layout. Preserve the original managed assemblies. Builds labelled v1.11.0 can contain different assemblies.
2. The historical export used AssetRipper 2.0.0, hybrid script export, extracted streaming assets and decompiled shaders. Its exported project targeted Unity 5.2.3f1. The native Android data also contained 5.2.1p3 assets.
3. Before the Unity 2022 arena setup, that export required a game port. The recovery repaired serialization for lane arrays, camera targets and creature spawn points, migrated legacy particle and GUI components, restored materials and streaming Blueprint tables, and configured local startup. In an already ported project, confirm that the startup scene can enter a battle with two five-card opening hands.
4. Run the preparation and baseline commands above. Compare the generated English catalog to the [published catalog](catalog.md) and verify the match trace.

The reproducibility check for this release starts at the working Unity 2022 editor project. The APK extraction and legacy-to-2022 migration are historical recovery notes, not an automated APK importer. Keep the recovered source and game assets outside Git; `local/` is ignored.
