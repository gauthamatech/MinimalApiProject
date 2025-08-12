namespace MinimalApiProject.Endpoints
{
    using Microsoft.EntityFrameworkCore;
    using MinimalApiProject.Data;
    using MinimalApiProject.Models;

    public static class UserEndpoints
    {
        public static void MapUserEndpoints(this WebApplication app)
        {
            app.MapGet("/api/users", async (AppDbContext db) =>
                await db.Users.ToListAsync());

            app.MapGet("/api/users/{id}", async (int id, AppDbContext db) =>
                await db.Users.FindAsync(id) is User user ? Results.Ok(user) : Results.NotFound());

            app.MapPost("/api/users", async (User user, AppDbContext db) =>
            {
                db.Users.Add(user);
                await db.SaveChangesAsync();
                return Results.Created($"/api/users/{user.Id}", user);
            });

            app.MapPut("/api/users/{id}", async (int id, User inputUser, AppDbContext db) =>
            {
                var user = await db.Users.FindAsync(id);
                if (user is null) return Results.NotFound();

                user.Name = inputUser.Name;
                user.Email = inputUser.Email;
                user.CreatedAt = inputUser.CreatedAt;

                await db.SaveChangesAsync();
                return Results.NoContent();
            });

            app.MapDelete("/api/users/{id}", async (int id, AppDbContext db) =>
            {
                if (await db.Users.FindAsync(id) is User user)
                {
                    db.Users.Remove(user);
                    await db.SaveChangesAsync();
                    return Results.NoContent();
                }
                return Results.NotFound();
            });
        }
    }

}
