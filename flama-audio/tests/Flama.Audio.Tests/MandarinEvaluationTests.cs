using System;
using System.Collections.Generic;
using System.IO;
using Flama.Audio.Engine.Kokoro;
using Flama.G2P.Chinese;
using Flama.G2P.English;
using Xunit;
using Xunit.Abstractions;

namespace Flama.Audio.Tests;

public class MandarinEvaluationTests
{
    private readonly ITestOutputHelper _output;

    public MandarinEvaluationTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public void ListVoices_And_SynthesizeTestCases()
    {
        string localDataFolder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Flama", "Audio", "engines", "kokoro");
        var voiceManager = new VoiceManager(Path.Combine(localDataFolder, "voices-v1.0.bin"));
        var voices = voiceManager.ListVoiceIds();
        _output.WriteLine($"Total voices available: {voices.Count}");
        foreach (var v in voices)
        {
            if (v.StartsWith("z", StringComparison.OrdinalIgnoreCase) || v.Contains("zh") || v.Contains("c"))
            {
                _output.WriteLine($"Potential Chinese Voice: {v}");
            }
        }

        using var engine = new KokoroOnnxEngine();
        engine.Initialize();
        _output.WriteLine($"IsChineseHighPrecisionMode: {engine.IsChineseHighPrecisionMode}");

        // Select voice: check if zf_xiaobei or zm_yunjian exists, or any z* voice
        string selectedVoice = voices.Contains("zf_xiaobei") ? "zf_xiaobei" :
                               voices.Contains("zm_yunjian") ? "zm_yunjian" :
                               voices.FirstOrDefault(v => v.StartsWith("z", StringComparison.OrdinalIgnoreCase)) ?? "zf_xiaobei";
        _output.WriteLine($"Using voice: {selectedVoice}");

        var testCases = new Dictionary<string, string>
        {
            ["01_phoneme_sibilants_tonguetwister"] = "四是四十是十，十四是十四，四十是四十。",
            ["02_phoneme_retroflex_contrast"] = "我知道他今天会迟到。",
            ["03_phoneme_jqx_u_er"] = "星期天小徐去学校学京剧，儿子喜欢吃鱼和热汤。",
            ["04_tone_accuracy_mamama"] = "妈妈骑马，马慢，妈妈骂马。",
            ["05_tone_sandhi_33"] = "你好，我想买五把小雨伞。",
            ["06_tone_sandhi_yi_bu"] = "一个人一天只能去一次，不好就不要去。",
            ["07_neutral_tone_words"] = "爸爸妈妈告诉我，买东西的时候要客气。",
            ["08_polyphone_bank_walk_music"] = "他去银行行走，听着欢快的音乐，觉得重担变轻了。",
            ["09_polyphone_return_grow"] = "虽然还欠钱，但他还有希望长大。",
            ["10_prosody_intonation_question"] = "今天天气真好，你想和我一起去公园散步吗？",
            ["11_prosody_intonation_compound"] = "虽然学中文很难，但是我觉得非常有意思，越学越想学！"
        };

        var outputDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "mandarin_eval_output");
        Directory.CreateDirectory(outputDir);

        var englishG2p = new EnglishG2P();
        var chineseG2p = new ChineseG2P(englishG2p);

        foreach (var (key, text) in testCases)
        {
            string ipa = chineseG2p.Phonemize(text);
            _output.WriteLine($"\n--- [{key}] ---");
            _output.WriteLine($"Text: {text}");
            _output.WriteLine($"IPA:  {ipa}");

            try
            {
                byte[] wav = engine.Synthesize(text, selectedVoice, speed: 1.0, language: "zh-CN");
                string filePath = Path.Combine(outputDir, $"{key}.wav");
                File.WriteAllBytes(filePath, wav);
                _output.WriteLine($"Generated WAV: {filePath} ({wav.Length} bytes, duration ~{wav.Length / (24000 * 2.0):F2}s)");
            }
            catch (Exception ex)
            {
                _output.WriteLine($"Error synthesizing '{key}': {ex.Message}");
            }
        }
    }
}
