using System;
using System.Text;
using System.Text.RegularExpressions;

namespace Flama.Audio.Engine.Kokoro.G2P;

public class EnglishG2P : IG2P
{
    private readonly CmuDictionary _dictionary;

    public EnglishG2P(CmuDictionary? dictionary = null)
    {
        _dictionary = dictionary ?? new CmuDictionary();
    }

    public string Phonemize(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return string.Empty;

        // Tokenize text into words and punctuation
        var tokens = Regex.Matches(text, @"[A-Za-z']+|[^\sA-Za-z']+|\s+");
        var sb = new StringBuilder();

        foreach (Match match in tokens)
        {
            string token = match.Value;

            if (string.IsNullOrWhiteSpace(token))
            {
                sb.Append(' ');
                continue;
            }

            if (Regex.IsMatch(token, @"^[A-Za-z']+$"))
            {
                if (_dictionary.TryLookup(token, out string[] arpabet))
                {
                    string ipa = ArpabetToIpa.ConvertWord(arpabet);
                    sb.Append(ipa);
                }
                else
                {
                    // OOV fallback: convert letter by letter
                    sb.Append(ConvertOovLetters(token));
                }
            }
            else
            {
                // Punctuation (preserve . , ! ? ; : etc.)
                sb.Append(token);
            }
        }

        return CleanPhonemeOutput(sb.ToString());
    }

    private static string ConvertOovLetters(string word)
    {
        var sb = new StringBuilder();
        string lower = word.ToLowerInvariant();

        for (int i = 0; i < lower.Length; i++)
        {
            char ch = lower[i];
            char next = i + 1 < lower.Length ? lower[i + 1] : '\0';

            // Digraph rules
            if (ch == 't' && next == 'h') { sb.Append("θ"); i++; continue; }
            if (ch == 's' && next == 'h') { sb.Append("ʃ"); i++; continue; }
            if (ch == 'c' && next == 'h') { sb.Append("ʧ"); i++; continue; }
            if (ch == 'p' && next == 'h') { sb.Append("f"); i++; continue; }
            if (ch == 'n' && next == 'g') { sb.Append("ŋ"); i++; continue; }

            switch (ch)
            {
                case 'a': sb.Append("æ"); break;
                case 'b': sb.Append("b"); break;
                case 'c': sb.Append(next == 'e' || next == 'i' || next == 'y' ? "s" : "k"); break;
                case 'd': sb.Append("d"); break;
                case 'e': sb.Append("ɛ"); break;
                case 'f': sb.Append("f"); break;
                case 'g': sb.Append("ɡ"); break;
                case 'h': sb.Append("h"); break;
                case 'i': sb.Append("ɪ"); break;
                case 'j': sb.Append("ʤ"); break;
                case 'k': sb.Append("k"); break;
                case 'l': sb.Append("l"); break;
                case 'm': sb.Append("m"); break;
                case 'n': sb.Append("n"); break;
                case 'o': sb.Append("ɑ"); break;
                case 'p': sb.Append("p"); break;
                case 'q': sb.Append("k"); break;
                case 'r': sb.Append("ɹ"); break;
                case 's': sb.Append("s"); break;
                case 't': sb.Append("t"); break;
                case 'u': sb.Append("ʌ"); break;
                case 'v': sb.Append("v"); break;
                case 'w': sb.Append("w"); break;
                case 'x': sb.Append("ks"); break;
                case 'y': sb.Append("j"); break;
                case 'z': sb.Append("z"); break;
                default: break;
            }
        }

        return sb.ToString();
    }

    private static string CleanPhonemeOutput(string input)
    {
        // Replace multiple spaces with single space
        string cleaned = Regex.Replace(input, @"\s+", " ");
        return cleaned.Trim();
    }
}
