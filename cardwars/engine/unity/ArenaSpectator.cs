using System;
using System.Collections.Generic;
using UnityEngine;

// Omniscient local Game-view overlay. It never writes to the player protocol.
public sealed partial class ArenaSpectator : MonoBehaviour
{
    private const float Width = 960f;
    private const float HandWidth = 165f;
    private const float Margin = 8f;

    private static readonly Color Ink = new Color32(15, 25, 33, 238);
    private static readonly Color Panel = new Color32(26, 39, 50, 251);
    private static readonly Color Tile = new Color32(39, 54, 65, 255);
    private static readonly Color Muted = new Color32(193, 207, 212, 255);
    private static readonly Color Gold = new Color32(255, 210, 97, 255);
    private static readonly Color[] Sides = { new Color32(110, 213, 244, 255), new Color32(247, 169, 137, 255) };
    private const float DrawSeconds = 6f;
    private static ArenaSpectator view;
    public static readonly int ViewSeat;

    static ArenaSpectator()
    {
        ViewSeat = int.TryParse(Environment.GetEnvironmentVariable("CARD_WARS_VIEW_SEAT"), out var seat) ? seat : -1;
    }
    private UISprite bottle;

    private GameState game;
    private int gameNumber;
    private string[] displayNames;
    private float opened;
    private int pickedSeat;
    private float pickedAt = float.NegativeInfinity;
    private CardItem pickedCard;
    private int pickedCost;
    private string announcement;
    private bool showDecks;
    private int manualPage;
    private CardForm[][] rosters;
    private string[][] landscapes;
    private GUIStyle textStyle;
    private readonly Dictionary<string, UIAtlas> atlases = new Dictionary<string, UIAtlas>();
    private readonly Dictionary<CardForm, Rect> artwork = new Dictionary<CardForm, Rect>();

    public static bool Presenting => view != null && Time.realtimeSinceStartup - view.opened < DrawSeconds;

    public static void Open(GameState game, int gameNumber, string[][] decks, string[][] landscapes, string[] displayNames)
    {
        var overlay = new GameObject("Arena spectator");
        view = overlay.AddComponent<ArenaSpectator>();
        view.game = game;
        view.gameNumber = gameNumber;
        view.displayNames = displayNames;
        view.landscapes = landscapes;
        view.PrepareTerrain();
        var panel = GameObject.Find("Battle UI Panel");
        view.bottle = panel.transform.Find("B/B_3_KetchupBottle/Pivot/B_3_1_Arrow/KetchupBottle").GetComponent<UISprite>();
        view.opened = Time.realtimeSinceStartup;
        view.rosters = new CardForm[2][];
        for (int seat = 0; seat < 2; seat++)
            view.rosters[seat] = Array.ConvertAll(decks[seat], id => CardDataManager.Instance.GetCard(id, false));
    }

    public static void Pick(int seat, CardItem card, string label)
    {
        if (view == null) return;
        view.previewLane = -1;
        view.pickedSeat = seat;
        view.pickedCard = card;
        view.pickedCost = card == null ? 0 : card.Form.DetermineCost(seat);
        view.announcement = label;
        view.pickedAt = Time.realtimeSinceStartup;
    }

    private void Update()
    {
        if (Presenting || ViewSeat >= 0) return;
        if (Input.GetKeyDown(KeyCode.Tab))
        {
            showDecks = !showDecks;
            manualPage = 0;
        }
        if (showDecks && (Input.GetKeyDown(KeyCode.RightArrow) || Input.GetKeyDown(KeyCode.LeftArrow)))
            manualPage = 1 - manualPage;
    }

    private void OnGUI()
    {
        if (game == null || Event.current.type != EventType.Repaint) return;
        if (textStyle == null)
        {
            textStyle = new GUIStyle(GUI.skin.label) { padding = new RectOffset(), margin = new RectOffset(),
                wordWrap = true, richText = false, clipping = TextClipping.Clip };
        }
        // Set one design-space scale for all labels, margins and art.
        float scale = Mathf.Min(Screen.width / Width, Screen.height / 474f);
        if (scale <= 0f) return;
        float height = Screen.height / scale;
        var previous = GUI.matrix;
        var previousColor = GUI.color;
        int previousDepth = GUI.depth;
        GUI.depth = -10000;
        GUI.color = Color.white;
        GUI.matrix = Matrix4x4.TRS(new Vector3((Screen.width - Width * scale) * .5f, 0f), Quaternion.identity,
            new Vector3(scale, scale, 1f));
        float elapsed = Time.realtimeSinceStartup - opened;
        if (Presenting) DrawFirstPlayer(height, elapsed);
        else if (showDecks) DrawDecks(height, manualPage);
        else DrawPlay(height);
        GUI.matrix = previous;
        GUI.color = previousColor;
        GUI.depth = previousDepth;
    }

