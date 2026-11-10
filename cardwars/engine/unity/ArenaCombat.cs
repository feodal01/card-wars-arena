using System;
using System.Collections;
using System.Globalization;
using System.Reflection;
using UnityEngine;

// Runs in the loaded BattleScene. The native sequence owns lane order, ring sectors,
// block/counter animations, creature damage, death triggers and the turn increment.
public static class ArenaCombat
{
    private static readonly FieldInfo RingStopped = typeof(CWBattleSequenceController)
        .GetField("_keyPressed", BindingFlags.Instance | BindingFlags.NonPublic);

    public static void Begin(PlayerType active, Action<string> publicEvent,
        Action completed, Action<Exception> failed)
    {
        BattleManagerScript.GetInstance().StartCoroutine(Guard(
            Resolve(active, publicEvent), completed, failed));
    }

    private static IEnumerator Guard(IEnumerator routine, Action completed, Action<Exception> failed)
    {
        while (true)
        {
            bool running;
            try { running = routine.MoveNext(); }
            catch (Exception ex)
            {
                failed(ex);
                yield break;
            }
            if (!running) break;
            yield return routine.Current;
        }
        completed();
    }

    private static IEnumerator Resolve(PlayerType active, Action<string> publicEvent)
    {
        var game = GameState.Instance;
        var data = game.GameData;
        var phases = BattlePhaseManager.GetInstance();
        var battle = BattleManagerScript.GetInstance();
        var wheel = CWBattleSequenceController.GetInstance();
        if (data.ActivePlayer != 1 + (int)active || data.Turn < 1 || battle.BattlePaused)
            throw new InvalidOperationException("Arena turn and native battle state disagree.");
        if (RingStopped == null)
            throw new MissingFieldException("CWBattleSequenceController", "_keyPressed");

        int turn = data.Turn;
        if (turn == 1)
        {
            // Both original setup branches skip combat on the first turn.
            if (active == PlayerType.User) battle.P1BattleFinished();
            else battle.P2BattleFinished();
        }
        else
        {
            phases.Phase = active == PlayerType.User ? BattlePhase.P1Battle : BattlePhase.P2Battle;
            PlayerInfoScript.GetInstance().AutoBattleSetting = false;
            DebugFlagsScript.GetInstance().battleDisplay.autoCrit = false;
            wheel.BattleSequence();
            var logged = new bool[GameState.LANE_COUNT];
            var sampled = new bool[GameState.LANE_COUNT];
            float deadline = Time.realtimeSinceStartup + 90f;
            while (data.Turn == turn && !data.GameOver)
            {
                if (Time.realtimeSinceStartup > deadline)
                    throw new TimeoutException("Native combat stalled at turn " + turn + ", lane " + wheel.lane);
                if (wheel.animateFlag)
                {
                    // WaitForKeyPress resumes its own StopRing coroutine at roundLimit.
                    // Freeze the spinner on the sampled angle and keep timeOutFlag false:
                    // StopRing itself decides the result and runs the original damage tweens.
                    wheel.animateFlag = false;
                    wheel.currentAngle = UnityEngine.Random.value;
                    wheel.barSprite.transform.localRotation = Quaternion.Euler(0f, 0f, -360f * wheel.currentAngle);
                    wheel.round = wheel.roundLimit;
                    wheel.timeOutFlag = false;
                    sampled[wheel.lane] = true;
                }
                if (!logged[wheel.lane] && (sampled[wheel.lane] || wheel.forceMiss || wheel.forceCrit)
                    && game.LaneHasCreature(active, wheel.lane) && (bool)RingStopped.GetValue(wheel))
                {
                    logged[wheel.lane] = true;
                    string angle = sampled[wheel.lane]
                        ? wheel.currentAngle.ToString("F5", CultureInfo.InvariantCulture) : "forced";
                    publicEvent(string.Format(CultureInfo.InvariantCulture,
                        "wheel seat={0} lane={1} mode={2} stop={3} result={4} hit=[{5:F5},{6:F5}] crit=[{7:F5},{8:F5}]",
                        (int)active, wheel.lane, active == PlayerType.User ? "attack" : "defense",
                        angle, wheel.result, wheel.hitAreaStart, wheel.hitAreaEnd, wheel.critAreaStart, wheel.critAreaEnd));
                }
                yield return null;
            }
        }

        if (data.GameOver) yield break;
        PlayerType next = !active;
        if (data.Turn != turn + 1 || data.ActivePlayer != 1 + (int)next)
            throw new InvalidOperationException("Native combat did not hand control to the other seat.");

        // The normal setup banner invokes CWStartTurnTrigger in this order.
        phases.Phase = next == PlayerType.User ? BattlePhase.P1Setup : BattlePhase.P2Setup;
        game.EndTurn(active);
        bool empty = game.GetDeck(next).CardCount() == 0;
        game.StartTurn(next);
        if (empty && !data.GameOver)
        {
            // Both participants choose the free player-side out-of-cards option:
            // lose the leader's rank in HP. Arena seats cannot purchase a reshuffle.
            wheel.result = null;
            if (next == PlayerType.User) game.DoResultBleed(next);
            else game.DealDamage(next, game.GetLeader(next).Rank);
            publicEvent("empty deck: seat=" + (int)next + " bleed=" + game.GetLeader(next).Rank);
        }
        if (!data.GameOver)
            phases.Phase = next == PlayerType.User ? BattlePhase.P1Setup : BattlePhase.P2Setup;
    }
}
