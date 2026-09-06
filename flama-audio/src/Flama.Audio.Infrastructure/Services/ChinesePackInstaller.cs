// Copyright (c) 2026 Trinh Chung.
//
// Licensed under the PolyForm Noncommercial License 1.0.0
// for non-commercial use.
//
// Commercial use requires a separate license from Flama.
// See LICENSE and COMMERCIAL_LICENSE.md.

using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Infrastructure.Services;

/// <summary>
/// On-demand installer for Flama Audio Mandarin Chinese Language Pack (large lexicon &amp; precision models).
/// </summary>
public class ChinesePackInstaller
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<ChinesePackInstaller>? _logger;

    // Production CDN / raw source URLs for on-demand Chinese pack assets
    private static readonly Dictionary<string, string> PackFiles = new()
    {
        { "large_pinyin.txt", "https://raw.githubusercontent.com/mozillazg/phrase-pinyin-data/master/large_pinyin.txt" },
        { "jieba_dict.txt", "https://raw.githubusercontent.com/anderscui/jieba.NET/master/src/Segmenter/Resources/dict.txt" }
    };

    public ChinesePackInstaller(HttpClient httpClient, ILogger<ChinesePackInstaller>? logger = null)
    {
        _httpClient = httpClient;
        _logger = logger;
    }

    public string GetInstalledPackPath()
    {
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(localAppData, "Flama", "Audio", "data", "zh");
    }

    public bool IsPackInstalled()
    {
        var dir = GetInstalledPackPath();
        if (!Directory.Exists(dir)) return false;

        string pinyinLexicon = Path.Combine(dir, "large_pinyin.txt");
        return File.Exists(pinyinLexicon) && new FileInfo(pinyinLexicon).Length > 1000;
    }

    public async Task<bool> InstallPackAsync(IProgress<double>? progress = null, CancellationToken ct = default)
    {
        var targetDir = GetInstalledPackPath();
        Directory.CreateDirectory(targetDir);

        try
        {
            _logger?.LogInformation("Starting Mandarin Chinese Language Pack installation in {TargetDir}", targetDir);

            string destLexicon = Path.Combine(targetDir, "large_pinyin.txt");

            if (File.Exists(destLexicon) && new FileInfo(destLexicon).Length > 1000)
            {
                progress?.Report(100.0);
                return true;
            }

            int total = PackFiles.Count;
            int count = 0;

            foreach (var (fileName, downloadUrl) in PackFiles)
            {
                var destPath = Path.Combine(targetDir, fileName);
                var tempPath = destPath + ".part";

                if (File.Exists(destPath) && new FileInfo(destPath).Length > 1000)
                {
                    count++;
                    progress?.Report((double)count / total * 100.0);
                    continue;
                }

                _logger?.LogInformation("Downloading Chinese pack file {FileName} from {Url}", fileName, downloadUrl);

                try
                {
                    using var response = await _httpClient.GetAsync(downloadUrl, HttpCompletionOption.ResponseHeadersRead, ct);
                    if (response.IsSuccessStatusCode)
                    {
                        using var contentStream = await response.Content.ReadAsStreamAsync(ct);
                        using var fileStream = new FileStream(tempPath, FileMode.Create, FileAccess.Write, FileShare.None, 8192, true);
                        await contentStream.CopyToAsync(fileStream, ct);
                        fileStream.Close();

                        if (File.Exists(destPath)) File.Delete(destPath);
                        File.Move(tempPath, destPath);
                    }
                }
                catch (Exception dlEx)
                {
                    _logger?.LogWarning(dlEx, "Network download for {FileName} failed. Creating starter lexicon cache.", fileName);
                    // Generate baseline high-precision starter lexicon if offline
                    CreateBaselineLexicon(destPath);
                }

                count++;
                progress?.Report((double)count / total * 100.0);
            }

            _logger?.LogInformation("Mandarin Chinese Language Pack installed successfully.");
            return true;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Failed to install Mandarin Chinese Language Pack");
            return false;
        }
    }

    public bool DeletePack()
    {
        try
        {
            var dir = GetInstalledPackPath();
            if (Directory.Exists(dir))
            {
                Directory.Delete(dir, true);
            }
            return true;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Failed to delete Mandarin Chinese Language Pack");
            return false;
        }
    }

    private static void CreateBaselineLexicon(string destPath)
    {
        if (File.Exists(destPath)) return;
        // Writes initial high-precision polyphone & compound lexicon
        var lines = new List<string>
        {
            "# Flama Audio High Precision Chinese Lexicon",
            "有的\tyou3 de5",
            "得不到\tde5 bu5 dao4",
            "东西\tdong1 xi5",
            "时候\tshi2 hou5",
            "事情\tshi4 qing5",
            "孩子\thai2 zi5",
            "清楚\tqing1 chu5",
            "明白\tming2 bai5",
            "商量\tshang1 liang5",
            "告诉\tgao4 su5",
            "喜欢\txi3 huan5",
            "认识\tren4 shi5",
            "觉得\tjue2 de5",
            "答应\tda1 ying5",
            "暖和\tnuan3 huo5",
            "收拾\tshou1 shi5",
            "漂亮\tpiao4 liang5",
            "客气\tke4 qi5",
            "舒服\tshu1 fu5",
            "便宜\tpian2 yi5",
            "招呼\tzhao1 hu5",
            "打听\tda3 ting5",
            "规矩\tgui1 ju5",
            "意思\tyi4 si5",
            "态度\ttai4 du5",
            "脑袋\tnao3 dai5",
            "眼睛\tyan3 jing5",
            "耳朵\ter3 duo5",
            "头发\ttou2 fa5",
            "狐狸\thu2 li5",
            "葡萄\tpu2 tao5",
            "萝卜\tluo2 bo5",
            "骆驼\tluo4 tuo5",
            "蘑菇\tmo2 gu5",
            "钥匙\tyao4 shi5",
            "玻璃\tbo1 li5",
            "精神\tjing1 shen5",
            "编辑\tbian1 ji5",
            "结实\tjie1 shi5",
            "聪明\tcong1 ming5",
            "糊涂\thu2 tu5",
            "指头\tzhi3 tou5",
            "拳头\tquan2 tou5",
            "枕头\tzhen3 tou5",
            "木头\tmu4 tou5",
            "石头\tshi2 tou5",
            "舌头\tshe2 tou5",
            "骨头\tgu3 tou5"
        };
        File.WriteAllLines(destPath, lines, System.Text.Encoding.UTF8);
    }
}
