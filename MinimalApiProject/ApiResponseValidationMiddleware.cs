using System.ComponentModel.DataAnnotations;
using System.Text;
using System.Text.Json;

namespace MinimalApiProject
{
    public class ApiResponseValidationMiddleware
    {
        private readonly RequestDelegate _next;
        private readonly ILogger<ApiResponseValidationMiddleware> _logger;

        public ApiResponseValidationMiddleware(RequestDelegate next, ILogger<ApiResponseValidationMiddleware> logger)
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

            try
            {
                // Capture the original response stream
                var originalBodyStream = context.Response.Body;

                using var responseBody = new MemoryStream();
                context.Response.Body = responseBody;

                // Process the request
                await _next(context);

                // Validate and potentially modify the response
                await ValidateAndProcessResponse(context, responseBody, originalBodyStream);
            }
            catch (ValidationException ex)
            {
                await HandleValidationException(context, ex);
            }
            catch (Exception ex) when (IsEntityFrameworkException(ex))
            {
                await HandleEntityFrameworkException(context, ex);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unhandled exception in API middleware");
                await HandleUnexpectedException(context, ex);
            }
        }

        private async Task ValidateAndProcessResponse(HttpContext context, MemoryStream responseBody, Stream originalBodyStream)
        {
            var method = context.Request.Method;
            var path = context.Request.Path.Value?.ToLower() ?? "";
            var statusCode = context.Response.StatusCode;

            // Read response content
            responseBody.Seek(0, SeekOrigin.Begin);
            var responseContent = await new StreamReader(responseBody).ReadToEndAsync();

            // Validate response according to spec
            var (isValid, correctedStatusCode, correctedContent) = ValidateResponse(method, path, statusCode, responseContent);

            if (!isValid)
            {
                _logger.LogWarning("Response validation failed for {Method} {Path}. Original status: {OriginalStatus}, Corrected: {CorrectedStatus}",
                    method, path, statusCode, correctedStatusCode);
            }

            // Set the corrected status code
            context.Response.StatusCode = correctedStatusCode;

            if (context.Response.StatusCode != 204)
            {
                var finalContent = correctedContent ?? responseContent;
                // Only write if the stream is writable and not closed
                if (originalBodyStream.CanWrite)
                {
                    await originalBodyStream.WriteAsync(Encoding.UTF8.GetBytes(finalContent));
                }
            }
        }

        private (bool isValid, int statusCode, string? content) ValidateResponse(string method, string path, int statusCode, string content)
        {
            // Extract entity and id from path
            var pathParts = path.Split('/', StringSplitOptions.RemoveEmptyEntries);
            if (pathParts.Length < 2) return (true, statusCode, null);

            var entity = pathParts[1]; // users, categories, products
            var hasId = pathParts.Length > 2;
            var isValidId = hasId && int.TryParse(pathParts[2], out _);

            switch (method.ToUpper())
            {
                case "GET":
                    return ValidateGetResponse(entity, hasId, isValidId, statusCode, content);
                case "POST":
                    return ValidatePostResponse(entity, statusCode, content);
                case "PUT":
                    return ValidatePutResponse(entity, hasId, isValidId, statusCode, content);
                case "DELETE":
                    return ValidateDeleteResponse(entity, hasId, isValidId, statusCode, content);
                default:
                    return (true, statusCode, null);
            }
        }

        private (bool isValid, int statusCode, string? content) ValidateGetResponse(string entity, bool hasId, bool isValidId, int statusCode, string content)
        {
            if (hasId)
            {
                // GET /api/{entity}/{id}
                if (!isValidId && statusCode != 404)
                {
                    // Invalid ID format should return 404 according to spec
                    return (false, 404, JsonSerializer.Serialize(new { error = $"{CapitalizeEntity(entity)} not found" }));
                }

                if (statusCode == 200)
                {
                    // Should return single object
                    if (string.IsNullOrEmpty(content) || content.StartsWith("["))
                    {
                        return (false, 404, JsonSerializer.Serialize(new { error = $"{CapitalizeEntity(entity)} not found" }));
                    }
                }
                else if (statusCode != 404)
                {
                    // Only 200 or 404 are valid for GET by ID
                    return (false, 404, JsonSerializer.Serialize(new { error = $"{CapitalizeEntity(entity)} not found" }));
                }
            }
            else
            {
                // GET /api/{entity}
                if (statusCode != 200)
                {
                    // Should always return 200 with array (even if empty)
                    return (false, 200, "[]");
                }

                // Should return array
                if (!string.IsNullOrEmpty(content) && !content.Trim().StartsWith("["))
                {
                    return (false, 200, "[]");
                }
            }

            return (true, statusCode, null);
        }

