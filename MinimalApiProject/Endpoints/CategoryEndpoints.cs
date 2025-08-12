namespace MinimalApiProject.Endpoints
{
    using Microsoft.EntityFrameworkCore;
    using MinimalApiProject.Data;
    using MinimalApiProject.Models;

    public static class CategoryEndpoints
    {
        public static void MapCategoryEndpoints(this WebApplication app)
        {
            app.MapGet("/api/categories", async (AppDbContext db) =>
                await db.Categories.ToListAsync());

            app.MapGet("/api/categories/{id}", async (int id, AppDbContext db) =>
                await db.Categories.FindAsync(id) is Category category ? Results.Ok(category) : Results.NotFound());

            app.MapPost("/api/categories", async (Category category, AppDbContext db) =>
            {
                db.Categories.Add(category);
                await db.SaveChangesAsync();
                return Results.Created($"/api/categories/{category.Id}", category);
            });

            app.MapPut("/api/categories/{id}", async (int id, Category inputCategory, AppDbContext db) =>
            {
                var category = await db.Categories.FindAsync(id);
                if (category is null) return Results.NotFound();

                category.Name = inputCategory.Name;
                category.Description = inputCategory.Description;

                await db.SaveChangesAsync();
                return Results.NoContent();
            });

            app.MapDelete("/api/categories/{id}", async (int id, AppDbContext db) =>
            {
                if (await db.Categories.FindAsync(id) is Category category)
                {
                    db.Categories.Remove(category);
                    await db.SaveChangesAsync();
                    return Results.NoContent();
                }
                return Results.NotFound();
            });
        }
    }

}
