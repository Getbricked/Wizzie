import asyncio
import aiomysql
import sys
from utils.const import DB_CONFIG

# Usage:
#   python fetch_data.py user <user_id> [guild_id]  - Fetch user data
#   python fetch_data.py all                        - Fetch all users
#   python fetch_data.py leaderboard <guild_id> [limit] - Fetch guild leaderboard


async def get_database_connection():
    """Create and return a database connection."""
    if not DB_CONFIG:
        print("Database configuration not loaded")
        return None

    try:
        connection = await aiomysql.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


async def fetch_user_data(user_id, guild_id=None):
    """Fetch user data from the database."""
    connection = await get_database_connection()
    if not connection:
        return None

    try:
        cursor = await connection.cursor()

        if guild_id:
            # Fetch data for specific guild
            await cursor.execute(
                "SELECT guild_id, user_id, bdate, xp FROM user_data WHERE user_id = %s AND guild_id = %s",
                (user_id, guild_id),
            )
        else:
            # Fetch data for all guilds
            await cursor.execute(
                "SELECT guild_id, user_id, bdate, xp FROM user_data WHERE user_id = %s",
                (user_id,),
            )

        results = await cursor.fetchall()
        return results

    except Exception as e:
        print(f"Error fetching user data: {e}")
        return None
    finally:
        await cursor.close()
        connection.close()


async def fetch_all_users():
    """Fetch all user data from the database."""
    connection = await get_database_connection()
    if not connection:
        return None

    try:
        cursor = await connection.cursor()
        await cursor.execute(
            "SELECT guild_id, user_id, bdate, xp FROM user_data ORDER BY xp DESC"
        )
        results = await cursor.fetchall()
        return results

    except Exception as e:
        print(f"Error fetching all user data: {e}")
        return None
    finally:
        await cursor.close()
        connection.close()


async def fetch_guild_leaderboard(guild_id, limit=10):
    """Fetch top users for a specific guild."""
    connection = await get_database_connection()
    if not connection:
        return None

    try:
        cursor = await connection.cursor()
        await cursor.execute(
            "SELECT user_id, bdate, xp FROM user_data WHERE guild_id = %s ORDER BY xp DESC LIMIT %s",
            (guild_id, limit),
        )
        results = await cursor.fetchall()
        return results

    except Exception as e:
        print(f"Error fetching guild leaderboard: {e}")
        return None
    finally:
        await cursor.close()
        connection.close()


async def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python fetch_data.py user <user_id> [guild_id]  - Fetch user data")
        print("  python fetch_data.py all                        - Fetch all users")
        print(
            "  python fetch_data.py leaderboard <guild_id> [limit] - Fetch guild leaderboard"
        )
        return

    command = sys.argv[1].lower()

    if command == "user":
        if len(sys.argv) < 3:
            print("Error: User ID required")
            return

        user_id = sys.argv[2]
        guild_id = sys.argv[3] if len(sys.argv) > 3 else None

        print(f"Fetching data for user: {user_id}")
        if guild_id:
            print(f"In guild: {guild_id}")

        results = await fetch_user_data(user_id, guild_id)

        if not results:
            print("No data found for this user.")
            return

        print("\n--- User Data ---")
        print(f"{'Guild ID':<20} {'User ID':<20} {'Birthday':<12} {'XP':<10}")
        print("-" * 65)

        for row in results:
            guild_id, user_id, bdate, xp = row
            print(f"{guild_id:<20} {user_id:<20} {bdate:<12} {xp:<10}")

    elif command == "all":
        print("Fetching all user data...")
        results = await fetch_all_users()

        if not results:
            print("No data found.")
            return

        print(f"\n--- All Users ({len(results)} total) ---")
        print(f"{'Guild ID':<20} {'User ID':<20} {'Birthday':<12} {'XP':<10}")
        print("-" * 65)

        for row in results:
            guild_id, user_id, bdate, xp = row
            print(f"{guild_id:<20} {user_id:<20} {bdate:<12} {xp:<10}")

    elif command == "leaderboard":
        if len(sys.argv) < 3:
            print("Error: Guild ID required")
            return

        guild_id = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10

        print(f"Fetching top {limit} users for guild: {guild_id}")
        results = await fetch_guild_leaderboard(guild_id, limit)

        if not results:
            print("No data found for this guild.")
            return

        print(f"\n--- Guild Leaderboard (Top {limit}) ---")
        print(f"{'Rank':<6} {'User ID':<20} {'Birthday':<12} {'XP':<10}")
        print("-" * 50)

        for i, row in enumerate(results, 1):
            user_id, bdate, xp = row
            print(f"{i:<6} {user_id:<20} {bdate:<12} {xp:<10}")

    else:
        print(f"Unknown command: {command}")
        print("Available commands: user, all, leaderboard")


if __name__ == "__main__":
    asyncio.run(main())
