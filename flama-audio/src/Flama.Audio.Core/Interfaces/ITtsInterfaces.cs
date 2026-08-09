using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Core.Models;

namespace Flama.Audio.Core.Interfaces;

public interface ITtsEngineAdapter
{
    string EngineId { get; }
    Task<EngineHealth> GetHealthAsync(CancellationToken ct = default);
    Task StartAsync(CancellationToken ct = default);
    Task StopAsync(CancellationToken ct = default);
    Task<IReadOnlyList<VoiceDescriptor>> ListVoicesAsync(CancellationToken ct = default);
    Task<TtsResult> SynthesizeAsync(TtsRequest request, CancellationToken ct = default);
}

public interface IEngineRouter
{
    ITtsEngineAdapter? GetAdapter(string engineId);
    IReadOnlyList<ITtsEngineAdapter> GetAllAdapters();
}

public interface IPairingManager
{
    event System.EventHandler? OnPairingRequested;
    Task<PairingChallenge> StartPairingAsync(string origin, string clientInfo, CancellationToken ct = default);
    PairingChallenge? GetChallenge(string pairingId);
    Task<bool> ApprovePairingAsync(string pairingId, CancellationToken ct = default);
    bool ValidateToken(string origin, string token);
    IReadOnlyList<PairingChallenge> ListPairings();
}
