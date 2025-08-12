using Microsoft.EntityFrameworkCore;
using Microsoft.OpenApi.Models;
using MinimalApiProject.Data;
using MinimalApiProject.Endpoints;
using MinimalApiProject.Extensions;
using MinimalApiProject;

var builder = WebApplication.CreateBuilder(args);

// Add services
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(builder.Configuration.GetConnectionString("DefaultConnection")));

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.Configure<Microsoft.AspNetCore.Http.Json.JsonOptions>(options =>
{
    options.SerializerOptions.PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.CamelCase;
    options.SerializerOptions.WriteIndented = true;
    // Fix circular reference issue by ignoring cycles
    options.SerializerOptions.ReferenceHandler = System.Text.Json.Serialization.ReferenceHandler.IgnoreCycles;
});

var app = builder.Build();

// Swagger middleware
app.UseSwagger();
app.UseSwaggerUI(options =>
{
    options.SwaggerEndpoint("/swagger/v1/swagger.json", "Minimal API V1");
    options.RoutePrefix = "swagger";
});

app.UseHttpsRedirection();

// Add custom middleware - order is important!
// Request validation middleware should run before response validation
app.UseMiddleware<ApiRequestValidationMiddleware>();
app.UseApiResponseValidation();

// Register endpoints
app.MapUserEndpoints();
app.MapCategoryEndpoints();
app.MapProductEndpoints();

app.Run();
