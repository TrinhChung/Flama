using System;
using System.Text.RegularExpressions;
using Flama.Audio.Engine.EdgeTts.Cryptography;
using Xunit;

namespace Flama.Audio.Tests;

public class EdgeTtsDrmTests : IDisposable
{
    public EdgeTtsDrmTests()
    {
        EdgeTtsDrm.ResetClockSkew();
    }

    public void Dispose()
    {
        EdgeTtsDrm.ResetClockSkew();
    }

    [Fact]
    public void GenerateSecMsGecV2_KnownVector_1730000000_BitParityMatches()
    {
        const double timestamp = 1730000000.0;
        const string expected = "50065ABF67B90F95-49BDAF24D28ECEB38DAEEC84DEAA71E91F92945EA8A47921C58FB4F8F79A4F5E";

        string actual = EdgeTtsDrm.GenerateSecMsGecV2(timestamp);

        Assert.Equal(expected, actual);
    }

    [Fact]
    public void GenerateSecMsGecV2_KnownVector_1700000000_BitParityMatches()
    {
        const double timestamp = 1700000000.0;
        const string expected = "2CD23A2CA0B2595A-F3C846C370E05F9CC83ACC5F995C5F5D87A4D0F14CE8936A0F902E64099E38A2";

        string actual = EdgeTtsDrm.GenerateSecMsGecV2(timestamp);

        Assert.Equal(expected, actual);
    }

    [Fact]
    public void GenerateSecMsGecV2_DateTimeOffsetOverload_MatchesUnixTimestamp()
    {
        var dto = DateTimeOffset.FromUnixTimeSeconds(1730000000);
        const string expected = "50065ABF67B90F95-49BDAF24D28ECEB38DAEEC84DEAA71E91F92945EA8A47921C58FB4F8F79A4F5E";

        string actual = EdgeTtsDrm.GenerateSecMsGecV2(dto);

        Assert.Equal(expected, actual);
    }

    [Fact]
    public void GenerateSecMsGecV2_FormatStructure_Is16HexDash64Hex()
    {
        string token = EdgeTtsDrm.GenerateSecMsGecV2();

        Assert.NotNull(token);
        Assert.Matches("^[0-9A-F]{16}-[0-9A-F]{64}$", token);
    }

    [Fact]
    public void GenerateSecMsGecV2_CustomToken_ChangesHash()
    {
        const double timestamp = 1730000000.0;
        string defaultToken = EdgeTtsDrm.GenerateSecMsGecV2(timestamp);
        string customToken = EdgeTtsDrm.GenerateSecMsGecV2(timestamp, "CUSTOM_CLIENT_TOKEN_12345");

        Assert.NotEqual(defaultToken, customToken);
    }

    [Fact]
    public void GenerateMuid_Produces32UppercaseHexChars()
    {
        string muid = EdgeTtsDrm.GenerateMuid();

        Assert.NotNull(muid);
        Assert.Equal(32, muid.Length);
        Assert.Matches("^[0-9A-F]{32}$", muid);
    }

    [Fact]
    public void GenerateMuid_ProducesUniqueValues()
    {
        string muid1 = EdgeTtsDrm.GenerateMuid();
        string muid2 = EdgeTtsDrm.GenerateMuid();

        Assert.NotEqual(muid1, muid2);
    }

    [Fact]
    public void GenerateMuidCookie_ProducesCorrectCookieHeader()
    {
        string cookie = EdgeTtsDrm.GenerateMuidCookie();

        Assert.NotNull(cookie);
        Assert.StartsWith("muid=", cookie);
        Assert.EndsWith(";", cookie);
        Assert.Matches("^muid=[0-9A-F]{32};$", cookie);
    }

    [Fact]
    public void ClockSkew_AdjustsCurrentTimestamp()
    {
        EdgeTtsDrm.SetClockSkew(TimeSpan.FromMinutes(2));
        Assert.Equal(TimeSpan.FromMinutes(2), EdgeTtsDrm.ClockSkew);

        EdgeTtsDrm.SetClockSkew(TimeSpan.FromHours(2));
        string skewedToken = EdgeTtsDrm.GenerateSecMsGecV2();

        EdgeTtsDrm.ResetClockSkew();
        Assert.Equal(TimeSpan.Zero, EdgeTtsDrm.ClockSkew);
        string normalToken = EdgeTtsDrm.GenerateSecMsGecV2();

        Assert.NotEqual(normalToken, skewedToken);
    }
}
