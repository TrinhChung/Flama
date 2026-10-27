using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using Flama.Audio.Engine.EdgeTts.Constants;

namespace Flama.Audio.Engine.EdgeTts.Cryptography;

public static class EdgeTtsDrm
{
    private const long WinEpoch = 11644473600L;
    private const double SToNs = 1e9;

    private static TimeSpan _clockSkew = TimeSpan.Zero;

    /// <summary>
    /// Clock skew offset applied when generating timestamps for Sec-MS-GEC v2 tokens.
    /// </summary>
    public static TimeSpan ClockSkew
    {
        get => _clockSkew;
        set => _clockSkew = value;
    }

    public static void SetClockSkew(TimeSpan skew) => _clockSkew = skew;
    public static void ResetClockSkew() => _clockSkew = TimeSpan.Zero;

    private static readonly uint[] Sha256Initial = {
        0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
        0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19
    };

    private static readonly uint[] Sha256State = {
        0xFD9FBEA2, 0x91243CE7, 0xBE499094, 0xCD2E1E0A,
        0x6C006F49, 0x04BD35AB, 0xFEB0A7E4, 0x03EFFBD2
    };

    private static readonly uint[] Sha256Schedule = {
        0xEB24BF9E, 0x1558691F, 0xA0C09EE2, 0x0CFA32BA,
        0xA622EE8C, 0xD1DD9491, 0xC0DD25A0, 0xF9E70AB6,
        0xF0C31573, 0x7058CE4E, 0x7188E606, 0x00E5AB33,
        0xD258B060, 0x72766564
    };

    private static readonly uint[] Sha256RoundConstants = {
        0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
        0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3, 0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
        0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
        0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
        0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13, 0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
        0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
        0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
        0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208, 0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2
    };

    private const uint Sha256Adjustment = 0xC9DC06A7;
    private static readonly uint[] Sha256BlockConstants = CreateBlockConstants();

    private static uint[] CreateBlockConstants()
    {
        var list = new uint[64];
        Array.Copy(Sha256RoundConstants, 0, list, 0, 14);
        list[14] = Sha256Adjustment;
        Array.Copy(Sha256RoundConstants, 15, list, 15, 49);
        return list;
    }

    private const uint Sha256Sigma0Adjustment = 0x059C0B80;
    private const uint Sha256Sigma1Adjustment = 0x000B92C0;

    private static readonly (uint Coeff, uint Offset)[] Cs64Coefficients = {
        (0xE82E91B1, 0xB32700D0), (0x44DE24C6, 0x88DFF51D),
        (0x3BEB65BC, 0x29514038), (0xC89C5933, 0xB328CBDF),
        (0x8D1EC211, 0xD405B4D5), (0x314EF5D5, 0x26E55F3C),
        (0xE92491B1, 0x607801C6), (0xF0A5B9D5, 0x82B2C1FB),
        (0x06064CF3, 0xFA51A3DA), (0xDA79FA60, 0x207CC464),
        (0xBED20560, 0x3C3C74F3), (0x89F9C9F8, 0xD2D14B61),
        (0x35FA38C6, 0xBB04A2C1), (0xCB49E3C6, 0xC5626167)
    };

    private const uint Cs64Factor = 0x82893933;
    private const uint Cs64Adjustment0 = 0xF2F90B1A;
    private const uint Cs64Adjustment1 = 0x0B1A0000;

    private static uint Rol16(uint value) => (value << 16) | (value >> 16);

    private static List<uint> WordsLe4Even(byte[] data)
    {
        int padLen = (-data.Length) & 3;
        var padded = new byte[data.Length + padLen];
        Array.Copy(data, 0, padded, 0, data.Length);

        var words = new List<uint>();
        for (int i = 0; i < padded.Length; i += 4)
        {
            words.Add(BinaryPrimitives.ReadUInt32LittleEndian(padded.AsSpan(i, 4)));
        }
        if ((words.Count % 2) != 0)
        {
            words.Add(0);
        }
        return words;
    }

    private static uint Sigma0(uint value) =>
        (value >> 7) ^ (value << 25) ^ (value >> 18) ^ (value << 14) ^ (value >> 3);

    private static uint Sigma1(uint value) =>
        (value >> 17) ^ (value << 15) ^ (value >> 19) ^ (value << 13) ^ (value >> 10);

