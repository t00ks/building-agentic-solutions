using System.ComponentModel;
using McpServer.Models;
using ModelContextProtocol.Server;

namespace McpServer.Tools;

[McpServerToolType]
public class Tools : ITool
{
    private static readonly Random _rng = new Random(42);

    [Description("Return basic info about a named place (mock).")]
    [McpServerTool]
    public PlaceInfo PlaceInfoTool([Description("Name of the place to look up.")] string placeName)
    {
        // Mock responses by simple heuristics
        var type = placeName.Contains("Museum", StringComparison.OrdinalIgnoreCase) ? "museum"
                 : placeName.Contains("Park", StringComparison.OrdinalIgnoreCase) ? "park"
                 : "attraction";
        var minutes = type == "museum" ? 90 : 45;
        var fee = type == "museum" ? 12.50m : 0m;
        var popularity = Math.Round(0.5 + _rng.NextDouble() * 0.5, 2);

        return new PlaceInfo(
            Name: placeName,
            Type: type,
            OpenHours: "09:00-18:00",
            AvgVisitMinutes: minutes,
            EntryFeeEur: fee,
            PopularityScore: popularity,
            Description: $"Mock description for {placeName}. A popular {type}.",
            Address: $"123 {placeName} St.");
    }

    [Description("Estimate transit time and cost between two POIs (mock).")]
    [McpServerTool]
    public TransitInfo TransitTimeTool(
        [Description("Starting location or point of interest.")] string origin,
        [Description("Destination location or point of interest.")] string destination,
        [Description("Preferred transport mode: walking, transit, or driving.")] string preferredMode = "walking")
    {
        // Simple distance-ish estimate based on name lengths
        var pseudoDistanceKm = Math.Abs(origin.Length - destination.Length) + 2; // 2-15 km-ish
        TimeSpan duration;
        decimal cost;

        switch (preferredMode.ToLower())
        {
            case "driving":
                duration = TimeSpan.FromMinutes(pseudoDistanceKm * 4 + 10);
                cost = pseudoDistanceKm * 0.5m + 1.5m;
                break;
            case "transit":
                duration = TimeSpan.FromMinutes(pseudoDistanceKm * 6 + 15);
                cost = pseudoDistanceKm * 0.25m + 1.2m;
                break;
            default: // walking
                duration = TimeSpan.FromMinutes(pseudoDistanceKm * 20 + 10);
                cost = 0m;
                break;
        }

        return new TransitInfo(
            Origin: origin,
            Destination: destination,
            EstimatedDuration: duration,
            Mode: preferredMode,
            EstimatedCostEur: Math.Round(cost, 2));
    }

    [Description("Provide a simple budget estimate given a list of items/costs or a rough itinerary.")]
    [McpServerTool]
    public BudgetEstimate BudgetEstimatorTool(
        [Description("Map of category to number of visits, for example museum=2.")] Dictionary<string, int> visitsPerCategory,
        [Description("Estimated meal cost per person in EUR.")] decimal perMealEur = 15m)
    {
        // visitsPerCategory: e.g., {"museum":2, "restaurant":3}
        var breakdown = new Dictionary<string, decimal>();
        decimal total = 0m;

        foreach (var kv in visitsPerCategory)
        {
            decimal cost = kv.Key.ToLower() switch
            {
                "museum" => kv.Value * 12.5m,
                "attraction" => kv.Value * 6.0m,
                "restaurant" => kv.Value * perMealEur,
                "transport" => kv.Value * 2.5m,
                _ => kv.Value * 5m
            };
            breakdown[kv.Key] = Math.Round(cost, 2);
            total += cost;
        }

        return new BudgetEstimate(
            TotalEstimatedEur: Math.Round(total, 2),
            BreakdownByCategory: breakdown);
    }

    [Description("Mock weather forecast for a given date and location.")]
    [McpServerTool]
    public WeatherForecast WeatherTool(
        [Description("Location to forecast weather for.")] string location,
        [Description("Forecast date.")] DateTime date)
    {
        // Deterministic-ish by hashing location+date
        int seed = location.Length + date.Day;
        var r = new Random(seed);
        var conditions = new[] { "Sunny", "Partly Cloudy", "Cloudy", "Rain", "Thunderstorms" };
        var condition = conditions[r.Next(conditions.Length)];
        int high = r.Next(12, 29);
        int low = high - r.Next(4, 10);
        double precip = condition.Contains("Rain") || condition.Contains("Thunder") ? Math.Round(r.NextDouble() * 0.8, 2) : Math.Round(r.NextDouble() * 0.2, 2);

        return new WeatherForecast(
            Date: date.Date,
            Condition: condition,
            HighCelsius: high,
            LowCelsius: low,
            PrecipitationProbability: precip);
    }

