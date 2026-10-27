using System;
using System.Collections.Generic;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Engine.EdgeTts.Network;

public class EdgeWebSocketClient : IEdgeWebSocketClient
{
    private ClientWebSocket? _ws;
    private readonly SemaphoreSlim _lock = new(1, 1);
    private readonly ILogger<EdgeWebSocketClient>? _logger;
    private bool _disposed;

    public bool IsConnected => _ws != null && _ws.State == WebSocketState.Open;

    public EdgeWebSocketClient(ILogger<EdgeWebSocketClient>? logger = null)
    {
        _logger = logger;
    }

    public async Task ConnectAsync(Uri uri, IDictionary<string, string> headers, CancellationToken ct)
    {
        await _lock.WaitAsync(ct);
        try
        {
            if (_ws != null)
            {
                try
                {
                    _ws.Dispose();
                }
                catch
                {
                    // Ignore disposal error
                }
                _ws = null;
            }

            _ws = new ClientWebSocket();
            _ws.Options.KeepAliveInterval = TimeSpan.FromSeconds(10);

            foreach (var kvp in headers)
            {
                if (kvp.Key.Equals("Cookie", StringComparison.OrdinalIgnoreCase))
                {
                    try
                    {
                        var container = new System.Net.CookieContainer();
                        container.SetCookies(uri, kvp.Value);
                        _ws.Options.Cookies = container;
                    }
                    catch
                    {
                        try { _ws.Options.SetRequestHeader(kvp.Key, kvp.Value); } catch { }
                    }
                    continue;
                }

                try
                {
                    _ws.Options.SetRequestHeader(kvp.Key, kvp.Value);
                }
                catch (Exception ex)
                {
                    _logger?.LogDebug(ex, "Failed to set request header {HeaderKey}", kvp.Key);
                }
            }

            _logger?.LogDebug("Connecting to Edge TTS WebSocket: {Uri}", uri);
            await _ws.ConnectAsync(uri, ct);
            _logger?.LogInformation("Connected to Edge TTS WebSocket successfully");
        }
        finally
        {
            _lock.Release();
        }
    }

    private static string GetJsTimestamp()
    {
        return DateTime.UtcNow.ToString("ddd MMM dd yyyy HH:mm:ss 'GMT+0000 (Coordinated Universal Time)'", System.Globalization.CultureInfo.InvariantCulture);
    }

    public async Task SendConfigAsync(string outputFormat, CancellationToken ct)
    {
        await _lock.WaitAsync(ct);
        try
        {
            if (_ws == null || _ws.State != WebSocketState.Open)
            {
                throw new InvalidOperationException("WebSocket is not connected.");
            }

            string timestamp = GetJsTimestamp();
            string configPayload = $"X-Timestamp:{timestamp}\r\n"
                + "Content-Type:application/json; charset=utf-8\r\n"
                + "Path:speech.config\r\n\r\n"
                + $"{{\"context\":{{\"synthesis\":{{\"audio\":{{\"metadataoptions\":{{\"sentenceBoundaryEnabled\":\"false\",\"wordBoundaryEnabled\":\"false\"}},\"outputFormat\":\"{outputFormat}\"}}}}}}}}\r\n";

            byte[] configBytes = Encoding.UTF8.GetBytes(configPayload);
            await _ws.SendAsync(new ArraySegment<byte>(configBytes), WebSocketMessageType.Text, true, ct);
            _logger?.LogDebug("Sent Edge TTS speech.config frame (Format: {OutputFormat})", outputFormat);
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
            if (_ws == null || _ws.State != WebSocketState.Open)
            {
                throw new InvalidOperationException("WebSocket is not connected.");
            }

            string timestamp = GetJsTimestamp();
            string ssmlPayload = $"X-RequestId:{requestId}\r\n"
                + "Content-Type:application/ssml+xml\r\n"
                + $"X-Timestamp:{timestamp}\r\n"
                + "Path:ssml\r\n\r\n"
                + ssml;

            byte[] ssmlBytes = Encoding.UTF8.GetBytes(ssmlPayload);
            await _ws.SendAsync(new ArraySegment<byte>(ssmlBytes), WebSocketMessageType.Text, true, ct);
            _logger?.LogDebug("Sent Edge TTS SSML request {RequestId}", requestId);

            using var audioMs = new MemoryStream();
            byte[] buffer = new byte[16384];
            bool turnEnded = false;

            while (_ws.State == WebSocketState.Open && !turnEnded)
            {
                var segment = new ArraySegment<byte>(buffer);
                using var frameMs = new MemoryStream();
                WebSocketReceiveResult result;

                do
                {
                    result = await _ws.ReceiveAsync(segment, ct);
                    frameMs.Write(buffer, 0, result.Count);
                } while (!result.EndOfMessage);

                byte[] frameBytes = frameMs.ToArray();

                if (result.MessageType == WebSocketMessageType.Text)
                {
                    string textMsg = Encoding.UTF8.GetString(frameBytes);
                    _logger?.LogDebug("[EdgeWebSocket] Received text frame: {Text}", textMsg);
                    if (textMsg.Contains("Path:turn.end", StringComparison.OrdinalIgnoreCase))
                    {
                        turnEnded = true;
                        break;
                    }
                }
                else if (result.MessageType == WebSocketMessageType.Binary)
                {
                    if (frameBytes.Length >= 2)
                    {
                        int headerLen = (frameBytes[0] << 8) | frameBytes[1];
                        if (frameBytes.Length >= 2 + headerLen)
                        {
                            string headerText = Encoding.UTF8.GetString(frameBytes, 2, headerLen);
                            _logger?.LogDebug("[EdgeWebSocket] Received binary audio header: {Header}", headerText);
                            if (headerText.Contains("Path:audio", StringComparison.OrdinalIgnoreCase))
                            {
                                int payloadOffset = 2 + headerLen;
                                int payloadLen = frameBytes.Length - payloadOffset;
                                if (payloadLen > 0)
                                {
                                    audioMs.Write(frameBytes, payloadOffset, payloadLen);
                                }
                            }
                        }
                    }
                }
                else if (result.MessageType == WebSocketMessageType.Close)
                {
                    _logger?.LogWarning("Edge TTS WebSocket received Close frame from server: {Status} - {Description}", result.CloseStatus, result.CloseStatusDescription);
                    break;
                }
            }

            if (!turnEnded || audioMs.Length == 0)
            {
                throw new InvalidOperationException($"Edge TTS synthesis incomplete or received no audio data (turnEnded={turnEnded}, bytes={audioMs.Length}).");
            }

            _logger?.LogInformation("Edge TTS synthesis completed for {RequestId}. Audio bytes: {Length}", requestId, audioMs.Length);
            return audioMs.ToArray();
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
            if (_ws != null)
            {
                if (_ws.State == WebSocketState.Open || _ws.State == WebSocketState.CloseReceived)
                {
                    try
                    {
                        using var closeCts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
                        await _ws.CloseOutputAsync(WebSocketCloseStatus.NormalClosure, "Client closing", closeCts.Token);
                    }
                    catch (Exception ex)
                    {
                        _logger?.LogDebug(ex, "Exception while closing WebSocket");
                    }
                }

                try
                {
                    _ws.Dispose();
                }
                catch { }
                _ws = null;
            }
        }
        finally
        {
            _lock.Release();
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        try
        {
            _ws?.Dispose();
        }
        catch
        {
            // Ignore
        }
        _ws = null;
        _lock.Dispose();
        GC.SuppressFinalize(this);
    }
}