        private (bool isValid, int statusCode, string? content) ValidatePostResponse(string entity, int statusCode, string content)
        {
            if (statusCode == 201)
            {
                // Valid creation response
                return (true, statusCode, null);
            }
            else if (statusCode == 422)
            {
                // Valid validation error
                return (true, statusCode, null);
            }
            else if (statusCode >= 400 && statusCode < 500)
            {
                // Convert other 4xx errors to 422 for validation issues
                var errorContent = JsonSerializer.Serialize(new { error = "Validation failed" });
                return (false, 422, errorContent);
            }

            return (true, statusCode, null);
        }

        private (bool isValid, int statusCode, string? content) ValidatePutResponse(string entity, bool hasId, bool isValidId, int statusCode, string content)
        {
            if (!hasId || !isValidId)
            {
                // PUT requires valid ID
                return (false, 404, JsonSerializer.Serialize(new { error = $"{CapitalizeEntity(entity)} not found" }));
            }

            if (statusCode == 204)
            {
                // Valid update response
                return (true, statusCode, null);
            }
            else if (statusCode == 404)
            {
                // Valid not found response
                return (true, statusCode, null);
            }
            else if (statusCode == 422)
            {
                // Valid validation error
                return (true, statusCode, null);
            }
            else if (statusCode >= 400 && statusCode < 500)
            {
                // Convert other 4xx errors appropriately
                if (content.Contains("not found") || content.Contains("Not found"))
                {
                    return (false, 404, JsonSerializer.Serialize(new { error = $"{CapitalizeEntity(entity)} not found" }));
                }
                else
                {
                    return (false, 422, JsonSerializer.Serialize(new { error = "Validation failed" }));
                }
            }

            return (true, statusCode, null);
        }

        private (bool isValid, int statusCode, string? content) ValidateDeleteResponse(string entity, bool hasId, bool isValidId, int statusCode, string content)
        {
            if (!hasId || !isValidId)
            {
                // DELETE requires valid ID
                return (false, 404, JsonSerializer.Serialize(new { error = $"{CapitalizeEntity(entity)} not found" }));
            }

            if (statusCode == 204)
            {
                // Valid deletion response
                return (true, statusCode, null);
            }
            else if (statusCode == 404)
            {
                // Valid not found response
                return (true, statusCode, null);
            }
            else if (statusCode >= 400 && statusCode < 500)
            {
                // Convert other 4xx errors to 404
                return (false, 404, JsonSerializer.Serialize(new { error = $"{CapitalizeEntity(entity)} not found" }));
            }

            return (true, statusCode, null);
        }

        private async Task HandleValidationException(HttpContext context, ValidationException ex)
        {
            context.Response.StatusCode = 422;
            context.Response.ContentType = "application/json";

            var response = JsonSerializer.Serialize(new
            {
                error = "Validation failed",
                details = ex.Message
            });

            await context.Response.WriteAsync(response);
        }

        private async Task HandleEntityFrameworkException(HttpContext context, Exception ex)
        {
            context.Response.StatusCode = 422;
            context.Response.ContentType = "application/json";

            // Handle common EF exceptions
            string errorMessage = "Validation failed";

            if (ex.Message.Contains("foreign key constraint") || ex.Message.Contains("FOREIGN KEY"))
            {
                errorMessage = "Invalid reference to related entity";
            }
            else if (ex.Message.Contains("duplicate") || ex.Message.Contains("unique"))
            {
                errorMessage = "Duplicate entry";
            }

            var response = JsonSerializer.Serialize(new
            {
                error = errorMessage
            });

            await context.Response.WriteAsync(response);
        }

        private async Task HandleUnexpectedException(HttpContext context, Exception ex)
        {
            context.Response.StatusCode = 500;
            context.Response.ContentType = "application/json";

            var response = JsonSerializer.Serialize(new
            {
                error = "Internal server error"
            });

            await context.Response.WriteAsync(response);
        }

        private static bool IsEntityFrameworkException(Exception ex)
        {
            var exceptionType = ex.GetType().Name;
            return exceptionType.Contains("DbUpdate") ||
                   exceptionType.Contains("SqlException") ||
                   ex.Message.Contains("foreign key") ||
                   ex.Message.Contains("FOREIGN KEY") ||
                   ex.Message.Contains("duplicate key") ||
                   ex.Message.Contains("unique constraint");
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
    }
}

// Extension method to register the middleware
namespace MinimalApiProject.Extensions
{
    public static class MiddlewareExtensions
    {
        public static IApplicationBuilder UseApiResponseValidation(this IApplicationBuilder builder)
        {
            return builder.UseMiddleware<ApiResponseValidationMiddleware>();
        }
    }
}
