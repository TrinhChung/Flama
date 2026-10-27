using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Media;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Core.Models;
using Flama.Audio.Engine.Kokoro;
using Flama.Audio.Infrastructure.Services;

namespace Flama.Audio.App;

public partial class MainWindow : Window
{
    private readonly IPairingManager? _pairingManager;
    private readonly IEngineRouter? _engineRouter;
    private readonly VoicevoxEngineInstaller? _voicevoxInstaller;
    private readonly KokoroEngineInstaller? _kokoroInstaller;
    private readonly ChinesePackInstaller? _chinesePackInstaller;

    private string _currentDetailEngineId = "voicevox";
    private bool _isPopulatingLanguages = false;
    private MediaPlayer? _mediaPlayer;
    private static System.Collections.Generic.List<(string Content, string Tag)>? _cachedEdgeTtsLocales;

    public MainWindow()
    {
        InitializeComponent();
    }

    public MainWindow(
        IPairingManager pairingManager,
        IEngineRouter engineRouter,
        VoicevoxEngineInstaller voicevoxInstaller,
        KokoroEngineInstaller kokoroInstaller,
        ChinesePackInstaller? chinesePackInstaller = null) : this()
    {
        _pairingManager = pairingManager;
        _engineRouter = engineRouter;
        _voicevoxInstaller = voicevoxInstaller;
        _kokoroInstaller = kokoroInstaller;
        _chinesePackInstaller = chinesePackInstaller;

        if (_pairingManager != null)
        {
            _pairingManager.OnPairingRequested += (s, e) =>
            {
                Dispatcher.Invoke(() =>
                {
                    RefreshData();
                    if (WindowState == WindowState.Minimized) WindowState = WindowState.Normal;
                    Activate();
                });
            };
        }

        // Live log streaming to LogOutputTextBox
        AppLogStore.Instance.OnLogAdded += entry =>
        {
            Dispatcher.Invoke(() =>
            {
                if (ViewLogs.Visibility == Visibility.Visible)
                {
                    RefreshLogDisplay();
                }
            });
        };

        ShowInstalledView();
        RefreshData();
    }

    // --- NAVIGATION LOGIC ---

    private void OnNavInstalledClicked(object sender, RoutedEventArgs e) => ShowInstalledView();
    private void OnNavUninstalledClicked(object sender, RoutedEventArgs e) => ShowUninstalledView();
    private void OnNavPairingClicked(object sender, RoutedEventArgs e) => ShowPairingView();
    private void OnNavLogsClicked(object sender, RoutedEventArgs e) => ShowLogsView();
    private void OnBackToListClicked(object sender, RoutedEventArgs e) => ShowInstalledView();

    private void ShowInstalledView()
    {
        ViewInstalledEngines.Visibility = Visibility.Visible;
        ViewEngineDetail.Visibility = Visibility.Collapsed;
        ViewUninstalledEngines.Visibility = Visibility.Collapsed;
        ViewPairing.Visibility = Visibility.Collapsed;
        ViewLogs.Visibility = Visibility.Collapsed;

        ViewTitleTextBlock.Text = "Quản lý TTS Engines • Các Engine đã sẵn sàng";
        BtnBackToList.Visibility = Visibility.Collapsed;

        HighlightTabButton(BtnNavInstalled);
        RefreshData();
    }

    private void ShowUninstalledView()
    {
        ViewInstalledEngines.Visibility = Visibility.Collapsed;
        ViewEngineDetail.Visibility = Visibility.Collapsed;
        ViewUninstalledEngines.Visibility = Visibility.Visible;
        ViewPairing.Visibility = Visibility.Collapsed;
        ViewLogs.Visibility = Visibility.Collapsed;

        ViewTitleTextBlock.Text = "Cài đặt TTS Engines mới";
        BtnBackToList.Visibility = Visibility.Collapsed;

        HighlightTabButton(BtnNavUninstalled);
        RefreshData();
    }

    private void ShowPairingView()
    {
        ViewInstalledEngines.Visibility = Visibility.Collapsed;
        ViewEngineDetail.Visibility = Visibility.Collapsed;
        ViewUninstalledEngines.Visibility = Visibility.Collapsed;
        ViewPairing.Visibility = Visibility.Visible;
        ViewLogs.Visibility = Visibility.Collapsed;

        ViewTitleTextBlock.Text = "Yêu cầu Ghép nối từ Flama Web Client";
        BtnBackToList.Visibility = Visibility.Collapsed;

        HighlightTabButton(BtnNavPairing);
        RefreshData();
    }

