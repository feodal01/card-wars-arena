using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

// Entry point for an isolated copy of the recovered Unity project.
[InitializeOnLoad]
public static class ArenaOpening
{
    [Serializable] private class Roster
    {
        public string hero;
        public string[] cards;
        public string[] landscapes;
        public string[] required_landscapes;
    }
    [Serializable] private class Opening
    {
        public Roster[] players;
        public string[] display_names;
        public string[] landscapes;
        public string landscape_placement;
        public int health;
        public int first;
        public int game;
        public int seed;
        public bool battle;
        public bool campaign_opponent;
    }

    private const string Active = "CardWarsArenaOpening";
    private static bool loadingBattle;
    private static EditorWindow watchView;
    private static double nextRepaint;
    private static ArenaMatch match;
    private static Opening opening;
    private static string[][] landscapeTiles;
    private static double started;
    private static string MatchFile => Environment.GetEnvironmentVariable("CARD_WARS_OPENING");

    static ArenaOpening()
    {
        if (SessionState.GetBool(Active, false)) Watch();
    }

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    private static void ConfigureHeadlessAudio()
    {
        if (Application.isBatchMode && SessionState.GetBool(Active, false))
            AudioListener.volume = 0f;
    }

    public static void Run()
    {
        if (PlayerSettings.companyName != "CardWarsArena" || !File.Exists(MatchFile))
            throw new InvalidOperationException("Use a separate arena project and a valid CARD_WARS_OPENING file.");
        // Use the same packaged scenes on every game, regardless of the last
        // saved editor window size. PlayerPrefs is isolated by arena branding.
        PlayerPrefs.SetString("M2H_lastLanguage", LanguageCode.EN.ToString());
        KFFLODManager.SetLowEndOverride(true);
        PlayerPrefs.Save();
        Application.runInBackground = true;
        EditorSceneManager.OpenScene("Assets/Scenes/StartupScene.unity");
        SessionState.SetBool(Active, true);
        Watch();
        EditorApplication.isPlaying = true;
    }

    private static void Watch()
    {
        started = EditorApplication.timeSinceStartup;
        EditorApplication.update -= Tick;
        EditorApplication.update += Tick;
    }

    private static string[][] ResolveLandscapes(Opening config)
    {
        if (config.players == null || config.players.Length != 2)
            throw new InvalidDataException("A match requires exactly two players.");
        bool individual = config.players.Any(p => p.landscapes != null && p.landscapes.Length > 0);
        string[][] orders;
        if (config.landscape_placement == "own_turn" || config.landscape_placement == "before_cards")
        {
            if (individual || config.landscapes != null && config.landscapes.Length != 0)
                throw new InvalidDataException("Per-turn placement takes an unordered supply instead of a layout.");
            orders = config.players.Select(p => p.required_landscapes).ToArray();
        }
        else if (string.IsNullOrEmpty(config.landscape_placement))
        {
            orders = individual ? config.players.Select(p => p.landscapes).ToArray()
                : new[] { config.landscapes, config.landscapes?.Reverse().ToArray() };
        }
        else throw new InvalidDataException("Unknown landscape placement mode: " + config.landscape_placement);
        foreach (var order in orders)
        {
            if (order == null || order.Length != GameState.LANE_COUNT)
                throw new InvalidDataException("Each seat must supply four landscape slots.");
            foreach (var type in order)
                if (!Enum.TryParse(type, out LandscapeType parsed) || parsed == LandscapeType.None
                    || !Enum.IsDefined(typeof(LandscapeType), parsed) || parsed.ToString() != type)
                    throw new InvalidDataException("Unknown landscape: " + type);
        }
        return orders;
    }

    private static Deck CreateDeck(Roster roster, string[] landscapes)
    {
        var deck = new Deck { Leader = LeaderManager.Instance.CreateLeader(roster.hero, 1) };
        foreach (string id in roster.cards)
            deck.AddCard(new CardItem(CardDataManager.Instance.GetCard(id, false), 1));
        foreach (string type in landscapes)
            deck.AddLandscape((LandscapeType)Enum.Parse(typeof(LandscapeType), type));
        deck.PrecacheCounts();
        if (ArenaChoices.ManualLandscapes || roster.landscapes != null && roster.landscapes.Length > 0)
        {
            var original = deck.Clone();
            CWDeckController.SetArenaDeckLandscapes(original);
            var expected = Enumerable.Range(0, GameState.LANE_COUNT)
                .Select(lane => original.GetLandscape(lane).ToString()).OrderBy(x => x);
            if (!expected.SequenceEqual(landscapes.OrderBy(x => x)))
                throw new InvalidDataException("Selected landscapes do not match this deck's original Card Wars tiles. Expected: "
                    + string.Join(", ", expected) + ". Submitted: " + string.Join(", ", landscapes));
        }
        return deck;
    }

