using System;
using System.Collections.Generic;
using System.IO;
using System.Net.WebSockets;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Core.Models;
using Flama.Audio.Engine.EdgeTts.Constants;
using Flama.Audio.Engine.EdgeTts.Cryptography;
using Flama.Audio.Engine.EdgeTts.Network;
using Flama.Audio.Engine.EdgeTts.Services;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Engine.EdgeTts;

public class EdgeTtsEngineAdapter : ITtsEngineAdapter, IDisposable
{
    public string EngineId => EdgeTtsConstants.EngineId;

    private readonly IEdgeWebSocketClient _client;
    private readonly EdgeTtsVoiceCatalog _voiceCatalog;
    private readonly ILogger<EdgeTtsEngineAdapter>? _logger;

    private DateTimeOffset _lastHealthCheckTime = DateTimeOffset.MinValue;
    private EngineHealth _lastHealth = new("ready", EdgeTtsConstants.ChromiumFullVersion, "Microsoft Edge TTS Online Engine ready");
    private readonly TimeSpan _healthTtl = TimeSpan.FromSeconds(30);
    private readonly SemaphoreSlim _healthLock = new(1, 1);
    private readonly SemaphoreSlim _connectLock = new(1, 1);
    private readonly SemaphoreSlim _synthesisGate = new(1, 1);
    private readonly Queue<DateTimeOffset> _requestTimestamps = new();
    private DateTimeOffset _lastRequestCompletedTime = DateTimeOffset.MinValue;
    private readonly object _rateLimiterLock = new();
    private readonly int _minDelayMs;
    private readonly int _maxRequestsPerMinute;
    private bool _disposed;

    public EdgeTtsEngineAdapter(
        IEdgeWebSocketClient? client = null,
        EdgeTtsVoiceCatalog? voiceCatalog = null,
        ILogger<EdgeTtsEngineAdapter>? logger = null,
        int minDelayMs = EdgeTtsConstants.MinInterRequestDelayMs,
        int maxRequestsPerMinute = EdgeTtsConstants.MaxRequestsPerMinute)
    {
        _client = client ?? new EdgeWebSocketClient();
        _voiceCatalog = voiceCatalog ?? new EdgeTtsVoiceCatalog();
        _logger = logger;
        _minDelayMs = minDelayMs;
        _maxRequestsPerMinute = maxRequestsPerMinute;
    }

    public async Task<EngineHealth> GetHealthAsync(CancellationToken ct = default)
    {
        if (DateTimeOffset.UtcNow - _lastHealthCheckTime < _healthTtl)
        {
            return _lastHealth;
        }

        await _healthLock.WaitAsync(ct);
        try
        {
            if (DateTimeOffset.UtcNow - _lastHealthCheckTime < _healthTtl)
            {
                return _lastHealth;
            }

            bool isOnline = false;
            try
            {
                using var pingCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
                pingCts.CancelAfter(TimeSpan.FromSeconds(3));

                var hostAddresses = await System.Net.Dns.GetHostAddressesAsync("speech.platform.bing.com", pingCts.Token);
                if (hostAddresses != null && hostAddresses.Length > 0)
                {
                    isOnline = true;
                }
            }
            catch (Exception ex)
            {
                _logger?.LogDebug(ex, "Network connectivity check failed for Edge TTS");
                isOnline = false;
            }

            if (isOnline)
            {
                _lastHealth = new EngineHealth("ready", EdgeTtsConstants.ChromiumFullVersion, "Microsoft Edge TTS Online Engine ready");
            }
            else
            {
                _lastHealth = new EngineHealth("unhealthy", null, "Không có kết nối Internet. Edge TTS cần kết nối mạng để phát âm.");
            }

            _lastHealthCheckTime = DateTimeOffset.UtcNow;
            return _lastHealth;
        }
        finally
        {
            _healthLock.Release();
        }
    }

    public async Task StartAsync(CancellationToken ct = default)
    {
        _logger?.LogInformation("Starting Edge TTS engine adapter, warming up voice catalog");
        await _voiceCatalog.GetVoicesAsync(forceRefresh: false, ct);
    }

    public async Task StopAsync(CancellationToken ct = default)
    {
        _logger?.LogInformation("Stopping Edge TTS engine adapter, closing active connections");
        await _client.CloseAsync(ct);
    }

    public async Task<IReadOnlyList<VoiceDescriptor>> ListVoicesAsync(CancellationToken ct = default)
    {
        return await _voiceCatalog.GetVoicesAsync(forceRefresh: false, ct);
    }

