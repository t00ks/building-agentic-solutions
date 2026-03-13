using System.Text.Json;
using System.Text.Json.Serialization;
using ModelContextProtocol.Protocol;

namespace McpServer.Models;

public abstract class ToolsBase(IConfiguration configuration)
{
    protected readonly JsonSerializerOptions SerializerOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        Converters = { new JsonStringEnumConverter() }
    };

    protected static (T? result, string? error) TryParseEnum<T>(string? value, string parameterName) where T : struct, Enum
    {
        if (value is null)
        {
            return (null, null);
        }

        var normalized = value.Trim();
        if (Enum.TryParse<T>(normalized, true, out var parsed))
        {
            return (parsed, null);
        }

        return (null, $"{parameterName} '{value}' is not valid. Valid values are: {string.Join(", ", Enum.GetNames<T>())}");
    }

    protected string SerializeResult(object? value)
    {
        return JsonSerializer.Serialize(value, SerializerOptions);
    }

    public (string folderName, string filePath) ResolveFilePath(string runId, string fileName)
    {
        var bucket = configuration["Storage:SharedBucket"] ?? "outputs";
        var objectName = $"{runId}/shared/{fileName}";
        return (bucket, objectName);
    }
}