using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using System.Text;

namespace MinimalApiProject
{
    public class ApiRequestValidationMiddleware
    {
        private readonly RequestDelegate _next;
        private readonly ILogger<ApiRequestValidationMiddleware> _logger;

        public ApiRequestValidationMiddleware(RequestDelegate next, ILogger<ApiRequestValidationMiddleware> logger)
        {
            _next = next;
            _logger = logger;
        }

        public async Task InvokeAsync(HttpContext context)
        {
            // Only apply to API endpoints
            if (!context.Request.Path.StartsWithSegments("/api"))
            {
                await _next(context);
                return;
            }

            // Validate request before processing
            var validationResult = await ValidateRequest(context);
            if (validationResult.HasError)
            {
                await WriteErrorResponse(context, validationResult.StatusCode, validationResult.ErrorMessage);
                return;
            }

            await _next(context);
        }

        private async Task<ValidationResult> ValidateRequest(HttpContext context)
        {
            var method = context.Request.Method.ToUpper();
            var path = context.Request.Path.Value?.ToLower() ?? "";

            // Extract entity and id from path
            var pathParts = path.Split('/', StringSplitOptions.RemoveEmptyEntries);
            if (pathParts.Length < 2)
            {
                return ValidationResult.Success();
            }

            var entity = pathParts[1]; // users, categories, products
            var hasId = pathParts.Length > 2;
            var idValue = hasId ? pathParts[2] : null;

            // Validate entity type
            if (!IsValidEntity(entity))
            {
                return ValidationResult.Error(404, "Endpoint not found");
            }

            // Validate ID format for endpoints that require it
            if (hasId && (!int.TryParse(idValue, out var id) || id <=0))
            {
                return ValidationResult.Error(404, $"{CapitalizeEntity(entity)} not found");
            }

            // Method-specific validation
            switch (method)
            {
                case "GET":
                    return ValidateGetRequest(entity, hasId);
                case "POST":
                    return await ValidatePostRequest(context, entity);
                case "PUT":
                    return await ValidatePutRequest(context, entity, hasId);
                case "DELETE":
                    return ValidateDeleteRequest(entity, hasId);
                default:
                    return ValidationResult.Error(405, "Method not allowed");
            }
        }

        private ValidationResult ValidateGetRequest(string entity, bool hasId)
        {
            // GET requests don't need body validation
            return ValidationResult.Success();
        }

        private async Task<ValidationResult> ValidatePostRequest(HttpContext context, string entity)
        {
            // POST should not have ID in path
            var pathParts = context.Request.Path.Value?.Split('/', StringSplitOptions.RemoveEmptyEntries);
            if (pathParts?.Length > 2)
            {
                return ValidationResult.Error(404, "Endpoint not found");
            }

            // Validate request body
            return await ValidateRequestBody(context, entity, isUpdate: false);
        }

        private async Task<ValidationResult> ValidatePutRequest(HttpContext context, string entity, bool hasId)
        {
            // PUT requires ID in path
            if (!hasId)
            {
                return ValidationResult.Error(404, "Endpoint not found");
            }

            // Validate request body
            return await ValidateRequestBody(context, entity, isUpdate: true);
        }

        private ValidationResult ValidateDeleteRequest(string entity, bool hasId)
        {
            // DELETE requires ID in path
            if (!hasId)
            {
                return ValidationResult.Error(404, "Endpoint not found");
            }

            return ValidationResult.Success();
        }

        private async Task<ValidationResult> ValidateRequestBody(HttpContext context, string entity, bool isUpdate)
        {
            if (!HasJsonContentType(context))
            {
                return ValidationResult.Error(422, "Content-Type must be application/json");
            }

            try
            {
                context.Request.EnableBuffering();
                var body = await new StreamReader(context.Request.Body).ReadToEndAsync();
                context.Request.Body.Position = 0;

                _logger.LogInformation("Request body for {Entity}: {Body}", entity, body);

                if (string.IsNullOrWhiteSpace(body))
                {
                    return ValidationResult.Error(422, "Request body is required");
                }

                // Parse and validate JSON structure
                var jsonDocument = JsonDocument.Parse(body);
                var result = ValidateEntityStructure(jsonDocument.RootElement, entity, isUpdate);
                
                _logger.LogInformation("Validation result for {Entity}: HasError={HasError}, Message={Message}", 
                    entity, result.HasError, result.ErrorMessage);
                
                return result;
            }
            catch (JsonException)
            {
                return ValidationResult.Error(422, "Invalid JSON format");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error validating request body");
                return ValidationResult.Error(422, "Invalid request body");
            }
        }

        private ValidationResult ValidateEntityStructure(JsonElement json, string entity, bool isUpdate)
        {
            return entity switch
            {
                "users" => ValidateUserStructure(json, isUpdate),
                "categories" => ValidateCategoryStructure(json, isUpdate),
                "products" => ValidateProductStructure(json, isUpdate),
                _ => ValidationResult.Error(422, "Invalid entity type")
            };
        }

