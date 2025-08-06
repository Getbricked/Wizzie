import json
import aiomysql
import asyncio
from datetime import datetime
import os
import warnings
from discord.ext import tasks

# Import database configuration from constants
from utils.const import DB_CONFIG


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


async def create_tables():
    """Create necessary database tables if they don't exist."""
    connection = await get_database_connection()
    if not connection:
        return False

    try:
        cursor = await connection.cursor()

        # Check if tables exist first to avoid warnings
        await cursor.execute("SHOW TABLES LIKE 'settings'")
        settings_exists = await cursor.fetchone()

        await cursor.execute("SHOW TABLES LIKE 'user_data'")
        user_data_exists = await cursor.fetchone()

        # Only create tables if they don't exist
        if not settings_exists:
            await cursor.execute(
                """
            CREATE TABLE settings (
                guild_id VARCHAR(50) PRIMARY KEY,
                birthday_role VARCHAR(100),
                birthday_channel VARCHAR(100),
                data_channel VARCHAR(100),
                announcement_channel VARCHAR(100),
                level BOOLEAN
            )
            """
            )
            print("Settings table created.")

        if not user_data_exists:
            await cursor.execute(
                """
            CREATE TABLE user_data (
                guild_id VARCHAR(50),
                user_id VARCHAR(50),
                bdate VARCHAR(10),
                xp INT,
                PRIMARY KEY (guild_id, user_id)
            )
            """
            )
            print("User data table created.")

        await connection.commit()
        if settings_exists and user_data_exists:
            print("Database tables already exist.")
        else:
            print("Database tables created successfully.")
        return True

    except Exception as e:
        print(f"Error creating tables: {e}")
        return False
    finally:
        await cursor.close()
        connection.close()


async def backup_settings_to_database():
    """Backup settings.json data to the database."""
    connection = await get_database_connection()
    if not connection:
        return False

    try:
        cursor = await connection.cursor()

        # Check if settings.json exists
        if not os.path.exists("settings.json"):
            print("settings.json not found, skipping settings backup.")
            return True

        # Read and insert settings.json
        with open("settings.json", "r") as file:
            settings_data = json.load(file)
            for guild_id, settings in settings_data.items():
                await cursor.execute(
                    """
                INSERT INTO settings (guild_id, birthday_role, birthday_channel, data_channel, announcement_channel, level)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                birthday_role = VALUES(birthday_role),
                birthday_channel = VALUES(birthday_channel),
                data_channel = VALUES(data_channel),
                announcement_channel = VALUES(announcement_channel),
                level = VALUES(level)
                """,
                    (
                        guild_id,
                        settings.get("birthday_role"),
                        settings.get("birthday_channel"),
                        settings.get("data_channel"),
                        settings.get("announcement_channel"),
                        settings.get("level", False),
                    ),
                )

        await connection.commit()
        print(
            f"Settings backup completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return True

    except Exception as e:
        print(f"Error backing up settings: {e}")
        return False
    except Exception as e:
        print(f"General error during settings backup: {e}")
        return False
    finally:
        await cursor.close()
        connection.close()


async def backup_user_data_to_database():
    """Backup data.json user data to the database."""
    connection = await get_database_connection()
    if not connection:
        return False

    try:
        cursor = await connection.cursor()

        # Check if data.json exists
        if not os.path.exists("data.json"):
            print("data.json not found, skipping user data backup.")
            return True

        # Read and insert data.json
        with open("data.json", "r") as file:
            data_data = json.load(file)
            for guild_id, users in data_data.items():
                for user_id, user_info in users.items():
                    await cursor.execute(
                        """
                    INSERT INTO user_data (guild_id, user_id, bdate, xp)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    bdate = VALUES(bdate),
                    xp = VALUES(xp)
                    """,
                        (
                            guild_id,
                            user_id,
                            user_info.get("bdate", "Unknown"),
                            user_info.get("xp", 0),
                        ),
                    )

        await connection.commit()
        print(
            f"User data backup completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return True

    except Exception as e:
        print(f"Error backing up user data: {e}")
        return False
    except Exception as e:
        print(f"General error during user data backup: {e}")
        return False
    finally:
        await cursor.close()
        connection.close()


async def backup_all_data():
    """Backup both settings and user data to the database."""
    print(f"Starting daily backup at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create tables if they don't exist
    await create_tables()

    # Backup settings and user data
    settings_success = await backup_settings_to_database()
    user_data_success = await backup_user_data_to_database()

    if settings_success and user_data_success:
        print("Daily backup completed successfully.")
        return True
    else:
        print("Daily backup completed with some errors.")
        return False


@tasks.loop(hours=24)
async def daily_backup_task():
    """Task that runs daily to backup data to the database."""
    await backup_all_data()


async def start_daily_backup():
    """Start the daily backup task."""
    if not daily_backup_task.is_running():
        daily_backup_task.start()
        print("Daily backup task started.")


# For backwards compatibility - run backup if script is executed directly
if __name__ == "__main__":
    asyncio.run(backup_all_data())
