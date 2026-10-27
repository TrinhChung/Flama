using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Engine.EdgeTts.Network;
using Xunit;

namespace Flama.Audio.Tests;

public class EdgeTtsWebSocketTests
{
    [Fact]
    public void EdgeWebSocketClient_InitialState_IsNotConnected()
    {
        using var client = new EdgeWebSocketClient();
        Assert.False(client.IsConnected);
    }

    [Fact]
    public async Task EdgeWebSocketClient_SendConfigAsync_WhenDisconnected_ThrowsInvalidOperationException()
    {
        using var client = new EdgeWebSocketClient();
        await Assert.ThrowsAsync<InvalidOperationException>(() =>
            client.SendConfigAsync("audio-24khz-48kbitrate-mono-mp3", CancellationToken.None));
    }

    [Fact]
    public async Task EdgeWebSocketClient_SynthesizeSsmlAsync_WhenDisconnected_ThrowsInvalidOperationException()
    {
        using var client = new EdgeWebSocketClient();
        await Assert.ThrowsAsync<InvalidOperationException>(() =>
            client.SynthesizeSsmlAsync("req-1", "<speak></speak>", CancellationToken.None));
    }

    [Fact]
    public async Task EdgeWebSocketClient_CloseAsync_WhenNotConnected_DoesNotThrow()
    {
        using var client = new EdgeWebSocketClient();
        await client.CloseAsync(CancellationToken.None);
        Assert.False(client.IsConnected);
    }

    [Fact]
    public void EdgeWebSocketClient_Dispose_CanBeCalledMultipleTimes()
    {
        var client = new EdgeWebSocketClient();
        client.Dispose();
        client.Dispose();
        Assert.False(client.IsConnected);
    }

    [Fact]
    public void BinaryFrameHeader_ParsingLogic_ExtractsCorrectPayload()
    {
        string header = "X-RequestId:12345678901234567890123456789012\r\nContent-Type:audio/mpeg\r\nPath:audio\r\n";
        byte[] headerBytes = Encoding.UTF8.GetBytes(header);
        byte[] fakeMp3 = new byte[] { 0xFF, 0xFB, 0x90, 0x64, 0x01, 0x02, 0x03, 0x04 };

        int headerLen = headerBytes.Length;
        byte[] frame = new byte[2 + headerLen + fakeMp3.Length];
        frame[0] = (byte)((headerLen >> 8) & 0xFF);
        frame[1] = (byte)(headerLen & 0xFF);
        Array.Copy(headerBytes, 0, frame, 2, headerLen);
        Array.Copy(fakeMp3, 0, frame, 2 + headerLen, fakeMp3.Length);

        int parsedHeaderLen = (frame[0] << 8) | frame[1];
        Assert.Equal(headerLen, parsedHeaderLen);

        string parsedHeader = Encoding.UTF8.GetString(frame, 2, parsedHeaderLen);
        Assert.Contains("Path:audio", parsedHeader);

        int payloadOffset = 2 + parsedHeaderLen;
        int payloadLen = frame.Length - payloadOffset;
        byte[] parsedPayload = new byte[payloadLen];
        Array.Copy(frame, payloadOffset, parsedPayload, 0, payloadLen);

        Assert.Equal(fakeMp3, parsedPayload);
    }
}
