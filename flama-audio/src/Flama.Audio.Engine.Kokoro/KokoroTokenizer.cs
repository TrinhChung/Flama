using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace Flama.Audio.Engine.Kokoro;

public class KokoroTokenizer
{
    private readonly Dictionary<string, int> _vocab = new(StringComparer.Ordinal);

    public KokoroTokenizer(string? configJsonPath = null)
    {
        LoadDefaultVocab();

        if (!string.IsNullOrEmpty(configJsonPath) && File.Exists(configJsonPath))
        {
            LoadFromConfigJson(configJsonPath);
        }
    }

    public static string NormalizePhonemes(string phonemes)
    {
        if (string.IsNullOrEmpty(phonemes)) return string.Empty;

        return phonemes
            .Replace("aʊ", "W")
            .Replace("aɪ", "I")
            .Replace("eɪ", "A")
            .Replace("oʊ", "O")
            .Replace("əʊ", "Q")
            .Replace("ɔɪ", "Y")
            .Replace("dʒ", "ʤ")
            .Replace("tʃ", "ʧ")
            .Replace("ɝ", "ɜɹ")
            .Replace("ɚ", "əɹ")
            .Replace("ʔ", "t");
    }

    public long[] Tokenize(string phonemes)
    {
        var tokens = new List<long> { 0 }; // Start PAD token

        if (!string.IsNullOrEmpty(phonemes))
        {
            phonemes = NormalizePhonemes(phonemes);

            int i = 0;
            while (i < phonemes.Length)
            {
                // Try 2-char graphemes first
                if (i + 1 < phonemes.Length)
                {
                    string pair = phonemes.Substring(i, 2);
                    if (_vocab.TryGetValue(pair, out int pairId))
                    {
                        tokens.Add(pairId);
                        i += 2;
                        if (tokens.Count >= 510) break;
                        continue;
                    }
                }

                // Single character
                string single = phonemes[i].ToString();
                if (_vocab.TryGetValue(single, out int singleId))
                {
                    tokens.Add(singleId);
                }
                else if (single == " ")
                {
                    tokens.Add(16); // space token in Kokoro config
                }
                else
                {
                    // Fallback to space token (16)
                    tokens.Add(16);
                }

                i++;
                if (tokens.Count >= 510) break;
            }
        }

        tokens.Add(0); // End PAD token
        return tokens.ToArray();
    }

    public void LoadFromConfigJson(string configPath)
    {
        try
        {
            string json = File.ReadAllText(configPath);
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("vocab", out var vocabElem))
            {
                _vocab.Clear();
                foreach (var prop in vocabElem.EnumerateObject())
                {
                    _vocab[prop.Name] = prop.Value.GetInt32();
                }
            }
        }
        catch
        {
            LoadDefaultVocab();
        }
    }

    private void LoadDefaultVocab()
    {
        _vocab.Clear();
        // Official Kokoro-82M vocab dictionary from config.json
        var defaultVocab = new Dictionary<string, int>
        {
            // Punctuation
            { ";", 1 }, { ":", 2 }, { ",", 3 }, { ".", 4 }, { "!", 5 }, { "?", 6 },
            { "\u2014", 9 }, { "\u2026", 10 }, { "\"", 11 }, { "(", 12 }, { ")", 13 },
            { "\u201C", 14 }, { "\u201D", 15 }, { " ", 16 },
            // Special characters
            { "\u0303", 17 }, // combining tilde
            { "\u02A3", 18 }, { "\u02A5", 19 }, { "\u02A6", 20 }, { "\u02A8", 21 }, { "\u1D5D", 22 },
            { "\uAB67", 23 },
            // Uppercase letters (sparse)
            { "A", 24 }, { "I", 25 }, { "O", 31 }, { "Q", 33 }, { "S", 35 }, { "T", 36 }, { "W", 39 }, { "Y", 41 },
            // Lowercase letters
            { "\u1D4A", 42 }, // superset-a ᵊ
            { "a", 43 }, { "b", 44 }, { "c", 45 }, { "d", 46 }, { "e", 47 }, { "f", 48 },
            { "g", 49 }, // CRITICAL: was missing in previous version
            { "h", 50 }, { "i", 51 },
            { "j", 52 }, { "k", 53 }, { "l", 54 }, { "m", 55 }, { "n", 56 }, { "o", 57 }, { "p", 58 }, { "q", 59 },
            { "r", 60 }, { "s", 61 }, { "t", 62 }, { "u", 63 }, { "v", 64 }, { "w", 65 }, { "x", 66 }, { "y", 67 }, { "z", 68 },
            // IPA vowels & consonants
            { "\u0251", 69 }, { "\u0250", 70 }, { "\u0252", 71 }, { "\u00E6", 72 },
            { "\u03B2", 75 }, { "\u0254", 76 }, { "\u0255", 77 }, { "\u00E7", 78 },
            { "\u0256", 80 }, { "\u00F0", 81 }, { "\u02A4", 82 }, { "\u0259", 83 },
            { "\u025A", 85 }, { "\u025B", 86 }, { "\u025C", 87 },
            { "\u025D", 87 }, // Map stressed-ER phoneme (ɝ) to same slot as ɜ
            { "\u025F", 90 },
            { "\u0261", 92 }, { "\u0265", 99 }, { "\u0268", 101 }, { "\u026A", 102 }, { "\u029D", 103 },
            { "\u026F", 110 }, { "\u0270", 111 }, { "\u014B", 112 },
            { "\u0273", 113 }, { "\u0272", 114 }, { "\u0274", 115 }, { "\u00F8", 116 },
            { "\u0278", 118 }, { "\u03B8", 119 }, { "\u0153", 120 }, { "\u0279", 123 },
            { "\u027E", 125 }, { "\u027B", 126 }, { "\u0281", 128 }, { "\u027D", 129 },
            { "\u0282", 130 }, { "\u0283", 131 }, { "\u0288", 132 }, { "\u02A7", 133 },
            { "\u028A", 135 }, { "\u028B", 136 }, { "\u028C", 138 }, { "\u0263", 139 },
            { "\u0264", 140 }, { "\u03C7", 142 }, { "\u028E", 143 }, { "\u0292", 147 },
            { "\u0294", 148 },
            // Suprasegmentals
            { "\u02C8", 156 }, { "\u02CC", 157 }, { "\u02D0", 158 },
            { "\u02B0", 162 }, { "\u02B2", 164 },
            // Arrows (intonation marks)
            { "\u2193", 169 }, { "\u2192", 171 }, { "\u2197", 172 }, { "\u2198", 173 },
            { "\u1D7B", 177 }
        };

        foreach (var (k, v) in defaultVocab)
        {
            _vocab[k] = v;
        }
    }
}
