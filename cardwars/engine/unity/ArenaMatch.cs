using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Map = System.Collections.Generic.Dictionary<string, object>;

public sealed class ArenaMatch
{
    [Serializable] private sealed class Submission { public string id; }
    private readonly GameState game;
    private readonly GameDataScript data;
    private readonly string directory;
    private sealed class Move
    {
        public Action Execute;
        public string Announcement;
        public CardItem Card;
        public Action Preview;
    }
    private readonly Dictionary<string, Move> handlers = new Dictionary<string, Move>();
    private readonly bool watching;
    private readonly LandscapeType[] campaignLandscapes;
    private readonly List<LandscapeType>[] remainingLandscapes = new List<LandscapeType>[2];
    private Move pending;
    private double showUntil;
    private readonly List<Map> choices = new List<Map>();
    private readonly List<string> events = new List<string>();
    private int revision;
    private bool published;
    private bool inCombat;
    private Exception failure;
    private double transitionStart;
    private int actedFrame;

    public ArenaMatch(GameState game, string directory, int first, int gameNumber, bool landscapesFirst, string[][] landscapes, string[][] decks, string[] displayNames = null)
    {
        if (first != 0 && first != 1) throw new ArgumentOutOfRangeException("first");
        this.game = game;
        this.directory = directory;
        data = GameDataScript.GetInstance();
        ArenaChoices.Enabled = true;
        // Setup has already shuffled the opponent's landscape slots, just as in campaign play.
        if (ArenaChoices.CampaignOpponent)
            campaignLandscapes = Enumerable.Range(0, GameState.LANE_COUNT)
                .Select(i => game.GetLandscapeInDeck(PlayerType.Opponent, i)).ToArray();
        var phaseManager = BattlePhaseManager.GetInstance();
        phaseManager.enabled = false;
        phaseManager.StopAllCoroutines();
        BattleManagerScript.GetInstance().enabled = false;
        BattleManagerScript.GetInstance().BattlePaused = false;
        data.enabled = false;
        CWOpponentActionSequencer.GetInstance().StopAllCoroutines();
        CWOpponentActionSequencer.GetInstance().enabled = false;
        for (int side = 0; side < 2; side++)
        {
            var tiles = landscapes[side].Select(t => (LandscapeType)Enum.Parse(typeof(LandscapeType), t)).ToList();
            if (ArenaChoices.ManualLandscapes) remainingLandscapes[side] = tiles;
            for (int lane = 0; lane < GameState.LANE_COUNT; lane++)
            {
                // Assets are pooled from the deck supply during GameState.Setup.
                // Reset the original opponent deck's shuffled slots before play.
                var type = ArenaChoices.ManualLandscapes ? LandscapeType.None : tiles[lane];
                if (ArenaChoices.ManualLandscapes) game.LandscapeManager.RemoveLandscape(side, lane);
                game.GetDeck(side).SetLandscape(lane, type);
                game.SetLandscape(side, lane, type);
            }
            if (!ArenaChoices.ManualLandscapes && !game.GetLanes(side).Select(l => l.Type).SequenceEqual(tiles))
                throw new InvalidOperationException("Native lane order differs from opening for seat " + side);
        }
        game.LandscapeManager.UpdateLandscapes();
        watching = Environment.GetEnvironmentVariable("CARD_WARS_WATCH") == "1";
        TakeOverScene(watching);
        data.FirstPlayer = data.ActivePlayer = first + 1;
        data.Turn = 0;
        if (!landscapesFirst) BeginFirstTurn();
        events.Add("First-player draw: seat " + first + " goes first. Opening turn has no attack.");
        SetSetupPhase();
        if (watching) ArenaSpectator.Open(game, gameNumber, decks, landscapes, displayNames);
        transitionStart = EditorApplication.timeSinceStartup;
        actedFrame = Time.frameCount;
    }

    private void BeginFirstTurn()
    {
        int first = data.FirstPlayer - 1;
        data.ActivePlayer = data.FirstPlayer;
        data.Turn = 1;
        game.SetMagicPoints(first, ParametersManager.Instance.Starting_Magic_Points);
        game.EndTurn(!(PlayerType)first);
        game.StartTurn(first);
    }

