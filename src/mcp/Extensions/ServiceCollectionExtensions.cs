using McpServer.Tools;

namespace McpServer.Extensions;

public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddToolDependencies(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddScoped<ITool, Tools.Tools>();

        return services;
    }
}