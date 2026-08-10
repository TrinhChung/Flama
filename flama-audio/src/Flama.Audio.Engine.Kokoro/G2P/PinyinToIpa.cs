using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

namespace Flama.Audio.Engine.Kokoro.G2P;

public static class PinyinToIpa
{
    private static readonly Dictionary<string, string[]> InitialMapping = new(StringComparer.OrdinalIgnoreCase)
    {
        { "b", new[] { "p" } },
        { "c", new[] { "ʦʰ" } },
        { "ch", new[] { "ʈʂʰ" } }, // \uAB67ʰ represents retroflex ʈʂʰ (using ʈʂʰ for Kokoro compatibility)
        { "d", new[] { "t" } },
        { "f", new[] { "f" } },
        { "g", new[] { "k" } },
        { "h", new[] { "x" } }, // Hexgrad first choice is "x"
        { "j", new[] { "ʨ" } },
        { "k", new[] { "kʰ" } },
        { "l", new[] { "l" } },
        { "m", new[] { "m" } },
        { "n", new[] { "n" } },
        { "p", new[] { "pʰ" } },
        { "q", new[] { "ʨʰ" } },
        { "r", new[] { "ɻ" } }, // Hexgrad first choice is "ɻ"
        { "s", new[] { "s" } },
        { "sh", new[] { "ʂ" } },
        { "t", new[] { "tʰ" } },
        { "x", new[] { "ɕ" } },
        { "z", new[] { "ʦ" } },
        { "zh", new[] { "ʈʂ" } } // \uAB67 maps to ʈʂ
    };

    private static readonly Dictionary<string, string[]> SyllabicConsonantMappings = new(StringComparer.OrdinalIgnoreCase)
    {
        { "hm", new[] { "h", "m0" } },
        { "hng", new[] { "h", "ŋ0" } },
        { "m", new[] { "m0" } },
        { "n", new[] { "n0" } },
        { "ng", new[] { "ŋ0" } }
    };

    private static readonly Dictionary<string, string[]> InterjectionMappings = new(StringComparer.OrdinalIgnoreCase)
    {
        { "io", new[] { "j", "ɔ0" } },
        { "ê", new[] { "ɛ0" } },
        { "er", new[] { "ɚ0" } }, // Hexgrad first choice is "ɚ0"
        { "o", new[] { "ɔ0" } }
    };

    private static readonly Dictionary<string, string[]> FinalMapping = new(StringComparer.OrdinalIgnoreCase)
    {
        { "a", new[] { "a0" } },
        { "ai", new[] { "ai̯0" } },
        { "an", new[] { "a0", "n" } },
        { "ang", new[] { "a0", "ŋ" } },
        { "ao", new[] { "au̯0" } },
        { "e", new[] { "ɤ0" } },
        { "ei", new[] { "ei̯0" } },
        { "en", new[] { "ə0", "n" } },
        { "eng", new[] { "ə0", "ŋ" } },
        { "i", new[] { "i0" } },
        { "ia", new[] { "j", "a0" } },
        { "ian", new[] { "j", "ɛ0", "n" } },
        { "iang", new[] { "j", "a0", "ŋ" } },
        { "iao", new[] { "j", "au̯0" } },
        { "ie", new[] { "j", "e0" } },
        { "in", new[] { "i0", "n" } },
        { "iou", new[] { "j", "ou̯0" } },
        { "ing", new[] { "i0", "ŋ" } },
        { "iong", new[] { "j", "ɔ0", "ŋ" } },
        { "ong", new[] { "ɔ0", "ŋ" } },
        { "ou", new[] { "ou̯0" } },
        { "u", new[] { "u0" } },
        { "uei", new[] { "w", "ei̯0" } },
        { "ua", new[] { "w", "a0" } },
        { "uai", new[] { "w", "ai̯0" } },
        { "uan", new[] { "w", "a0", "n" } },
        { "uen", new[] { "w", "ə0", "n" } },
        { "uang", new[] { "w", "a0", "ŋ" } },
        { "ueng", new[] { "w", "ə0", "ŋ" } },
        { "uo", new[] { "w", "o0" } },
        { "o", new[] { "w", "o0" } },
        { "ü", new[] { "y0" } },
        { "üe", new[] { "ɥ", "e0" } },
        { "üan", new[] { "ɥ", "ɛ0", "n" } },
        { "ün", new[] { "y0", "n" } }
    };

    private static readonly Dictionary<string, string[]> FinalMappingAfterZhChShR = new(StringComparer.OrdinalIgnoreCase)
    {
        { "i", new[] { "ɻ̩0" } } // \u027b\u03290 retroflex syllabic consonant (using ɻ̩0 for compatibility)
    };

    private static readonly Dictionary<string, string[]> FinalMappingAfterZCS = new(StringComparer.OrdinalIgnoreCase)
    {
        { "i", new[] { "ɹ̩0" } } // \u0279\u03290 dental syllabic consonant (using ɹ̩0 for compatibility)
    };

