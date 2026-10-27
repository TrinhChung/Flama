using System;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Core.Models;
using Flama.Audio.Engine.EdgeTts.Services;
using Xunit;

namespace Flama.Audio.Tests;

public class EdgeTtsVoiceCatalogTests
{
    [Fact]
    public void LoadFromEmbeddedResource_ReturnsAll322EmbeddedVoices()
    {
        var catalog = new EdgeTtsVoiceCatalog();
        var voices = catalog.LoadFromEmbeddedResource();

        Assert.NotNull(voices);
        Assert.Equal(322, voices.Count);
    }

    [Fact]
    public void EmbeddedVoices_CoverRequiredLocalesAndKeyVoices()
    {
        var catalog = new EdgeTtsVoiceCatalog();
        var voices = catalog.LoadFromEmbeddedResource();

        // Japanese
        Assert.Contains(voices, v => v.VoiceId == "ja-JP-NanamiNeural");
        Assert.Contains(voices, v => v.VoiceId == "ja-JP-KeitaNeural");

        // Vietnamese
        Assert.Contains(voices, v => v.VoiceId == "vi-VN-HoaiMyNeural");
        Assert.Contains(voices, v => v.VoiceId == "vi-VN-NamMinhNeural");

        // English US
        Assert.Contains(voices, v => v.VoiceId == "en-US-AvaNeural");
        Assert.Contains(voices, v => v.VoiceId == "en-US-AndrewNeural");
        Assert.Contains(voices, v => v.VoiceId == "en-US-JennyNeural");

        // English UK
        Assert.Contains(voices, v => v.VoiceId == "en-GB-SoniaNeural");
        Assert.Contains(voices, v => v.VoiceId == "en-GB-RyanNeural");

        // Chinese
        Assert.Contains(voices, v => v.VoiceId == "zh-CN-XiaoxiaoNeural");

        // Korean
        Assert.Contains(voices, v => v.VoiceId == "ko-KR-SunHiNeural");
    }

    [Fact]
    public void EmbeddedVoices_SatisfyFieldMappingInvariants()
    {
        var catalog = new EdgeTtsVoiceCatalog();
        var voices = catalog.LoadFromEmbeddedResource();

        foreach (var voice in voices)
        {
            Assert.False(string.IsNullOrWhiteSpace(voice.VoiceId), $"VoiceId is empty for {voice}");
            Assert.False(string.IsNullOrWhiteSpace(voice.Name), $"Name is empty for {voice.VoiceId}");
            Assert.False(string.IsNullOrWhiteSpace(voice.SpeakerName), $"SpeakerName is empty for {voice.VoiceId}");
            Assert.False(string.IsNullOrWhiteSpace(voice.StyleName), $"StyleName is empty for {voice.VoiceId}");
            Assert.False(string.IsNullOrWhiteSpace(voice.Locale), $"Locale is empty for {voice.VoiceId}");

            Assert.True(voice.CommercialSafe, $"CommercialSafe should be true for {voice.VoiceId}");
            Assert.Equal("Microsoft Edge TTS", voice.Attribution);

            // "Neural" must be stripped from SpeakerName
            Assert.DoesNotContain("Neural", voice.SpeakerName);
        }
    }

    [Fact]
    public void MapToDescriptor_CorrectlyExtractsSpeakerGenderAndLocale()
    {
        var rawItem = new EdgeVoiceRawItem(
            Name: "Microsoft Server Speech Text to Speech Voice (ja-JP, NanamiNeural)",
            ShortName: "ja-JP-NanamiNeural",
            Gender: "Female",
            Locale: "ja-JP",
            LocaleName: "Japanese (Japan)",
            SuggestedCodec: "audio-24khz-48kbitrate-mono-mp3",
            FriendlyName: "Microsoft Nanami Online (Natural) - Japanese (Japan)",
            Status: "GA"
        );

        var descriptor = EdgeTtsVoiceCatalog.MapToDescriptor(rawItem);

        Assert.Equal("ja-JP-NanamiNeural", descriptor.VoiceId);
        Assert.Equal("Nanami", descriptor.SpeakerName);
        Assert.Equal("Female", descriptor.StyleName);
        Assert.Equal("Nanami (Female)", descriptor.Name);
        Assert.Equal("ja-JP", descriptor.Locale);
        Assert.True(descriptor.CommercialSafe);
        Assert.Equal("Microsoft Edge TTS", descriptor.Attribution);
    }

    [Fact]
    public void MapToDescriptor_HandlesMultilingualVoices()
    {
        var rawItem = new EdgeVoiceRawItem(
            Name: "Microsoft Server Speech Text to Speech Voice (en-US, AndrewMultilingualNeural)",
            ShortName: "en-US-AndrewMultilingualNeural",
            Gender: "Male",
            Locale: "en-US",
            LocaleName: "English (United States)",
            SuggestedCodec: "audio-24khz-48kbitrate-mono-mp3",
            FriendlyName: "Microsoft Andrew Multilingual Online (Natural) - English (United States)",
            Status: "GA"
        );

        var descriptor = EdgeTtsVoiceCatalog.MapToDescriptor(rawItem);

        Assert.Equal("en-US-AndrewMultilingualNeural", descriptor.VoiceId);
        Assert.Equal("Andrew (Multi)", descriptor.SpeakerName);
        Assert.Equal("Male", descriptor.StyleName);
        Assert.Equal("Andrew (Multi) (Male)", descriptor.Name);
    }

    [Fact]
    public async Task GetVoicesAsync_NetworkFailure_FallsBackToEmbeddedCatalog()
    {
        var failingHandler = new MockHttpMessageHandler(_ => throw new HttpRequestException("Simulated offline"));
        using var httpClient = new HttpClient(failingHandler);
        
        string nonExistentCache = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"), "cache.json");
        var catalog = new EdgeTtsVoiceCatalog(httpClient, nonExistentCache);

        var voices = await catalog.GetVoicesAsync();

        Assert.NotNull(voices);
        Assert.Equal(322, voices.Count);
        Assert.Contains(voices, v => v.VoiceId == "ja-JP-NanamiNeural");
    }

    [Fact]
    public async Task GetVoicesAsync_DiskCache_LoadsSuccessfully()
    {
        string tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDir);
        string diskCacheFile = Path.Combine(tempDir, "edge_voices_cache.json");

        try
        {
            string json = @"[
                {
                    ""Name"": ""Microsoft Server Speech Text to Speech Voice (ja-JP, NanamiNeural)"",
                    ""ShortName"": ""ja-JP-NanamiNeural"",
                    ""Gender"": ""Female"",
                    ""Locale"": ""ja-JP""
                }
            ]";
            await File.WriteAllTextAsync(diskCacheFile, json);

            var failingHandler = new MockHttpMessageHandler(_ => throw new HttpRequestException("Simulated offline"));
            using var httpClient = new HttpClient(failingHandler);

            var catalog = new EdgeTtsVoiceCatalog(httpClient, diskCacheFile);
            var voices = await catalog.GetVoicesAsync();

            Assert.Single(voices);
            Assert.Equal("ja-JP-NanamiNeural", voices[0].VoiceId);
            Assert.Equal("Nanami", voices[0].SpeakerName);
        }
        finally
        {
            if (Directory.Exists(tempDir))
            {
                Directory.Delete(tempDir, true);
            }
        }
    }

    private class MockHttpMessageHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, HttpResponseMessage> _handler;

        public MockHttpMessageHandler(Func<HttpRequestMessage, HttpResponseMessage> handler)
        {
            _handler = handler;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            return Task.FromResult(_handler(request));
        }
    }
}
