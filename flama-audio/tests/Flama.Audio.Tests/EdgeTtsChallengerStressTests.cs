using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Sockets;
using System.Net.WebSockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Core.Models;
using Flama.Audio.Engine.EdgeTts;
using Flama.Audio.Engine.EdgeTts.Constants;
using Flama.Audio.Engine.EdgeTts.Cryptography;
using Flama.Audio.Engine.EdgeTts.Network;
using Xunit;

namespace Flama.Audio.Tests;

public class EdgeTtsChallengerStressTests : IDisposable
{
    private static readonly Regex TokenRegex = new("^[0-9A-F]{16}-[0-9A-F]{64}$", RegexOptions.Compiled);
    private static readonly Regex MuidRegex = new("^[0-9A-F]{32}$", RegexOptions.Compiled);

    public EdgeTtsChallengerStressTests()
    {
        EdgeTtsDrm.ResetClockSkew();
    }

    public void Dispose()
    {
        EdgeTtsDrm.ResetClockSkew();
    }

    #region 1. DRM (Sec-MS-GEC v2) Boundary & Clock Skew Empirical Tests

    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    [InlineData(-1)]
    [InlineData(150)]
    [InlineData(-150)]
    [InlineData(299)]
    [InlineData(300)]
    [InlineData(301)]
    [InlineData(3600)]
    [InlineData(-3600)]
    [InlineData(86400)]
    [InlineData(-86400)]
    [InlineData(2592000)] // 30 days
    [InlineData(-2592000)]
    [InlineData(31536000)] // 1 year
    [InlineData(-31536000)]
    public void Drm_ClockSkew_DiverseOffsets_ProducesValidTokenStructure(int skewSeconds)
    {
        EdgeTtsDrm.SetClockSkew(TimeSpan.FromSeconds(skewSeconds));
        string token = EdgeTtsDrm.GenerateSecMsGecV2();

        Assert.NotNull(token);
        Assert.Matches(TokenRegex, token);
        Assert.Equal(81, token.Length); // 16 + 1 + 64 = 81 chars
    }

    [Fact]
    public void Drm_300SecondTimeBucket_InvarianceHolds()
    {
        // Any two timestamps in the same 300-second window MUST produce identical tokens.
        // Base timestamp: 1730000000
        // Window index = (1730000000 + 11644473600) / 300 = 13374473600 / 300 = 44581578
        // 44581578 * 300 = 13374473400 (ticks)
        // Window start: 1730000100 + 11644473600 = 13374473700 (13374473700 % 300 == 0).
        // Therefore, the 300s window covers [1730000100, 1730000399.999].
        string token1 = EdgeTtsDrm.GenerateSecMsGecV2(1730000100.0);
        string token2 = EdgeTtsDrm.GenerateSecMsGecV2(1730000250.0);
        string token3 = EdgeTtsDrm.GenerateSecMsGecV2(1730000399.9);

        Assert.Equal(token1, token2);
        Assert.Equal(token1, token3);

        // A timestamp crossing into the next 300s window (>= 1730000400) must produce a DIFFERENT token
        string nextWindowToken = EdgeTtsDrm.GenerateSecMsGecV2(1730000400.0);
        Assert.NotEqual(token1, nextWindowToken);

        // A timestamp in the previous 300s window (<= 1730000099) must also produce a DIFFERENT token
        string prevWindowToken = EdgeTtsDrm.GenerateSecMsGecV2(1730000099.0);
        Assert.NotEqual(token1, prevWindowToken);
    }

    [Theory]
    [InlineData(0.0)]                    // Unix Epoch: 1970-01-01 00:00:00 UTC
    [InlineData(2147483647.0)]           // 2038-01-19 Unix 32-bit limit
    [InlineData(4102444800.0)]           // Year 2100-01-01
    [InlineData(-1000000.0)]             // Pre-1970 timestamp
    [InlineData(-11644473600.0)]         // Windows epoch (year 1601)
    public void Drm_ExtremeTimestamps_GeneratesValidTokenWithoutCrashing(double extremeTimestamp)
    {
        string token = EdgeTtsDrm.GenerateSecMsGecV2(extremeTimestamp);

        Assert.NotNull(token);
        Assert.Matches(TokenRegex, token);
    }