    private void DrawFirstPlayer(float height, float elapsed)
    {
        // Show the original bottle asset. The presentation reveals the same
        // fair draw that initialized GameData.FirstPlayer, with no second draw.
        int first = game.GameData.FirstPlayer - 1;
        float y = (height - 222) / 2;
        Fill(new Rect(157, y, 646, 222), Ink);
        Label(new Rect(157, y + 9, 646, 30), "Who goes first?", 22, Color.white, true, TextAnchor.MiddleCenter);
        FitPlayer(new Rect(164, y + 56, 256, 82), Player(0), 25, Sides[0], TextAnchor.MiddleCenter);
        FitPlayer(new Rect(540, y + 56, 256, 82), Player(1), 25, Sides[1], TextAnchor.MiddleCenter);
        float progress = Mathf.Clamp01(elapsed / 3f);
        float endAngle = first == 0 ? 270f : 90f;
        float angle = (4f * 360f + endAngle) * (1f - Mathf.Pow(1f - progress, 2f));
        var pivot = new Vector2(480, y + 105);
        var matrix = GUI.matrix;
        // Pivot is in design coordinates; compose before the Game view scale.
        GUI.matrix = matrix * Matrix4x4.Translate(pivot) * Matrix4x4.Rotate(Quaternion.Euler(0f, 0f, angle))
            * Matrix4x4.Translate(-pivot);
        var atlas = bottle.atlas;
        Rect uv = atlas.GetSprite(bottle.spriteName).outer;
        if (atlas.coordinates == UIAtlas.Coordinates.Pixels)
            uv = NGUIMath.ConvertToTexCoords(uv, atlas.texture.width, atlas.texture.height);
        GUI.DrawTextureWithTexCoords(new Rect(463, y + 53, 34, 104), atlas.texture, uv);
        GUI.matrix = matrix;
        if (progress >= 1f)
            FitPlayer(new Rect(157, y + 148, 646, 34), Player(first) + " goes first", 23, Gold, TextAnchor.MiddleCenter);
        Label(new Rect(157, y + 183, 646, 28), "Turn 1 · play cards without attacking", 17, Color.white, false, TextAnchor.MiddleCenter);
    }

    private void DrawDecks(float height, int page)
    {
        float top = 8f;
        float bottom = Mathf.Min(height - 8f, 545f);
        Fill(new Rect(8, top, Width - 16, bottom - top), Ink);
        Label(new Rect(24, top + 7, 600, 36), "Game " + gameNumber + "   /   Starting decks", 23, Color.white, true);
        string paging = "Cards " + (page == 0 ? "1–10" : "11–20") + " of 20";
        paging += "    ← →    Tab";
        Label(new Rect(595, top + 8, 337, 32), paging, 15, Gold, true, TextAnchor.MiddleRight);
        for (int seat = 0; seat < 2; seat++)
        {
            float x = 20 + 466 * seat;
            Fill(new Rect(x, 57, 454, 3), Sides[seat]);
            FitPlayer(new Rect(x, 64, 450, 25), Player(seat) + "    ·    " + game.GetLeader(seat).Form.Name,
                18, Sides[seat]);
            for (int lane = 0; lane < 4; lane++)
            {
                string terrain = game.GetLandscapeType(seat, lane).ToString();
                float lx = x + lane * 114;
                Fill(new Rect(lx, 94, 111, 28), Tile);
                Fill(new Rect(lx, 94, 3, 28), TerrainColor(terrain));
                Label(new Rect(lx + 7, 94, 103, 28), (lane + 1) + "  " + TerrainName(terrain), 13, Color.white);
            }
            float rowHeight = Mathf.Min(76f, (bottom - 137f) / 5f);
            for (int n = 0; n < 10; n++)
            {
                int index = page * 10 + n;
                if (index >= rosters[seat].Length) continue;
                var card = rosters[seat][index];
                float cx = x + n % 2 * 228;
                float cy = 130 + n / 2 * rowHeight;
                float h = rowHeight - 4;
                float art = Mathf.Min(h - 6, 58);
                Fill(new Rect(cx, cy, 225, h), Panel);
                Art(card, new Rect(cx + 3, cy + (h - art) / 2, art, art));
                float tx = cx + art + 9;
                float tw = 216 - art;
                Label(new Rect(tx, cy + 2, tw, h - 19), card.Name, 14, Color.white, true);
                Label(new Rect(tx, cy + h - 18, tw, 16), Stats(card, card.Cost, card.BaseATK, card.BaseDEF), 11, Muted);
            }
        }
    }

