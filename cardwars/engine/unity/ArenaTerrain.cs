using System;
using System.Collections;
using UnityEngine;

// The scene's real landscape model is spawned once, then lands on its native lane
// anchor. The GameState mutation belongs to ArenaMatch and precedes this view.
public sealed partial class ArenaSpectator
{
    private UIAtlas landscapeAtlas;
    private Camera boardCamera;
    private int previewLane = -1;
    private LandscapeType previewType;
    private bool terrainInFlight;
    private readonly int[,] supplied = new int[2, (int)LandscapeType.None];

    public static bool Placing => view != null && view.terrainInFlight;

    private void PrepareTerrain()
    {
        boardCamera = PanelManagerBattle.GetInstance().newCamera.GetComponent<Camera>();
        var landscapeCard = game.LandscapeManager.CardScripts[0];
        foreach (var sprite in landscapeCard.GetComponentsInChildren<UISprite>(true))
            if (sprite.name == "Card_Art") { landscapeAtlas = sprite.atlas; break; }
        if (landscapeAtlas == null)
            throw new InvalidOperationException("Arena: original landscape card art is missing");
        for (int seat = 0; seat < 2; seat++)
            foreach (string name in landscapes[seat])
                supplied[seat, (int)(LandscapeType)Enum.Parse(typeof(LandscapeType), name)]++;
    }

    public static void PreviewPlacement(int seat, int lane, LandscapeType type)
    {
        if (view == null) return;
        Pick(seat, null, TerrainName(type.ToString()) + " · lane " + (lane + 1));
        view.previewLane = lane;
        view.previewType = type;
    }

    public static void Place(int seat, int lane, LandscapeType type)
    {
        var state = GameState.Instance;
        if (state.GetLandscapeType(seat, lane) != type)
            throw new InvalidOperationException("Arena: cannot animate an uncommitted landscape");
        var manager = state.LandscapeManager;
        var anchor = (seat == 0 ? manager.player1LandscapeLanes : manager.player2LandscapeLanes)[lane].transform;
        int before = anchor.childCount;
        manager.UpdateLandscapes();
        if (view == null) return;
        if (anchor.childCount != before + 1)
            throw new InvalidOperationException("Arena: selected landscape did not spawn on its lane");
        PreviewPlacement(seat, lane, type);
        view.terrainInFlight = true;
        view.StartCoroutine(view.FlyTerrain(anchor.GetChild(before), seat, lane));
    }

    private IEnumerator FlyTerrain(Transform tile, int seat, int lane)
    {
        var manager = game.LandscapeManager;
        var sound = manager.CardScripts[lane];
        var audio = SLOTGameSingleton<SLOTAudioManager>.GetInstance();
        if (sound.CardMove != null) audio.PlayOneShot(sound.CardMove);
        Vector3 destination = tile.position;
        Quaternion finalRotation = tile.rotation;
        float depth = boardCamera.WorldToViewportPoint(destination).z;
        var start = boardCamera.ViewportToWorldPoint(new Vector3(.5f, .13f, depth * .76f));
        var tilt = Quaternion.AngleAxis(-58f, boardCamera.transform.right) * finalRotation;
        float started = Time.realtimeSinceStartup;
        const float travel = .85f;
        while (Time.realtimeSinceStartup - started < travel)
        {
            float t = Mathf.Clamp01((Time.realtimeSinceStartup - started) / travel);
            float ease = Mathf.SmoothStep(0f, 1f, t);
            tile.position = Vector3.Lerp(start, destination, ease) + Vector3.up * (2.1f * Mathf.Sin(t * Mathf.PI));
            tile.rotation = Quaternion.Slerp(tilt, finalRotation, ease);
            tile.localScale = Vector3.one * Mathf.Lerp(.30f, 1f, ease);
            yield return null;
        }
        tile.localPosition = Vector3.zero;
        tile.localRotation = Quaternion.identity;
        tile.localScale = Vector3.one;
        if (sound.SummonSound != null) audio.PlayOneShot(sound.SummonSound);
        if (sound.PlaceCardSounds.Length > 0)
        {
            // Keep spectator-only sounds independent of gameplay randomness.
            var clip = sound.PlaceCardSounds[(seat + lane) % sound.PlaceCardSounds.Length];
            if (clip != null) audio.PlayOneShot(clip);
        }
        yield return new WaitForSecondsRealtime(.24f);
        terrainInFlight = false;
        previewLane = -1;
        announcement = null;
    }

    private bool DrawTerrainChoice(int active, float height)
    {
        if (active < 0 || active > 1 || (ViewSeat >= 0 && active != ViewSeat)) return false;
        int empty = 0;
        var remaining = new int[(int)LandscapeType.None];
        for (int i = 0; i < remaining.Length; i++) remaining[i] = supplied[active, i];
        for (int lane = 0; lane < GameState.LANE_COUNT; lane++)
        {
            var terrain = game.GetLandscapeType(active, lane);
            if (terrain == LandscapeType.None) empty++;
            else remaining[(int)terrain]--;
        }
        if (empty == 0 && !terrainInFlight) return false;

        var anchors = active == 0 ? game.LandscapeManager.player1LandscapeLanes : game.LandscapeManager.player2LandscapeLanes;
        for (int lane = 0; lane < GameState.LANE_COUNT; lane++)
        {
            bool focus = previewLane == lane && pickedSeat == active;
            if (!focus && game.GetLandscapeType(active, lane) != LandscapeType.None) continue;
            var screenPoint = boardCamera.WorldToViewportPoint(anchors[lane].transform.position);
            float scale = Mathf.Min(Screen.width / Width, Screen.height / 474f);
            float x = (screenPoint.x * Screen.width - (Screen.width - Width * scale) * .5f) / scale;
            float y = (1f - screenPoint.y) * height;
            float w = focus ? 75f : 23f;
            var tag = new Rect(x - w / 2, y - 11, w, 22);
            Fill(tag, focus ? Gold : Ink);
            Label(tag, focus ? "Lane " + (lane + 1) : (lane + 1).ToString(),
                14, focus ? Ink : Color.white, true, TextAnchor.MiddleCenter);
        }

        float y0 = height - 79;
        Fill(new Rect(197, y0, 566, 73), Ink);
        string title = previewLane >= 0 && pickedSeat == active
            ? TerrainName(previewType.ToString()) + " → lane " + (previewLane + 1)
            : "Choose a landscape";
        Label(new Rect(208, y0 + 2, 544, 24), Player(active) + "   ·   " + title, 15, Sides[active], true);
        int slot = 0;
        for (int type = 0; type < remaining.Length; type++)
        {
            if (remaining[type] <= 0) continue;
            var land = (LandscapeType)type;
            float x = 208 + slot++ * 137;
            Fill(new Rect(x, y0 + 30, 132, 35), Tile);
            string name = land.ToString();
            var uv = landscapeAtlas.GetSprite("Landscape_" + name + "1").outer;
            if (landscapeAtlas.coordinates == UIAtlas.Coordinates.Pixels)
                uv = NGUIMath.ConvertToTexCoords(uv, landscapeAtlas.texture.width, landscapeAtlas.texture.height);
            GUI.DrawTextureWithTexCoords(new Rect(x + 2, y0 + 32, 31, 31), landscapeAtlas.texture, uv);
            string count = remaining[type] > 1 ? " ×" + remaining[type] : "";
            Label(new Rect(x + 38, y0 + 30, 91, 35), TerrainName(name) + count, 12, Color.white, true);
        }
        return true;
    }
}