    private void TakeOverScene(bool showHud)
    {
        // The external seats already placed their landscapes. Hide the entire
        // setup UI root so delayed intro tweens cannot redisplay its cards.
        var panel = GameObject.Find("Battle UI Panel").transform;
        panel.Find("B").gameObject.SetActive(false);
        panel.Find("A_0_ContinueButton").gameObject.SetActive(false);
        panel.Find("A_1_BattleIntroLabels").gameObject.SetActive(false);
        var intro = CWBattleIntroController.GetInstance();
        if (intro != null)
        {
            intro.enabled = false;
            intro.StopAllCoroutines();
            var nis = intro.GetComponent<NisLaunchHelper>();
            nis.StopAllCoroutines();
            nis.Reset();
            if (intro.Logos != null) intro.Logos.SetActive(false);
        }

        // The campaign intro's ContinueButton schedules LandScape on this same
        // phase manager even in batch mode. Both modes must cancel it above.
        if (!showHud) return;
        foreach (var name in new[] {"Q_Player", "Q_OpponentInfo"})
        {
            var hud = panel.Find("Q/Q_8_PlayersInfo/" + name).gameObject;
            hud.SetActive(true);
            var tween = hud.GetComponent<UITweener>();
            if (tween != null) tween.Sample(1f, true);
        }
    }

    private void FrameActiveSeat()
    {
        var manager = PanelManagerBattle.GetInstance();
        var camera = manager.newCamera;
        var target = manager.newCameraTarget;
        camera.GetComponent<Animation>().Stop();
        iTween.Stop(camera);
        iTween.Stop(target);
        var position = GameObject.Find("Battle GameCamera Destinations/Pos_P1SetupPosition").transform.position;
        var lookAt = GameObject.Find("Battle GameCamera LookAtTargetDestinations/Pos_P1SetupTarget").transform.position;
        if (Seat == 1)
        {
            // The retail CPU camera stays on the human's side of the table.
            // Mirror the human board framing about the center of its eight slots.
            Vector3 center = Vector3.zero;
            for (int side = 0; side < 2; side++)
                for (int lane = 0; lane < GameState.LANE_COUNT; lane++)
                    center += game.CreatureManager.Spawn_Points[side, lane, 0].position;
            center /= 2 * GameState.LANE_COUNT;
            var rotation = Quaternion.Euler(0, 180, 0);
            position = center + rotation * (position - center);
            lookAt = center + rotation * (lookAt - center);
        }
        camera.transform.position = position;
        target.transform.position = lookAt;
        target.GetComponent<CWMenuCameraTarget>().followFlag = true;
        camera.transform.LookAt(lookAt);
    }

    private int Seat => data.ActivePlayer - 1;
    private int Winner => game.GetHealth(0) <= 0 ? 1 : game.GetHealth(1) <= 0 ? 0 : -1;

    private void SetSetupPhase()
    {
        BattlePhaseManager.GetInstance().Phase = Seat == 0 ? BattlePhase.P1Setup : BattlePhase.P2Setup;
        if (watching) FrameActiveSeat();
    }

    public bool Tick()
    {
        if (failure != null) throw new InvalidOperationException("Arena combat failed", failure);
        if (pending != null)
        {
            if (EditorApplication.timeSinceStartup < showUntil) return false;
            var move = pending;
            pending = null;
            actedFrame = Time.frameCount;
            move.Execute();
            return false;
        }
        if (watching && revision == 0 && ArenaSpectator.Presenting) return false;
        if (!published)
        {
            if (EditorApplication.timeSinceStartup - transitionStart > 180)
                throw new TimeoutException("Arena transition timed out at revision " + revision);
            if (inCombat || ArenaSpectator.Placing || Time.frameCount <= actedFrame + 1) return false;
            if (Winner < 0 && (game.GetSummoning() != null || HasDyingCreature())) return false;
            if (data.Turn == 0 && remainingLandscapes[Seat].Count == 0)
            {
                if (remainingLandscapes[1 - Seat].Count == 0) BeginFirstTurn();
                else data.ActivePlayer = 2 - Seat;
                SetSetupPhase();
            }
            Publish();
            return Winner >= 0;
        }

        var file = Path.Combine(directory, "action-" + revision + ".json");
        if (!File.Exists(file)) return false;
        var selected = JsonUtility.FromJson<Submission>(File.ReadAllText(file));
        if (!handlers.TryGetValue(selected.id, out var run))
            throw new InvalidDataException("Invalid action for revision " + revision + ": " + selected.id);
        events.Clear();
        string publicLabel = selected.id.StartsWith("discard:", StringComparison.Ordinal)
            ? "Selected a card from the discard pile"
            : (string)choices.First(c => (string)c["id"] == selected.id)["label"];
        events.Add("Seat " + Seat + ": " + publicLabel);
        published = false;
        ArenaCapture.CaptureUntil = double.PositiveInfinity;
        revision++;
        transitionStart = EditorApplication.timeSinceStartup;
        actedFrame = Time.frameCount;
        if (watching)
        {
            if (ArenaSpectator.ViewSeat >= 0 && Seat != ArenaSpectator.ViewSeat && selected.id.StartsWith("discard:", StringComparison.Ordinal))
                ArenaSpectator.Pick(Seat, null, publicLabel);
            else if (run.Preview == null) ArenaSpectator.Pick(Seat, run.Card, run.Announcement);
            else run.Preview();
            pending = run;
            showUntil = transitionStart + 1.8;
        }
        else run.Execute();
        return false;
    }