    private void DrawPlay(float height)
    {
        int active = game.GameData.ActivePlayer - 1;
        float centerX = (Width - 560f) / 2f;
        Fill(new Rect(centerX, 4, 560, 26), Ink);
        FitPlayer(new Rect(centerX, 4, 560, 26), "Game " + gameNumber + "   ·   " + (game.GameData.Turn == 0 ? "Landscape setup" : "Turn " + game.GameData.Turn)
            + "   ·   View from " + Player(active) + (ViewSeat < 0 ? "   ·   Tab: decks" : ""), 12, Color.white, TextAnchor.MiddleCenter);
        for (int seat = 0; seat < 2; seat++)
        {
            float x = seat == 0 ? Margin : Width - HandWidth - Margin;
            var hand = game.GetHand(seat);
            int visibleCards = ViewSeat < 0 || ViewSeat == seat ? hand.Count : 0;
            float y = 82;
            float rowH = Mathf.Min(48, (height - y - 52) / 7);
            Fill(new Rect(x, y, HandWidth, 45 + rowH * visibleCards + 2), Ink);
            Fill(new Rect(x, y, 3, 44), Sides[seat]);
            FitPlayer(new Rect(x + 8, y, HandWidth - 12, 27), Player(seat), 13, Sides[seat]);
            Label(new Rect(x + 8, y + 27, 90, 17), "Hand " + hand.Count, 11, Muted);
            if (seat == active)
                Label(new Rect(x + HandWidth - 39, y + 27, 32, 17), "TURN", 10, Gold, true, TextAnchor.MiddleRight);
            for (int i = 0; i < visibleCards; i++)
            {
                var item = hand[i];
                float cy = y + 45 + i * rowH;
                bool selected = seat == pickedSeat && ReferenceEquals(item, pickedCard) && Time.realtimeSinceStartup - pickedAt < 4;
                Fill(new Rect(x + 2, cy, HandWidth - 4, rowH - 1), selected ? Gold : Panel);
                float size = rowH - 6;
                Art(item.Form, new Rect(x + 5, cy + 2, size, size));
                float tx = x + size + 10;
                float tw = HandWidth - size - 14;
                FitHandName(new Rect(tx, cy, tw, rowH - 13), item.Form.Name, selected ? Ink : Color.white);
                int cost = item.Form.DetermineCost(seat);
                string numbers = item.Form.Type == CardType.Creature
                    ? "Mana " + cost + "  ATK " + item.ATK + "  HP " + item.DEF
                    : "Mana " + cost;
                FitLine(new Rect(tx, cy + rowH - 15, tw, 13), numbers, selected ? Ink : Muted);
            }
        }
        if (DrawTerrainChoice(active, height)) return;
        if (Time.realtimeSinceStartup - pickedAt > 4f || string.IsNullOrEmpty(announcement))
        {
            if (game.GameData.Turn == 1)
            {
                Fill(new Rect(303, height - 37, 354, 30), Ink);
                Label(new Rect(303, height - 37, 354, 30), "Turn 1 · play cards without attacking",
                    15, Gold, true, TextAnchor.MiddleCenter);
            }
            return;
        }
        float panelW = 450, panelH = pickedCard == null ? 44 : 72;
        float px = (Width - panelW) / 2, py = height - panelH - 7;
        Fill(new Rect(px, py, panelW, panelH), Ink);
        Fill(new Rect(px, py, 4, panelH), Sides[pickedSeat]);
        float left = px + 13;
        if (pickedCard != null)
        {
            Art(pickedCard.Form, new Rect(left - 4, py + 4, panelH - 8, panelH - 8));
            left += panelH - 2;
        }
        Label(new Rect(left, py + 3, px + panelW - left - 8, 17), Player(pickedSeat), 11, Sides[pickedSeat], true);
        float textWidth = px + panelW - left - 8;
        Label(new Rect(left, py + 19, textWidth, pickedCard == null ? panelH - 21 : 33), announcement, 15, Color.white, true);
        if (pickedCard != null)
            Label(new Rect(left, py + panelH - 21, textWidth, 18),
                Stats(pickedCard.Form, pickedCost, pickedCard.ATK, pickedCard.DEF), 12, Muted);
    }

    private static string Stats(CardForm card, int cost, int atk, int def)
    {
        if (card.Type == CardType.Creature) return "Mana " + cost + "   ATK " + atk + "   HP " + def;
        return "Mana " + cost + "    " + (card.Type == CardType.Spell ? "Spell" : "Building");
    }

