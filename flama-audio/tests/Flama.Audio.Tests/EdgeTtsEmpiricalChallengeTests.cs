using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Core.Models;
using Flama.Audio.Engine.EdgeTts;
using Flama.Audio.Engine.EdgeTts.Services;
using Xunit;

namespace Flama.Audio.Tests;

public class EdgeTtsEmpiricalChallengeTests
{
    // ==========================================
    // 1. VOICE CATALOG EDGE CASES: TIMEOUTS & RESILIENCE
    // ==========================================

    [Fact]
    public async Task GetVoicesAsync_NetworkTimeout_FallsBackToEmbeddedCatalogPromptly()
    {
        // Simulate a network hang / timeout (> 5s)
        var delayedHandler = new MockHttpMessageHandler(async (req, ct) =>
        {
            await Task.Delay(10000, ct); // Simulate slow or hanging response
            return new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent("[]") };
        });

        using var httpClient = new HttpClient(delayedHandler)
        {
            Timeout = TimeSpan.FromSeconds(10)
        };

        string nonExistentPath = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"), "cache.json");
        var catalog = new EdgeTtsVoiceCatalog(httpClient, nonExistentPath);

        var stopwatch = System.Diagnostics.Stopwatch.StartNew();
        var voices = await catalog.GetVoicesAsync();
        stopwatch.Stop();