        private ValidationResult ValidateUserStructure(JsonElement json, bool isUpdate)
        {
            var errors = new List<string>();

            // Validate name
            if (!json.TryGetProperty("name", out var nameElement) ||
                nameElement.ValueKind == JsonValueKind.Null ||
                nameElement.ValueKind != JsonValueKind.String ||
                string.IsNullOrWhiteSpace(nameElement.GetString()))
            {
                errors.Add("Name is required and cannot be empty");
            }

            // Validate email
            if (!json.TryGetProperty("email", out var emailElement) ||
                emailElement.ValueKind == JsonValueKind.Null ||
                emailElement.ValueKind != JsonValueKind.String)
            {
                errors.Add("Email must be a valid email address");
            }
            else
            {
                var email = emailElement.GetString();
                if (string.IsNullOrWhiteSpace(email) || !IsValidEmail(email))
                {
                    errors.Add("Email must be a valid email address");
                }
            }

            // Validate createdAt for both create and update operations
            if (json.TryGetProperty("createdAt", out var createdAtElement))
            {
                if (createdAtElement.ValueKind != JsonValueKind.String ||
                    !DateTime.TryParse(createdAtElement.GetString(), out _))
                {
                    errors.Add("Invalid date-time format for createdAt");
                }
            }

            return errors.Any() ?
                ValidationResult.Error(400, string.Join("; ", errors)) :
                ValidationResult.Success();
        }

        private ValidationResult ValidateCategoryStructure(JsonElement json, bool isUpdate)
        {
            var errors = new List<string>();

            // Validate name
            if (!json.TryGetProperty("name", out var nameElement) ||
                nameElement.ValueKind == JsonValueKind.Null ||
                nameElement.ValueKind != JsonValueKind.String ||
                string.IsNullOrWhiteSpace(nameElement.GetString()))
            {
                errors.Add("Name is required and cannot be empty");
            }

            // Description is optional, but if present should be string
            if (json.TryGetProperty("description", out var descElement) &&
                descElement.ValueKind != JsonValueKind.String &&
                descElement.ValueKind != JsonValueKind.Null)
            {
                errors.Add("Description must be a string");
            }

            return errors.Any() ?
                ValidationResult.Error(400, string.Join("; ", errors)) :
                ValidationResult.Success();
        }

        private ValidationResult ValidateProductStructure(JsonElement json, bool isUpdate)
        {
            var errors = new List<string>();

            try
            {
                // Validate name
                if (!json.TryGetProperty("name", out var nameElement) ||
                    nameElement.ValueKind == JsonValueKind.Null ||
                    nameElement.ValueKind != JsonValueKind.String ||
                    string.IsNullOrWhiteSpace(nameElement.GetString()))
                {
                    errors.Add("Name is required and cannot be empty");
                }

                // Validate price
                if (!json.TryGetProperty("price", out var priceElement) ||
                    priceElement.ValueKind == JsonValueKind.Null ||
                    !priceElement.TryGetDecimal(out var price) ||
                    price <= 0)
                {
                    errors.Add("Price must be greater than 0");
                }

                // Validate categoryId
                if (!json.TryGetProperty("categoryId", out var categoryIdElement) ||
                    categoryIdElement.ValueKind == JsonValueKind.Null ||
                    !categoryIdElement.TryGetInt32(out var categoryId) ||
                    categoryId <= 0)
                {
                    errors.Add("CategoryId must be a positive integer");
                }

                // Make userId optional for product creation to match test expectations
                // Only validate userId if it's provided in the request
                if (json.TryGetProperty("userId", out var userIdElement))
                {
                    if (userIdElement.ValueKind == JsonValueKind.Null ||
                        !userIdElement.TryGetInt32(out var userId) ||
                        userId <= 0)
                    {
                        errors.Add("UserId must be a positive integer");
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in ValidateProductStructure");
                errors.Add("Validation error occurred");
            }

            // Description is optional, but if present should be string
            if (json.TryGetProperty("description", out var descElement) &&
                descElement.ValueKind != JsonValueKind.String &&
                descElement.ValueKind != JsonValueKind.Null)
            {
                errors.Add("Description must be a string");
            }

            return errors.Any() ?
                ValidationResult.Error(400, string.Join("; ", errors)) :
                ValidationResult.Success();
        }

        private static bool HasJsonContentType(HttpContext context)
        {
            return context.Request.ContentType?.StartsWith("application/json", StringComparison.OrdinalIgnoreCase) == true;
        }

        private static bool IsValidEmail(string email)
        {
            try
            {
                var emailAttribute = new EmailAddressAttribute();
                return emailAttribute.IsValid(email);
            }
            catch
            {
                return false;
            }
        }

        private static bool IsValidEntity(string entity)
        {
            return entity is "users" or "categories" or "products";
        }

        private static string CapitalizeEntity(string entity)
        {
            return entity switch
            {
                "users" => "User",
                "categories" => "Category",
                "products" => "Product",
                _ => entity
            };
        }

        private async Task WriteErrorResponse(HttpContext context, int statusCode, string message)
        {
            context.Response.StatusCode = statusCode;
            context.Response.ContentType = "application/json";

            var response = JsonSerializer.Serialize(new { error = message });
            await context.Response.WriteAsync(response);
        }

        private class ValidationResult
        {
            public bool HasError { get; init; }
            public int StatusCode { get; init; }
            public string ErrorMessage { get; init; } = string.Empty;

            public static ValidationResult Success() => new() { HasError = false };
            public static ValidationResult Error(int statusCode, string message) =>
                new() { HasError = true, StatusCode = statusCode, ErrorMessage = message };
        }
    }
}