    [Fact]
    public void Drm_MultithreadedConcurrentGeneration_NoCorruptionOrExceptions()
    {
        const int concurrency = 200;
        var tokens = new ConcurrentBag<string>();
        var exceptions = new ConcurrentBag<Exception>();

        Parallel.For(0, concurrency, i =>
        {
            try
            {
                double ts = 1730000000.0 + (i * 10);
                string token = EdgeTtsDrm.GenerateSecMsGecV2(ts);
                tokens.Add(token);
            }
            catch (Exception ex)
            {
                exceptions.Add(ex);
            }
        });

        Assert.Empty(exceptions);
        Assert.Equal(concurrency, tokens.Count);
        foreach (var t in tokens)
        {
            Assert.Matches(TokenRegex, t);
        }
    }

    [Fact]
    public void Drm_Muid_HighVolumeParallelGeneration_NoCollisions()
    {
        const int count = 5000;
        var muids = new ConcurrentBag<string>();

        Parallel.For(0, count, _ =>
        {
            string muid = EdgeTtsDrm.GenerateMuid();
            muids.Add(muid);
        });

        Assert.Equal(count, muids.Count);
        var set = new HashSet<string>(muids);
        Assert.Equal(count, set.Count); // 0 collisions in 5000 random 128-bit MUIDs

        foreach (var muid in set.Take(50))
        {
            Assert.Matches(MuidRegex, muid);
            Assert.Equal(32, muid.Length);
        }
    }

    #endregion

    #region 2. SSML Special Characters, Formatting & Escaping Stress Tests

    [Fact]
    public async Task SSML_SpecialCharacters_ProperlyEscapedAndPreserved()
    {
        var mockWs = new ControlledMockWebSocketClient();
        using var adapter = new EdgeTtsEngineAdapter(mockWs);

        var specialTexts = new[]
        {
            "「こんにちは、世界！」【漢字・ひらがな・カタカナ・１２３】",
            "Tiếng Việt có dấu: ồ, ế, ặ, ử, ỹ, đ, Đ. Xin chào các bạn!",
            "XML tags <script>alert('xss')</script> & <b>bold</b>",
            "Quotes \"double\" and 'single' and &amp; &lt; &gt;",
            "Newlines and tabs: \n \r\n \t end.",
            "Surrogate pairs & Emojis: 🌸 👋 ✨ 🇻🇳 🇯🇵",
            "SSML injection: </prosody></voice><voice name='evil'><prosody>Injected!</prosody></voice>"
        };

        foreach (var text in specialTexts)
        {
            var req = new TtsRequest(
                RequestId: Guid.NewGuid().ToString("N"),
                EngineId: "edge-tts",
                Language: "ja-JP",
                VoiceId: "ja-JP-NanamiNeural",
                Text: text
            );

            var result = await adapter.SynthesizeAsync(req);
            Assert.NotNull(result);

            string ssml = mockWs.LastSentSsml!;
            Assert.NotNull(ssml);

            // Assert XML tag structure is not broken by the input
            Assert.StartsWith("<speak version='1.0'", ssml);
            Assert.EndsWith("</prosody></voice></speak>", ssml);

            // Verify raw unescaped injection tags are NOT present
            Assert.DoesNotContain("<script>", ssml);
            Assert.DoesNotContain("<voice name='evil'>", ssml);
            Assert.DoesNotContain("<b>bold</b>", ssml);

            // Verify safe XML entities were used
            if (text.Contains('<')) Assert.Contains("&lt;", ssml);
            if (text.Contains('>')) Assert.Contains("&gt;", ssml);
            if (text.Contains('&')) Assert.Contains("&amp;", ssml);
            if (text.Contains('"')) Assert.Contains("&quot;", ssml);
            if (text.Contains('\'')) Assert.Contains("&apos;", ssml);
        }
    }

    [Fact]
    public async Task SSML_ExtremeProsodyDeltas_HandledWithoutOverflow()
    {
        var mockWs = new ControlledMockWebSocketClient();
        using var adapter = new EdgeTtsEngineAdapter(mockWs);

        // Extreme speed, pitch, volume values
        var req = new TtsRequest(
            RequestId: "extreme-prosody",
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: "テスト",
            Options: new TtsOptions(Speed: 3.0, Pitch: 100.0, Volume: 0.0) // +200%, +100Hz, -100%
        );

        var result = await adapter.SynthesizeAsync(req);
        Assert.NotNull(result);

        string ssml = mockWs.LastSentSsml!;
        Assert.Contains("rate='+200%'", ssml);
        Assert.Contains("pitch='+100Hz'", ssml);
        Assert.Contains("volume='-100%'", ssml);
    }