    private static void Tick()
    {
        try
        {
            if (EditorApplication.isPlaying && Environment.GetEnvironmentVariable("CARD_WARS_WATCH") == "1"
                && !Application.isBatchMode)
            {
                Application.runInBackground = true;
                if (watchView == null)
                {
                    var type = typeof(EditorWindow).Assembly.GetType("UnityEditor.GameView", true);
                    watchView = EditorWindow.GetWindow(type);
                    watchView.Show();
                    watchView.maximized = true;
                    ArenaCapture.SetGameViewSize(watchView);
                    watchView.Focus();
                }
                // In the editor, an unfocused Game view may stop receiving
                // player-loop paints. Repaint without taking keyboard focus.
                if (EditorApplication.timeSinceStartup >= nextRepaint)
                {
                    nextRepaint = EditorApplication.timeSinceStartup + 1.0 / 60;
                    EditorApplication.QueuePlayerLoopUpdate();
                    watchView.Repaint();
                }
            }
            if (match != null)
            {
                if (match.Tick()) Finish(0);
                return;
            }
            if (EditorApplication.timeSinceStartup - started > 150)
                throw new TimeoutException("Arena: timed out in " + SceneManager.GetActiveScene().name);
            if (!EditorApplication.isPlaying) return;
            var game = GameState.Instance;
            var scene = SceneManager.GetActiveScene().name;
            if (!loadingBattle)
            {
                var session = SessionManager.GetInstance();
                if (!scene.Contains("AdventureTime") || session == null || !session.IsReady()) return;
                opening = JsonUtility.FromJson<Opening>(File.ReadAllText(MatchFile));
                ArenaChoices.CampaignOpponent = opening.campaign_opponent;
                UnityEngine.Random.InitState(opening.seed);
                var quest = QuestManager.Instance.GetQuestByIndex("main", 0);
                PlayerInfoScript.GetInstance().SetCurrentQuest(quest);
                landscapeTiles = ResolveLandscapes(opening);
                ArenaChoices.ManualLandscapes = !string.IsNullOrEmpty(opening.landscape_placement);
                var decks = opening.players.Select((p, i) => CreateDeck(p, landscapeTiles[i])).ToArray();
                game.ResetFromQuestData(quest, decks[0], decks[1]);
                // A tutorial quest can override a player's loadout. The arena owns both rosters.
                game.SetDecks(decks[0], decks[1]);
                game.SetHealth(opening.health, opening.health);
                game.SetCharacters(CharacterDataManager.Instance.GetCharacterData(decks[0].Leader.Form.CharacterID),
                    CharacterDataManager.Instance.GetCharacterData(decks[1].Leader.Form.CharacterID));
                loadingBattle = true;
                SLOTGameSingleton<SLOTSceneManager>.GetInstance().LoadLevel("BattleScene");
                return;
            }
            if (!scene.Contains("BattleScene") || !game.IsSetUp) return;
            VerifyDeal(game);
            if (!opening.battle && Environment.GetEnvironmentVariable("CARD_WARS_BATTLE") != "1")
            {
                Finish(0);
                return;
            }
            var directory = Path.GetDirectoryName(MatchFile);
            int gameNumber = opening.game;
            if (gameNumber <= 0 && Path.GetFileName(directory).StartsWith("game-", StringComparison.Ordinal))
                int.TryParse(Path.GetFileName(directory).Substring(5), out gameNumber);
            if (watchView != null) watchView.Focus();
            match = new ArenaMatch(game, directory, opening.first, gameNumber, opening.landscape_placement == "before_cards", landscapeTiles,
                opening.players.Select(p => p.cards).ToArray(), opening.display_names);
        }
        catch (Exception e)
        {
            UnityEngine.Debug.LogException(e);
            Finish(1);
        }
    }

    private static void VerifyDeal(GameState game)
    {
        if (Language.CurrentLanguage() != LanguageCode.EN)
            throw new InvalidOperationException("Arena expected the English language in the battle scene.");
        UnityEngine.Debug.Log("Arena battle language: " + Language.CurrentLanguage());
        for (int i = 0; i < 2; i++)
        {
            PlayerType side = i;
            var hand = game.GetHand(side);
            var remaining = game.GetDeck(side).GetCards();
            var actual = hand.Concat(remaining).Select(c => c.Form.ID).OrderBy(id => id);
            var expected = opening.players[i];
            if (!actual.SequenceEqual(expected.cards.OrderBy(id => id)) || hand.Count != 5
                || game.GetLeader(side).Form.ID != expected.hero || game.GetHealth(side) != opening.health)
                throw new InvalidOperationException("Arena roster or opening hand mismatch for seat " + i);
            UnityEngine.Debug.LogFormat("Arena opening: seat={0} hero={1} hand={2} deck={3} HP={4}",
                i, expected.hero, hand.Count, remaining.Count, game.GetHealth(side));
        }
    }

    private static void Finish(int code)
    {
        SessionState.EraseBool(Active);
        EditorApplication.update -= Tick;
        EditorApplication.Exit(code);
    }
}
