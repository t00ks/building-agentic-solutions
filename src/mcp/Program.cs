using McpServer.Extensions;

var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddToolDependencies(builder.Configuration)
    .AddMcpServer()
    .WithHttpTransport(options => options.RunSessionHandler = async (httpContext, mcpServer, cancellationToken) =>
    {
        await mcpServer.RunAsync(cancellationToken);
    })
    .WithToolsFromAssembly();

builder.Services.AddHealthChecks();

// Configure logging - all logs go to stderr for MCP compatibility
builder.Logging.ClearProviders();
builder.Logging.AddConsole(consoleLogOptions =>
{
    // Configure all logs to go to stderr
    consoleLogOptions.LogToStandardErrorThreshold = LogLevel.Trace;
});
builder.Logging.AddJsonConsole(options =>
{
    options.IncludeScopes = true;
    options.TimestampFormat = "yyyy-MM-dd HH:mm:ss ";
});

var app = builder.Build();

app.MapMcp("/mcp");
app.MapHealthChecks("/health");

await app.RunAsync();
