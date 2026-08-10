using System;
using System.Collections.Generic;
using System.Text;

namespace Flama.Audio.Engine.Kokoro.G2P;

public static class ArpabetToIpa
{
    private static readonly Dictionary<string, string> BaseMap = new(StringComparer.OrdinalIgnoreCase)
    {
        // Consonants
        { "B", "b" }, { "D", "d" }, { "F", "f" }, { "G", "ɡ" }, { "HH", "h" },
        { "K", "k" }, { "L", "l" }, { "M", "m" }, { "N", "n" }, { "P", "p" },
        { "R", "ɹ" }, { "S", "s" }, { "T", "t" }, { "V", "v" }, { "W", "w" },
        { "Y", "j" }, { "Z", "z" },
        { "CH", "ʧ" }, { "DH", "ð" }, { "JH", "ʤ" }, { "NG", "ŋ" },
        { "SH", "ʃ" }, { "TH", "θ" }, { "ZH", "ʒ" }
    };

    public static string ConvertWord(string[] arpabetTokens)
    {
        var sb = new StringBuilder();

        foreach (string rawToken in arpabetTokens)
        {
            string token = rawToken.Trim().ToUpperInvariant();
            if (string.IsNullOrEmpty(token)) continue;

            // Extract stress digit if present (e.g. AH0, ER1, OW2)
            char lastChar = token[^1];
            int stress = -1;
            if (char.IsDigit(lastChar))
            {
                stress = lastChar - '0';
                token = token[..^1];
            }

            if (stress == 1) sb.Append("ˈ");
            else if (stress == 2) sb.Append("ˌ");

            if (BaseMap.TryGetValue(token, out string? ipa))
            {
                sb.Append(ipa);
            }
            else
            {
                // Vowels mapping depending on stress
                switch (token)
                {
                    case "AA": sb.Append("ɑ"); break;
                    case "AE": sb.Append("æ"); break;
                    case "AH": sb.Append(stress == 0 ? "ə" : "ʌ"); break;
                    case "AO": sb.Append("ɔ"); break;
                    case "AW": sb.Append("aʊ"); break;
                    case "AY": sb.Append("aɪ"); break;
                    case "EH": sb.Append("ɛ"); break;
                    case "ER": sb.Append(stress == 0 ? "ɚ" : "ɝ"); break;
                    case "EY": sb.Append("eɪ"); break;
                    case "IH": sb.Append(stress == 0 ? "ᵻ" : "ɪ"); break;
                    case "IY": sb.Append("i"); break;
                    case "OW": sb.Append("oʊ"); break;
                    case "OY": sb.Append("ɔɪ"); break;
                    case "UH": sb.Append("ʊ"); break;
                    case "UW": sb.Append("u"); break;
                    default:
                        // Fallback: keep lowecase token char
                        sb.Append(token.ToLowerInvariant());
                        break;
                }
            }
        }

        return sb.ToString();
    }
}
