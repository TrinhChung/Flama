using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Core.Models;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Infrastructure.Services;

public class PairingManager : IPairingManager
{
    private readonly ConcurrentDictionary<string, PairingChallenge> _challenges = new();
    private readonly ConcurrentDictionary<string, string> _tokens = new(); // tokenHash -> origin
    private readonly string _storagePath;
    private readonly ILogger<PairingManager>? _logger;

    public PairingManager(ILogger<PairingManager>? logger = null)
    {
        _logger = logger;
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var dir = Path.Combine(localAppData, "Flama", "Audio", "state");
        Directory.CreateDirectory(dir);
        _storagePath = Path.Combine(dir, "pairings.json");
        LoadState();
    }

    public event EventHandler? OnPairingRequested;

    public Task<PairingChallenge> StartPairingAsync(string origin, string clientInfo, CancellationToken ct = default)
    {
        var pairingId = Guid.NewGuid().ToString("N");
        var challenge = new PairingChallenge(
            PairingId: pairingId,
            Origin: origin,
            ClientInfo: clientInfo,
            Approved: false,
            Token: null,
            CreatedAt: DateTimeOffset.UtcNow
        );

        _challenges[pairingId] = challenge;
        _logger?.LogInformation("Started pairing challenge {PairingId} for origin {Origin}", pairingId, origin);
        OnPairingRequested?.Invoke(this, EventArgs.Empty);
        return Task.FromResult(challenge);
    }

    public PairingChallenge? GetChallenge(string pairingId)
    {
        _challenges.TryGetValue(pairingId, out var challenge);
        return challenge;
    }

    public Task<bool> ApprovePairingAsync(string pairingId, CancellationToken ct = default)
    {
        if (!_challenges.TryGetValue(pairingId, out var challenge))
        {
            return Task.FromResult(false);
        }

        var token = GenerateSecureToken();
        var approvedChallenge = challenge with { Approved = true, Token = token };
        _challenges[pairingId] = approvedChallenge;

        var tokenHash = HashToken(token);
        _tokens[tokenHash] = challenge.Origin;

        SaveState();
        _logger?.LogInformation("Approved pairing {PairingId} for origin {Origin}", pairingId, challenge.Origin);
        return Task.FromResult(true);
    }

    public bool ValidateToken(string origin, string token)
    {
        if (string.IsNullOrWhiteSpace(token)) return false;
        var hash = HashToken(token);
        if (_tokens.TryGetValue(hash, out var allowedOrigin))
        {
            // Allowed if origin matches or allowed origins check
            return string.Equals(allowedOrigin, origin, StringComparison.OrdinalIgnoreCase) ||
                   origin.StartsWith("http://localhost", StringComparison.OrdinalIgnoreCase) ||
                   origin.StartsWith("http://127.0.0.1", StringComparison.OrdinalIgnoreCase);
        }
        return false;
    }

    public IReadOnlyList<PairingChallenge> ListPairings()
    {
        return _challenges.Values.ToList();
    }

    private static string GenerateSecureToken()
    {
        var bytes = new byte[32];
        using var rng = RandomNumberGenerator.Create();
        rng.GetBytes(bytes);
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private static string HashToken(string token)
    {
        using var sha = SHA256.Create();
        var bytes = sha.ComputeHash(Encoding.UTF8.GetBytes(token));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private void SaveState()
    {
        try
        {
            var data = new
            {
                Tokens = _tokens.ToDictionary(k => k.Key, v => v.Value)
            };
            var json = JsonSerializer.Serialize(data, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(_storagePath, json);
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Failed to save pairings state to {Path}", _storagePath);
        }
    }

    private void LoadState()
    {
        try
        {
            if (!File.Exists(_storagePath)) return;
            var json = File.ReadAllText(_storagePath);
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("Tokens", out var tokensElement))
            {
                foreach (var prop in tokensElement.EnumerateObject())
                {
                    _tokens[prop.Name] = prop.Value.GetString() ?? "";
                }
            }
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Failed to load pairings state from {Path}", _storagePath);
        }
    }
}