    [Description("Return a list of mock flight options between origin and dest on given date.")]
    [McpServerTool]
    public List<FlightOption> FlightSearchTool(
        [Description("Origin airport code or name.")] string originAirport,
        [Description("Destination airport code or name.")] string destAirport,
        [Description("Departure date.")] DateTime departDate,
        [Description("Maximum number of flight options to return.")] int maxResults = 3)
    {
        var list = new List<FlightOption>();
        var basePrice = 80m + Math.Abs(originAirport.Length - destAirport.Length) * 5;

        for (int i = 0; i < maxResults; i++)
        {
            var depart = departDate.Date.AddHours(8 + i * 3 + _rng.Next(0, 2));
            var duration = TimeSpan.FromHours(1 + _rng.Next(0, 6));
            var arrival = depart.Add(duration);
            var price = basePrice + i * 25 + _rng.Next(0, 40);

            list.Add(new FlightOption(
                Airline: $"AirMock{i + 1}",
                FlightNumber: $"AM{100 + i}",
                Departure: depart,
                Arrival: arrival,
                PriceEur: Math.Round(price, 2),
                IsDirect: _rng.NextDouble() > 0.3));
        }

        return list;
    }

    [Description("Return hotel search results (mock).")]
    [McpServerTool]
    public List<HotelOption> HotelSearchTool(
        [Description("City to search hotels in.")] string city,
        [Description("Check-in date.")] DateTime checkIn,
        [Description("Check-out date.")] DateTime checkOut,
        [Description("Maximum number of hotel options to return.")] int maxResults = 5)
    {
        var nights = (checkOut.Date - checkIn.Date).Days;
        var list = new List<HotelOption>();
        for (int i = 0; i < maxResults; i++)
        {
            var price = 50m + i * 30 + _rng.Next(0, 40);
            list.Add(new HotelOption(
                Name: $"{city} Hotel {(char)('A' + i)}",
                Address: $"{100 + i} {city} Center",
                PricePerNightEur: Math.Round(price, 2),
                Rating: Math.Round(3.0 + _rng.NextDouble() * 2.0, 1),
                Availability: _rng.NextDouble() > 0.1,
                RoomType: i == 0 ? "Standard" : "Superior"));
        }

        return list;
    }

    [Description("Simple restaurant search.")]
    [McpServerTool]
    public List<RestaurantOption> RestaurantSearchTool(
        [Description("City to search restaurants in.")] string city,
        [Description("Optional cuisine filter.")] string? cuisine = null,
        [Description("Maximum number of restaurant options to return.")] int maxResults = 5)
    {
        var list = new List<RestaurantOption>();
        var cuisines = new[] { "Portuguese", "Italian", "Seafood", "Vegetarian", "Cafe" };
        for (int i = 0; i < maxResults; i++)
        {
            var c = cuisine ?? cuisines[i % cuisines.Length];
            list.Add(new RestaurantOption(
                Name: $"{c} Place {(i + 1)}",
                Cuisine: c,
                AvgPricePerPersonEur: Math.Round(10m + i * 5m + _rng.Next(0, 8), 2),
                Rating: Math.Round(3.0 + _rng.NextDouble() * 2.0, 1),
                Address: $"{i + 1} {city} Street",
                IsVegetarianFriendly: c == "Vegetarian" || _rng.NextDouble() > 0.5));
        }

        return list;
    }

    [Description("Return local events in the date range (mock).")]
    [McpServerTool]
    public List<LocalEvent> LocalEventsTool(
        [Description("City to search events in.")] string city,
        [Description("Start date for event search.")] DateTime fromDate,
        [Description("End date for event search.")] DateTime toDate)
    {
        var list = new List<LocalEvent>();
        var categories = new[] { "Music", "Exhibition", "Theatre", "Market", "Festival" };
        int days = Math.Max(1, (toDate - fromDate).Days);
        for (int i = 0; i < Math.Min(6, days + 1); i++)
        {
            var start = fromDate.Date.AddDays(i).AddHours(18 + _rng.Next(0, 6));
            list.Add(new LocalEvent(
                Title: $"{categories[i % categories.Length]} Night {(i + 1)}",
                Start: start,
                End: start.AddHours(2 + _rng.Next(0, 3)),
                Venue: $"Venue {(i + 1)}",
                Category: categories[i % categories.Length],
                TicketPriceEur: Math.Round(5m + _rng.Next(0, 35), 2)));
        }
        return list;
    }