    private static (uint a, uint b, uint c, uint d, uint e, uint f, uint g, uint h) Sha256Rounds(
        uint[] state, IList<uint> words, int firstRound = 0)
    {
        uint a = state[0], b = state[1], c = state[2], d = state[3];
        uint e = state[4], f = state[5], g = state[6], h = state[7];

        var constants = (firstRound == 14) ? Sha256BlockConstants : Sha256RoundConstants;
        int aligned = Math.Min(64, ((firstRound + 7) / 8) * 8);

        for (int index = firstRound; index < aligned; index++)
        {
            ulong rotE = (ulong)e * 0x100000001UL;
            ulong rotA = (ulong)a * 0x100000001UL;
            uint t1 = (uint)(h + ((rotE >> 6) ^ (rotE >> 11) ^ (rotE >> 25)) + (g ^ (e & (f ^ g))) + constants[index] + words[index]);
            uint t2 = (uint)(((rotA >> 2) ^ (rotA >> 13) ^ (rotA >> 22)) + ((a & b) | (c & (a | b))));
            h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }

        for (int index = aligned; index < 64; index += 8)
        {
            ulong rotE = (ulong)e * 0x100000001UL;
            ulong rotA = (ulong)a * 0x100000001UL;
            uint t1 = (uint)(h + ((rotE >> 6) ^ (rotE >> 11) ^ (rotE >> 25)) + (g ^ (e & (f ^ g))) + constants[index] + words[index]);
            d += t1;
            h = (uint)(t1 + ((rotA >> 2) ^ (rotA >> 13) ^ (rotA >> 22)) + ((a & b) | (c & (a | b))));

            rotE = (ulong)d * 0x100000001UL;
            rotA = (ulong)h * 0x100000001UL;
            t1 = (uint)(g + ((rotE >> 6) ^ (rotE >> 11) ^ (rotE >> 25)) + (f ^ (d & (e ^ f))) + constants[index + 1] + words[index + 1]);
            c += t1;
            g = (uint)(t1 + ((rotA >> 2) ^ (rotA >> 13) ^ (rotA >> 22)) + ((h & a) | (b & (h | a))));

            rotE = (ulong)c * 0x100000001UL;
            rotA = (ulong)g * 0x100000001UL;
            t1 = (uint)(f + ((rotE >> 6) ^ (rotE >> 11) ^ (rotE >> 25)) + (e ^ (c & (d ^ e))) + constants[index + 2] + words[index + 2]);
            b += t1;
            f = (uint)(t1 + ((rotA >> 2) ^ (rotA >> 13) ^ (rotA >> 22)) + ((g & h) | (a & (g | h))));

            rotE = (ulong)b * 0x100000001UL;
            rotA = (ulong)f * 0x100000001UL;
            t1 = (uint)(e + ((rotE >> 6) ^ (rotE >> 11) ^ (rotE >> 25)) + (d ^ (b & (c ^ d))) + constants[index + 3] + words[index + 3]);
            a += t1;
            e = (uint)(t1 + ((rotA >> 2) ^ (rotA >> 13) ^ (rotA >> 22)) + ((f & g) | (h & (f | g))));

            rotE = (ulong)a * 0x100000001UL;
            rotA = (ulong)e * 0x100000001UL;
            t1 = (uint)(d + ((rotE >> 6) ^ (rotE >> 11) ^ (rotE >> 25)) + (c ^ (a & (b ^ c))) + constants[index + 4] + words[index + 4]);
            h += t1;
            d = (uint)(t1 + ((rotA >> 2) ^ (rotA >> 13) ^ (rotA >> 22)) + ((e & f) | (g & (e | f))));

            rotE = (ulong)h * 0x100000001UL;
            rotA = (ulong)d * 0x100000001UL;
            t1 = (uint)(c + ((rotE >> 6) ^ (rotE >> 11) ^ (rotE >> 25)) + (b ^ (h & (a ^ b))) + constants[index + 5] + words[index + 5]);
            g += t1;
            c = (uint)(t1 + ((rotA >> 2) ^ (rotA >> 13) ^ (rotA >> 22)) + ((d & e) | (f & (d | e))));

            rotE = (ulong)g * 0x100000001UL;
            rotA = (ulong)c * 0x100000001UL;
            t1 = (uint)(b + ((rotE >> 6) ^ (rotE >> 11) ^ (rotE >> 25)) + (a ^ (g & (h ^ a))) + constants[index + 6] + words[index + 6]);
            f += t1;
            b = (uint)(t1 + ((rotA >> 2) ^ (rotA >> 13) ^ (rotA >> 22)) + ((c & d) | (e & (c | d))));

            rotE = (ulong)f * 0x100000001UL;
            rotA = (ulong)b * 0x100000001UL;
            t1 = (uint)(a + ((rotE >> 6) ^ (rotE >> 11) ^ (rotE >> 25)) + (h ^ (f & (g ^ h))) + constants[index + 7] + words[index + 7]);
            e += t1;
            a = (uint)(t1 + ((rotA >> 2) ^ (rotA >> 13) ^ (rotA >> 22)) + ((b & c) | (d & (b | c))));
        }

        return (a, b, c, d, e, f, g, h);
    }

