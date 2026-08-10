using System;
using System.Collections.Generic;
using System.Text;
using System.Text.RegularExpressions;

namespace Flama.Audio.Engine.Kokoro.G2P;

public class ChineseG2P : IG2P
{
    private readonly PinyinDictionary _pinyinDict;
    private readonly IG2P _englishG2p;

    public ChineseG2P(IG2P englishG2p)
    {
        _pinyinDict = new PinyinDictionary();
        _englishG2p = englishG2p;
    }

    public string Phonemize(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return string.Empty;

        // 1. Normalize numbers
        text = NormalizeNumbers(text);

        // 2. Map punctuation
        text = MapPunctuation(text);

        // 3. Segment and phonemize
        // Tách chữ Hán (CJK Unified Ideographs) vs các ký tự khác (Latinh, khoảng trắng, dấu câu)
        var matches = Regex.Matches(text, @"[\u4E00-\u9FFF]+|[^\u4E00-\u9FFF]+");
        var result = new StringBuilder();

        foreach (Match match in matches)
        {
            string segment = match.Value;
            if (string.IsNullOrEmpty(segment)) continue;

            if (Regex.IsMatch(segment, @"^[\u4E00-\u9FFF]+$"))
            {
                // Chinese character segment
                result.Append(PhonemizeChineseSegment(segment));
            }
            else
            {
                // Non-Chinese segment (may contain English words, punctuation, etc.)
                result.Append(PhonemizeNonChineseSegment(segment));
            }
        }

        return CleanOutput(result.ToString());
    }

    private string PhonemizeChineseSegment(string segment)
    {
        var pinyins = new List<string>();

        // 1. Hanzi to Pinyin lookup
        foreach (char c in segment)
        {
            string? py = _pinyinDict.GetPinyin(c);
            if (py != null)
            {
                pinyins.Add(py);
            }
            else
            {
                // If not found in pinyin dict, keep character to let it fall through or be skipped
                pinyins.Add(c.ToString());
            }
        }

        // 2. Apply Tone Sandhi (3rd tone modification)
        for (int i = 0; i < pinyins.Count - 1; i++)
        {
            if (pinyins[i].EndsWith("3") && pinyins[i + 1].EndsWith("3"))
            {
                pinyins[i] = pinyins[i][..^1] + "2";
            }
        }

        // 3. Apply Tone Sandhi for 'yi' and 'bu'
        for (int i = 0; i < pinyins.Count - 1; i++)
        {
            string current = pinyins[i];
            string next = pinyins[i + 1];

            if (next.Length > 1 && char.IsDigit(next[^1]))
            {
                char nextTone = next[^1];

                if (current.StartsWith("bu", StringComparison.OrdinalIgnoreCase) && current.EndsWith("4"))
                {
                    if (nextTone == '4')
                    {
                        pinyins[i] = current[..^1] + "2";
                    }
                }
                else if (current.StartsWith("yi", StringComparison.OrdinalIgnoreCase) && current.EndsWith("1"))
                {
                    if (nextTone == '4')
                    {
                        pinyins[i] = current[..^1] + "2";
                    }
                    else if (nextTone == '1' || nextTone == '2' || nextTone == '3')
                    {
                        pinyins[i] = current[..^1] + "4";
                    }
                }
            }
        }

        // 4. Convert Pinyin to IPA and apply retone arrows
        var ipaParts = new List<string>();
        foreach (string py in pinyins)
        {
            // If it's a raw non-pinyin char, skip or copy
            if (py.Length > 0 && !char.IsLetter(py[0]))
            {
                continue;
            }

            string ipa = PinyinToIpa.Convert(py);
            ipa = Retone(ipa);
            if (!string.IsNullOrEmpty(ipa))
            {
                ipaParts.Add(ipa);
            }
        }

        return " " + string.Join(" ", ipaParts) + " ";
    }

    private string PhonemizeNonChineseSegment(string segment)
    {
        // Segment could contain English words, punctuation, or mixed whitespace.
        // We find all words of Latin characters and dispatch them to the English G2P.
        var tokens = Regex.Matches(segment, @"[A-Za-z']+|[^\sA-Za-z']+|\s+");
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
                // Dispatch English word to English G2P
                string enIpa = _englishG2p.Phonemize(token);
                sb.Append(enIpa);
            }
            else
            {
                // Punctuation or other characters
                sb.Append(token);
            }
        }

        return sb.ToString();
    }

    private static string Retone(string p)
    {
        p = p.Replace("˧˩˧", "↓"); // third tone
        p = p.Replace("˧˥", "↗");  // second tone
        p = p.Replace("˥˩", "↘");  // fourth tone
        p = p.Replace("˥", "→");   // first tone
        
        // Map syllabic consonants to ɨ according to Hexgrad misaki
        p = p.Replace("ɻ\u0329", "ɨ").Replace("ɹ\u0329", "ɨ");
        p = p.Replace("ɻ̩", "ɨ").Replace("ɹ̩", "ɨ");
        p = p.Replace("m0", "m").Replace("n0", "n").Replace("ŋ0", "ŋ");
        return p;
    }

    private static string MapPunctuation(string text)
    {
        text = text.Replace("、", ", ").Replace("，", ", ");
        text = text.Replace("。", ". ").Replace("．", ". ");
        text = text.Replace("！", "! ");
        text = text.Replace("：", ": ");
        text = text.Replace("；", "; ");
        text = text.Replace("？", "? ");
        text = text.Replace("«", " “").Replace("»", "” ");
        text = text.Replace("《", " “").Replace("》", "” ");
        text = text.Replace("「", " “").Replace("」", "” ");
        text = text.Replace("『", " “").Replace("』", "” ");
        text = text.Replace("（", " (").Replace("）", ") ");
        return text.Trim();
    }

    private static string NormalizeNumbers(string text)
    {
        return Regex.Replace(text, @"\d+", m =>
        {
            if (long.TryParse(m.Value, out long val))
            {
                return IntegerToChinese(val);
            }
            return m.Value;
        });
    }

    private static readonly string[] ChineseDigits = { "零", "一", "二", "三", "四", "五", "六", "七", "八", "九" };
    private static readonly string[] ChineseUnits = { "", "十", "百", "千", "万", "十万", "百万", "千万", "亿" };

    private static string IntegerToChinese(long number)
    {
        if (number == 0) return ChineseDigits[0];
        if (number < 0) return "负" + IntegerToChinese(-number);

        var result = new StringBuilder();
        int unitIndex = 0;
        bool lastWasZero = false;

        while (number > 0)
        {
            long digit = number % 10;
            if (digit > 0)
            {
                if (lastWasZero)
                {
                    result.Insert(0, ChineseDigits[0]);
                    lastWasZero = false;
                }
                string unit = unitIndex < ChineseUnits.Length ? ChineseUnits[unitIndex] : "";
                result.Insert(0, ChineseDigits[digit] + unit);
            }
            else
            {
                lastWasZero = true;
            }

            number /= 10;
            unitIndex++;
        }

        string s = result.ToString();
        if (s.StartsWith("一十"))
        {
            s = s[1..];
        }
        return s;
    }

    private static string CleanOutput(string input)
    {
        string cleaned = Regex.Replace(input, @"\s+", " ");
        return cleaned.Trim();
    }
}
