
namespace McpServer.Models;

public record PlaceInfo(
        string Name,
        string Type,
        string OpenHours,
        int AvgVisitMinutes,
        decimal EntryFeeEur,
        double PopularityScore, // 0.0 - 1.0
        string Description,
        string Address);

public record TransitInfo(
    string Origin,
    string Destination,
    TimeSpan EstimatedDuration,
    string Mode, // e.g., "walking", "transit", "driving"
    decimal EstimatedCostEur);

public record BudgetEstimate(
    decimal TotalEstimatedEur,
    Dictionary<string, decimal> BreakdownByCategory); // e.g., "food": 20, "entryFees": 15

public record WeatherForecast(
    DateTime Date,
    string Condition, // e.g., "Sunny", "Rain", "Cloudy"
    int HighCelsius,
    int LowCelsius,
    double PrecipitationProbability); // 0-1

public record FlightOption(
    string Airline,
    string FlightNumber,
    DateTime Departure,
    DateTime Arrival,
    decimal PriceEur,
    bool IsDirect);

public record HotelOption(
    string Name,
    string Address,
    decimal PricePerNightEur,
    double Rating, // 0-5
    bool Availability,
    string RoomType);

public record RestaurantOption(
    string Name,
    string Cuisine,
    decimal AvgPricePerPersonEur,
    double Rating,
    string Address,
    bool IsVegetarianFriendly);

public record LocalEvent(
    string Title,
    DateTime Start,
    DateTime End,
    string Venue,
    string Category,
    decimal TicketPriceEur);

public record CurrencyConversion(
    string FromCurrency,
    string ToCurrency,
    decimal Rate,
    decimal ConvertedAmount);

public record RouteInfo(
    string Start,
    string End,
    double DistanceKm,
    TimeSpan EstimatedDuration,
    List<string> Steps);

public record BookingResult(
    bool Success,
    string BookingReference,
    string Provider,
    string Message);

public record ValidationResult(
    bool IsValid,
    List<string> Errors,
    List<string> Warnings);

public record NotificationResult(
    bool Sent,
    string Channel,
    string MessageId,
    string Message);

public record UserPreferences(
    string UserId,
    List<string> Interests,
    List<string> DietaryRestrictions,
    string PreferredCurrency,
    string PreferredLocale);

public record EmergencyInfo(
    string Country,
    string EmbassyContact,
    string LocalEmergencyNumber,
    string Notes);