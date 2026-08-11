using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Core.Models;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;

namespace Flama.Audio.Api;

public record PairingStartRequest(string? Origin, string? ClientInfo);

public static class ApiEndpoints
{
    public static IEndpointRouteBuilder MapFlamaAudioEndpoints(this IEndpointRouteBuilder endpoints)
    {
        // GET /health
        endpoints.MapGet("/health", async (IEngineRouter router) =>
        {
            var adapters = router.GetAllAdapters();
            var engineStatuses = new Dictionary<string, EngineHealth>();
            foreach (var adapter in adapters)
            {
                engineStatuses[adapter.EngineId] = await adapter.GetHealthAsync();
            }

            return Results.Ok(new
            {
                status = "ok",
                app = "Flama Audio MVP",
                version = "1.0.0",
                port = 4791,
                engines = engineStatuses
            });
        });

        // POST /v1/pairing/start
        endpoints.MapPost("/v1/pairing/start", async (PairingStartRequest? body, HttpContext context, IPairingManager pairingManager) =>
        {
            var origin = context.Request.Headers["Origin"].ToString();
            if (string.IsNullOrEmpty(origin) && !string.IsNullOrEmpty(body?.Origin))
            {
                origin = body.Origin;
            }
            if (string.IsNullOrEmpty(origin)) origin = "http://localhost";

            var clientInfo = !string.IsNullOrEmpty(body?.ClientInfo) ? body.ClientInfo : "Web Client";
            var challenge = await pairingManager.StartPairingAsync(origin, clientInfo);
            return Results.Ok(challenge);
        });

        // GET /v1/pairing/{id}
        endpoints.MapGet("/v1/pairing/{id}", (string id, IPairingManager pairingManager) =>
        {
            var challenge = pairingManager.GetChallenge(id);
            if (challenge == null) return Results.NotFound(new { error = "pairing_not_found" });
            return Results.Ok(challenge);
        });

        // GET /v1/engines
        endpoints.MapGet("/v1/engines", async (IEngineRouter router) =>
        {
            var list = new List<EnginePackageState>();
            foreach (var adapter in router.GetAllAdapters())
            {
                var health = await adapter.GetHealthAsync();
                list.Add(new EnginePackageState(
                    EngineId: adapter.EngineId,
                    InstalledVersion: health.Version ?? "1.0.0",
                    Status: health.Status,
                    IsAvailable: health.Status == "ready"
                ));
            }
            return Results.Ok(list);
        });

        // POST /v1/engines/voicevox/install
        endpoints.MapPost("/v1/engines/voicevox/install", async (Flama.Audio.Infrastructure.Services.VoicevoxEngineInstaller installer) =>
        {
            var success = await installer.InstallEngineAsync();
            if (success)
            {
                installer.LaunchEngineProcess();
                return Results.Ok(new { status = "installed_and_launched", message = "Tải và khởi chạy VOICEVOX Engine thành công!" });
            }
            return Results.Problem("Không thể tải hoặc giải nén VOICEVOX Engine.");
        });

        // POST /v1/engines/voicevox/launch
        endpoints.MapPost("/v1/engines/voicevox/launch", (Flama.Audio.Infrastructure.Services.VoicevoxEngineInstaller installer) =>
        {
            var launched = installer.LaunchEngineProcess();
            if (launched)
            {
                return Results.Ok(new { status = "launched", message = "Đã bật VOICEVOX Engine." });
            }
            return Results.Problem("Không thể tìm thấy file chạy VOICEVOX Engine.");
        });

        // POST /v1/engines/kokoro/install
        endpoints.MapPost("/v1/engines/kokoro/install", async (Flama.Audio.Infrastructure.Services.KokoroEngineInstaller installer) =>
        {
            var success = await installer.InstallEngineAsync();
            if (success)
            {
                return Results.Ok(new { status = "installed", message = "Tải và cấu hình Kokoro-82M Engine thành công!" });
            }
            return Results.Problem("Không thể tải hoặc cài đặt Kokoro-82M Engine.");
        });

        // POST /v1/engines/kokoro/launch
        endpoints.MapPost("/v1/engines/kokoro/launch", (Flama.Audio.Infrastructure.Services.KokoroEngineInstaller installer) =>
        {
            if (installer.IsEngineInstalled())
            {
                return Results.Ok(new { status = "ready", message = "Kokoro-82M Engine sẵn sàng." });
            }
            return Results.Problem("Kokoro-82M Engine chưa được cài đặt.");
        });


        // GET /v1/voices
        endpoints.MapGet("/v1/voices", async (string? engine_id, IEngineRouter router) =>
        {
            var id = string.IsNullOrEmpty(engine_id) ? "voicevox" : engine_id;
            var adapter = router.GetAdapter(id);
            if (adapter == null)
            {
                return Results.NotFound(new { error = "engine_not_found", message = $"Engine {id} not found" });
            }
            var voices = await adapter.ListVoicesAsync();
            return Results.Ok(voices);
        });

        // POST /v1/tts
        endpoints.MapPost("/v1/tts", async (TtsRequest request, IEngineRouter router, HttpContext context) =>
        {
            if (string.IsNullOrWhiteSpace(request.Text))
            {
                return Results.BadRequest(new { error = "empty_text", message = "Text is required for TTS synthesis" });
            }

            var engineId = string.IsNullOrEmpty(request.EngineId) ? "voicevox" : request.EngineId;
            var adapter = router.GetAdapter(engineId);
            if (adapter == null)
            {
                return Results.NotFound(new { error = "engine_not_found", message = $"Engine '{engineId}' is not registered" });
            }

            try
            {
                var result = await adapter.SynthesizeAsync(request, context.RequestAborted);
                return Results.File(result.AudioData, result.ContentType, fileDownloadName: $"{result.RequestId}.wav");
            }
            catch (Exception ex)
            {
                return Results.Problem(
                    detail: ex.Message,
                    statusCode: StatusCodes.Status500InternalServerError,
                    title: "Synthesis Error"
                );
            }
        });

        return endpoints;
    }
}
