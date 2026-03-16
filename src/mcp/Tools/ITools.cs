
using McpServer.Models;

namespace McpServer.Tools;

public interface ITool
{
    PlaceInfo PlaceInfoTool(string placeName);
    TransitInfo TransitTimeTool(string origin, string destination, string preferredMode = "walking");
    BudgetEstimate BudgetEstimatorTool(Dictionary<string, int> visitsPerCategory, decimal perMealEur = 15m);
    WeatherForecast WeatherTool(string location, DateTime date);
    List<FlightOption> FlightSearchTool(string originAirport, string destAirport, DateTime departDate, int maxResults = 3);
    List<HotelOption> HotelSearchTool(string city, DateTime checkIn, DateTime checkOut, int maxResults = 5);
    List<RestaurantOption> RestaurantSearchTool(string city, string? cuisine = null, int maxResults = 5);
    List<LocalEvent> LocalEventsTool(string city, DateTime fromDate, DateTime toDate);
    CurrencyConversion CurrencyTool(string fromCurrency, string toCurrency, decimal amount);
    RouteInfo MapRouteTool(string start, string end, string mode = "walking");
    BookingResult BookingApiSimulator(string provider, string itemType, Dictionary<string, string> details);
    ValidationResult ValidatorTool(decimal proposedBudgetEur, decimal budgetLimitEur, DateTime startDate, DateTime endDate, List<string> requiredFields);
    UserPreferences UserPrefStore(string userId);
    EmergencyInfo EmergencyInfoTool(string country);
}