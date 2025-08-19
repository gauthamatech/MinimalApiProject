namespace MinimalApiProject.Endpoints
{
    using Microsoft.EntityFrameworkCore;
    using MinimalApiProject.Data;
    using MinimalApiProject.Models;

    public static class ProductEndpoints
    {
        public static void MapProductEndpoints(this WebApplication app)
        {
            app.MapGet("/api/products", async (AppDbContext db) =>
                await db.Products.Include(p => p.Category).Include(p => p.User).ToListAsync());

            app.MapGet("/api/products/{id}", async (int id, AppDbContext db) =>
                await db.Products.Include(p => p.Category).Include(p => p.User)
                    .FirstOrDefaultAsync(p => p.Id == id) is Product product
                    ? Results.Ok(product) : Results.NotFound());

            app.MapPost("/api/products", async (Product product, AppDbContext db) =>
            {
                // Validate that the Category exists
                var categoryExists = await db.Categories.AnyAsync(c => c.Id == product.CategoryId);
                if (!categoryExists)
                {
                    return Results.BadRequest("Invalid CategoryId");
                }

                // If UserId is provided, validate that the User exists
                if (product.UserId.HasValue)
                {
                    var userExists = await db.Users.AnyAsync(u => u.Id == product.UserId.Value);
                    if (!userExists)
                    {
                        return Results.BadRequest("Invalid UserId");
                    }
                }

                db.Products.Add(product);
                await db.SaveChangesAsync();
                return Results.Created($"/api/products/{product.Id}", product);
            });

            app.MapPut("/api/products/{id}", async (int id, Product inputProduct, AppDbContext db) =>
            {
                var product = await db.Products.FindAsync(id);
                if (product is null) return Results.NotFound();

                product.Name = inputProduct.Name;
                product.Description = inputProduct.Description;
                product.Price = inputProduct.Price;
                product.CategoryId = inputProduct.CategoryId;
                
                // Only update UserId if it's provided
                if (inputProduct.UserId.HasValue)
                {
                    product.UserId = inputProduct.UserId;
                }

                await db.SaveChangesAsync();
                return Results.NoContent();
            });

            app.MapDelete("/api/products/{id}", async (int id, AppDbContext db) =>
            {
                if (await db.Products.FindAsync(id) is Product product)
                {
                    db.Products.Remove(product);
                    await db.SaveChangesAsync();
                    return Results.NoContent();
                }
                return Results.NotFound();
            });
        }
    }

}