using System.Net.Http;
using System.Threading.Tasks;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Core.Models;
using Flama.Audio.Engine.Voicevox;
using Flama.Audio.Engine.Kokoro;
using Flama.Audio.Infrastructure.Services;
using Xunit;

namespace Flama.Audio.Tests;

public class FlamaAudioTests
{
    [Fact]
    public async Task PairingManager_Flow_Succeeds()
    {
        var pairingManager = new PairingManager();
        var origin = "http://localhost:5173";

        var challenge = await pairingManager.StartPairingAsync(origin, "Test Client");
        Assert.NotNull(challenge);
        Assert.False(challenge.Approved);

        var approved = await pairingManager.ApprovePairingAsync(challenge.PairingId);
        Assert.True(approved);

        var updated = pairingManager.GetChallenge(challenge.PairingId);
        Assert.NotNull(updated);
        Assert.True(updated.Approved);
        Assert.NotNull(updated.Token);

        var isValid = pairingManager.ValidateToken(origin, updated.Token);
        Assert.True(isValid);
    }

    [Fact]
    public void EngineRouter_Returns_VoicevoxAdapter()
    {
        using var httpClient = new HttpClient();
        var voicevox = new VoicevoxEngineAdapter(httpClient);
        var kokoro = new KokoroEngineAdapter();
        var router = new EngineRouter(new ITtsEngineAdapter[] { voicevox, kokoro });

        var adapter = router.GetAdapter("voicevox");
        Assert.NotNull(adapter);
        Assert.Equal("voicevox", adapter.EngineId);
    }

    [Fact]
    public void EngineRouter_Returns_KokoroAdapter()
    {
        using var httpClient = new HttpClient();
        var voicevox = new VoicevoxEngineAdapter(httpClient);
        var kokoro = new KokoroEngineAdapter();
        var router = new EngineRouter(new ITtsEngineAdapter[] { voicevox, kokoro });

        var adapter = router.GetAdapter("kokoro");
        Assert.NotNull(adapter);
        Assert.Equal("kokoro", adapter.EngineId);
    }

    [Fact]
    public async Task KokoroAdapter_ListVoices_ReturnsEnglishVoices()
    {
        var kokoro = new KokoroEngineAdapter();
        var voices = await kokoro.ListVoicesAsync();

        Assert.NotEmpty(voices);
        Assert.Contains(voices, v => v.VoiceId == "af_bella" && v.Locale == "en-US");
        Assert.Contains(voices, v => v.VoiceId == "bf_emma" && v.Locale == "en-GB");
    }

    [Fact]
    public async Task KokoroAdapter_Synthesize_ExecutesOrThrowsIfMissing()
    {
        var kokoro = new KokoroEngineAdapter();
        var health = await kokoro.GetHealthAsync();
        var request = new TtsRequest(
            RequestId: "req-123",
            EngineId: "kokoro",
            Language: "en-US",
            VoiceId: "af_bella",
            Text: "Hello, welcome to Flama Audio English Local TTS!"
        );

        if (health.Status == "ready")
        {
            var result = await kokoro.SynthesizeAsync(request);
            Assert.NotNull(result);
            Assert.Equal("audio/wav", result.ContentType);
            Assert.Equal("kokoro", result.EngineId);
            Assert.NotNull(result.AudioData);
            Assert.True(result.AudioData.Length > 44);
        }
        else
        {
            await Assert.ThrowsAsync<FileNotFoundException>(() => kokoro.SynthesizeAsync(request));
        }
    }

    [Fact]
    public async Task VoicevoxAdapter_ListVoices_ReturnsFallbackWhenOffline()
    {
        using var httpClient = new HttpClient();
        var voicevox = new VoicevoxEngineAdapter(httpClient, "http://127.0.0.1:59999");
        var voices = await voicevox.ListVoicesAsync();

        Assert.NotEmpty(voices);
        Assert.Contains(voices, v => v.SpeakerName == "Zundamon");
    }
}