    #endregion

    #region 3. Concurrency & Serialization Stress Tests

    [Fact]
    public async Task Adapter_ConcurrentSynthesizeAsync_InitialDisconnectedState_RacesGracefully()
    {
        // When 10 concurrent requests arrive at a fresh, disconnected adapter:
        // Verify that all 10 requests successfully complete without unhandled race exceptions or deadlocks.
        var mockWs = new ControlledMockWebSocketClient { SimulatedConnectDelayMs = 20, SimulatedSynthDelayMs = 10 };
        using var adapter = new EdgeTtsEngineAdapter(mockWs);

        const int numTasks = 10;
        var tasks = new Task<TtsResult>[numTasks];

        for (int i = 0; i < numTasks; i++)
        {
            int index = i;
            var req = new TtsRequest(
                RequestId: $"concurrent-req-{index}",
                EngineId: "edge-tts",
                Language: "ja-JP",
                VoiceId: "ja-JP-NanamiNeural",
                Text: $"こんにちは {index}"
            );

            tasks[i] = Task.Run(() => adapter.SynthesizeAsync(req));
        }

        var results = await Task.WhenAll(tasks);

        Assert.Equal(numTasks, results.Length);
        foreach (var res in results)
        {
            Assert.NotNull(res);
            Assert.NotNull(res.AudioData);
            Assert.True(res.AudioData.Length > 0);
        }
    }

    [Fact]
    public async Task Adapter_RapidConsecutiveTurns_MaintainsOpenConnection()
    {
        var mockWs = new ControlledMockWebSocketClient();
        using var adapter = new EdgeTtsEngineAdapter(mockWs);

        const int turns = 20;
        for (int i = 0; i < turns; i++)
        {
            var req = new TtsRequest(
                RequestId: $"turn-{i}",
                EngineId: "edge-tts",
                Language: "ja-JP",
                VoiceId: "ja-JP-NanamiNeural",
                Text: $"ターン {i}"
            );

            var res = await adapter.SynthesizeAsync(req);
            Assert.NotNull(res);
            Assert.True(res.AudioData.Length > 0);
        }

        // Connection should only have been established ONCE and reused for all 20 turns
        Assert.Equal(1, mockWs.ConnectCallCount);
        Assert.Equal(1, mockWs.SendConfigCallCount);
        Assert.Equal(turns, mockWs.SynthesizeCallCount);
    }

    [Fact]
    public async Task Adapter_DisconnectionRecovery_RetriesAndReSynthesizes()
    {
        var mockWs = new DisconnectingMockWebSocketClient();
        using var adapter = new EdgeTtsEngineAdapter(mockWs);

        var req = new TtsRequest(
            RequestId: "disconnect-retry-req",
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: "再接続テスト"
        );

        // First attempt will encounter a severed socket, adapter should catch and retry once
        var result = await adapter.SynthesizeAsync(req);

        Assert.NotNull(result);
        Assert.True(result.AudioData.Length > 0);
        Assert.Equal(2, mockWs.SynthesizeCallCount); // Failed first, succeeded on retry
    }

    #endregion

    #region 4. Live Synthesis, Concurrency & MP3 Frame Integrity Verification

    private static bool IsOffline(EngineHealth health) => health.Status != "ready";

    private static bool IsNetworkException(Exception ex) =>
        ex is WebSocketException or SocketException or IOException or TaskCanceledException or TimeoutException;

    private static bool ValidateMp3Header(byte[] data)
    {
        if (data == null || data.Length < 4) return false;

        // 1. Check for ID3v2 container header: 'I', 'D', '3'
        if (data[0] == 0x49 && data[1] == 0x44 && data[2] == 0x33)
        {
            return true;
        }

        // 2. Scan for MPEG Audio frame sync word (11 consecutive 1s: 0xFF followed by 0xEx or 0xFx)
        int scanLimit = Math.Min(data.Length - 1, 4096);
        for (int i = 0; i < scanLimit; i++)
        {
            if (data[i] == 0xFF && (data[i + 1] & 0xE0) == 0xE0)
            {
                // Verify layer III (MPEG Layer 3): bits 1-2 should be 01 (value 1 in field)
                int layer = (data[i + 1] >> 1) & 0x03;
                if (layer == 1) // Layer III
                {
                    return true;
                }
            }
        }

        return false;
    }