    [Description("Convert currency using a mock rate.")]
    [McpServerTool]
    public CurrencyConversion CurrencyTool(
        [Description("Source currency code, for example EUR.")] string fromCurrency,
        [Description("Target currency code, for example USD.")] string toCurrency,
        [Description("Amount to convert.")] decimal amount)
    {
        if (string.Equals(fromCurrency, toCurrency, StringComparison.OrdinalIgnoreCase))
        {
            return new CurrencyConversion(fromCurrency, toCurrency, 1m, amount);
        }

        // Simple mock rate generation
        decimal pseudoRate = (decimal)(0.5 + (_rng.NextDouble() * 1.5)); // 0.5 - 2.0
        var converted = Math.Round(amount * pseudoRate, 2);

        return new CurrencyConversion(fromCurrency, toCurrency, Math.Round(pseudoRate, 4), converted);
    }

    [Description("Return a simple route (distance, steps).")]
    [McpServerTool]
    public RouteInfo MapRouteTool(
        [Description("Route starting point.")] string start,
        [Description("Route ending point.")] string end,
        [Description("Travel mode: walking, transit, or driving.")] string mode = "walking")
    {
        double distance = Math.Abs(start.Length - end.Length) + 3.2; // km
        TimeSpan duration = mode.ToLower() switch
        {
            "driving" => TimeSpan.FromMinutes((int)(distance * 4 + 10)),
            "transit" => TimeSpan.FromMinutes((int)(distance * 6 + 15)),
            _ => TimeSpan.FromMinutes((int)(distance * 20 + 10))
        };

        var steps = new List<string>
            {
                $"Start at {start}",
                $"Head towards Main St.",
                $"Follow signs to {end}",
                $"Arrive at {end}"
            };

        return new RouteInfo(start, end, Math.Round(distance, 2), duration, steps);
    }

    [Description("Simulate a booking API (hotel/flight/restaurant) that may succeed or fail.")]
    [McpServerTool]
    public BookingResult BookingApiSimulator(
        [Description("Booking provider name.")] string provider,
        [Description("Item type to book, for example hotel, flight, or restaurant.")] string itemType,
        [Description("Booking details as key value pairs.")] Dictionary<string, string> details)
    {
        // details contains things like "hotelId","checkIn","guestName" etc.
        bool success = _rng.NextDouble() > 0.15; // 85% success
        if (success)
        {
            var refId = $"{provider.ToUpper().Substring(0, Math.Min(3, provider.Length))}-{_rng.Next(10000, 99999)}";
            return new BookingResult(true, refId, provider, $"Booking confirmed for {itemType}.");
        }
        else
        {
            return new BookingResult(false, null!, provider, $"Provider {provider} returned an error booking {itemType} (simulated).");
        }
    }

    [Description("Validate an itinerary or other structured payload against simple constraints (budget, timings).")]
    [McpServerTool]
    public ValidationResult ValidatorTool(
        [Description("Proposed total budget in EUR.")] decimal proposedBudgetEur,
        [Description("Maximum allowed budget in EUR.")] decimal budgetLimitEur,
        [Description("Start date of itinerary.")] DateTime startDate,
        [Description("End date of itinerary.")] DateTime endDate,
        [Description("List of required field names to check.")] List<string> requiredFields)
    {
        var errors = new List<string>();
        var warnings = new List<string>();

        if (proposedBudgetEur > budgetLimitEur)
            errors.Add($"Proposed budget {proposedBudgetEur} EUR exceeds limit of {budgetLimitEur} EUR.");

        if (endDate <= startDate)
            errors.Add("End date must be after start date.");

        foreach (var f in requiredFields)
        {
            if (string.IsNullOrWhiteSpace(f))
                warnings.Add("One of the required fields is empty.");
        }

        return new ValidationResult(errors.Count == 0, errors, warnings);
    }

    [Description("Return stored user preferences (mock).")]
    [McpServerTool]
    public UserPreferences UserPrefStore([Description("User identifier.")] string userId)
    {
        var interests = new List<string> { "coffee", "architecture", "museums" };
        var dietary = new List<string> { "vegetarian" };
        return new UserPreferences(userId, interests, dietary, "EUR", "en-GB");
    }

    [Description("Return emergency info for a country (mock).")]
    [McpServerTool]
    public EmergencyInfo EmergencyInfoTool([Description("Country name.")] string country)
    {
        return new EmergencyInfo(
            Country: country,
            EmbassyContact: $"{country} Embassy: +44 20 7000 0000",
            LocalEmergencyNumber: "112",
            Notes: $"General emergency information for {country}. Check local government advice.");
    }
}
