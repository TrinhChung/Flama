using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;

namespace Flama.Audio.Engine.Kokoro.G2P;

public class CmuDictionary
{
    private readonly Dictionary<string, string[]> _dict = new(StringComparer.OrdinalIgnoreCase);

    public CmuDictionary(string? dictFilePath = null)
    {
        LoadBuiltinDefaults();

        if (!string.IsNullOrEmpty(dictFilePath) && File.Exists(dictFilePath))
        {
            LoadFromFile(dictFilePath);
        }
    }

    public bool TryLookup(string word, out string[] arpabetTokens)
    {
        string cleaned = CleanWord(word);
        return _dict.TryGetValue(cleaned, out arpabetTokens!);
    }

    public void LoadFromFile(string filePath)
    {
        foreach (var line in File.ReadLines(filePath))
        {
            if (string.IsNullOrWhiteSpace(line) || line.StartsWith(";;;")) continue;

            // CMU dict formats use either double-space, single-space, or tab as separator
            // Split on first whitespace run to separate word from phonemes
            var parts = Regex.Split(line.Trim(), @"\s{2,}|\t");
            if (parts.Length < 2)
            {
                // Fallback: split on first space
                int spaceIdx = line.IndexOf(' ');
                if (spaceIdx <= 0) continue;
                parts = new[] { line[..spaceIdx], line[(spaceIdx + 1)..].Trim() };
            }

            string rawWord = parts[0];
            // Remove alternate pronunciation suffix like WORD(2)
            string word = Regex.Replace(rawWord, @"\(\d+\)$", "").Trim().ToUpperInvariant();
            
            string[] phonemes = parts[1].Split(' ', StringSplitOptions.RemoveEmptyEntries);
            
            // Keep first/primary entry if not present
            _dict.TryAdd(word, phonemes);
        }
    }

    private static string CleanWord(string word)
    {
        return Regex.Replace(word.Trim().ToUpperInvariant(), @"[^A-Z']", "");
    }

    private void LoadBuiltinDefaults()
    {
        var defaults = new Dictionary<string, string[]>
        {
            { "HELLO", new[] { "HH", "AH0", "L", "OW1" } },
            { "WORLD", new[] { "W", "ER1", "L", "D" } },
            { "THIS", new[] { "DH", "IH1", "S" } },
            { "IS", new[] { "IH1", "Z" } },
            { "A", new[] { "AH0" } },
            { "TEST", new[] { "T", "EH1", "S", "T" } },
            { "OF", new[] { "AH1", "V" } },
            { "KOKORO", new[] { "K", "OW1", "K", "ER0", "OW0" } },
            { "TEXT", new[] { "T", "EH1", "K", "S", "T" } },
            { "TO", new[] { "T", "UW1" } },
            { "SPEECH", new[] { "S", "P", "IY1", "CH" } },
            { "ENGINE", new[] { "EH1", "N", "JH", "AH0", "N" } },
            { "ENGLISH", new[] { "IH1", "NG", "G", "L", "IH0", "SH" } },
            { "JAPANESE", new[] { "JH", "AE1", "P", "AH0", "N", "IY1", "Z" } },
            { "FLAMA", new[] { "F", "L", "AA1", "M", "AH0" } },
            { "AUDIO", new[] { "AA1", "D", "IY0", "OW0" } },
            { "GOOD", new[] { "G", "UH1", "D" } },
            { "MORNING", new[] { "M", "AO1", "R", "N", "IH0", "NG" } },
            { "AFTERNOON", new[] { "AE2", "F", "T", "ER0", "N", "UW1", "N" } },
            { "EVENING", new[] { "IY1", "V", "N", "IH0", "NG" } },
            { "THE", new[] { "DH", "AH0" } },
            { "YOU", new[] { "Y", "UW1" } },
            { "ARE", new[] { "AA1", "R" } },
            { "HOW", new[] { "HH", "AW1" } },
            { "WELCOME", new[] { "W", "EH1", "L", "K", "AH0", "M" } }
        };

        foreach (var (k, v) in defaults)
        {
            _dict[k] = v;
        }
    }
}
