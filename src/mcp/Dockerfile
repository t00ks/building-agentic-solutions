FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build

WORKDIR /src

COPY ["excel-tools-mcp.csproj", "./"]
RUN dotnet restore excel-tools-mcp.csproj

COPY . .
RUN dotnet restore excel-tools-mcp.csproj
RUN dotnet publish excel-tools-mcp.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final

WORKDIR /app

COPY --from=build /app/publish .

ENV ASPNETCORE_ENVIRONMENT=Production
ENV ASPNETCORE_URLS=http://+:8080
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

EXPOSE 8080

ENTRYPOINT ["dotnet", "excel-tools-mcp.dll"]
