"""Install the Unity bridge into a separate, arena-branded recovered game project."""
import argparse
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def install(project):
    if 'companyName: CardWarsArena' not in (project / 'ProjectSettings/ProjectSettings.asset').read_text():
        raise ValueError("Use an isolated project with companyName CardWarsArena")
    scripts = project / 'Assets/Scripts/Assembly-CSharp'
    editor = project / 'Assets/Editor'
    for name in ('ArenaOpening', 'ArenaMatch', 'ArenaCombat', 'ArenaCapture'):
        source = HERE / (name + '.cs')
        shutil.copyfile(source, editor / source.name)
    for name in ('ArenaChoices.cs', 'ArenaSpectator.cs', 'ArenaTerrain.cs', 'ArenaRecordingAudio.cs'):
        shutil.copyfile(HERE / name, scripts / name)

    # Split the original deck editor's method at its UI boundaries. Both callers
    # now invoke exactly one native implementation of the landscape calculation.
    controller = scripts / 'CWDeckController.cs'
    source = controller.read_text()
    signature = 'public static void SetArenaDeckLandscapes(Deck deck)'
    if signature not in source:
        start = source.index('\tpublic void SetLandscapes()')
        counts = source.index('\t\tDictionary<Faction, int> dictionary', start)
        preview = source.index('\t\tLandscapePreviewController instance', counts)
        end = source.index('\n\t}\n', preview) + len('\n\t}\n')
        shared = '\n\t' + signature + '\n\t{\n' + source[counts:preview] + '\t}\n'
        controller.write_text(source[:counts] + '\t\tSetArenaDeckLandscapes(deck);\n'
                              + source[preview:end] + shared + source[end:])

    # Use the human target picker for both seats, preserving the owner and the
    # card-specific side, target filters and OnTargetSelected callbacks.
    for path in scripts.glob('*.cs'):
        content = path.read_text()
        if 'StartTargetSelection(' in content or 'OpenDiscardPile();' in content:
            before = content
            content = content.replace('ArenaChoices.Enabled || base.Owner == PlayerType.User',
                                      'ArenaChoices.ExternalOpponent || base.Owner == PlayerType.User')
            patched = re.sub(r'if \(base.Owner == PlayerType.User\)(\s*\{\s*(?:SelectingBuilding = true;\s*)?(?:StartTargetSelection|OpenDiscardPile)\()',
                             r'if (ArenaChoices.ExternalOpponent || base.Owner == PlayerType.User)\1', content)
            if patched != before:
                path.write_text(patched)

    # These early-outs prune unprofitable moves for the built-in computer
    # player. Human seats can legally spend the ability even when it helps no card.
    for name in ('ActionPointCreatures', 'ActionPointLandscapes', 'DestroyEntityForAction',
                 'DiscardForPoints', 'FlatFloopCost', 'GainActionPointsLeader', 'SacrificeForMP',
                 'BlockFloopTarget', 'BlockTargetFloop'):
        path = scripts / (name + '.cs')
        content = path.read_text()
        before = content
        content = content.replace('!ArenaChoices.Enabled && flag', '!ArenaChoices.ExternalOpponent && flag')
        content = content.replace('ArenaChoices.Enabled || player == PlayerType.User', 'ArenaChoices.ExternalOpponent || player == PlayerType.User')
        if name.startswith('Block'):
            guarded = re.sub(r'(?<!ArenaChoices.ExternalOpponent \|\| )((?:base.Owner|player) == PlayerType.User \|\| creature.CanFloop\(\))',
                             r'ArenaChoices.ExternalOpponent || \1', content)
        else:
            guarded = re.sub(r'(?<!!)\b((?:base.Owner|player) == PlayerType.Opponent) && flag',
                             r'\1 && !ArenaChoices.ExternalOpponent && flag', content)
        if guarded != before:
            path.write_text(guarded)

    def inject(file, signature, body):
        path = scripts / (file + '.cs')
        content = path.read_text()
        anchor = signature + '\n\t{\n'
        if content.count(anchor) != 1:
            raise ValueError(f"Unexpected recovered source: {file}.{signature}")
        block = anchor + '\t\t' + body + '\n'
        if block not in content:
            path.write_text(content.replace(anchor, block))

    # Gunter's FC blueprint refers to the missing cosmetic key Gunter02. Its
    # portrait and both packaged Gunter character prefabs match ordinary Gunter.
    # CharacterData controls visuals/audio. LeaderForm still owns all game rules.
    inject('CharacterDataManager', 'public CharacterData GetCharacterData(string id)',
           'if (id == "Gunter02" && !Characters.ContainsKey(id) && '
           '!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("CARD_WARS_OPENING"))) id = "Gunter";')
    target_hook = 'if (ArenaChoices.Enabled) { ArenaChoices.SelectLane(this, player, targetType, instruction); return; }'
    card_script = scripts / 'CardScript.cs'
    old_hook = target_hook.replace('player, targetType, instruction', 'player, instruction')
    content = card_script.read_text()
    if old_hook in content:
        card_script.write_text(content.replace(old_hook, target_hook))
    inject('CardScript', 'protected void StartTargetSelection(PlayerType player, SelectionType targetType, string instruction)',
           target_hook)
    inject('CardScript', 'protected void EndTargetSelection()',
           'if (ArenaChoices.Enabled) { Flooping = false; return; }')
    inject('CardScript', 'public void OpenDiscardPile()',
           'if (ArenaChoices.Enabled) { CardSelected = false; ArenaChoices.Discard = this; return; }')
    inject('CardScript', 'public void CloseDiscardPile()',
           'if (ArenaChoices.Enabled) { CardSelected = true; return; }')
    # Native animation sequences normally call these same DoResult methods at
    # the impact frame. Invoke synchronously before publishing the next state.
    for call in ('DoEffect', 'DoEffectNeutral'):
        inject('CWFloopActionManager', f'public void {call}(CardScript source, CardScript[] targets)',
               'if (ArenaChoices.Enabled) { ArenaChoices.Resolve(source, targets); return; }')
    inject('CWFloopActionManager', 'public void DoEffect(CardScript source, PlayerType player)',
           'if (ArenaChoices.Enabled) { source.DoResult(null); return; }')
    inject('CWFloopActionManager', 'public void DoEffect(CardScript source, int lane)',
           'if (ArenaChoices.Enabled) return; // Persistent lane FX has no DoResult callback.')
    inject('TutorialMonitor', 'public bool ShouldTriggerTutorial(TutorialInfo info, bool ignoreDummy)',
           'if (ArenaChoices.Enabled) return false;')
    # Landscape variety powers count distinct placed types. In manual setup
    # the None sentinel represents an empty table slot, not another faction.
    state = scripts / 'GameState.cs'
    source = state.read_text()
    for signature in ('public int LandscapeTypeCount(PlayerType player)', 'public int LandscapeTypeCount()'):
        start = signature + '\n\t{\n\t\tbool[] array = new bool[Enum.GetNames(typeof(LandscapeType)).Length];\n'
        changed = start + '\t\tarray[(int)LandscapeType.None] = ArenaChoices.ManualLandscapes;\n'
        if start not in source:
            raise ValueError('Unexpected ' + signature)
        if changed not in source:
            source = source.replace(start, changed)
    if source != state.read_text():
        state.write_text(source)
    inject('BlockSummon', 'public override bool CanFloop()',
           'if (ArenaChoices.ManualLandscapes && CurrentLane.OpponentLane.Type == LandscapeType.None) return false;')
    inject('GameState', 'public void FlipLandscape(PlayerType player, int lane, bool flip)',
           'if (ArenaChoices.ManualLandscapes && GetLandscapeType(player, lane) == LandscapeType.None) return;')
    inject('GameState', 'public void HighlightLandscape(PlayerType player, int lane)',
           'if (ArenaChoices.ManualLandscapes && GetLandscapeType(player, lane) == LandscapeType.None) return;')
    # The arena drives phases, while the stock intro/NGUI tweens schedule
    # delayed setup phases. Those callbacks can otherwise interrupt a wheel.
    inject('BattlePhaseManager', 'public void SetPhase(float delay, BattlePhase phase)',
           'if (ArenaChoices.Enabled) return;')
    # The recovered client can apply the opponent's entire deck layout on a
    # scene event or auto-place the user's row through its old landscape UI.
    inject('LandscapeManagerScript', 'public void AssignOpponentLandscapes()',
           'if (ArenaChoices.ManualLandscapes) return;')
    inject('CWiTweenLandscapeTrigger', 'private void OnClick()',
           'if (ArenaChoices.ManualLandscapes) return;')
    inject('CWLandscapeCardDragOld', 'private void OnPress(bool pressed)',
           'if (ArenaChoices.ManualLandscapes) return;')
    inject('CWLandscapeFillCards', 'private void OnEnable()',
           'if (ArenaChoices.ManualLandscapes) return;')
    inject('CWOpponentActionSequencer', 'public IEnumerator StartOpponentSequence()',
           'if (ArenaChoices.Enabled) yield break;')
    # Keep GameState.Summon bookkeeping but use the animation-independent
    # DoResultSummon entry point for rare cards in an external-player session.
    path = scripts / 'GameState.cs'
    content = path.read_text()
    old = 'if (card.Form.Rarity >= 5)'
    new = 'if (!ArenaChoices.Enabled && card.Form.Rarity >= 5)'
    if old in content:
        assert content.count(old) == 1
        path.write_text(content.replace(old, new))
    elif new not in content:
        raise ValueError('Unexpected GameState.Summon implementation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    install(parser.parse_args().project)