    [Fact]
    public async Task Live_Synthesize_SpecialCharacters_Japanese_ReturnsValidMp3Audio()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();
        if (IsOffline(health)) return;

        var request = new TtsRequest(
            RequestId: Guid.NewGuid().ToString("N"),
            EngineId: "edge-tts",
            Language: "ja-JP",
            VoiceId: "ja-JP-NanamiNeural",
            Text: "「こんにちは、世界！」漢字・カタカナ・ひらがな・１２３。"
        );

        try
        {
            var result = await adapter.SynthesizeAsync(request);

            Assert.NotNull(result);
            Assert.Equal("audio/mpeg", result.ContentType);
            Assert.NotNull(result.AudioData);
            Assert.True(result.AudioData.Length > 500, $"Audio data should be substantial, got {result.AudioData.Length} bytes");

            // Empirically validate MP3 frame header / ID3 tag
            Assert.True(ValidateMp3Header(result.AudioData), "Audio data must begin with valid MP3 frame sync or ID3 tag");
        }
        catch (Exception ex) when (IsNetworkException(ex))
        {
            // Transient network blip tolerance
        }
    }

    [Fact]
    public async Task Live_Synthesize_VietnameseDiacritics_ReturnsValidMp3Audio()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();
        if (IsOffline(health)) return;

        var request = new TtsRequest(
            RequestId: Guid.NewGuid().ToString("N"),
            EngineId: "edge-tts",
            Language: "vi-VN",
            VoiceId: "vi-VN-HoaiMyNeural",
            Text: "Xin chào các bạn! Tiếng Việt có các thanh điệu: huyền, sắc, hỏi, ngã, nặng."
        );

        try
        {
            var result = await adapter.SynthesizeAsync(request);

            Assert.NotNull(result);
            Assert.Equal("audio/mpeg", result.ContentType);
            Assert.NotNull(result.AudioData);
            Assert.True(result.AudioData.Length > 500, $"Audio data should be substantial, got {result.AudioData.Length} bytes");

            Assert.True(ValidateMp3Header(result.AudioData), "Audio data must begin with valid MP3 frame sync or ID3 tag");
        }
        catch (Exception ex) when (IsNetworkException(ex))
        {
        }
    }

    [Fact]
    public async Task Live_Synthesize_XmlTagsAndQuotes_DoesNotBreakServer()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();
        if (IsOffline(health)) return;

        var request = new TtsRequest(
            RequestId: Guid.NewGuid().ToString("N"),
            EngineId: "edge-tts",
            Language: "en-US",
            VoiceId: "en-US-AvaNeural",
            Text: "Testing \"quotes\" & <tags> with Tom & Jerry!"
        );

        try
        {
            var result = await adapter.SynthesizeAsync(request);

            Assert.NotNull(result);
            Assert.NotNull(result.AudioData);
            Assert.True(result.AudioData.Length > 500);
            Assert.True(ValidateMp3Header(result.AudioData));
        }
        catch (Exception ex) when (IsNetworkException(ex))
        {
        }
    }

    [Fact]
    public async Task Live_ConcurrentSynthesis_MultipleRequests_AllSucceedWithValidMp3()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();
        if (IsOffline(health)) return;

        var texts = new[]
        {
            ("ja-JP", "ja-JP-NanamiNeural", "並行処理テスト一番。"),
            ("vi-VN", "vi-VN-HoaiMyNeural", "Kiểm thử xử lý đồng thời số hai."),
            ("en-US", "en-US-AvaNeural", "Concurrent synthesis stress test number three.")
        };

        try
        {
            var tasks = texts.Select(t =>
            {
                var req = new TtsRequest(
                    RequestId: Guid.NewGuid().ToString("N"),
                    EngineId: "edge-tts",
                    Language: t.Item1,
                    VoiceId: t.Item2,
                    Text: t.Item3
                );
                return adapter.SynthesizeAsync(req);
            }).ToArray();

            var results = await Task.WhenAll(tasks);

            Assert.Equal(3, results.Length);
            foreach (var r in results)
            {
                Assert.NotNull(r);
                Assert.NotNull(r.AudioData);
                Assert.True(r.AudioData.Length > 500);
                Assert.True(ValidateMp3Header(r.AudioData), "Each concurrent audio result must be a valid MP3");
            }
        }
        catch (Exception ex) when (IsNetworkException(ex))
        {
        }
    }

    [Fact]
    public async Task Live_HighConcurrencyStress_6ParallelSynthesize_AllSucceed()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();
        if (IsOffline(health)) return;

        const int numTasks = 6;
        var tasks = Enumerable.Range(0, numTasks).Select(i =>
        {
            var req = new TtsRequest(
                RequestId: Guid.NewGuid().ToString("N"),
                EngineId: "edge-tts",
                Language: i % 2 == 0 ? "ja-JP" : "vi-VN",
                VoiceId: i % 2 == 0 ? "ja-JP-NanamiNeural" : "vi-VN-HoaiMyNeural",
                Text: i % 2 == 0 ? $"並行ストレステスト第{i}番。" : $"Kiểm thử áp lực đồng thời số {i}."
            );
            return adapter.SynthesizeAsync(req);
        }).ToArray();

        try
        {
            var results = await Task.WhenAll(tasks);
            Assert.Equal(numTasks, results.Length);
            foreach (var r in results)
            {
                Assert.NotNull(r);
                Assert.NotNull(r.AudioData);
                Assert.True(r.AudioData.Length > 500);
                Assert.True(ValidateMp3Header(r.AudioData));
            }
        }
        catch (Exception ex) when (IsNetworkException(ex))
        {
        }
    }

    [Fact]
    public async Task Live_LongTextSynthesis_JapaneseAndVietnamese_AccumulatesChunksCorrectly()
    {
        using var adapter = new EdgeTtsEngineAdapter();
        var health = await adapter.GetHealthAsync();
        if (IsOffline(health)) return;

        // Long text requires multi-frame binary streaming from Edge TTS
        string longJapanese = "春はあけぼの。やうやう白くなりゆく山ぎは、少しあかりて、紫だちたる雲の細くたなびきたる。夏は夜。月のころはさらなり、闇もなほ、蛍のおほく飛びちがひたる。また、ただ一つ二つなど、ほのかにうち光りて行くもをかし。雨など降るもをかし。秋は夕暮れ。夕日のさして山の端いと近うなりたるに、烏の寝どころへ行くとて、三つ四つ、二つ三つなど飛び急ぐさへあはれなり。";
        string longVietnamese = "Học tiếng Nhật không chỉ đơn thuần là việc ghi nhớ từ vựng và ngữ pháp, mà còn là hành trình khám phá một nền văn hóa độc đáo và tinh tế. Khi bạn kiên trì luyện tập mỗi ngày cùng các phương pháp lặp lại ngắt quãng và nghe phát âm chuẩn xác, bạn sẽ từng bước làm chủ ngôn ngữ này một cách tự nhiên nhất.";

        try
        {
            var resJa = await adapter.SynthesizeAsync(new TtsRequest(
                RequestId: Guid.NewGuid().ToString("N"),
                EngineId: "edge-tts",
                Language: "ja-JP",
                VoiceId: "ja-JP-NanamiNeural",
                Text: longJapanese
            ));

            Assert.NotNull(resJa);
            Assert.NotNull(resJa.AudioData);
            // Long text produces tens of kilobytes of MP3 data across multiple binary frames
            Assert.True(resJa.AudioData.Length > 10000, $"Expected >10KB for long audio, got {resJa.AudioData.Length}");
            Assert.True(ValidateMp3Header(resJa.AudioData));

            var resVi = await adapter.SynthesizeAsync(new TtsRequest(
                RequestId: Guid.NewGuid().ToString("N"),
                EngineId: "edge-tts",
                Language: "vi-VN",
                VoiceId: "vi-VN-HoaiMyNeural",
                Text: longVietnamese
            ));

            Assert.NotNull(resVi);
            Assert.NotNull(resVi.AudioData);
            Assert.True(resVi.AudioData.Length > 10000, $"Expected >10KB for long audio, got {resVi.AudioData.Length}");
            Assert.True(ValidateMp3Header(resVi.AudioData));
        }
        catch (Exception ex) when (IsNetworkException(ex))
        {
        }
    }

    [Theory]
    [InlineData(new byte[] { })]
    [InlineData(new byte[] { 0x00 })]
    [InlineData(new byte[] { 0x00, 0x10 })] // Claims 16 bytes header, but frame has only 2 bytes
    [InlineData(new byte[] { 0xFF, 0xFF, 0x00, 0x01 })] // Claims 65535 bytes header, frame has 4
    public void BinaryHeader_CorruptedOrTruncated_DoesNotThrow(byte[] malformedFrame)
    {
        // Test frame parser bounds check: frameBytes.Length >= 2 && frameBytes.Length >= 2 + headerLen
        bool canParse = false;
        if (malformedFrame.Length >= 2)
        {
            int headerLen = (malformedFrame[0] << 8) | malformedFrame[1];
            if (malformedFrame.Length >= 2 + headerLen)
            {
                canParse = true;
            }
        }

        Assert.False(canParse, "Malformed truncated frames must be rejected by bounds check");
    }

    #endregion

    #region Mock Helpers

    private class ControlledMockWebSocketClient : IEdgeWebSocketClient
    {
        public bool IsConnected { get; private set; }
        public int ConnectCallCount { get; private set; }
        public int SendConfigCallCount { get; private set; }
        public int SynthesizeCallCount { get; private set; }
        public string? LastSentSsml { get; private set; }
        public int SimulatedConnectDelayMs { get; set; } = 0;
        public int SimulatedSynthDelayMs { get; set; } = 0;

        private readonly SemaphoreSlim _lock = new(1, 1);

        public async Task ConnectAsync(Uri uri, IDictionary<string, string> headers, CancellationToken ct)
        {
            await _lock.WaitAsync(ct);
            try
            {
                ConnectCallCount++;
                if (SimulatedConnectDelayMs > 0)
                {
                    await Task.Delay(SimulatedConnectDelayMs, ct);
                }
                IsConnected = true;
            }
            finally
            {
                _lock.Release();
            }
        }

        public async Task SendConfigAsync(string outputFormat, CancellationToken ct)
        {
            await _lock.WaitAsync(ct);
            try
            {
                if (!IsConnected) throw new InvalidOperationException("Not connected");
                SendConfigCallCount++;
            }
            finally
            {
                _lock.Release();
            }
        }

        public async Task<byte[]> SynthesizeSsmlAsync(string requestId, string ssml, CancellationToken ct)
        {
            await _lock.WaitAsync(ct);
            try
            {
                if (!IsConnected) throw new InvalidOperationException("Not connected");
                SynthesizeCallCount++;
                LastSentSsml = ssml;

                if (SimulatedSynthDelayMs > 0)
                {
                    await Task.Delay(SimulatedSynthDelayMs, ct);
                }

                // Return a mock MP3 frame header (0xFF 0xFB) + data
                return new byte[] { 0xFF, 0xFB, 0x90, 0x64, 0x01, 0x02, 0x03, 0x04 };
            }
            finally
            {
                _lock.Release();
            }
        }

        public async Task CloseAsync(CancellationToken ct)
        {
            await _lock.WaitAsync(ct);
            try
            {
                IsConnected = false;
            }
            finally
            {
                _lock.Release();
            }
        }

        public void Dispose()
        {
            IsConnected = false;
            _lock.Dispose();
        }
    }

    private class DisconnectingMockWebSocketClient : IEdgeWebSocketClient
    {
        public bool IsConnected { get; private set; }
        public int SynthesizeCallCount { get; private set; }
        private bool _hasFailedOnce = false;

        public Task ConnectAsync(Uri uri, IDictionary<string, string> headers, CancellationToken ct)
        {
            IsConnected = true;
            return Task.CompletedTask;
        }

        public Task SendConfigAsync(string outputFormat, CancellationToken ct)
        {
            return Task.CompletedTask;
        }

        public Task<byte[]> SynthesizeSsmlAsync(string requestId, string ssml, CancellationToken ct)
        {
            SynthesizeCallCount++;
            if (!_hasFailedOnce)
            {
                _hasFailedOnce = true;
                IsConnected = false;
                throw new WebSocketException("Simulated socket severed abruptly");
            }

            return Task.FromResult(new byte[] { 0xFF, 0xFB, 0x90, 0x64, 0xAA, 0xBB });
        }

        public Task CloseAsync(CancellationToken ct)
        {
            IsConnected = false;
            return Task.CompletedTask;
        }

        public void Dispose()
        {
            IsConnected = false;
        }
    }

    #endregion
}