    private static readonly Dictionary<int, string> ToneMapping = new()
    {
        { 1, "˥" },
        { 2, "˧˥" },
        { 3, "˧˩˧" },
        { 4, "˥˩" },
        { 5, "" }
    };

    public static string Convert(string pinyin)
    {
        if (string.IsNullOrWhiteSpace(pinyin)) return string.Empty;

        // 1. Extract tone (last digit 1-5)
        int tone = 5;
        string normalPinyin = pinyin;
        if (pinyin.Length > 1 && char.IsDigit(pinyin[^1]))
        {
            if (int.TryParse(pinyin[^1].ToString(), out int parsedTone))
            {
                tone = parsedTone;
                normalPinyin = pinyin[..^1];
            }
        }

        // Adjust tone to bounds just in case
        if (!ToneMapping.ContainsKey(tone)) tone = 5;

        // 2. Check Syllabic Consonants and Interjections
        if (SyllabicConsonantMappings.TryGetValue(normalPinyin, out var syllabic))
        {
            return ApplyTone(syllabic, tone);
        }

        if (InterjectionMappings.TryGetValue(normalPinyin, out var interj))
        {
            return ApplyTone(interj, tone);
        }

        // 3. Split Initial & Final
        var (initial, final) = SplitInitialFinal(normalPinyin);

        // 4. Map Initial to IPA
        string initialIpa = "";
        if (initial != null)
        {
            if (InitialMapping.TryGetValue(initial, out var initIpaArr))
            {
                initialIpa = initIpaArr[0];
            }
        }

        // 5. Map Final to IPA
        string finalIpa = "";
        if (final != null)
        {
            string[]? finalIpaArr = null;

            if (initial != null && (initial == "zh" || initial == "ch" || initial == "sh" || initial == "r"))
            {
                FinalMappingAfterZhChShR.TryGetValue(final, out finalIpaArr);
            }
            else if (initial != null && (initial == "z" || initial == "c" || initial == "s"))
            {
                FinalMappingAfterZCS.TryGetValue(final, out finalIpaArr);
            }

            if (finalIpaArr == null)
            {
                FinalMapping.TryGetValue(final, out finalIpaArr);
            }

            if (finalIpaArr != null)
            {
                finalIpa = ApplyTone(finalIpaArr, tone);
            }
            else
            {
                // Fallback to verbatim
                finalIpa = final;
            }
        }

        return initialIpa + finalIpa;
    }

    private static string ApplyTone(string[] phonemes, int tone)
    {
        string toneSymbol = ToneMapping[tone];
        return string.Concat(phonemes.Select(p => p.Replace("0", toneSymbol)));
    }

    private static (string? Initial, string Final) SplitInitialFinal(string pinyin)
    {
        // 1. Double letter initials
        if (pinyin.StartsWith("zh", StringComparison.OrdinalIgnoreCase) ||
            pinyin.StartsWith("ch", StringComparison.OrdinalIgnoreCase) ||
            pinyin.StartsWith("sh", StringComparison.OrdinalIgnoreCase))
        {
            return (pinyin[..2], pinyin[2..]);
        }

        // 2. Single letter initials
        string[] strictInitials = { "b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "j", "q", "x", "r", "z", "c", "s" };
        foreach (var init in strictInitials)
        {
            if (pinyin.StartsWith(init, StringComparison.OrdinalIgnoreCase))
            {
                return (init, pinyin[init.Length..]);
            }
        }

        // 3. Zero-initial orthographic rules for y/w
        if (pinyin.StartsWith("y", StringComparison.OrdinalIgnoreCase))
        {
            return pinyin.ToLowerInvariant() switch
            {
                "yi" => (null, "i"),
                "ya" => (null, "ia"),
                "yan" => (null, "ian"),
                "yang" => (null, "iang"),
                "yao" => (null, "iao"),
                "ye" => (null, "ie"),
                "yin" => (null, "in"),
                "ying" => (null, "ing"),
                "yong" => (null, "iong"),
                "yung" => (null, "iong"),
                "you" => (null, "iou"),
                "yu" => (null, "ü"),
                "yue" => (null, "üe"),
                "yuan" => (null, "üan"),
                "yun" => (null, "ün"),
                _ => (null, pinyin[1..]) // fallback
            };
        }

        if (pinyin.StartsWith("w", StringComparison.OrdinalIgnoreCase))
        {
            return pinyin.ToLowerInvariant() switch
            {
                "wu" => (null, "u"),
                "wa" => (null, "ua"),
                "wai" => (null, "uai"),
                "wan" => (null, "uan"),
                "wen" => (null, "uen"),
                "wang" => (null, "uang"),
                "weng" => (null, "ueng"),
                "wo" => (null, "uo"),
                _ => (null, pinyin[1..]) // fallback
            };
        }

        // 4. Syllable starting directly with vowel
        return (null, pinyin);
    }
}
