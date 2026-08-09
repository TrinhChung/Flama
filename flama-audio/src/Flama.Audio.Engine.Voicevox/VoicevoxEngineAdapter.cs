using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Core.Models;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Engine.Voicevox;

public class VoicevoxEngineAdapter : ITtsEngineAdapter
{
    public string EngineId => "voicevox";
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;
    private readonly ILogger<VoicevoxEngineAdapter>? _logger;

    public VoicevoxEngineAdapter(HttpClient httpClient, string baseUrl = "http://127.0.0.1:50021", ILogger<VoicevoxEngineAdapter>? logger = null)
    {
        _httpClient = httpClient;
        _baseUrl = baseUrl.TrimEnd('/');
        _logger = logger;
    }

    public async Task<EngineHealth> GetHealthAsync(CancellationToken ct = default)
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_baseUrl}/version", ct);
            if (response.IsSuccessStatusCode)
            {
                var version = await response.Content.ReadAsStringAsync(ct);
                version = version.Trim('"').Trim();
                return new EngineHealth("ready", version, "VOICEVOX engine is active");
            }
            return new EngineHealth("unhealthy", null, $"Returned HTTP status {response.StatusCode}");
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "VOICEVOX health check failed on {BaseUrl}", _baseUrl);
            return new EngineHealth("stopped", null, "VOICEVOX engine is not running locally");
        }
    }

    public Task StartAsync(CancellationToken ct = default) => Task.CompletedTask;
    public Task StopAsync(CancellationToken ct = default) => Task.CompletedTask;

    public async Task<IReadOnlyList<VoiceDescriptor>> ListVoicesAsync(CancellationToken ct = default)
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_baseUrl}/speakers", ct);
            if (!response.IsSuccessStatusCode)
            {
                return GetFallbackVoices();
            }

            var json = await response.Content.ReadAsStringAsync(ct);
            using var doc = JsonDocument.Parse(json);
            var voices = new List<VoiceDescriptor>();

            foreach (var speaker in doc.RootElement.EnumerateArray())
            {
                var speakerName = speaker.GetProperty("name").GetString() ?? "Unknown";
                if (speaker.TryGetProperty("styles", out var styles))
                {
                    foreach (var style in styles.EnumerateArray())
                    {
                        var styleId = style.GetProperty("id").GetInt32().ToString();
                        var styleName = style.GetProperty("name").GetString() ?? "Normal";
                        voices.Add(new VoiceDescriptor(
                            VoiceId: styleId,
                            Name: $"{speakerName} ({styleName})",
                            SpeakerName: speakerName,
                            StyleName: styleName,
                            Locale: "ja-JP",
                            CommercialSafe: true,
                            Attribution: "VOICEVOX"
                        ));
                    }
                }
            }

            return voices.Count > 0 ? voices : GetFallbackVoices();
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "Failed to list VOICEVOX speakers from {BaseUrl}, returning fallback list", _baseUrl);
            return GetFallbackVoices();
        }
    }

    public async Task<TtsResult> SynthesizeAsync(TtsRequest request, CancellationToken ct = default)
    {
        var styleId = request.VoiceId;
        var text = Uri.EscapeDataString(request.Text);

        try
        {
            // Step 1: Create AudioQuery
            var queryUrl = $"{_baseUrl}/audio_query?text={text}&speaker={styleId}";
            var queryResponse = await _httpClient.PostAsync(queryUrl, null, ct);
            queryResponse.EnsureSuccessStatusCode();

            var queryJson = await queryResponse.Content.ReadAsStringAsync(ct);
            var queryObj = JsonNode.Parse(queryJson)?.AsObject();

            if (queryObj != null && request.Options != null)
            {
                queryObj["speedScale"] = request.Options.Speed;
                queryObj["pitchScale"] = request.Options.Pitch;
                queryObj["intonationScale"] = request.Options.Intonation;
                queryObj["volumeScale"] = request.Options.Volume;
            }

            // Step 2: Synthesis
            var synthesisUrl = $"{_baseUrl}/synthesis?speaker={styleId}";
            var content = new StringContent(queryObj?.ToJsonString() ?? queryJson, Encoding.UTF8, "application/json");
            var synthesisResponse = await _httpClient.PostAsync(synthesisUrl, content, ct);
            synthesisResponse.EnsureSuccessStatusCode();

            var wavBytes = await synthesisResponse.Content.ReadAsByteArrayAsync(ct);

            return new TtsResult(
                AudioData: wavBytes,
                ContentType: "audio/wav",
                EngineId: EngineId,
                VoiceId: request.VoiceId,
                RequestId: request.RequestId
            );
        }
        catch (HttpRequestException ex)
        {
            _logger?.LogError(ex, "VOICEVOX Engine at {BaseUrl} connection refused", _baseUrl);
            throw new InvalidOperationException($"Không thể kết nối tới VOICEVOX Engine local ({_baseUrl}). Vui lòng mở ứng dụng VOICEVOX trên máy tính của bạn.");
        }
    }

    private static List<VoiceDescriptor> GetFallbackVoices() => new()
    {
        new VoiceDescriptor("3", "Zundamon (ノーマル)", "Zundamon", "ノーマル", "ja-JP"),
        new VoiceDescriptor("1", "Zundamon (あまあま)", "Zundamon", "あまあま", "ja-JP"),
        new VoiceDescriptor("7", "Zundamon (ツンツン)", "Zundamon", "ツンツン", "ja-JP"),
        new VoiceDescriptor("2", "Shikikoin Metan (ノーマル)", "Shikikoin Metan", "ノーマル", "ja-JP"),
        new VoiceDescriptor("8", "Kasukabe Tsumugi (ノーマル)", "Kasukabe Tsumugi", "ノーマル", "ja-JP")
    };
}