    private bool HasDyingCreature()
    {
        for (int seat = 0; seat < 2; seat++)
            foreach (var lane in game.GetLanes(seat))
                if (lane.HasCreature() && lane.GetCreature().Health <= 0) return true;
        return false;
    }

    private void Add(string id, string label, string announcement, CardItem card, Action action, Action preview = null)
    {
        handlers.Add(id, new Move { Execute = action, Announcement = announcement, Card = card, Preview = preview });
        choices.Add(new Map { {"id", id}, {"label", label} });
    }

    private void BuildChoices()
    {
        int seat = Seat;
        var remaining = remainingLandscapes[seat];
        if (remaining != null && remaining.Count > 0)
        {
            var empty = game.GetLanes(seat).Where(lane => lane.Type == LandscapeType.None).ToArray();
            if (empty.Length != remaining.Count)
                throw new InvalidOperationException("Empty native lanes and remaining tiles disagree at seat " + seat);
            foreach (var type in remaining.Distinct().OrderBy(t => t))
            {
                foreach (var lane in empty)
                {
                    string id = "place:" + type + ":" + lane.Index;
                    Add(id, "Place " + type + " in lane " + lane.Index, null, null, () => {
                        remaining.Remove(type);
                        game.GetDeck(seat).SetLandscape(lane.Index, type);
                        game.SetLandscape(seat, lane.Index, type);
                        ArenaSpectator.Place(seat, lane.Index, type);
                    }, () => ArenaSpectator.PreviewPlacement(seat, lane.Index, type));
                }
            }
            return;
        }
        CardScript target = ArenaChoices.Target;
        if (target != null)
        {
            foreach (var lane in game.GetLanes(ArenaChoices.Side))
            {
                if (!ArenaChoices.CanTarget(target, lane)) continue;
                var selected = ArenaChoices.Kind == SelectionType.Creature ? (CardScript)lane.GetCreature()
                    : ArenaChoices.Kind == SelectionType.Building ? lane.GetBuilding() : null;
                Add("target:" + lane.Index, ArenaChoices.Prompt + " (seat " + (int)ArenaChoices.Side
                    + ", lane " + lane.Index + ")", "Target: " + game.GetLeader(ArenaChoices.Side).Form.Name
                    + ", lane " + (lane.Index + 1) + (selected != null ? " · " + selected.Data.Form.Name : ""),
                    selected?.Data, () => {
                    ArenaChoices.Target = null;
                    target.OnTargetSelected(lane);
                });
            }
        }
        else if (ArenaChoices.Discard != null)
        {
            var script = ArenaChoices.Discard;
            foreach (var card in game.GetDiscardPile(script.Owner).Where(script.CardFilter))
                Add("discard:" + choices.Count, "Return " + card.Form.ID, "Return from discard: " + card.Form.Name, card, () => {
                    ArenaChoices.Discard = null;
                    script.CardSelection(card);
                });
        }
        else
        {
            foreach (var card in game.GetHand(seat))
            {
                if (remainingLandscapes[1 - seat]?.Count == GameState.LANE_COUNT
                    && card.Form.GetScriptClass() == typeof(DisableLane)) continue;
                int index = game.GetHand(seat).IndexOf(card);
                foreach (var lane in game.GetLanes(seat))
                {
                    if (!card.Form.CanPlay(seat, lane.Index)) continue;
                    string cost = " (" + card.Form.DetermineCost(seat) + " MP)";
                    if (card.Form.Type == CardType.Spell)
                    {
                        Add("cast:" + index, "Cast " + card.Form.ID + cost, "Cast " + card.Form.Name, card, () => game.CastSpell(seat, card));
                        break;
                    }
                    string replace = lane.HasCard(card.Form.Type) ? ", replacing " + lane.GetScript(card.Form.Type).Data.Form.ID : "";
                    Add("play:" + index + ":" + lane.Index, "Play " + card.Form.ID + " in lane " + lane.Index + replace + cost,
                        "Play " + card.Form.Name + " in lane " + (lane.Index + 1)
                        + (lane.HasCard(card.Form.Type) ? ", replacing " + lane.GetScript(card.Form.Type).Data.Form.Name : ""),
                        card, () => game.Summon(seat, lane.Index, card));
                }
            }
            foreach (var lane in game.GetLanes(seat))
                if (game.IsFloopingEnabled(seat) && lane.HasCreature() && game.CanFloopCard(seat, lane.GetCreature()))
                    Add("floop:" + lane.Index, "Floop " + lane.GetCreature().Data.Form.ID + " in lane " + lane.Index
                        + " (" + lane.GetCreature().DetermineFloopCost() + " MP)",
                        "Floop " + lane.GetCreature().Data.Form.Name + " · lane " + (lane.Index + 1),
                        lane.GetCreature().Data, () => game.FloopCard(seat, lane.Index, CardType.Creature));
            if (game.IsLeaderAbilityReady(seat))
                Add("hero", "Use " + game.GetLeader(seat).Form.ID, "Hero ability · " + game.GetLeader(seat).Form.Name,
                    null, () => game.UseLeaderAbility(seat));
            bool openingTurn = data.Turn == 1;
            string endLabel = openingTurn ? "End opening setup without attacking" : "End turn and resolve battle wheel";
            string announcement = openingTurn ? "End the opening turn without attacking" : "End turn and begin combat";
            Add("end", endLabel, announcement, null, () => {
                if (openingTurn) events.Add("No attack on opening turn");
                inCombat = true;
                ArenaCombat.Begin(seat, events.Add, () => {
                    inCombat = false;
                    actedFrame = Time.frameCount;
                    if (Winner < 0) SetSetupPhase();
                }, ex => { failure = ex; });
            });
        }
        if (choices.Count == 0) throw new InvalidOperationException("Native target prompt has no legal choices");
    }

