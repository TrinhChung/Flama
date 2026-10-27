using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace Flama.Audio.Engine.EdgeTts.Network;

public interface IEdgeWebSocketClient : IDisposable
{
    Task ConnectAsync(Uri uri, IDictionary<string, string> headers, CancellationToken ct);
    Task SendConfigAsync(string outputFormat, CancellationToken ct);
    Task<byte[]> SynthesizeSsmlAsync(string requestId, string ssml, CancellationToken ct);
    Task CloseAsync(CancellationToken ct);
    bool IsConnected { get; }
}