    private static void ExpandSha256Schedule(List<uint> words, int firstWord = 16)
    {
        for (int index = firstWord; index < 64; index++)
        {
            uint x = words[index - 2], y = words[index - 15];
            uint s1 = Sigma1(x);
            uint s0 = Sigma0(y);
            words.Add(s1 + words[index - 7] + s0 + words[index - 16]);
        }
    }

    private static uint[] Sha256Init(ReadOnlySpan<byte> data)
    {
        var words = new List<uint>();
        for (int i = 0; i < 14; i++) words.Add(0);
        uint w14 = ((uint)data[0] << 16) | ((uint)data[1] << 8) | (uint)data[2];
        words.Add(w14);
        uint w15 = BinaryPrimitives.ReadUInt32BigEndian(data.Slice(3, 4));
        words.Add(w15);

        for (int index = 16; index < 30; index++)
        {
            uint value = Sha256Schedule[index - 16];
            if (index - 2 >= 14)
            {
                value += (index == 16) ? (Sigma1(words[index - 2]) ^ Sha256Sigma1Adjustment) : Sigma1(words[index - 2]);
            }
            if (index - 7 >= 14)
            {
                value += words[index - 7];
            }
            if (index - 15 >= 14)
            {
                value += (index == 29) ? (Sigma0(words[index - 15]) ^ Sha256Sigma0Adjustment) : Sigma0(words[index - 15]);
            }
            words.Add(value);
        }

        uint w30 = Sigma1(words[28]) + words[23] + Sigma0(words[15]) + words[14] + Sha256Adjustment - Sha256RoundConstants[14];
        words.Add(w30);

        ExpandSha256Schedule(words, 31);
        var working = Sha256Rounds(Sha256State, words, 14);

        return new uint[] {
            Sha256Initial[0] + working.a,
            Sha256Initial[1] + working.b,
            Sha256Initial[2] + working.c,
            Sha256Initial[3] + working.d,
            Sha256Initial[4] + working.e,
            Sha256Initial[5] + working.f,
            Sha256Initial[6] + working.g,
            Sha256Initial[7] + working.h
        };
    }

