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
        long[] tokens = tokenizer.Tokenize("həˈloʊ wɝːld");

        Assert.NotNull(tokens);
        Assert.True(tokens.Length >= 3);
        Assert.Equal(0, tokens[0]); // Start pad token
        Assert.Equal(0, tokens[^1]); // End pad token
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
        Assert.Contains("xau̯↓", ipa);
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
}