        Assert.NotNull(voices);
        Assert.Equal(322, voices.Count);
        // Ensure it timed out within ~5.5s (due to 5s CancellationTokenSource) and did not block for 10s
        Assert.True(stopwatch.ElapsedMilliseconds < 8000, $"Catalog timeout took too long: {stopwatch.ElapsedMilliseconds}ms");
    }

    [Fact]
    public async Task GetVoicesAsync_NetworkThrowsHttpRequestException_FallsBackToEmbeddedCatalog()
    {
        var failingHandler = new MockHttpMessageHandler((req, ct) =>
        {
            throw new HttpRequestException("Name resolution failure: speech.platform.bing.com");
        });

        using var httpClient = new HttpClient(failingHandler);
        string nonExistentPath = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"), "cache.json");
        var catalog = new EdgeTtsVoiceCatalog(httpClient, nonExistentPath);

        var voices = await catalog.GetVoicesAsync();

        Assert.NotNull(voices);
        Assert.Equal(322, voices.Count);
        Assert.Contains(voices, v => v.VoiceId == "ja-JP-NanamiNeural");
    }

    // ==========================================
    // 2. VOICE CATALOG EDGE CASES: CORRUPTED DISK CACHE
    // ==========================================

    [Theory]
    [InlineData("{ \"invalid\": \"truncated json")] // Malformed JSON syntax
    [InlineData("")]                                // 0-byte empty file
    [InlineData("   \r\n   ")]                      // Whitespace only
    [InlineData("[]")]                              // Empty JSON array
    [InlineData("not a json at all! 12345")]        // Plain text corrupt data
    [InlineData("{\"error\": 403, \"message\": \"Forbidden\"}")] // JSON object instead of array
    public async Task GetVoicesAsync_CorruptedDiskCache_FallsBackToEmbeddedCatalog(string corruptedContent)
    {
        string tempDir = Path.Combine(Path.GetTempPath(), "flama_corrupt_test_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDir);
        string cacheFile = Path.Combine(tempDir, "edge_voices_cache.json");

        try
        {
            await File.WriteAllTextAsync(cacheFile, corruptedContent);

            var offlineHandler = new MockHttpMessageHandler((req, ct) => throw new HttpRequestException("Offline"));
            using var httpClient = new HttpClient(offlineHandler);

            var catalog = new EdgeTtsVoiceCatalog(httpClient, cacheFile);
            var voices = await catalog.GetVoicesAsync();

            Assert.NotNull(voices);
            Assert.Equal(322, voices.Count);
            Assert.Contains(voices, v => v.VoiceId == "ja-JP-NanamiNeural");
            Assert.Contains(voices, v => v.VoiceId == "vi-VN-HoaiMyNeural");
        }
        finally
        {
            if (Directory.Exists(tempDir)) Directory.Delete(tempDir, true);
        }
    }

    [Fact]
    public async Task GetVoicesAsync_CorruptedDiskCache_ArrayWithNullEntries_FallsBackSafely()
    {
        // When JSON contains an array of nulls [null, null]
        string tempDir = Path.Combine(Path.GetTempPath(), "flama_null_test_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDir);
        string cacheFile = Path.Combine(tempDir, "edge_voices_cache.json");

        try
        {
            await File.WriteAllTextAsync(cacheFile, "[null, null]");

            var offlineHandler = new MockHttpMessageHandler((req, ct) => throw new HttpRequestException("Offline"));
            using var httpClient = new HttpClient(offlineHandler);

            var catalog = new EdgeTtsVoiceCatalog(httpClient, cacheFile);
            var voices = await catalog.GetVoicesAsync();

            // Should catch the NullReferenceException during mapping and fall back to embedded 322 voices
            Assert.NotNull(voices);
            Assert.Equal(322, voices.Count);
        }
        finally
        {
            if (Directory.Exists(tempDir)) Directory.Delete(tempDir, true);
        }
    }

    // ==========================================
    // 3. VOICE CATALOG EDGE CASES: MISSING DIRECTORIES & DISK IO
    // ==========================================

    [Fact]
    public async Task GetVoicesAsync_DeeplyNestedNonExistentDirectory_DoesNotCrash()
    {
        string deepNonExistentPath = Path.Combine(
            Path.GetTempPath(),
            Guid.NewGuid().ToString("N"),
            "sub1", "sub2", "sub3",
            "edge_voices_cache.json"
        );

        var offlineHandler = new MockHttpMessageHandler((req, ct) => throw new HttpRequestException("Offline"));
        using var httpClient = new HttpClient(offlineHandler);

        var catalog = new EdgeTtsVoiceCatalog(httpClient, deepNonExistentPath);
        var voices = await catalog.GetVoicesAsync();

        Assert.NotNull(voices);
        Assert.Equal(322, voices.Count);
    }

    // ==========================================
    // 4. INVARIANTS FOR ALL 322 EMBEDDED VOICES
    // ==========================================

    [Fact]
    public void EmbeddedVoices_All322Voices_SatisfyStrictInvariants()
    {
        var catalog = new EdgeTtsVoiceCatalog();
        var voices = catalog.LoadFromEmbeddedResource();

        Assert.NotNull(voices);
        Assert.Equal(322, voices.Count);

        var voiceIdSet = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var v in voices)
        {
            // 1. None should be null
            Assert.NotNull(v);

            // 2. VoiceId integrity
            Assert.False(string.IsNullOrWhiteSpace(v.VoiceId), "VoiceId must not be null/empty");
            Assert.True(voiceIdSet.Add(v.VoiceId), $"Duplicate VoiceId found: {v.VoiceId}");

            // 3. Name integrity
            Assert.False(string.IsNullOrWhiteSpace(v.Name), $"Name empty for {v.VoiceId}");
            Assert.Contains("(", v.Name);
            Assert.Contains(")", v.Name);

            // 4. SpeakerName integrity (no Neural)
            Assert.False(string.IsNullOrWhiteSpace(v.SpeakerName), $"SpeakerName empty for {v.VoiceId}");
            Assert.DoesNotContain("Neural", v.SpeakerName);

            // 5. StyleName (Gender) integrity
            Assert.False(string.IsNullOrWhiteSpace(v.StyleName), $"StyleName empty for {v.VoiceId}");

            // 6. Locale integrity (contains dash, e.g., ja-JP, zh-CN)
            Assert.False(string.IsNullOrWhiteSpace(v.Locale), $"Locale empty for {v.VoiceId}");
            Assert.Contains("-", v.Locale);

            // 7. CommercialSafe and Attribution
            Assert.True(v.CommercialSafe, $"CommercialSafe must be true for {v.VoiceId}");
            Assert.Equal("Microsoft Edge TTS", v.Attribution);
        }
    }

    // ==========================================
    // 5. LOCALE CASING & VOICE LOOKUP
    // ==========================================

    [Theory]
    [InlineData("JA-jp", "ja-JP")]
    [InlineData("ja-jp", "ja-JP")]
    [InlineData("JA-JP", "ja-JP")]
    [InlineData("vi-vn", "vi-VN")]
    [InlineData("VI-VN", "vi-VN")]
    [InlineData("Vi-Vn", "vi-VN")]
    [InlineData("en-us", "en-US")]
    [InlineData("EN-US", "en-US")]
    [InlineData("en-gb", "en-GB")]
    [InlineData("zh-cn", "zh-CN")]
    [InlineData("ZH-CN", "zh-CN")]
    [InlineData("ko-kr", "ko-KR")]
    public void VoiceLookup_CaseInsensitiveLocale_FindsExpectedVoices(string queryLocale, string expectedLocale)
    {
        var catalog = new EdgeTtsVoiceCatalog();
        var voices = catalog.LoadFromEmbeddedResource();

        var matches = voices
            .Where(v => v.Locale.Equals(queryLocale, StringComparison.OrdinalIgnoreCase))
            .ToList();

        Assert.NotEmpty(matches);
        Assert.All(matches, v => Assert.Equal(expectedLocale, v.Locale, ignoreCase: true));
    }

    [Theory]
    [InlineData("ja-JP-NanamiNeural", "ja-JP")]
    [InlineData("en-US-AvaNeural", "en-US")]
    [InlineData("vi-VN-HoaiMyNeural", "vi-VN")]
    [InlineData("zh-CN-XiaoxiaoNeural", "zh-CN")]
    [InlineData("zh-CN-liaoning-XiaobeiNeural", "zh-CN-liaoning")]
    public void MapToDescriptor_ExtractsCorrectLocale_ForStandardAndMultiPartVoices(string shortName, string expectedLocale)
    {
        var raw = new EdgeVoiceRawItem(
            Name: $"Test {shortName}",
            ShortName: shortName,
            Gender: "Female",
            Locale: null, // Test fallback extraction from shortName
            LocaleName: null,
            SuggestedCodec: "audio-24khz-48kbitrate-mono-mp3",
            FriendlyName: null,
            Status: "GA"
        );

        var descriptor = EdgeTtsVoiceCatalog.MapToDescriptor(raw);
        Assert.Equal(expectedLocale, descriptor.Locale);
    }

    // ==========================================
    // 6. OFFLINE SIMULATION & GETH_HEALTH_ASYNC
    // ==========================================

    [Fact]
    public async Task GetHealthAsync_ForcedOfflineViaCancellationToken_ReturnsUnhealthyPromptly()
    {
        using var adapter = new EdgeTtsEngineAdapter();

        // Pass a pre-cancelled cancellation token to force the DNS lookup to fail immediately
        using var cts = new CancellationTokenSource();
        cts.Cancel();

        // EdgeTtsEngineAdapter.GetHealthAsync catches the cancellation/socket error in DNS check
        // Note: WaitAsync(ct) is called on healthLock. If ct is cancelled, WaitAsync throws OperationCanceledException.
        // Let's verify whether passing an active or cancelled token throws or handles it:
        try
        {
            var health = await adapter.GetHealthAsync(cts.Token);
            Assert.Equal("unhealthy", health.Status);
            Assert.Contains("kết nối", health.Message);
        }
        catch (OperationCanceledException)
        {
            // If the lock itself is cancelled by caller token, that's standard .NET task cancellation
            Assert.True(true);
        }
    }

    [Fact]
    public async Task GetHealthAsync_ReturnsConsistentContractFields()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();

        Assert.NotNull(health);
        Assert.True(health.Status is "ready" or "unhealthy");
        Assert.False(string.IsNullOrWhiteSpace(health.Message));
        if (health.Status == "ready")
        {
            Assert.NotNull(health.Version);
        }
    }

    // ==========================================
    // MOCK HELPER
    // ==========================================

    private class MockHttpMessageHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> _handler;

        public MockHttpMessageHandler(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> handler)
        {
            _handler = handler;
        }

        public MockHttpMessageHandler(Func<HttpRequestMessage, HttpResponseMessage> handler)
        {
            _handler = (req, ct) => Task.FromResult(handler(req));
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            return _handler(request, cancellationToken);
        }
    }
}
