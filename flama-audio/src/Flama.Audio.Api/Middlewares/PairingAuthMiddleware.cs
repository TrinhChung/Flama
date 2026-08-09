using System;
using System.Threading.Tasks;
using Flama.Audio.Core.Interfaces;
using Microsoft.AspNetCore.Http;

namespace Flama.Audio.Api.Middlewares;

public class PairingAuthMiddleware
{
    private readonly RequestDelegate _next;

    public PairingAuthMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context, IPairingManager pairingManager)
    {
        var path = context.Request.Path.Value ?? "";

        // Public endpoints that don't require pairing auth token
        if (HttpMethods.IsOptions(context.Request.Method) ||
            path.Equals("/health", StringComparison.OrdinalIgnoreCase) ||
            path.StartsWith("/v1/pairing", StringComparison.OrdinalIgnoreCase))
        {
            await _next(context);
            return;
        }

        var origin = context.Request.Headers["Origin"].ToString();
        if (string.IsNullOrEmpty(origin)) origin = "http://localhost";

        var authHeader = context.Request.Headers["Authorization"].ToString();
        var token = authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)
            ? authHeader["Bearer ".Length..].Trim()
            : "";

        if (!pairingManager.ValidateToken(origin, token))
        {
            context.Response.StatusCode = StatusCodes.Status401Unauthorized;
            context.Response.ContentType = "application/json";
            await context.Response.WriteAsync("{\"error\":\"unauthorized\",\"message\":\"Valid pairing token required\"}");
            return;
        }

        await _next(context);
    }
}