    private string Player(int seat)
    {
        if (seat < 0 || seat > 1) return "—";
        if (displayNames != null && seat < displayNames.Length && !string.IsNullOrEmpty(displayNames[seat]))
            return displayNames[seat];
        return "Player " + (seat + 1);
    }

    private void FitPlayer(Rect rect, string value, int size, Color color, TextAnchor align = TextAnchor.MiddleLeft)
    {
        var content = new GUIContent(value);
        textStyle.fontStyle = FontStyle.Bold;
        textStyle.fontSize = size;
        while (size > 9 && textStyle.CalcHeight(content, rect.width) > rect.height)
            textStyle.fontSize = --size;
        Label(rect, value, size, color, true, align);
    }

    private static string TerrainName(string type)
    {
        switch (type)
        {
            case "None": return "Empty";
            case "Corn": return "Corn Fields";
            case "Plains": return "Blue Plains";
            case "Swamp": return "Useless Swamp";
            case "Cotton": return "Nice Lands";
            case "Sand": return "Sandy Lands";
            default: return type;
        }
    }

    private static Color TerrainColor(string type)
    {
        switch (type)
        {
            case "None": return Muted;
            case "Corn": return new Color32(219, 181, 74, 255);
            case "Plains": return new Color32(100, 179, 225, 255);
            case "Swamp": return new Color32(145, 175, 108, 255);
            case "Cotton": return new Color32(219, 146, 196, 255);
            default: return new Color32(231, 165, 101, 255);
        }
    }

    private void Art(CardForm card, Rect target)
    {
        UIAtlas atlas;
        if (!atlases.TryGetValue(card.IconAtlas, out atlas))
        {
            var asset = SLOTGameSingleton<SLOTResourceManager>.GetInstance().LoadResource(card.IconAtlas) as GameObject;
            atlas = asset.GetComponent<UIAtlas>();
            atlases.Add(card.IconAtlas, atlas);
        }
        Rect uv;
        if (!artwork.TryGetValue(card, out uv))
        {
            uv = atlas.GetSprite(card.SpriteName).outer;
            if (atlas.coordinates == UIAtlas.Coordinates.Pixels)
                uv = NGUIMath.ConvertToTexCoords(uv, atlas.texture.width, atlas.texture.height);
            artwork.Add(card, uv);
        }
        GUI.DrawTextureWithTexCoords(target, atlas.texture, uv);
        string edition = Edition(card.Quality);
        if (edition != null)
        {
            var badge = new Rect(target.x, target.yMax - 13f, target.width, 13f);
            bool gold = card.Quality == Quality.Gold;
            Fill(badge, gold ? Gold : Ink);
            Label(badge, edition, target.width < 50f ? 9 : 10, gold ? Ink : Color.white, true, TextAnchor.MiddleCenter);
        }
    }

    private static string Edition(Quality quality)
    {
        switch (quality)
        {
            case Quality.Gold: return "Gold";
            case Quality.Obsidian: return "Obsidian";
            case Quality.Halloween: return "Halloween";
            case Quality.Christmas: return "Christmas";
            case Quality.FionnaCake: return "Fionna";
            default: return null;
        }
    }

    private void FitLine(Rect rect, string value, Color color)
    {
        var content = new GUIContent(value);
        int size = 10;
        textStyle.fontStyle = FontStyle.Normal;
        textStyle.fontSize = size;
        textStyle.wordWrap = false;
        while (size > 8 && textStyle.CalcSize(content).x > rect.width)
            textStyle.fontSize = --size;
        Label(rect, value, size, color);
        textStyle.wordWrap = true;
    }

    private void FitHandName(Rect rect, string name, Color color)
    {
        var content = new GUIContent(name);
        textStyle.fontStyle = FontStyle.Bold;
        int size = 12;
        textStyle.fontSize = size;
        while (size > 9 && textStyle.CalcHeight(content, rect.width) > rect.height)
            textStyle.fontSize = --size;
        Label(rect, name, size, color, true);
    }

    private void Label(Rect rect, string text, int size, Color color, bool bold = false,
        TextAnchor alignment = TextAnchor.MiddleLeft)
    {
        textStyle.fontSize = size;
        textStyle.fontStyle = bold ? FontStyle.Bold : FontStyle.Normal;
        textStyle.normal.textColor = color;
        textStyle.alignment = alignment;
        GUI.Label(rect, text, textStyle);
    }

    private static void Fill(Rect rect, Color color)
    {
        GUI.color = color;
        GUI.DrawTexture(rect, Texture2D.whiteTexture);
        GUI.color = Color.white;
    }
}
