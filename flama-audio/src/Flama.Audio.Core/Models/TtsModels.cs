using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Flama.Audio.Core.Models;

public record TtsOptions(
    [property: JsonPropertyName("speed")] double Speed = 1.0,
    [property: JsonPropertyName("pitch")] double Pitch = 0.0,
    [property: JsonPropertyName("intonation")] double Intonation = 1.0,
    [property: JsonPropertyName("volume")] double Volume = 1.0
);

public record TtsRequest(
    [property: JsonPropertyName("request_id")] string RequestId,
    [property: JsonPropertyName("engine_id")] string EngineId,
    [property: JsonPropertyName("language")] string Language,
    [property: JsonPropertyName("voice_id")] string VoiceId,
    [property: JsonPropertyName("text")] string Text,
    [property: JsonPropertyName("output_format")] string OutputFormat = "wav",
    [property: JsonPropertyName("options")] TtsOptions? Options = null,
    [property: JsonPropertyName("engine_options")] Dictionary<string, object>? EngineOptions = null
);

public record TtsResult(
    byte[] AudioData,
    string ContentType,
    string EngineId,
    string VoiceId,
    string RequestId
);

public record VoiceDescriptor(
    [property: JsonPropertyName("voice_id")] string VoiceId,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("speaker_name")] string SpeakerName,
    [property: JsonPropertyName("style_name")] string StyleName,
    [property: JsonPropertyName("locale")] string Locale,
    [property: JsonPropertyName("commercial_safe")] bool CommercialSafe = true,
    [property: JsonPropertyName("attribution")] string? Attribution = null
);

public record EngineHealth(
    [property: JsonPropertyName("status")] string Status, // "ready", "unhealthy", "starting", "stopped", "not_installed"
    [property: JsonPropertyName("version")] string? Version = null,
    [property: JsonPropertyName("message")] string? Message = null
);

public record EnginePackageState(
    [property: JsonPropertyName("engine_id")] string EngineId,
    [property: JsonPropertyName("installed_version")] string? InstalledVersion,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("is_available")] bool IsAvailable
);

public record PairingChallenge(
    [property: JsonPropertyName("pairing_id")] string PairingId,
    [property: JsonPropertyName("origin")] string Origin,
    [property: JsonPropertyName("client_info")] string ClientInfo,
    [property: JsonPropertyName("approved")] bool Approved,
    [property: JsonPropertyName("token")] string? Token,
    [property: JsonPropertyName("created_at")] DateTimeOffset CreatedAt
);
