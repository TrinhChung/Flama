using System;
using System.Collections.Generic;
using System.Linq;
using Flama.Audio.Core.Interfaces;

namespace Flama.Audio.Infrastructure.Services;

public class EngineRouter : IEngineRouter
{
    private readonly Dictionary<string, ITtsEngineAdapter> _adapters;

    public EngineRouter(IEnumerable<ITtsEngineAdapter> adapters)
    {
        _adapters = adapters.ToDictionary(a => a.EngineId, a => a, StringComparer.OrdinalIgnoreCase);
    }

    public ITtsEngineAdapter? GetAdapter(string engineId)
    {
        _adapters.TryGetValue(engineId, out var adapter);
        return adapter;
    }

    public IReadOnlyList<ITtsEngineAdapter> GetAllAdapters()
    {
        return _adapters.Values.ToList();
    }
}