    private Map DescribeLane(Lane lane)
    {
        var result = new Map { {"lane", lane.Index}, {"opposingLane", lane.OpponentLane.Index},
            {"landscape", lane.Type.ToString()}, {"flipped", lane.Flipped}, {"disabled", lane.Disabled},
            {"building", lane.HasBuilding() ? lane.GetBuilding().Data.Form.ID : null}, {"creature", null} };
        if (lane.HasCreature())
        {
            var card = lane.GetCreature();
            result["creature"] = new Map { {"id", card.Data.Form.ID}, {"attack", card.ATK}, {"hp", card.Health},
                {"maxHP", card.DEF}, {"flooped", card.Flooped}, {"cantAttack", card.CantAttack},
                {"helpless", card.Helpless}, {"protected", card.Protected}, {"floopBlocked", card.FloopBlocked} };
        }
        return result;
    }

    private string CampaignAction()
    {
        int left = remainingLandscapes[1].Count;
        if (left > 0)
        {
            int lane = GameState.LANE_COUNT - left;
            return "place:" + campaignLandscapes[lane] + ":" + lane;
        }
        if (ArenaChoices.Target != null || ArenaChoices.Discard != null)
            throw new InvalidOperationException("Campaign card unexpectedly requested a human target.");
        // CWOpponentActionSequencer asks this same policy again after each resolved action.
        AIDecision decision = AIManager.Instance.MakeDecision();
        if (decision == null) return "end";
        if (decision.IsLeaderAbility) return "hero";
        if (decision.IsFloop) return "floop:" + decision.LaneChoice.Index;
        int index = game.GetHand(PlayerType.Opponent).IndexOf(decision.CardChoice);
        return decision.CardChoice.Form.Type == CardType.Spell
            ? "cast:" + index : "play:" + index + ":" + decision.LaneChoice.Index;
    }

    private void Publish()
    {
        handlers.Clear();
        choices.Clear();
        if (Winner < 0) BuildChoices();
        var seats = new[] { 0, 1 };
        var state = new Map {
            {"revision", revision}, {"active", Seat}, {"turn", data.Turn}, {"winner", Winner},
            {"hp", seats.Select(s => game.GetHealth(s)).ToArray()},
            {"hands", seats.Select(s => game.GetHand(s).Select(c => c.Form.ID).ToArray()).ToArray()},
            {"board", seats.Select(s => new Map { {"seat", s}, {"mp", game.GetMagicPoints(s)},
                {"spellMP", game.GetSpellPoints(s)}, {"hero", game.GetLeader(s).Form.ID},
                {"heroCooldown", game.GetLeaderCooldown(s)}, {"deckCount", game.GetDeck(s).CardCount()},
                {"handCount", game.GetHand(s).Count}, {"lanes", game.GetLanes(s).Select(DescribeLane).ToArray()} }).ToArray()},
            {"events", events}, {"actions", choices} };
        if (Winner < 0 && Seat == 1 && campaignLandscapes != null)
        {
            string selected = CampaignAction();
            if (!handlers.ContainsKey(selected))
                throw new InvalidOperationException("Campaign AI selected unavailable action: " + selected);
            state["campaign_action"] = selected;
        }
        string path = Path.Combine(directory, "state.json");
        File.WriteAllText(path + ".tmp", MiniJSON.Json.Serialize(state));
        if (File.Exists(path)) File.Replace(path + ".tmp", path, null);
        else File.Move(path + ".tmp", path);
        ArenaCapture.CaptureUntil = EditorApplication.timeSinceStartup + 1.5;
        published = true;
    }
}
