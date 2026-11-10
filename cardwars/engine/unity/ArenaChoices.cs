// Part of the runtime assembly in the isolated arena project. The editor bridge
// exposes the same target filters and callbacks as the touch UI to each seat.
public static class ArenaChoices
{
    public static bool Enabled;
    public static bool CampaignOpponent;
    public static bool ExternalOpponent => Enabled && !CampaignOpponent;
    public static bool ManualLandscapes;
    public static CardScript Target;
    public static PlayerType Side;
    public static SelectionType Kind;
    public static string Prompt;
    public static CardScript Discard;

    public static bool CanTarget(CardScript source, Lane lane)
    {
        return (!ManualLandscapes || lane.Type != LandscapeType.None) && source.SelectionFilter(lane);
    }

    public static void SelectLane(CardScript source, PlayerType side, SelectionType kind, string prompt)
    {
        for (int lane = 0; lane < GameState.LANE_COUNT; lane++)
        {
            if (!CanTarget(source, GameState.Instance.GetLane(side, lane))) continue;
            source.Flooping = true;
            Target = source;
            Side = side;
            Kind = kind;
            Prompt = prompt;
            return;
        }
    }

    public static void Resolve(CardScript source, CardScript[] targets)
    {
        foreach (CardScript target in targets)
        {
            source.TargetScript = target;
            source.DoResult(target);
        }
    }
}