    private void ShowLogsView()
    {
        ViewInstalledEngines.Visibility = Visibility.Collapsed;
        ViewEngineDetail.Visibility = Visibility.Collapsed;
        ViewUninstalledEngines.Visibility = Visibility.Collapsed;
        ViewPairing.Visibility = Visibility.Collapsed;
        ViewLogs.Visibility = Visibility.Visible;

        ViewTitleTextBlock.Text = "Nhật ký Hoạt động & Log Lỗi Service Debug";
        BtnBackToList.Visibility = Visibility.Visible;

        ResetTabButtonHighlights();
        RefreshLogDisplay();
    }

    // --- TOP MENU HANDLERS ---

    private void OnExitClicked(object sender, RoutedEventArgs e)
    {
        Application.Current.Shutdown();
    }

    private void OnOpenWebClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = "http://localhost:5173",
                UseShellExecute = true
            });
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể mở trình duyệt: {ex.Message}", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
        }
    }

    private void OnAboutClicked(object sender, RoutedEventArgs e)
    {
        MessageBox.Show(
            "Flama Audio Local Service v1.1.0\n\n" +
            "Trợ lý tổng hợp phát âm đa ngôn ngữ cho hệ sinh thái Flama.\n" +
            "• Tiếng Nhật: VOICEVOX Engine (Port 50021)\n" +
            "• Tiếng Anh & Trung: Kokoro-82M Neural Engine (C# Native + ONNX Runtime CPU)\n" +
            "• Đa ngôn ngữ trực tuyến: Microsoft Edge TTS (320+ giọng đọc AI)\n\n" +
            "Flama G2P\n" +
            "Source Available\n" +
            "Free for non-commercial use under PolyForm Noncommercial 1.0.0.\n" +
            "Commercial use requires a separate Flama license.\n\n" +
            "See the licenses directory for license and third-party notices.\n\n" +
            "Phát triển bởi đội ngũ Flama.",
            "Về Flama Audio",
            MessageBoxButton.OK,
            MessageBoxImage.Information
        );
    }

    private async void ShowEngineDetailView(string engineId)
    {
        _currentDetailEngineId = engineId;

        ViewInstalledEngines.Visibility = Visibility.Collapsed;
        ViewEngineDetail.Visibility = Visibility.Visible;
        ViewUninstalledEngines.Visibility = Visibility.Collapsed;
        ViewPairing.Visibility = Visibility.Collapsed;

        BtnBackToList.Visibility = Visibility.Visible;
        ResetTabButtonHighlights();

        if (engineId == "edge-tts")
        {
            DetailEngineTitle.Text = "MICROSOFT EDGE TTS (ONLINE ENGINE)";
            DetailEngineBadgeText.Text = "Đa Ngôn Ngữ (Cloud Native)";
            DetailEngineBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#F3E8FF"));
            DetailEngineBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E9D5FF"));
            DetailEngineBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#7E22CE"));

            DetailEngineDescription.Text = "Hệ thống giọng đọc AI đa ngôn ngữ trực tuyến từ Microsoft Edge với hơn 320 giọng đọc tự nhiên.";
            ViewTitleTextBlock.Text = "Chi tiết Engine & Test Voice > Microsoft Edge TTS (Đa Ngôn Ngữ)";
        }
        else if (engineId == "kokoro")
        {
            DetailEngineTitle.Text = "🇺🇸/🌐 Kokoro-82M Neural Engine";
            DetailEngineBadgeText.Text = "Đa Ngôn Ngữ (Multi-Language)";
            DetailEngineBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#EFF6FF"));
            DetailEngineBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#93C5FD"));
            DetailEngineBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#1D4ED8"));

            DetailEngineDescription.Text = "Mô hình TTS Kokoro-82M hỗ trợ đa ngôn ngữ offline (Tiếng Anh, Trung, Tây Ban Nha, Pháp, Ý, Bồ Đào Nha...).";
            ViewTitleTextBlock.Text = "Chi tiết Engine & Test Voice > Kokoro-82M (Đa Ngôn Ngữ)";
        }
        else
        {
            DetailEngineTitle.Text = "🇯🇵 VOICEVOX Local Engine";
            DetailEngineBadgeText.Text = "Tiếng Nhật (Japanese)";
            DetailEngineBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFF1E7"));
            DetailEngineBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FEA46B"));
            DetailEngineBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E05C07"));

            DetailEngineDescription.Text = "Bộ tổng hợp phát âm tiếng Nhật VOICEVOX Engine Standalone CPU (Port 50021). Hỗ trợ giọng đọc Zundamon, Metan và hơn 20 nhân vật khác.";
            ViewTitleTextBlock.Text = "Chi tiết Engine & Test Voice > VOICEVOX (Japanese)";
        }

        // Populate Language Selector
        _isPopulatingLanguages = true;
        TestLanguageComboBox.Items.Clear();
        if (engineId == "voicevox")
        {
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇯🇵 Tiếng Nhật (Japanese)", Tag = "ja-JP" });
            _isPopulatingLanguages = false;
            TestLanguageComboBox.SelectedIndex = 0;
        }
        else if (engineId == "kokoro")
        {
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇺🇸 Tiếng Anh - Mỹ (English US)", Tag = "en-US" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇬🇧 Tiếng Anh - Anh (English UK)", Tag = "en-GB" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇨🇳 Tiếng Trung (Mandarin Chinese)", Tag = "zh-CN" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇪🇸 Tiếng Tây Ban Nha (Spanish)", Tag = "es-ES" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇫🇷 Tiếng Pháp (French)", Tag = "fr-FR" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇮🇳 Tiếng Hindi", Tag = "hi-IN" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇮🇹 Tiếng Ý (Italian)", Tag = "it-IT" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇧🇷 Tiếng Bồ Đào Nha (Portuguese)", Tag = "pt-BR" });
            _isPopulatingLanguages = false;
            TestLanguageComboBox.SelectedIndex = 0;
        }
        else if (engineId == "edge-tts")
        {
            // Tier 1: Featured languages
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇯🇵 Tiếng Nhật (Japanese) [ja-JP]", Tag = "ja-JP" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇻🇳 Tiếng Việt (Vietnamese) [vi-VN]", Tag = "vi-VN" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇺🇸 Tiếng Anh - Mỹ (English US) [en-US]", Tag = "en-US" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇬🇧 Tiếng Anh - Anh (English UK) [en-GB]", Tag = "en-GB" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇨🇳 Tiếng Trung (Mandarin) [zh-CN]", Tag = "zh-CN" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇰🇷 Tiếng Hàn (Korean) [ko-KR]", Tag = "ko-KR" });

            // Separator
            TestLanguageComboBox.Items.Add(new ComboBoxItem
            {
                Content = "────────── Tất cả ngôn ngữ khác (All Locales) ──────────",
                Tag = "",
                IsEnabled = false
            });

            // Tier 2: All other 100+ locales from Edge TTS catalog (Cached for 0ms lag)
            var adapter = _engineRouter?.GetAdapter("edge-tts");
            if (adapter != null)
            {
                try
                {
                    if (_cachedEdgeTtsLocales == null)
                    {
                        var voices = await adapter.ListVoicesAsync();
                        var featured = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
                        {
                            "ja-JP", "vi-VN", "en-US", "en-GB", "zh-CN", "ko-KR"
                        };

                        var otherLocales = voices
                            .Select(v => v.Locale)
                            .Where(loc => !string.IsNullOrWhiteSpace(loc) && !featured.Contains(loc))
                            .Distinct(StringComparer.OrdinalIgnoreCase)
                            .OrderBy(loc => loc, StringComparer.OrdinalIgnoreCase)
                            .ToList();

                        var list = new System.Collections.Generic.List<(string Content, string Tag)>();
                        foreach (var loc in otherLocales)
                        {
                            string displayName = loc;
                            try
                            {
                                displayName = System.Globalization.CultureInfo.GetCultureInfo(loc).DisplayName;
                            }
                            catch
                            {
                                displayName = loc;
                            }

                            list.Add(($"🌐 {displayName} [{loc}]", loc));
                        }
                        _cachedEdgeTtsLocales = list;
                    }

                    if (_currentDetailEngineId == "edge-tts")
                    {
                        foreach (var (locContent, locTag) in _cachedEdgeTtsLocales)
                        {
                            TestLanguageComboBox.Items.Add(new ComboBoxItem
                            {
                                Content = locContent,
                                Tag = locTag
                            });
                        }
                    }
                }
                catch (Exception ex)
                {
                    AppLogStore.Instance.AddLog(LogSeverity.Warning, "WPF", $"Error loading Edge TTS locales: {ex.Message}");
                }
            }

            if (_currentDetailEngineId == "edge-tts")
            {
                _isPopulatingLanguages = false;
                TestLanguageComboBox.SelectedIndex = 0;
            }
        }
    }

    private void HighlightTabButton(Button activeButton)
    {
        ResetTabButtonHighlights();
        activeButton.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFF1E7"));
        activeButton.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FEA46B"));
        activeButton.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E05C07"));
    }

    private void ResetTabButtonHighlights()
    {
        var inactiveBg = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFFFFF"));
        var inactiveBorder = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E9DDD4"));
        var inactiveText = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#1F1A17"));

        BtnNavInstalled.Background = inactiveBg;
        BtnNavInstalled.BorderBrush = inactiveBorder;
        BtnNavInstalled.Foreground = inactiveText;

        BtnNavUninstalled.Background = inactiveBg;
        BtnNavUninstalled.BorderBrush = inactiveBorder;
        BtnNavUninstalled.Foreground = inactiveText;

        BtnNavPairing.Background = inactiveBg;
        BtnNavPairing.BorderBrush = inactiveBorder;
        BtnNavPairing.Foreground = inactiveText;
    }

    // --- LOG MANAGEMENT & DEBUGGING ---

    private void RefreshLogDisplay()
    {
        if (LogOutputTextBox == null) return;

        string tag = (LogFilterComboBox?.SelectedItem as ComboBoxItem)?.Tag as string ?? "All";
        LogSeverity? minSeverity = tag switch
        {
            "Error" => LogSeverity.Error,
            "Warning" => LogSeverity.Warning,
            "Info" => LogSeverity.Info,
            _ => null
        };

        string logs = AppLogStore.Instance.GetFormattedLogs(minSeverity);
        LogOutputTextBox.Text = string.IsNullOrEmpty(logs) ? "[Chưa có log nhật ký nào]" : logs;
        LogOutputTextBox.ScrollToEnd();
    }

    private void OnLogFilterChanged(object sender, SelectionChangedEventArgs e)
    {
        RefreshLogDisplay();
    }

    private void OnCopyAllLogsClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            string logs = AppLogStore.Instance.GetFormattedLogs();
            if (string.IsNullOrWhiteSpace(logs))
            {
                MessageBox.Show("Hiện chưa có log nào để copy.", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            Clipboard.SetText(logs);
            MessageBox.Show("📋 Đã copy toàn bộ Nhật ký & Log vào Clipboard thành công!\nBạn có thể dán (Ctrl+V) để gửi cho đội hỗ trợ.", "Đã Copy Log", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể copy log vào Clipboard: {ex.Message}", "Lỗi", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OnCopyErrorLogsClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            string errors = AppLogStore.Instance.GetFormattedErrorsOnly();
            if (string.IsNullOrWhiteSpace(errors))
            {
                MessageBox.Show("🎉 Hiện không có log lỗi nào!", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            Clipboard.SetText(errors);
            MessageBox.Show("🚨 Đã copy tất cả Log Lỗi (Errors & Stack Traces) vào Clipboard!", "Đã Copy Log Lỗi", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể copy log lỗi vào Clipboard: {ex.Message}", "Lỗi", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OnOpenLogFolderClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            string logPath = AppLogStore.Instance.LogFilePath;
            string logDir = Path.GetDirectoryName(logPath) ?? "";
            if (Directory.Exists(logDir))
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = logDir,
                    UseShellExecute = true
                });
            }
            else
            {
                MessageBox.Show($"Thư mục log chưa được tạo tại: {logDir}", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể mở thư mục log: {ex.Message}", "Lỗi", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OnClearLogsClicked(object sender, RoutedEventArgs e)
    {
        AppLogStore.Instance.Clear();
        RefreshLogDisplay();
    }

    // --- ENGINE ACTIONS & VOICE TESTING ---

    private void OnOpenEngineDetailClicked(object sender, RoutedEventArgs e)
    {
        if (sender is Button btn && btn.Tag is string engineId)
        {
            ShowEngineDetailView(engineId);
        }
    }

    private async void OnTestLanguageChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_isPopulatingLanguages) return;

        var selectedItem = TestLanguageComboBox.SelectedItem as ComboBoxItem;
        var langTag = selectedItem?.Tag as string;
        if (string.IsNullOrEmpty(langTag)) return;

        // 1. Update Sample Text corresponding to language
        UpdateSampleText(langTag);

        // 2. Populate Voice Selector filtered by language tag
        await PopulateVoiceSelectorAsync(_currentDetailEngineId, langTag);
    }

    private void UpdateSampleText(string langTag)
    {
        TestSampleTextBox.Text = langTag switch
        {
            "ja-JP" => "こんにちは！Flama Audioへようこそ！",
            "vi-VN" => "Xin chào! Chào mừng bạn đến với Flama Audio!",
            "en-US" => "Hello! Welcome to Flama Audio desktop companion!",
            "en-GB" => "Hello! Welcome to Flama Audio desktop companion!",
            "zh-CN" => "你好！欢迎使用 Flama Audio！",
            "ko-KR" => "안녕하세요! Flama Audio에 오신 것을 환영합니다!",
            "es-ES" => "¡Hola! Bienvenido a la síntesis de voz local de Flama Audio.",
            "fr-FR" => "Bonjour, bienvenue sur la synthèse vocale locale de Flama Audio.",
            "hi-IN" => "नमस्ते, फ्लामा ऑडियो लोकल स्पीच सिंथेसिस में आपका स्वागत है।",
            "it-IT" => "Ciao, benvenuto nella sintesi vocale locale di Flama Audio.",
            "pt-BR" => "Olá, bem-vindo à síntese de voz local do Flama Audio.",
            _ => "Hello! Welcome to Flama Audio desktop companion!"
        };
    }

    private async Task PopulateVoiceSelectorAsync(string engineId, string langTag)
    {
        TestVoiceComboBox.Items.Clear();

        var adapter = _engineRouter?.GetAdapter(engineId);
        if (adapter != null)
        {
            try
            {
                var voices = await adapter.ListVoicesAsync();
                var filtered = voices.Where(v => v.Locale.Equals(langTag, StringComparison.OrdinalIgnoreCase)).ToList();

                foreach (var voice in filtered)
                {
                    TestVoiceComboBox.Items.Add(new ComboBoxItem
                    {
                        Content = voice.Name,
                        Tag = voice.VoiceId
                    });
                }

                if (TestVoiceComboBox.Items.Count > 0)
                {
                    TestVoiceComboBox.SelectedIndex = 0;
                }
                else
                {
                    TestVoiceComboBox.Items.Add(new ComboBoxItem { Content = "Không tìm thấy giọng đọc phù hợp", Tag = "" });
                    TestVoiceComboBox.SelectedIndex = 0;
                }
            }
            catch (Exception ex)
            {
                TestVoiceComboBox.Items.Add(new ComboBoxItem { Content = $"Lỗi đọc danh sách giọng: {ex.Message}", Tag = "" });
                TestVoiceComboBox.SelectedIndex = 0;
            }
        }
    }

    private void OnTestSpeedSliderChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (TestSpeedValueText != null)
        {
            TestSpeedValueText.Text = $"{e.NewValue:F1}x";
        }
    }

    private async void OnPlayVoiceTestClicked(object sender, RoutedEventArgs e)
    {
        string text = TestSampleTextBox.Text?.Trim() ?? "";
        if (string.IsNullOrWhiteSpace(text))
        {
            MessageBox.Show("Vui lòng nhập văn bản thử nghiệm.", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        string voiceId = (TestVoiceComboBox.SelectedItem as ComboBoxItem)?.Tag as string ?? "";
        if (string.IsNullOrEmpty(voiceId))
        {
            MessageBox.Show("Vui lòng chọn giọng đọc.", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var adapter = _engineRouter?.GetAdapter(_currentDetailEngineId);
        if (adapter == null)
        {
            MessageBox.Show("Engine không khả dụng.", "Lỗi", MessageBoxButton.OK, MessageBoxImage.Error);
            return;
        }

        BtnPlayVoiceTest.IsEnabled = false;
        TestStatusText.Text = "⏳ Đang tổng hợp âm thanh...";
        TestStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E05C07"));

        try
        {
            var selectedItem = TestLanguageComboBox.SelectedItem as ComboBoxItem;
            string langTag = selectedItem?.Tag as string ?? (_currentDetailEngineId == "kokoro" ? "en-US" : "ja-JP");

            double speed = TestSpeedSlider.Value;
            var request = new TtsRequest(
                RequestId: $"test_{DateTime.Now.Ticks}",
                EngineId: _currentDetailEngineId,
                Language: langTag,
                VoiceId: voiceId,
                Text: text,
                Options: new TtsOptions(Speed: speed)
            );

            var result = await Task.Run(() => adapter.SynthesizeAsync(request));

            if (result?.AudioData != null && result.AudioData.Length > 0)
            {
                TestStatusText.Text = "🔊 Đang phát âm thanh...";
                TestStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#16A34A"));

                if (result.ContentType == "audio/mpeg" || result.ContentType == "audio/mp3")
                {
                    string tempFile = Path.Combine(Path.GetTempPath(), $"flama_tts_{Guid.NewGuid():N}.mp3");
                    await File.WriteAllBytesAsync(tempFile, result.AudioData);

                    _mediaPlayer?.Stop();
                    _mediaPlayer?.Close();
                    _mediaPlayer = new MediaPlayer();

                    _mediaPlayer.MediaEnded += (s, ev) =>
                    {
                        Dispatcher.Invoke(() =>
                        {
                            TestStatusText.Text = "✅ Phát âm xong!";
                            BtnPlayVoiceTest.IsEnabled = true;
                        });
                        try { File.Delete(tempFile); } catch { }
                    };
                    _mediaPlayer.MediaFailed += (s, ev) =>
                    {
                        Dispatcher.Invoke(() =>
                        {
                            TestStatusText.Text = "❌ Lỗi phát audio!";
                            BtnPlayVoiceTest.IsEnabled = true;
                        });
                        try { File.Delete(tempFile); } catch { }
                    };

                    _mediaPlayer.Open(new Uri(tempFile));
                    _mediaPlayer.Play();
                }
                else
                {
                    await Task.Run(() =>
                    {
                        using var ms = new MemoryStream(result.AudioData);
                        using var player = new SoundPlayer(ms);
                        player.PlaySync();
                    });
                    TestStatusText.Text = "✅ Phát âm xong!";
                    BtnPlayVoiceTest.IsEnabled = true;
                }
            }
            else
            {
                TestStatusText.Text = "❌ Không nhận được dữ liệu âm thanh";
                TestStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DC2626"));
            }
        }
        catch (Exception ex)
        {
            TestStatusText.Text = $"❌ Lỗi: {ex.Message}";
            TestStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DC2626"));
        }
        finally
        {
            BtnPlayVoiceTest.IsEnabled = true;
        }
    }

    // --- INSTALLER ACTIONS ---

    private async void OnInstallKokoroClicked(object sender, RoutedEventArgs e)
    {
        if (_kokoroInstaller == null) return;

        BtnInstallKokoro.IsEnabled = false;
        KokoroInstallProgressBar.Visibility = Visibility.Visible;
        KokoroInstallProgressBar.IsIndeterminate = false;
        KokoroInstallProgressBar.Value = 0;

        var progress = new Progress<double>(p =>
        {
            Dispatcher.Invoke(() =>
            {
                KokoroInstallProgressBar.Value = p;
            });
        });

        try
        {
            var success = await _kokoroInstaller.InstallEngineAsync(progress);
            if (success)
            {
                RefreshData();
                MessageBox.Show("Tải và cài đặt Kokoro-82M English Engine thành công!", "Thành công", MessageBoxButton.OK, MessageBoxImage.Information);
                ShowInstalledView();
            }
            else
            {
                MessageBox.Show("Tải Kokoro Engine thất bại. Vui lòng kiểm tra kết nối mạng.", "Lỗi cài đặt", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }
        finally
        {
            BtnInstallKokoro.IsEnabled = true;
            KokoroInstallProgressBar.Visibility = Visibility.Collapsed;
        }
    }

    private async void OnInstallVoicevoxClicked(object sender, RoutedEventArgs e)
    {
        if (_voicevoxInstaller == null) return;

        BtnInstallVoicevox.IsEnabled = false;
        VoicevoxInstallProgressBar.Visibility = Visibility.Visible;
        VoicevoxInstallProgressBar.IsIndeterminate = false;
        VoicevoxInstallProgressBar.Value = 0;

        var progress = new Progress<double>(p =>
        {
            Dispatcher.Invoke(() =>
            {
                VoicevoxInstallProgressBar.Value = p;
            });
        });

        try
        {
            var success = await _voicevoxInstaller.InstallEngineAsync(progress);
            if (success)
            {
                VoicevoxInstallProgressBar.IsIndeterminate = true;
                _voicevoxInstaller.LaunchEngineProcess();

                await Task.Delay(2000);
                RefreshData();
                MessageBox.Show("Đã tải & khởi chạy VOICEVOX Engine thành công!", "Thành công", MessageBoxButton.OK, MessageBoxImage.Information);
                ShowInstalledView();
            }
            else
            {
                MessageBox.Show("Tải VOICEVOX Engine thất bại. Vui lòng kiểm tra kết nối mạng.", "Lỗi cài đặt", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }
        finally
        {
            BtnInstallVoicevox.IsEnabled = true;
            VoicevoxInstallProgressBar.Visibility = Visibility.Collapsed;
        }
    }

    private async void OnInstallChinesePackClicked(object sender, RoutedEventArgs e)
    {
        if (_chinesePackInstaller == null) return;

        BtnInstallChinesePack.IsEnabled = false;
        ChinesePackInstallProgressBar.Visibility = Visibility.Visible;
        ChinesePackInstallProgressBar.IsIndeterminate = false;
        ChinesePackInstallProgressBar.Value = 0;

        var progress = new Progress<double>(p =>
        {
            Dispatcher.Invoke(() =>
            {
                ChinesePackInstallProgressBar.Value = p;
            });
        });

        try
        {
            var success = await _chinesePackInstaller.InstallPackAsync(progress);
            if (success)
            {
                if (_engineRouter?.GetAdapter("kokoro") is KokoroEngineAdapter kokoroExt)
                {
                    kokoroExt.ReloadChinesePack();
                }

                RefreshData();
                MessageBox.Show("Đã tải và kích hoạt Gói Tiếng Trung Độ Chính Xác Cao thành công!\nTừ điển ~100.000 cụm từ và quy tắc biến điệu chuyên sâu đã sẵn sàng.", "Thành công", MessageBoxButton.OK, MessageBoxImage.Information);
                ShowInstalledView();
            }
            else
            {
                MessageBox.Show("Tải Gói Tiếng Trung thất bại. Vui lòng kiểm tra kết nối mạng.", "Lỗi cài đặt", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }
        finally
        {
            BtnInstallChinesePack.IsEnabled = true;
            ChinesePackInstallProgressBar.Visibility = Visibility.Collapsed;
        }
    }

    private async void OnLaunchVoicevoxClicked(object sender, RoutedEventArgs e)
    {
        if (_voicevoxInstaller == null) return;

        BtnLaunchVoicevox.IsEnabled = false;
        try
        {
            var launched = _voicevoxInstaller.LaunchEngineProcess();
            if (launched)
            {
                await Task.Delay(2000);
                RefreshData();
                MessageBox.Show("Đã phát lệnh khởi chạy VOICEVOX Engine (port 50021).", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            else
            {
                MessageBox.Show("Chưa tìm thấy bản VOICEVOX Engine đã cài. Vui lòng bấm tab 'Engine Chưa Cài đặt' để tải về.", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }
        finally
        {
            BtnLaunchVoicevox.IsEnabled = true;
        }
    }

    private void OnRefreshClicked(object sender, RoutedEventArgs e)
    {
        RefreshData();
    }

    private async void OnApprovePairingClicked(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && button.Tag is string pairingId && _pairingManager != null)
        {
            await _pairingManager.ApprovePairingAsync(pairingId);
            RefreshData();
            MessageBox.Show("Đã phê duyệt yêu cầu ghép nối!", "Thành công", MessageBoxButton.OK, MessageBoxImage.Information);
        }
    }

    public async void RefreshData()
    {
        // 1. Update Pairing List
        if (_pairingManager != null)
        {
            var pending = _pairingManager.ListPairings().Where(p => !p.Approved).ToList();
            PairingListBox.ItemsSource = pending;

            BtnNavPairing.Content = pending.Count > 0
                ? $"🔗 Ghép nối ({pending.Count} chờ)"
                : "🔗 Ghép nối Web Client";
        }

        // 2. Check Engine Statuses
        await UpdateEngineStatusesAsync();

        // 3. Check Chinese Language Pack Status
        bool isChinesePackInstalled = _chinesePackInstaller?.IsPackInstalled() ?? false;
        if (isChinesePackInstalled)
        {
            ChinesePackStatusText.Text = "🟢 Đã cài đặt";
            ChinesePackStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DCFCE7"));
            ChinesePackStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#86EFAC"));
            ChinesePackStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#15803D"));
            BtnInstallChinesePack.Content = "✅ Đã kích hoạt Độ chính xác cao";
            BtnInstallChinesePack.IsEnabled = false;
            ChinesePackCard.Visibility = Visibility.Collapsed;
        }
        else
        {
            ChinesePackStatusText.Text = "⚪ Chưa cài đặt";
            ChinesePackStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#F1F5F9"));
            ChinesePackStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#CBD5E1"));
            ChinesePackStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#64748B"));
            BtnInstallChinesePack.Content = "⚡ Tải & Cài đặt Gói Tiếng Trung (~15MB)";
            BtnInstallChinesePack.IsEnabled = true;
            ChinesePackCard.Visibility = Visibility.Visible;
        }

        // 4. Update Uninstalled Tab Empty State
        bool isVoicevoxInstalled = _voicevoxInstaller?.IsEngineInstalled() ?? false;
        bool isKokoroInstalled = _kokoroInstaller?.IsEngineInstalled() ?? false;

        VoicevoxInstallCard.Visibility = isVoicevoxInstalled ? Visibility.Collapsed : Visibility.Visible;
        KokoroInstallCard.Visibility = isKokoroInstalled ? Visibility.Collapsed : Visibility.Visible;

        UninstalledEmptyText.Visibility = (isVoicevoxInstalled && isKokoroInstalled && isChinesePackInstalled)
            ? Visibility.Visible
            : Visibility.Collapsed;
    }

    public async Task UpdateEngineStatusesAsync()
    {
        // Check VOICEVOX Status
        var voicevoxAdapter = _engineRouter?.GetAdapter("voicevox");
        if (voicevoxAdapter != null)
        {
            var health = await voicevoxAdapter.GetHealthAsync();
            if (health.Status == "ready")
            {
                VoicevoxStatusBadgeText.Text = "🟢 Sẵn sàng";
                VoicevoxStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DCFCE7"));
                VoicevoxStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#86EFAC"));
                VoicevoxStatusBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#15803D"));

                VoicevoxDetailTextBlock.Text = $"VOICEVOX Engine Active (Port 50021 • v{health.Version ?? "0.14.4"})";
                BtnLaunchVoicevox.Visibility = Visibility.Collapsed;
            }
            else
            {
                VoicevoxStatusBadgeText.Text = "🟡 Chưa bật";
                VoicevoxStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FEF3C7"));
                VoicevoxStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FDE68A"));
                VoicevoxStatusBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#B45309"));

                VoicevoxDetailTextBlock.Text = "VOICEVOX Engine chưa chạy trên Port 50021. Bấm 'Bật Engine' để kích hoạt.";
                BtnLaunchVoicevox.Visibility = Visibility.Visible;
            }
        }

        // Check Kokoro Status
        var kokoroAdapter = _engineRouter?.GetAdapter("kokoro");
        if (kokoroAdapter != null)
        {
            var health = await kokoroAdapter.GetHealthAsync();
            if (health.Status == "ready")
            {
                KokoroStatusBadgeText.Text = "🟢 Sẵn sàng";
                KokoroStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DCFCE7"));
                KokoroStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#86EFAC"));
                KokoroStatusBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#15803D"));

                bool hasZhPack = _chinesePackInstaller?.IsPackInstalled() ?? false;
                KokoroDetailTextBlock.Text = hasZhPack
                    ? "Neural Engine Kokoro-82M Active (C# Native) • 🇨🇳 Tiếng Trung: Độ Chính Xác Cao (~100k từ)"
                    : "Neural Engine Kokoro-82M Active (C# Native) • 🇨🇳 Tiếng Trung: Cơ bản (Chưa tải gói dữ liệu)";
                KokoroInstallCard.Visibility = Visibility.Collapsed;
            }
            else
            {
                KokoroStatusBadgeText.Text = "⚪ Chưa cài đặt";
                KokoroStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#F3F4F6"));
                KokoroStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E5E7EB"));
                KokoroStatusBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#4B5563"));

                KokoroDetailTextBlock.Text = "Chưa cài đặt mô hình Kokoro-82M (~120MB). Bấm 'Engine Chưa Cài đặt' để tải về.";
                KokoroInstallCard.Visibility = Visibility.Visible;
            }
        }

        // Check Edge TTS Status
        var edgeTtsAdapter = _engineRouter?.GetAdapter("edge-tts");
        if (edgeTtsAdapter != null)
        {
            var health = await edgeTtsAdapter.GetHealthAsync();
            if (health.Status == "ready")
            {
                EdgeTtsStatusText.Text = "🟢 Sẵn sàng";
                EdgeTtsStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DCFCE7"));
                EdgeTtsStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#86EFAC"));
                EdgeTtsStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#15803D"));

                EdgeTtsDetailTextBlock.Text = "320+ giọng đọc AI đa ngôn ngữ (Nhật, Anh, Việt, Trung, Hàn...) • Trực tuyến không cần tải model";
            }
            else
            {
                EdgeTtsStatusText.Text = "🟡 Ngoại tuyến";
                EdgeTtsStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FEF3C7"));
                EdgeTtsStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FDE68A"));
                EdgeTtsStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#B45309"));

                EdgeTtsDetailTextBlock.Text = health.Message ?? "Không thể kết nối đến máy chủ Microsoft Edge TTS. Vui lòng kiểm tra kết nối Internet.";
            }
        }
    }

    protected override void OnClosed(EventArgs e)
    {
        try
        {
            _mediaPlayer?.Stop();
            _mediaPlayer?.Close();
        }
        catch { }
        base.OnClosed(e);
    }
}