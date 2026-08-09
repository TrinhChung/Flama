using System.Net.Http;
using System.Threading.Tasks;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Engine.Voicevox;
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
        var router = new EngineRouter(new ITtsEngineAdapter[] { voicevox });

        var adapter = router.GetAdapter("voicevox");
        Assert.NotNull(adapter);
        Assert.Equal("voicevox", adapter.EngineId);
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
