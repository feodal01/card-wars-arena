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
