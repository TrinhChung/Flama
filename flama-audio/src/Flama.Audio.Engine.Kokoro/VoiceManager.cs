using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Flama.Audio.Engine.Kokoro.IO;

namespace Flama.Audio.Engine.Kokoro;

public class VoiceManager
{
    private readonly Dictionary<string, (float[] Data, int[] Shape)> _voices = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, float[]> _fallbackEmbeddings = new(StringComparer.OrdinalIgnoreCase);
    public int StyleDim { get; private set; } = 256;

    public VoiceManager(string? voicesBinPath = null)
    {
        LoadDefaultFallbackVoices();

        if (!string.IsNullOrEmpty(voicesBinPath) && File.Exists(voicesBinPath))
        {
            LoadFromNpz(voicesBinPath);
        }
    }

    public float[] GetStyleVector(string voiceId, int tokenLength)
    {
        if (_voices.TryGetValue(voiceId, out var voiceData))
        {
            return ExtractVectorFromVoiceData(voiceData, tokenLength);
        }

        // Try fallback voice embeddings
        if (_fallbackEmbeddings.TryGetValue(voiceId, out var fallbackVec))
        {
            return fallbackVec;
        }

        // Default to af_bella fallback
        return _fallbackEmbeddings["af_bella"];
    }

    public IReadOnlyList<string> ListVoiceIds()
    {
        if (_voices.Count > 0)
        {
            return _voices.Keys.ToList();
        }
        return _fallbackEmbeddings.Keys.ToList();
    }

    public void LoadFromNpz(string npzPath)
    {
        try
        {
            var parsed = NpyReader.ReadNpz(npzPath);
            _voices.Clear();
            foreach (var (k, v) in parsed)
            {
                _voices[k] = v;
                if (v.Shape.Length >= 1)
                {
                    StyleDim = v.Shape[^1];
                }
            }
        }
        catch
        {
            // Keep fallbacks on error
        }
    }

    private float[] ExtractVectorFromVoiceData((float[] Data, int[] Shape) voiceData, int tokenLength)
    {
        float[] data = voiceData.Data;
        int[] shape = voiceData.Shape;

        if (shape.Length == 0 || data.Length == 0)
        {
            return new float[StyleDim];
        }

        int dim = shape[^1]; // last dimension is always the style vector size

        // Determine the number of indexable rows based on shape rank
        int numRows = shape.Length switch
        {
            1 => 1,                                        // [256] → single vector, no indexing
            2 => shape[0],                                 // [511, 256] → standard layout
            3 => shape[0] == 1 ? shape[1] : shape[0],     // [1, 511, 256] or [511, 1, 256]
            _ => shape[0]
        };

        int clampedIdx = Math.Clamp(tokenLength, 0, numRows - 1);

        // Calculate byte offset into the flat array
        int elementsPerRow = data.Length / numRows;
        int offset = clampedIdx * elementsPerRow;

        if (offset + dim > data.Length)
        {
            offset = Math.Max(0, data.Length - dim);
        }

        float[] result = new float[dim];
        Array.Copy(data, offset, result, 0, Math.Min(dim, data.Length - offset));
        return result;
    }

    private void LoadDefaultFallbackVoices()
    {
        _fallbackEmbeddings.Clear();
        string[] defaultVoiceIds = {
            "af_bella", "af_sarah", "am_adam", "am_michael",
            "bf_emma", "bm_george",
            "zf_xiaobei", "zm_yunjian",
            "ef_dora", "ff_siwis"
        };

        var rand = new Random(42);
        foreach (string id in defaultVoiceIds)
        {
            float[] vec = new float[256];
            for (int i = 0; i < 256; i++)
            {
                vec[i] = (float)(rand.NextDouble() * 0.4 - 0.2);
            }
            _fallbackEmbeddings[id] = vec;
        }
    }
}
