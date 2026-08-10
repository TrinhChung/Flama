using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;

namespace Flama.Audio.Engine.Kokoro.G2P;

public class PinyinDictionary
{
    private readonly Dictionary<char, string> _dict = new();

    public PinyinDictionary()
    {
        try
        {
            var assembly = Assembly.GetExecutingAssembly();
            string resourceName = "Flama.Audio.Engine.Kokoro.G2P.pinyin_dict.txt";
            using Stream? stream = assembly.GetManifestResourceStream(resourceName);
            if (stream == null)
            {
                var names = assembly.GetManifestResourceNames();
                foreach (var name in names)
                {
                    if (name.EndsWith("pinyin_dict.txt", StringComparison.OrdinalIgnoreCase))
                    {
                        using Stream? fallbackStream = assembly.GetManifestResourceStream(name);
                        if (fallbackStream != null)
                        {
                            LoadFromStream(fallbackStream);
                            return;
                        }
                    }
                }
                throw new FileNotFoundException($"Could not find embedded resource {resourceName}");
            }

            LoadFromStream(stream);
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Failed to load Pinyin dictionary: {ex.Message}");
        }
    }

    private void LoadFromStream(Stream stream)
    {
        using var reader = new StreamReader(stream, Encoding.UTF8);
        string? line;
        while ((line = reader.ReadLine()) != null)
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            var parts = line.Split('\t');
            if (parts.Length >= 2 && parts[0].Length > 0)
            {
                char hanzi = parts[0][0];
                string pinyin = parts[1].Trim();
                _dict[hanzi] = pinyin;
            }
        }
    }

    public string? GetPinyin(char hanzi)
    {
        return _dict.TryGetValue(hanzi, out var pinyin) ? pinyin : null;
    }
}