    public async Task<TtsResult> SynthesizeAsync(TtsRequest request, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(request.Text))
        {
            throw new ArgumentException("Text cannot be empty.", nameof(request));
        }

        await _synthesisGate.WaitAsync(ct);
        try
        {
            await EnforceRateLimitAsync(ct);

            string voiceId = string.IsNullOrWhiteSpace(request.VoiceId)
                ? ResolveDefaultVoice(request.Language)
                : request.VoiceId;

            string lang = ResolveLanguage(request.Language, voiceId);

            // Convert prosody options
            double speed = request.Options?.Speed ?? 1.0;
            int rateDelta = (int)Math.Round((speed - 1.0) * 100);
            string rateStr = rateDelta >= 0 ? $"+{rateDelta}%" : $"{rateDelta}%";

            double pitch = request.Options?.Pitch ?? 0.0;
            int pitchHz = (int)Math.Round(pitch);
            string pitchStr = pitchHz >= 0 ? $"+{pitchHz}Hz" : $"{pitchHz}Hz";

            double volume = request.Options?.Volume ?? 1.0;
            int volDelta = (int)Math.Round((volume - 1.0) * 100);
            string volumeStr = volDelta >= 0 ? $"+{volDelta}%" : $"{volDelta}%";

            string escapedText = System.Security.SecurityElement.Escape(request.Text) ?? request.Text;

            string ssml = $"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{lang}'>"
                + $"<voice name='{voiceId}'>"
                + $"<prosody pitch='{pitchStr}' rate='{rateStr}' volume='{volumeStr}'>"
                + $"{escapedText}"
                + "</prosody></voice></speak>";

            string originalRequestId = string.IsNullOrWhiteSpace(request.RequestId)
                ? Guid.NewGuid().ToString("N")
                : request.RequestId;

            // Microsoft Edge TTS strictly enforces X-RequestId header to be a 32-character no-dash UUID.
            string wsRequestId = Guid.TryParse(originalRequestId, out var parsedGuid)
                ? parsedGuid.ToString("N")
                : (originalRequestId.Replace("-", "") is { Length: 32 } cleaned && cleaned.All(Uri.IsHexDigit)
                    ? cleaned
                    : Guid.NewGuid().ToString("N"));

            byte[] audioBytes;
            try
            {
                await EnsureConnectedAsync(ct);
                audioBytes = await _client.SynthesizeSsmlAsync(wsRequestId, ssml, ct);
            }
            catch (Exception ex) when (ex is WebSocketException or InvalidOperationException or IOException)
            {
                _logger?.LogWarning(ex, "Edge TTS synthesis encountered disconnected socket, attempting clean reconnect retry");
                await _connectLock.WaitAsync(ct);
                try
                {
                    await ReconnectAsync(ct);
                }
                finally
                {
                    _connectLock.Release();
                }
                audioBytes = await _client.SynthesizeSsmlAsync(wsRequestId, ssml, ct);
            }

            return new TtsResult(
                AudioData: audioBytes,
                ContentType: EdgeTtsConstants.DefaultContentType,
                EngineId: EdgeTtsConstants.EngineId,
                VoiceId: voiceId,
                RequestId: originalRequestId
            );
        }
        finally
        {
            lock (_rateLimiterLock)
            {
                _lastRequestCompletedTime = DateTimeOffset.UtcNow;
            }
            _synthesisGate.Release();
        }
    }

    private async Task EnforceRateLimitAsync(CancellationToken ct)
    {
        TimeSpan delayNeeded = TimeSpan.Zero;
        lock (_rateLimiterLock)
        {
            var now = DateTimeOffset.UtcNow;

            // 1. Minimum pause between consecutive requests (pacing)
            if (_minDelayMs > 0 && _lastRequestCompletedTime != DateTimeOffset.MinValue)
            {
                var elapsedSinceLast = now - _lastRequestCompletedTime;
                if (elapsedSinceLast < TimeSpan.FromMilliseconds(_minDelayMs))
                {
                    delayNeeded = TimeSpan.FromMilliseconds(_minDelayMs) - elapsedSinceLast;
                }
            }

            // 2. Clean up timestamps older than 60 seconds
            while (_requestTimestamps.Count > 0 && (now - _requestTimestamps.Peek()) > TimeSpan.FromSeconds(60))
            {
                _requestTimestamps.Dequeue();
            }

            // 3. Sliding window check
            if (_maxRequestsPerMinute > 0 && _requestTimestamps.Count >= _maxRequestsPerMinute)
            {
                var oldestInWindow = _requestTimestamps.Peek();
                var windowDelay = TimeSpan.FromSeconds(60) - (now - oldestInWindow);
                if (windowDelay > delayNeeded)
                {
                    delayNeeded = windowDelay;
                }
            }

            if (delayNeeded > TimeSpan.FromMilliseconds(EdgeTtsConstants.MaxThrottleWaitMs))
            {
                throw new InvalidOperationException(
                    $"Edge TTS rate limit exceeded ({_maxRequestsPerMinute} requests/minute limit to prevent Microsoft IP ban). Please wait before trying again.");
            }
        }

        if (delayNeeded > TimeSpan.Zero)
        {
            _logger?.LogDebug("Edge TTS rate limiter pacing: waiting {DelayMs}ms", delayNeeded.TotalMilliseconds);
            await Task.Delay(delayNeeded, ct);
        }

        lock (_rateLimiterLock)
        {
            _requestTimestamps.Enqueue(DateTimeOffset.UtcNow);
        }
    }

    private async Task EnsureConnectedAsync(CancellationToken ct)
    {
        if (_client.IsConnected) return;

        await _connectLock.WaitAsync(ct);
        try
        {
            if (_client.IsConnected) return;
            await ReconnectAsync(ct);
        }
        finally
        {
            _connectLock.Release();
        }
    }

    private async Task ReconnectAsync(CancellationToken ct)
    {
        try
        {
            await _client.CloseAsync(ct);
        }
        catch { }

        string connectionId = Guid.NewGuid().ToString("N");
        string secMsGec = EdgeTtsDrm.GenerateSecMsGecV2();

        string wssUrl = $"{EdgeTtsConstants.WssUrl}"
            + $"?TrustedClientToken={EdgeTtsConstants.TrustedClientToken}"
            + $"&ConnectionId={connectionId}"
            + $"&Sec-MS-GEC={secMsGec}"
            + $"&Sec-MS-GEC-Version={EdgeTtsConstants.SecMsGecVersion}";

        var headers = new Dictionary<string, string>
        {
            { "Pragma", "no-cache" },
            { "Cache-Control", "no-cache" },
            { "Origin", EdgeTtsConstants.Origin },
            { "User-Agent", EdgeTtsConstants.DefaultUserAgent },
            { "Accept-Encoding", EdgeTtsConstants.DefaultAcceptEncoding },
            { "Accept-Language", EdgeTtsConstants.DefaultAcceptLanguage },
            { "Cookie", EdgeTtsDrm.GenerateMuidCookie() }
        };

        await _client.ConnectAsync(new Uri(wssUrl), headers, ct);
        await _client.SendConfigAsync(EdgeTtsConstants.DefaultOutputFormat, ct);
    }

    private static string ResolveDefaultVoice(string? language)
    {
        if (string.IsNullOrWhiteSpace(language)) return "ja-JP-NanamiNeural";
        string lower = language.ToLowerInvariant();
        if (lower.StartsWith("ja")) return "ja-JP-NanamiNeural";
        if (lower.StartsWith("vi")) return "vi-VN-HoaiMyNeural";
        if (lower.StartsWith("en")) return "en-US-AvaNeural";
        if (lower.StartsWith("zh")) return "zh-CN-XiaoxiaoNeural";
        if (lower.StartsWith("ko")) return "ko-KR-SunHiNeural";
        if (lower.StartsWith("fr")) return "fr-FR-DeniseNeural";
        if (lower.StartsWith("de")) return "de-DE-AmalaNeural";
        if (lower.StartsWith("es")) return "es-ES-ElviraNeural";
        return "ja-JP-NanamiNeural";
    }

    private static string ResolveLanguage(string? language, string voiceId)
    {
        if (!string.IsNullOrWhiteSpace(language)) return language;
        int firstDash = voiceId.IndexOf('-');
        if (firstDash > 0)
        {
            int secondDash = voiceId.IndexOf('-', firstDash + 1);
            if (secondDash > 0)
            {
                return voiceId[..secondDash];
            }
            return voiceId[..firstDash];
        }
        return "ja-JP";
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        _client.Dispose();
        _healthLock.Dispose();
        _connectLock.Dispose();
        _synthesisGate.Dispose();
        GC.SuppressFinalize(this);
    }
}
