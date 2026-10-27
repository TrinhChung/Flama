using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Core.Models;
using Flama.Audio.Engine.EdgeTts;
using Flama.Audio.Engine.EdgeTts.Network;
using Flama.Audio.Engine.EdgeTts.Services;
using Flama.Audio.Infrastructure.Services;
using Xunit;

namespace Flama.Audio.Tests;

public class EdgeTtsEngineAdapterTests
{
    [Fact]
    public void EngineId_IsEdgeTts()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        Assert.Equal("edge-tts", adapter.EngineId);
    }

    [Fact]
    public async Task GetHealthAsync_ReturnsValidHealthStatus()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();

        Assert.NotNull(health);
        Assert.True(health.Status == "ready" || health.Status == "unhealthy");
        Assert.False(string.IsNullOrWhiteSpace(health.Message));
    }

    [Fact]
    public async Task ListVoicesAsync_Returns322Voices()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var voices = await adapter.ListVoicesAsync();

        Assert.NotNull(voices);
        Assert.Equal(322, voices.Count);
    }

    [Fact]
    public async Task StartAsync_And_StopAsync_ExecuteWithoutError()
    {
        var mockWs = new MockEdgeWebSocketClient();
        using var adapter = new EdgeTtsEngineAdapter(mockWs);

        await adapter.StartAsync();
        Assert.True(true);

        await adapter.StopAsync();
        Assert.True(mockWs.CloseCalled);
    }

    [Fact]
    public void EngineRouter_DiscoversAndReturns_EdgeTtsAdapter()
    {
        var mockWs = new MockEdgeWebSocketClient();
        using var edgeAdapter = new EdgeTtsEngineAdapter(mockWs);
        var router = new EngineRouter(new ITtsEngineAdapter[] { edgeAdapter });

        var adapter = router.GetAdapter("edge-tts");
        Assert.NotNull(adapter);
        Assert.Equal("edge-tts", adapter.EngineId);

        var all = router.GetAllAdapters();
        Assert.Contains(all, a => a.EngineId == "edge-tts");
    }

    [Fact]
    public async Task SynthesizeAsync_EmptyText_ThrowsArgumentException()
    {
        var mockWs = new MockEdgeWebSocketClient();
        using var adapter = new EdgeTtsEngineAdapter(mockWs);

        var emptyReq = new TtsRequest(
            RequestId: "req-1",
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: ""
        );

        await Assert.ThrowsAsync<ArgumentException>(() => adapter.SynthesizeAsync(emptyReq));

        var whitespaceReq = emptyReq with { Text = "   " };
        await Assert.ThrowsAsync<ArgumentException>(() => adapter.SynthesizeAsync(whitespaceReq));
    }

    [Fact]
    public async Task SynthesizeAsync_FormatsSsmlProsody_Correctly()
    {
        var mockWs = new MockEdgeWebSocketClient();
        using var adapter = new EdgeTtsEngineAdapter(mockWs);

        var options = new TtsOptions(
            Speed: 1.25,  // +25%
            Pitch: 15.0,  // +15Hz
            Volume: 0.8   // -20%
        );

        var request = new TtsRequest(
            RequestId: "test-req-001",
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: "こんにちは",
            Options: options
        );

        var result = await adapter.SynthesizeAsync(request);

        Assert.NotNull(result);
        Assert.Equal("test-req-001", result.RequestId);
        Assert.Equal("audio/mpeg", result.ContentType);
        Assert.Equal("edge-tts", result.EngineId);
        Assert.Equal("ja-JP-NanamiNeural", result.VoiceId);

        string sentSsml = mockWs.LastSentSsml!;
        Assert.NotNull(sentSsml);
        Assert.Contains("rate='+25%'", sentSsml);
        Assert.Contains("pitch='+15Hz'", sentSsml);
        Assert.Contains("volume='-20%'", sentSsml);
        Assert.Contains("voice name='ja-JP-NanamiNeural'", sentSsml);
        Assert.Contains("xml:lang='ja-JP'", sentSsml);
        Assert.Contains("こんにちは", sentSsml);
    }

    [Fact]
    public async Task SynthesizeAsync_EscapesXmlSpecialCharacters()
    {
        var mockWs = new MockEdgeWebSocketClient();
        using var adapter = new EdgeTtsEngineAdapter(mockWs);

        var request = new TtsRequest(
            RequestId: "test-escape",
            EngineId: "edge-tts",
            Language: "en-US",
            VoiceId: "en-US-AvaNeural",
            Text: "Tom & Jerry <friends> \"great\" 'show'"
        );

        await adapter.SynthesizeAsync(request);

        string sentSsml = mockWs.LastSentSsml!;
        Assert.NotNull(sentSsml);
        Assert.Contains("Tom &amp; Jerry &lt;friends&gt; &quot;great&quot; &apos;show&apos;", sentSsml);
        Assert.DoesNotContain("<friends>", sentSsml);
    }

    [Theory]
    [InlineData("ja", "ja-JP-NanamiNeural")]
    [InlineData("vi", "vi-VN-HoaiMyNeural")]
    [InlineData("en", "en-US-AvaNeural")]
    [InlineData("zh", "zh-CN-XiaoxiaoNeural")]
    [InlineData("ko", "ko-KR-SunHiNeural")]
    public async Task SynthesizeAsync_ResolvesDefaultVoice_WhenVoiceIdEmpty(string language, string expectedVoice)
    {
        var mockWs = new MockEdgeWebSocketClient();
        using var adapter = new EdgeTtsEngineAdapter(mockWs);

        var request = new TtsRequest(
            RequestId: "test-default-voice",
            EngineId: "edge-tts",
            Language: language,
            VoiceId: "",
            Text: "Testing default voice"
        );

        var result = await adapter.SynthesizeAsync(request);

        Assert.Equal(expectedVoice, result.VoiceId);
        Assert.Contains($"voice name='{expectedVoice}'", mockWs.LastSentSsml);
    }

    [Fact]
    public async Task RateLimiter_ConsecutiveRequests_EnforcesMinimumDelay()
    {
        var mockWs = new MockEdgeWebSocketClient();
        // Use a 100ms pacing delay for test speed
        using var adapter = new EdgeTtsEngineAdapter(mockWs, minDelayMs: 100, maxRequestsPerMinute: 50);

        var req1 = new TtsRequest(
            RequestId: "req-1",
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: "テスト1"
        );
        var req2 = new TtsRequest(
            RequestId: "req-2",
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: "テスト2"
        );

        var sw = System.Diagnostics.Stopwatch.StartNew();
        await adapter.SynthesizeAsync(req1);
        await adapter.SynthesizeAsync(req2);
        sw.Stop();

        // Second request must have been paced by at least ~80ms (accounting for timer granularity)
        Assert.True(sw.ElapsedMilliseconds >= 80, $"Elapsed was {sw.ElapsedMilliseconds}ms, expected >= 80ms");
    }

    [Fact]
    public async Task RateLimiter_SlidingWindowExceeded_ThrowsInvalidOperationException()
    {
        var mockWs = new MockEdgeWebSocketClient();
        // Configure max 2 requests per minute with 0ms pacing
        using var adapter = new EdgeTtsEngineAdapter(mockWs, minDelayMs: 0, maxRequestsPerMinute: 2);

        var req = new TtsRequest(
            RequestId: "req-limit",
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: "テスト"
        );

        // Req 1 and 2 succeed
        await adapter.SynthesizeAsync(req);
        await adapter.SynthesizeAsync(req);

        // Req 3 would have to wait 60 seconds (which exceeds MaxThrottleWaitMs = 15s), so it throws
        var ex = await Assert.ThrowsAsync<InvalidOperationException>(() => adapter.SynthesizeAsync(req));
        Assert.Contains("rate limit exceeded", ex.Message, StringComparison.OrdinalIgnoreCase);
    }

    private class MockEdgeWebSocketClient : IEdgeWebSocketClient
    {
        public bool IsConnected { get; set; } = false;
        public bool CloseCalled { get; set; }
        public string? LastSentSsml { get; private set; }
        public string? LastRequestId { get; private set; }
        public string? OutputFormat { get; private set; }

        public Task ConnectAsync(Uri uri, IDictionary<string, string> headers, CancellationToken ct)
        {
            IsConnected = true;
            return Task.CompletedTask;
        }

        public Task SendConfigAsync(string outputFormat, CancellationToken ct)
        {
            OutputFormat = outputFormat;
            return Task.CompletedTask;
        }

        public Task<byte[]> SynthesizeSsmlAsync(string requestId, string ssml, CancellationToken ct)
        {
            LastRequestId = requestId;
            LastSentSsml = ssml;
            return Task.FromResult(new byte[] { 0xFF, 0xFB, 0x90, 0x64 });
        }

        public Task CloseAsync(CancellationToken ct)
        {
            CloseCalled = true;
            IsConnected = false;
            return Task.CompletedTask;
        }

        public void Dispose()
        {
            IsConnected = false;
        }
    }
}
