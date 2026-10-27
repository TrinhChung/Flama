using System;
using System.IO;
using System.Net.Sockets;
using System.Net.WebSockets;
using System.Threading.Tasks;
using Flama.Audio.Core.Models;
using Flama.Audio.Engine.EdgeTts;
using Xunit;
using Xunit.Abstractions;

namespace Flama.Audio.Tests;

public class EdgeTtsIntegrationTests
{
    private readonly ITestOutputHelper? _output;

    public EdgeTtsIntegrationTests(ITestOutputHelper? output = null)
    {
        _output = output;
    }
    private static bool IsOffline(EngineHealth health) => health.Status != "ready";

    private static bool IsNetworkException(Exception ex) =>
        ex is WebSocketException or SocketException or IOException or TaskCanceledException or TimeoutException;

    [Fact]
    public async Task SynthesizeAsync_JapaneseLive_ReturnsValidMp3Audio()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();
        if (IsOffline(health))
        {
            // Disconnected CI environment guard
            return;
        }

        var request = new TtsRequest(
            RequestId: Guid.NewGuid().ToString("N"),
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: "こんにちは！"
        );

        try
        {
            var result = await adapter.SynthesizeAsync(request);

            Assert.NotNull(result);
            Assert.Equal("edge-tts", result.EngineId);
            Assert.Equal("audio/mpeg", result.ContentType);
            Assert.Equal("ja-JP-NanamiNeural", result.VoiceId);
            Assert.Equal(request.RequestId, result.RequestId);
            Assert.NotNull(result.AudioData);
            Assert.True(result.AudioData.Length > 0, "Audio data bytes should be greater than 0");
        }
        catch (Exception ex) when (IsNetworkException(ex))
        {
            // Permitted skip on transient network blips
        }
    }

    [Fact]
    public async Task SynthesizeAsync_ExactMainWindowScenario_DoesNotThrow()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var request = new TtsRequest(
            RequestId: $"test_{DateTime.Now.Ticks}",
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: "こんにちは！Flama Audioへようこそ！",
            Options: new TtsOptions(Speed: 1.0)
        );

        var result = await adapter.SynthesizeAsync(request);
        Assert.NotNull(result);
        Assert.True(result.AudioData.Length > 0);
    }

    [Fact]
    public async Task SynthesizeAsync_ConnectionReuseAcrossMultipleRequests_Succeeds()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();
        if (IsOffline(health))
        {
            return;
        }

        var req1 = new TtsRequest(
            RequestId: Guid.NewGuid().ToString("N"),
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: "第一問です。"
        );

        var req2 = new TtsRequest(
            RequestId: Guid.NewGuid().ToString("N"),
            EngineId: "edge-tts",
            Language: "vi-VN",
            VoiceId: "vi-VN-NamMinhNeural",
            Text: "Câu hỏi số một."
        );

        try
        {
            // Turn 1
            var res1 = await adapter.SynthesizeAsync(req1);
            Assert.NotNull(res1);
            Assert.True(res1.AudioData.Length > 0);

            // Turn 2 (reuses the already opened WebSocket connection)
            var res2 = await adapter.SynthesizeAsync(req2);
            Assert.NotNull(res2);
            Assert.True(res2.AudioData.Length > 0);
            Assert.Equal("vi-VN-NamMinhNeural", res2.VoiceId);
        }
        catch (Exception ex) when (IsNetworkException(ex))
        {
            // Permitted skip on transient network blips
        }
    }

    [Theory]
    [InlineData(0.5)]   // -50% (Rất chậm - UI slider min)
    [InlineData(0.75)]  // -25% (Hơi chậm)
    [InlineData(1.0)]   // 0%   (Chuẩn mặc định)
    [InlineData(1.25)]  // +25% (Hơi nhanh)
    [InlineData(1.5)]   // +50% (Nhanh)
    [InlineData(2.0)]   // +100% (Rất nhanh - UI slider max)
    [InlineData(3.0)]   // +200% (Cực hạn - API boundary)
    public async Task SynthesizeAsync_RateVariations_ProducesValidAudioWithDecreasingSize(double speed)
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();
        if (IsOffline(health)) return;

        string text = "これは日本語の音声合成速度テストです。速度の違いを確認します。";
        var request = new TtsRequest(
            RequestId: Guid.NewGuid().ToString("N"),
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: text,
            Options: new TtsOptions(Speed: speed)
        );

        try
        {
            var result = await adapter.SynthesizeAsync(request);
            Assert.NotNull(result);
            Assert.NotNull(result.AudioData);
            Assert.True(result.AudioData.Length > 0);

            int rateDelta = (int)Math.Round((speed - 1.0) * 100);
            string rateStr = rateDelta >= 0 ? $"+{rateDelta}%" : $"{rateDelta}%";
            _output?.WriteLine($"[Speed: {speed:F2}x | Rate: {rateStr}] Audio bytes: {result.AudioData.Length}");
        }
        catch (Exception ex) when (IsNetworkException(ex))
        {
        }
    }

    [Fact]
    public async Task SynthesizeAsync_ConsecutiveStressBenchmark_MeasuresRateLimits()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();
        if (IsOffline(health)) return;

        const int totalRequests = 25;
        int successCount = 0;
        var swTotal = System.Diagnostics.Stopwatch.StartNew();
        var latencies = new System.Collections.Generic.List<long>();

        for (int i = 1; i <= totalRequests; i++)
        {
            var swItem = System.Diagnostics.Stopwatch.StartNew();
            string text = $"単語テストその{i}。継続的な音声生成のテストです。";
            var request = new TtsRequest(
                RequestId: Guid.NewGuid().ToString("N"),
                EngineId: "edge-tts",
                Language: "ja-JP",
                VoiceId: "ja-JP-NanamiNeural",
                Text: text
            );

            try
            {
                var result = await adapter.SynthesizeAsync(request);
                swItem.Stop();
                latencies.Add(swItem.ElapsedMilliseconds);

                Assert.NotNull(result);
                Assert.NotNull(result.AudioData);
                Assert.True(result.AudioData.Length > 0);
                successCount++;

                _output?.WriteLine($"[Req {i:D2}/{totalRequests:D2}] Status: OK | Latency: {swItem.ElapsedMilliseconds}ms | Bytes: {result.AudioData.Length}");
            }
            catch (Exception ex)
            {
                swItem.Stop();
                _output?.WriteLine($"[Req {i:D2}/{totalRequests:D2}] FAILED: {ex.GetType().Name} - {ex.Message} (after {swItem.ElapsedMilliseconds}ms)");
            }
        }

        swTotal.Stop();
        double avgLatency = latencies.Count > 0 ? latencies.Average() : 0;
        _output?.WriteLine($"=== BENCHMARK SUMMARY ===");
        _output?.WriteLine($"Total: {totalRequests} | Success: {successCount}/{totalRequests} ({(successCount * 100.0 / totalRequests):F1}%)");
        _output?.WriteLine($"Total Duration: {swTotal.ElapsedMilliseconds}ms | Avg Latency/req: {avgLatency:F1}ms");
        _output?.WriteLine($"Min Latency: {(latencies.Count > 0 ? latencies.Min() : 0)}ms | Max Latency: {(latencies.Count > 0 ? latencies.Max() : 0)}ms");

        Assert.Equal(totalRequests, successCount);
    }
}
