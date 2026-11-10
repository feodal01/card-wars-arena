using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;

// Archive original Game view frames. The live viewer reads only completed JPEGs.
[InitializeOnLoad]
public static class ArenaCapture
{
    private const int Width = 1600, Height = 850;
    private const double FrameInterval = 1.0 / 30;
    // The broadcast edit retains the action animation and a short tail after the next decision.
    public static double CaptureUntil = double.PositiveInfinity;
    private static bool IsRecording
    {
        get
        {
            string opening = Environment.GetEnvironmentVariable("CARD_WARS_OPENING");
            return opening != null && File.Exists(Path.Combine(Path.GetDirectoryName(opening), "..", "record-frames"));
        }
    }

    // The editor's free-aspect Game view follows the window's logical pixel size.
    // Select an actual rendering resolution before the battle camera is created.
    public static void SetGameViewSize(EditorWindow view)
    {
        if (!IsRecording) return;
        var assembly = typeof(EditorWindow).Assembly;
        var sizesType = assembly.GetType("UnityEditor.GameViewSizes", true);
        var singleton = typeof(ScriptableSingleton<>).MakeGenericType(sizesType);
        var sizes = singleton.GetProperty("instance").GetValue(null, null);
        var groupType = assembly.GetType("UnityEditor.GameViewSizeGroupType", true);
        var group = sizesType.GetMethod("GetGroup").Invoke(sizes,
            new object[] { Enum.Parse(groupType, "Standalone") });
        var type = group.GetType();
        var flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        var labels = (string[])type.GetMethod("GetDisplayTexts", flags).Invoke(group, null);
        const string name = "Card Wars broadcast";
        int index = Array.FindIndex(labels, l => l.Contains(name));
        if (index < 0)
        {
            var sizeType = assembly.GetType("UnityEditor.GameViewSize", true);
            var kind = assembly.GetType("UnityEditor.GameViewSizeType", true);
            var size = Activator.CreateInstance(sizeType, flags, null,
                new object[] { Enum.Parse(kind, "FixedResolution"), Width, Height, name }, null);
            type.GetMethod("AddCustomSize", flags).Invoke(group, new object[] { size });
            index = labels.Length;
        }
        view.GetType().GetProperty("selectedSizeIndex", flags).SetValue(view, index, null);
    }

    static ArenaCapture()
    {
        if (Environment.GetEnvironmentVariable("CARD_WARS_WATCH") == "1" && IsRecording)
            EditorApplication.update += StartInBattle;
    }

    private static void StartInBattle()
    {
        if (!EditorApplication.isPlaying || !UnityEngine.SceneManagement.SceneManager.GetActiveScene().name.Contains("BattleScene")) return;
        var host = GameDataScript.GetInstance();
        if (host == null || !host.gameObject.activeInHierarchy || !GameState.Instance.IsSetUp) return;
        EditorApplication.update -= StartInBattle;
        var folder = Path.GetDirectoryName(Environment.GetEnvironmentVariable("CARD_WARS_OPENING"));
        var listener = UnityEngine.Object.FindObjectOfType<AudioListener>();
        if (listener != null) listener.gameObject.AddComponent<ArenaRecordingAudio>();
        host.StartCoroutine(Record(folder));
    }

    private static IEnumerator Record(string folder)
    {
        string directory = Path.Combine(folder, "frames");
        Directory.CreateDirectory(directory);
        var target = new RenderTexture(Width, Height, 0, RenderTextureFormat.ARGB32);
        target.Create();
        var tasks = new List<Task>();
        var publish = new object();
        long lastPublished = 0;
        string latest = Path.Combine(folder, "frame.latest");
        var end = new WaitForEndOfFrame();
        int inFlight = 0;
        double next = 0;
        try
        {
            while (true)
            {
                yield return end;
                foreach (var task in tasks) if (task.IsFaulted) throw task.Exception;
                tasks.RemoveAll(task => task.IsCompleted);
                double now = EditorApplication.timeSinceStartup;
                if (ArenaSpectator.ViewSeat >= 0 && now > CaptureUntil) continue;
                if (now < next || tasks.Count + inFlight >= 3) continue;
                next = Math.Max(next + FrameInterval, now);
                long timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                ScreenCapture.CaptureScreenshotIntoRenderTexture(target);
                inFlight++;
                int width = target.width, height = target.height;
                bool flipY = SystemInfo.graphicsUVStartsAtTop;
                AsyncGPUReadback.Request(target, 0, TextureFormat.RGBA32, request =>
                {
                    inFlight--;
                    if (request.hasError) { Debug.LogError("Arena GPU frame read failed"); return; }
                    var pixels = request.GetData<byte>().ToArray();
                    tasks.Add(Task.Run(() =>
                    {
                        // Metal's captured render target starts at the top; Unity's image encoder expects bottom-up rows.
                        if (flipY)
                        {
                            int stride = width * 4;
                            var row = new byte[stride];
                            for (int y = 0; y < height / 2; y++)
                            {
                                int a = y * stride, b = (height - 1 - y) * stride;
                                Buffer.BlockCopy(pixels, a, row, 0, stride);
                                Buffer.BlockCopy(pixels, b, pixels, a, stride);
                                Buffer.BlockCopy(row, 0, pixels, b, stride);
                            }
                        }
                        byte[] jpeg = ImageConversion.EncodeArrayToJPG(pixels, GraphicsFormat.R8G8B8A8_UNorm,
                            (uint)width, (uint)height, 0, 93);
                        string path = Path.Combine(directory, "frame-" + timestamp + ".jpg");
                        File.WriteAllBytes(path + ".part", jpeg);
                        File.Move(path + ".part", path);
                        lock (publish)
                        {
                            if (timestamp <= lastPublished) return;
                            File.WriteAllText(latest + ".part", timestamp.ToString());
                            if (File.Exists(latest)) File.Replace(latest + ".part", latest, null);
                            else File.Move(latest + ".part", latest);
                            lastPublished = timestamp;
                        }
                    }));
                });
            }
        }
        finally
        {
            AsyncGPUReadback.WaitAllRequests();
            Task.WaitAll(tasks.ToArray());
            target.Release();
            UnityEngine.Object.Destroy(target);
        }
    }
}
