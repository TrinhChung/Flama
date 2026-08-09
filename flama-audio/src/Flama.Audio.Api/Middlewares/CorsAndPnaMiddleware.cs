using System;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;

namespace Flama.Audio.Api.Middlewares;

public class CorsAndPnaMiddleware
{
    private readonly RequestDelegate _next;

    public CorsAndPnaMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var origin = context.Request.Headers["Origin"].ToString();
        var allowOrigin = (!string.IsNullOrEmpty(origin) && origin != "null") ? origin : "*";

        context.Response.Headers["Access-Control-Allow-Origin"] = allowOrigin;
        context.Response.Headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE";
        context.Response.Headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Access-Control-Allow-Private-Network";
        context.Response.Headers["Access-Control-Allow-Private-Network"] = "true";

        if (HttpMethods.IsOptions(context.Request.Method))
        {
            context.Response.StatusCode = StatusCodes.Status204NoContent;
            return;
        }

        await _next(context);
    }
}
