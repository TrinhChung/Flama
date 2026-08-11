using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Text.RegularExpressions;

namespace Flama.Audio.Engine.Kokoro.IO;

public static class NpyReader
{
    private static readonly byte[] MagicBytes = new byte[] { 0x93, (byte)'N', (byte)'U', (byte)'M', (byte)'P', (byte)'Y' };

    public static (float[] Data, int[] Shape) ReadNpy(Stream stream)
    {
        using var reader = new BinaryReader(stream, Encoding.UTF8, leaveOpen: true);
        
        byte[] magic = reader.ReadBytes(6);
        if (magic.Length < 6 || !IsMagicMatch(magic))
        {
            throw new FormatException("Invalid .npy magic header");
        }

        byte major = reader.ReadByte();
        byte minor = reader.ReadByte();

        int headerLen;
        if (major == 1)
        {
            headerLen = reader.ReadUInt16();
        }
        else if (major == 2 || major == 3)
        {
            headerLen = (int)reader.ReadUInt32();
        }
        else
        {
            throw new FormatException($"Unsupported .npy version {major}.{minor}");
        }

        byte[] headerBytes = reader.ReadBytes(headerLen);
        string headerStr = Encoding.ASCII.GetString(headerBytes);

        // Parse shape: e.g., 'shape': (511, 1, 256) or (512, 256) or (256,)
        var shapeMatch = Regex.Match(headerStr, @"'shape'\s*:\s*\(([^)]*)\)");
        if (!shapeMatch.Success)
        {
            throw new FormatException("Failed to parse shape from .npy header");
        }

        string shapeContent = shapeMatch.Groups[1].Value.Trim();
        int[] shape;
        if (string.IsNullOrWhiteSpace(shapeContent))
        {
            shape = Array.Empty<int>();
        }
        else
        {
            var parts = shapeContent.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            shape = Array.ConvertAll(parts, int.Parse);
        }

        int totalElements = 1;
        foreach (int dim in shape)
        {
            totalElements *= dim;
        }

        float[] data = new float[totalElements];
        byte[] buffer = reader.ReadBytes(totalElements * sizeof(float));
        Buffer.BlockCopy(buffer, 0, data, 0, buffer.Length);

        return (data, shape);
    }

    public static Dictionary<string, (float[] Data, int[] Shape)> ReadNpz(string npzPath)
    {
        var result = new Dictionary<string, (float[] Data, int[] Shape)>(StringComparer.OrdinalIgnoreCase);

        using var zip = ZipFile.OpenRead(npzPath);
        foreach (var entry in zip.Entries)
        {
            if (!entry.Name.EndsWith(".npy", StringComparison.OrdinalIgnoreCase))
                continue;

            string key = Path.GetFileNameWithoutExtension(entry.Name);
            using var entryStream = entry.Open();
            var npyData = ReadNpy(entryStream);
            result[key] = npyData;
        }

        return result;
    }

    private static bool IsMagicMatch(byte[] magic)
    {
        for (int i = 0; i < MagicBytes.Length; i++)
        {
            if (magic[i] != MagicBytes[i]) return false;
        }
        return true;
    }
}
