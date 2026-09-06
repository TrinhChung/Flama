using System;
using System.IO;
using Flama.Audio.Engine.Kokoro;
using Flama.G2P;
using Flama.G2P.English;
using Flama.G2P.Chinese;
using Flama.Audio.Engine.Kokoro.IO;
using Xunit;

namespace Flama.Audio.Tests;

public class KokoroEngineTests
{
    [Fact]
    public void EnglishG2P_Phonemize_SimpleText_ReturnsIPA()
    {
        var g2p = new EnglishG2P();
        string ipa = g2p.Phonemize("Hello world");

        Assert.NotNull(ipa);
        Assert.NotEmpty(ipa);
        Assert.Contains("h", ipa);
        Assert.Contains("w", ipa);
    }

    [Fact]
    public void KokoroTokenizer_Tokenize_ReturnsPaddedTokenIds()
    {
        var tokenizer = new KokoroTokenizer();
        long[] tokens = tokenizer.Tokenize("həlˈO wˈɜɹld");

        Assert.NotNull(tokens);
        Assert.True(tokens.Length >= 3);
        Assert.Equal(0, tokens[0]); // Start pad token
        Assert.Equal(0, tokens[^1]); // End pad token
    }

    [Fact]
    public void KokoroTokenizer_Tokenize_DiphthongsAndAliases_MapsToSingleKokoroTokens()
    {
        var tokenizer = new KokoroTokenizer();

        // Test that Kokoro diphthong tokens O (31), W (39), I (25), A (24), Y (41) are preserved
        long[] tokensDirect = tokenizer.Tokenize("O W I A Y");
        Assert.Contains(31, tokensDirect);
        Assert.Contains(39, tokensDirect);
        Assert.Contains(25, tokensDirect);
        Assert.Contains(24, tokensDirect);
        Assert.Contains(41, tokensDirect);

        // Test that traditional 2-char aliases (oʊ, aʊ, aɪ, eɪ, ɔɪ) are normalized to the exact same tokens
        long[] tokensAlias = tokenizer.Tokenize("oʊ aʊ aɪ eɪ ɔɪ");
        Assert.Contains(31, tokensAlias);
        Assert.Contains(39, tokensAlias);
        Assert.Contains(25, tokensAlias);
        Assert.Contains(24, tokensAlias);
        Assert.Contains(41, tokensAlias);
    }

    [Fact]
    public void VoiceManager_GetStyleVector_Returns256DimensionArray()
    {
        var voiceManager = new VoiceManager();
        float[] vec = voiceManager.GetStyleVector("af_bella", 15);

        Assert.NotNull(vec);
        Assert.Equal(256, vec.Length);
    }

    [Fact]
    public void NpyReader_ReadNpy_ValidHeader_ParsesSuccessfully()
    {
        using var ms = new MemoryStream();
        using (var writer = new BinaryWriter(ms, System.Text.Encoding.UTF8, leaveOpen: true))
        {
            // Magic \x93NUMPY
            writer.Write(new byte[] { 0x93, (byte)'N', (byte)'U', (byte)'M', (byte)'P', (byte)'Y' });
            writer.Write((byte)1); // Major
            writer.Write((byte)0); // Minor

            string header = "{'descr': '<f4', 'fortran_order': False, 'shape': (2, 4), }";
            while ((header.Length + 10 + 2) % 64 != 0) header += " ";
            header += "\n";

            writer.Write((ushort)header.Length);
            writer.Write(System.Text.Encoding.ASCII.GetBytes(header));

            // Write 8 float32 values (2*4)
            for (int i = 0; i < 8; i++)
            {
                writer.Write((float)i * 0.1f);
            }
            writer.Flush();
        }

        ms.Position = 0;
        var (data, shape) = NpyReader.ReadNpy(ms);

        Assert.Equal(8, data.Length);
        Assert.Equal(new[] { 2, 4 }, shape);
    }

    [Fact]
    public void ChineseG2P_Phonemize_SimpleText_ReturnsMandarinIPA()
    {
        var englishG2p = new EnglishG2P();
        var g2p = new ChineseG2P(englishG2p);
        string ipa = g2p.Phonemize("你好");

        Assert.NotNull(ipa);
        Assert.NotEmpty(ipa);
        Assert.Contains("ni↗", ipa);
        Assert.Contains("xau↓", ipa);
    }

    [Fact]
    public void ChineseG2P_Phonemize_MixedText_DispatchesEnglishCorrectly()
    {
        var englishG2p = new EnglishG2P();
        var g2p = new ChineseG2P(englishG2p);
        string ipa = g2p.Phonemize("你好 test");

        Assert.NotNull(ipa);
        Assert.NotEmpty(ipa);
        Assert.Contains("ni↗", ipa);
        Assert.Contains("tˈɛst", ipa);
    }

    [Fact]
    public void PinyinToIpa_Convert_SimplePinyin_ReturnsIPA()
    {
        string ipa = PinyinToIpa.Convert("zhong1");
        Assert.Equal("ʈʂɔ˥ŋ", ipa);
    }

    [Fact]
    public void ChineseTextNormalizer_NormalizesDatesTimesDecimals()
    {
        Assert.Equal("二零二六年九月六日", ChineseTextNormalizer.Normalize("2026年9月6日"));
        Assert.Equal("三点一四", ChineseTextNormalizer.Normalize("3.14"));
        Assert.Equal("百分之八十五", ChineseTextNormalizer.Normalize("85%"));
        Assert.Equal("十五点半", ChineseTextNormalizer.Normalize("15:30"));
    }

    [Fact]
    public void ChineseToneSandhi_AppliesProperly()
    {
        var sandhi = new ToneSandhi();

        // Potential complement: 得不到 -> de5 bu5 dao4
        var buPinyins = new List<string> { "de5", "bu4", "dao4" };
        sandhi.ApplyBuSandhi("得不到", buPinyins);
        Assert.Equal("bu5", buPinyins[1]);

        // 一 before 4th tone -> yi2 (一个 -> yi2 ge4)
        var yiPinyins = new List<string> { "yi1", "ge4" };
        sandhi.ApplyYiSandhi("一个", yiPinyins);
        Assert.Equal("yi2", yiPinyins[0]);
    }

    [Fact]
    public void ChineseG2P_ExternalLexicon_LoadsSuccessfully()
    {
        var tempFile = Path.GetTempFileName();
        try
        {
            File.WriteAllLines(tempFile, new[]
            {
                "# Custom test lexicon",
                "有的\tyou3 de5",
                "测试词库: ce4,shi4,ci2,ku4",
                "人工智能: rén gōng zhì néng"
            });

            var tempDir = Path.GetDirectoryName(tempFile)!;
            var targetLexicon = Path.Combine(tempDir, "large_pinyin.txt");
            File.Copy(tempFile, targetLexicon, true);

            var g2p = new ChineseG2P(null, tempDir);
            Assert.True(g2p.IsHighPrecisionMode);
            Assert.True(g2p.LexiconWordCount >= 3);

            string ipa = g2p.Phonemize("有的");
            Assert.NotNull(ipa);
            Assert.NotEmpty(ipa);

            if (File.Exists(targetLexicon)) File.Delete(targetLexicon);
        }
        finally
        {
            if (File.Exists(tempFile)) File.Delete(tempFile);
        }
    }
}