    private static byte[] Sha256Digest(byte[] data)
    {
        if (data.Length < 7) throw new ArgumentException("Token salt must contain at least seven bytes");
        int length = 57 + data.Length;
        int padZeroCount = (55 - length) % 64;
        if (padZeroCount < 0) padZeroCount += 64;

        int paddedLen = (data.Length - 7) + 1 + padZeroCount + 8;
        var padded = new byte[paddedLen];
        Array.Copy(data, 7, padded, 0, data.Length - 7);
        int pos = data.Length - 7;
        padded[pos++] = 0x80;
        pos += padZeroCount;
        BinaryPrimitives.WriteUInt64BigEndian(padded.AsSpan(pos, 8), (ulong)length * 8UL);

        uint[] state = Sha256Init(data.AsSpan(0, 7));
        for (int offset = 0; offset < padded.Length; offset += 64)
        {
            var words = new List<uint>();
            for (int i = 0; i < 64; i += 4)
            {
                words.Add(BinaryPrimitives.ReadUInt32BigEndian(padded.AsSpan(offset + i, 4)));
            }
            ExpandSha256Schedule(words);
            var working = Sha256Rounds(state, words);
            state[0] += working.a;
            state[1] += working.b;
            state[2] += working.c;
            state[3] += working.d;
            state[4] += working.e;
            state[5] += working.f;
            state[6] += working.g;
            state[7] += working.h;
        }

        var result = new byte[32];
        for (int i = 0; i < 8; i++)
        {
            BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(i * 4, 4), state[i]);
        }
        return result;
    }

    private static (uint, uint) Cs64Digest(byte[] data, byte[] digest)
    {
        uint keyA = BinaryPrimitives.ReadUInt32LittleEndian(digest.AsSpan(0, 4)) | 1;
        uint keyB = BinaryPrimitives.ReadUInt32LittleEndian(digest.AsSpan(4, 4)) | 1;

        uint factor0 = keyA * Cs64Factor;
        uint factor1 = keyB * Cs64Factor;

        var terms = new List<uint>();
        var offsets = new List<uint>();

        for (int i = 0; i < Cs64Coefficients.Length; i++)
        {
            terms.Add(Cs64Coefficients[i].Coeff * (i % 2 == 0 ? factor0 : factor1));
            offsets.Add(Cs64Coefficients[i].Offset);
        }

        var dataWithZero = new byte[data.Length + 1];
        dataWithZero[0] = 0;
        Array.Copy(data, 0, dataWithZero, 1, data.Length);

        var words = WordsLe4Even(dataWithZero);
        for (int index = 0; index < words.Count; index++)
        {
            uint word = words[index];
            uint term = word * (index % 2 == 0 ? keyA : keyB);
            uint offset = Rol16(word) * (index % 2 == 0 ? 0xEF0569FBu : 0xC31713DBu);
            if (index == 0)
            {
                term += Cs64Adjustment0 * factor0;
                offset += Cs64Adjustment1;
            }
            terms.Add(term);
            offsets.Add(offset);
        }

        uint swapAcc = 0, swapLast = 0, state = 0, acc = 0;
        for (int index = 0; index < terms.Count; index += 2)
        {
            uint x = terms[index], y = terms[index + 1];
            uint t = Rol16(offsets[index] + x);
            uint q = t * 0x76F50F34u;
            swapAcc += Rol16(q) * 0xC3EFEA97u + q;

            t = Rol16(offsets[index + 1] + y);
            q = t * 0x1881CE3Cu;
            swapLast = Rol16(q) * 0x35BD1EC9u + q;
            swapAcc += swapLast;

            state = state * keyA + x;
            state = Rol16(state) * 0xCF98B111u;
            state = Rol16(state) * 0x87085B9Fu;
            state = Rol16(state) * 0x12CEB96Du;
            state = Rol16(state) * 0x257E1D83u;
            acc += state;

            t = state * keyB + y;
            t = Rol16(t) * 0xA27416F5u;
            t = Rol16(t) * 0xD38396FFu;
            state = Rol16(Rol16(t) * 0x7C932B89u) * 0xBFA49F69u;
            acc += state;
        }

        return (swapLast ^ state, swapAcc ^ acc);
    }

    /// <summary>
    /// Generates the Sec-MS-GEC v2 token in format {cs64}-{sha256}.
    /// </summary>
    /// <param name="unixTimestamp">Optional unix timestamp. If null, current UTC time adjusted for clock skew is used.</param>
    /// <param name="trustedClientToken">Client token, default is EdgeTtsConstants.TrustedClientToken.</param>
    /// <returns>Formatted token string.</returns>
    public static string GenerateSecMsGecV2(double? unixTimestamp = null, string? trustedClientToken = null)
    {
        double timestamp = unixTimestamp ?? (DateTimeOffset.UtcNow + _clockSkew).ToUnixTimeSeconds();
        double ticks = timestamp + WinEpoch;
        ticks -= ticks % 300;
        ticks *= SToNs / 100;

        string token = trustedClientToken ?? EdgeTtsConstants.TrustedClientToken;
        string strToHash = $"{ticks:0}{token}";
        byte[] data = Encoding.ASCII.GetBytes(strToHash);

        byte[] sha256 = Sha256Digest(data);
        var (c0, c1) = Cs64Digest(data, sha256);

        byte[] cs64Bytes = new byte[8];
        BinaryPrimitives.WriteUInt32LittleEndian(cs64Bytes.AsSpan(0, 4), c0);
        BinaryPrimitives.WriteUInt32LittleEndian(cs64Bytes.AsSpan(4, 4), c1);

        return $"{Convert.ToHexString(cs64Bytes)}-{Convert.ToHexString(sha256)}";
    }

    /// <summary>
    /// Generates the Sec-MS-GEC v2 token using a DateTimeOffset.
    /// </summary>
    public static string GenerateSecMsGecV2(DateTimeOffset timestamp, string? trustedClientToken = null)
    {
        return GenerateSecMsGecV2(timestamp.ToUnixTimeSeconds(), trustedClientToken);
    }

    /// <summary>
    /// Generates a cryptographically random 16-byte MUID hex string (32 uppercase hex characters).
    /// </summary>
    public static string GenerateMuid()
    {
        byte[] muid = new byte[16];
        RandomNumberGenerator.Fill(muid);
        return Convert.ToHexString(muid);
    }

    /// <summary>
    /// Generates standard MUID cookie header value ("muid={32 hex};").
    /// </summary>
    public static string GenerateMuidCookie()
    {
        return $"muid={GenerateMuid()};";
    }
}
