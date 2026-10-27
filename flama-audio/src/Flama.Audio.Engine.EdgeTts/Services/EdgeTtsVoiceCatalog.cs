using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Core.Models;
using Flama.Audio.Engine.EdgeTts.Constants;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Engine.EdgeTts.Services;

public record EdgeVoiceRawItem(
    [property: JsonPropertyName("Name")] string? Name,
    [property: JsonPropertyName("ShortName")] string ShortName,
    [property: JsonPropertyName("Gender")] string? Gender,
    [property: JsonPropertyName("Locale")] string? Locale,
    [property: JsonPropertyName("LocaleName")] string? LocaleName,
    [property: JsonPropertyName("SuggestedCodec")] string? SuggestedCodec,
    [property: JsonPropertyName("FriendlyName")] string? FriendlyName,
    [property: JsonPropertyName("Status")] string? Status
);

public class EdgeTtsVoiceCatalog
{
    private readonly HttpClient _httpClient;
    private readonly string _diskCachePath;
    private readonly ILogger<EdgeTtsVoiceCatalog>? _logger;
    private readonly SemaphoreSlim _lock = new(1, 1);
    private List<VoiceDescriptor>? _inMemoryCache;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public EdgeTtsVoiceCatalog(
        HttpClient? httpClient = null,
        string? diskCachePath = null,
        ILogger<EdgeTtsVoiceCatalog>? logger = null)
    {
        _httpClient = httpClient ?? new HttpClient();
        _diskCachePath = diskCachePath ?? Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Flama",
            "Audio",
            "edge_voices_cache.json"
        );
        _logger = logger;
    }

    /// <summary>
    /// Gets all Edge TTS voice descriptors with 3-tier resilience:
    /// In-memory cache -> Live fetch / Disk cache -> Embedded resource fallback.
    /// </summary>
    public async Task<IReadOnlyList<VoiceDescriptor>> GetVoicesAsync(bool forceRefresh = false, CancellationToken ct = default)
    {
        if (!forceRefresh && _inMemoryCache != null && _inMemoryCache.Count > 0)
        {
            return _inMemoryCache;
        }

        await _lock.WaitAsync(ct);
        try
        {
            if (!forceRefresh && _inMemoryCache != null && _inMemoryCache.Count > 0)
            {
                return _inMemoryCache;
            }

            // Fast Path: Immediately load from disk cache or embedded resource (0ms latency)
            if (!forceRefresh)
            {
                try
                {
                    if (File.Exists(_diskCachePath))
                    {
                        string json = await File.ReadAllTextAsync(_diskCachePath, ct);
                        var rawList = JsonSerializer.Deserialize<List<EdgeVoiceRawItem>>(json, JsonOptions);
                        if (rawList != null && rawList.Count > 0)
                        {
                            var descriptors = rawList.Select(MapToDescriptor).ToList();
                            _inMemoryCache = descriptors;
                            _logger?.LogInformation("Loaded {Count} Edge TTS voices from persistent disk cache: {Path}", descriptors.Count, _diskCachePath);
                            return descriptors;
                        }
                    }
                }
                catch { }

                var fastLocal = LoadFromEmbeddedResource();
                if (fastLocal != null && fastLocal.Count > 0)
                {
                    _inMemoryCache = fastLocal;
                    _logger?.LogInformation("Loaded {Count} Edge TTS voices instantly from embedded manifest", fastLocal.Count);
                    return fastLocal;
                }
            }

            // Remote Live Fetch with proper browser headers
            try
            {
                using var timeoutCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
                timeoutCts.CancelAfter(TimeSpan.FromSeconds(3));

                string url = $"{EdgeTtsConstants.VoiceListUrl}?trustedclienttoken={EdgeTtsConstants.TrustedClientToken}";
                using var requestMsg = new HttpRequestMessage(HttpMethod.Get, url);
                requestMsg.Headers.Add("User-Agent", EdgeTtsConstants.DefaultUserAgent);
                requestMsg.Headers.Add("Accept", "*/*");
                requestMsg.Headers.Add("Authority", "speech.platform.bing.com");

                var response = await _httpClient.SendAsync(requestMsg, timeoutCts.Token);
                if (response.IsSuccessStatusCode)
                {
                    string json = await response.Content.ReadAsStringAsync(timeoutCts.Token);
                    var rawList = JsonSerializer.Deserialize<List<EdgeVoiceRawItem>>(json, JsonOptions);
                    if (rawList != null && rawList.Count > 0)
                    {
                        var descriptors = rawList.Select(MapToDescriptor).ToList();
                        _inMemoryCache = descriptors;
                        _logger?.LogInformation("Loaded {Count} voices from live Edge TTS endpoint", descriptors.Count);

                        // Save to disk cache in background
                        _ = SaveToDiskCacheAsync(json);
                        return descriptors;
                    }
                }
            }
            catch (Exception ex)
            {
                _logger?.LogWarning(ex, "Live Edge TTS voice catalog fetch failed. Falling back to disk/embedded cache.");
            }

            // Tier 2: Persistent Local Disk Cache
            try
            {
                if (File.Exists(_diskCachePath))
                {
                    string json = await File.ReadAllTextAsync(_diskCachePath, ct);
                    var rawList = JsonSerializer.Deserialize<List<EdgeVoiceRawItem>>(json, JsonOptions);
                    if (rawList != null && rawList.Count > 0)
                    {
                        var descriptors = rawList.Select(MapToDescriptor).ToList();
                        _inMemoryCache = descriptors;
                        _logger?.LogInformation("Loaded {Count} Edge TTS voices from persistent disk cache: {Path}", descriptors.Count, _diskCachePath);
                        return descriptors;
                    }
                }
            }
            catch (Exception ex)
            {
                _logger?.LogWarning(ex, "Failed to load Edge TTS voice catalog from disk cache at {Path}", _diskCachePath);
            }

            // Tier 3: Bundled Embedded Assembly Catalog Fallback
            var embedded = LoadFromEmbeddedResource();
            if (embedded != null && embedded.Count > 0)
            {
                _inMemoryCache = embedded;
                _logger?.LogInformation("Loaded {Count} Edge TTS voices from embedded assembly fallback", embedded.Count);
                return embedded;
            }

            return _inMemoryCache ?? (IReadOnlyList<VoiceDescriptor>)Array.Empty<VoiceDescriptor>();
        }
        finally
        {
            _lock.Release();
        }
    }

    /// <summary>
    /// Loads voice catalog directly from embedded assembly manifest resource.
    /// </summary>
    public List<VoiceDescriptor> LoadFromEmbeddedResource()
    {
        try
        {
            var assembly = typeof(EdgeTtsVoiceCatalog).Assembly;
            var resName = assembly.GetManifestResourceNames()
                .FirstOrDefault(n => n.EndsWith("edge_voices_catalog.json", StringComparison.OrdinalIgnoreCase));

            if (resName == null)
            {
                _logger?.LogError("Embedded resource edge_voices_catalog.json not found in assembly {Assembly}", assembly.FullName);
                return new List<VoiceDescriptor>();
            }

            using var stream = assembly.GetManifestResourceStream(resName);
            if (stream == null) return new List<VoiceDescriptor>();

            using var reader = new StreamReader(stream, Encoding.UTF8);
            string json = reader.ReadToEnd();
            var rawList = JsonSerializer.Deserialize<List<EdgeVoiceRawItem>>(json, JsonOptions);
            return rawList != null ? rawList.Select(MapToDescriptor).ToList() : new List<VoiceDescriptor>();
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Failed to load embedded Edge TTS voice catalog from resource");
            return new List<VoiceDescriptor>();
        }
    }

    /// <summary>
    /// Maps an Edge TTS raw voice item to the core VoiceDescriptor model.
    /// </summary>
    public static VoiceDescriptor MapToDescriptor(EdgeVoiceRawItem raw)
    {
        string shortName = raw.ShortName;
        int lastDash = shortName.LastIndexOf('-');
        string rawSpeaker = lastDash >= 0 ? shortName[(lastDash + 1)..] : shortName;
        string speaker = rawSpeaker.Replace("Neural", "").Replace("Multilingual", " (Multi)");
        string gender = raw.Gender ?? "Unknown";
        string name = $"{speaker} ({gender})";
        string locale = raw.Locale ?? (lastDash >= 0 ? shortName[..lastDash] : "en-US");

        return new VoiceDescriptor(
            VoiceId: shortName,
            Name: name,
            SpeakerName: speaker,
            StyleName: gender,
            Locale: locale,
            CommercialSafe: true,
            Attribution: "Microsoft Edge TTS"
        );
    }

    private async Task SaveToDiskCacheAsync(string json)
    {
        try
        {
            string? dir = Path.GetDirectoryName(_diskCachePath);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
            {
                Directory.CreateDirectory(dir);
            }
            await File.WriteAllTextAsync(_diskCachePath, json);
        }
        catch (Exception ex)
        {
            _logger?.LogDebug(ex, "Could not save Edge TTS catalog to disk cache {Path}", _diskCachePath);
        }
    }
}
