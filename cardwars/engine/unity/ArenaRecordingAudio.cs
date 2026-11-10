using System;
using System.IO;
using UnityEngine;

// Capture the game's listener mix. No desktop or microphone input is involved.
public class ArenaRecordingAudio : MonoBehaviour
{
    private string directory;
    private int sampleRate;
    private FileStream output;
    private byte[] bytes;
    private readonly object sync = new object();

    private void Awake()
    {
        sampleRate = AudioSettings.outputSampleRate;
        directory = Path.GetDirectoryName(Environment.GetEnvironmentVariable("CARD_WARS_OPENING"));
    }

    private void OnAudioFilterRead(float[] data, int channels)
    {
        lock (sync)
        {
            if (directory == null) return;
            if (output == null)
            {
                output = new FileStream(Path.Combine(directory, "mix.f32"), FileMode.Create, FileAccess.Write, FileShare.Read);
                File.WriteAllText(Path.Combine(directory, "mix.txt"),
                    DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + " " + sampleRate + " " + channels);
            }
            int length = data.Length * sizeof(float);
            if (bytes == null || bytes.Length != length) bytes = new byte[length];
            Buffer.BlockCopy(data, 0, bytes, 0, length);
            output.Write(bytes, 0, length);
        }
    }

    private void OnDestroy()
    {
        lock (sync)
        {
            directory = null;
            if (output != null) output.Dispose();
        }
    }
}
