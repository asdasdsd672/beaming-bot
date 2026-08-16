import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional

class StrikeSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/strikes.db"

    async def cog_load(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS strikes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    strikes INTEGER DEFAULT 0,
                    last_strike TIMESTAMP,
                    reset_at TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS strike_config (
                    guild_id INTEGER PRIMARY KEY,
                    delete_threshold INTEGER DEFAULT 3,
                    timeout_threshold INTEGER DEFAULT 5,
                    kick_threshold INTEGER DEFAULT 8,
                    ban_threshold INTEGER DEFAULT 10,
                    reset_hours INTEGER DEFAULT 24
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS strike_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    reason TEXT,
                    action_taken TEXT,
                    strike_count INTEGER,
                    timestamp TIMESTAMP
                )
            """)
            await db.commit()

    async def get_strike_count(self, guild_id: int, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT strikes, reset_at FROM strikes WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            row = await cursor.fetchone()
            
            if not row:
                return 0
            
            strikes, reset_at = row
            
            # Check if strikes should be reset
            if reset_at and datetime.now() > datetime.fromisoformat(reset_at):
                await self.reset_strikes(guild_id, user_id)
                return 0
            
            return strikes

    async def add_strike(self, guild_id: int, user_id: int, reason: str) -> tuple[int, str]:
        """Add a strike and return (new_strike_count, action_taken)"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get current config
            cursor = await db.execute(
                "SELECT delete_threshold, timeout_threshold, kick_threshold, ban_threshold, reset_hours FROM strike_config WHERE guild_id = ?",
                (guild_id,)
            )
            config_row = await cursor.fetchone()
            
            if not config_row:
                # Default config
                delete_threshold, timeout_threshold, kick_threshold, ban_threshold, reset_hours = 3, 5, 8, 10, 24
            else:
                delete_threshold, timeout_threshold, kick_threshold, ban_threshold, reset_hours = config_row
            
            # Get current strikes
            cursor = await db.execute(
                "SELECT strikes, reset_at FROM strikes WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            row = await cursor.fetchone()
            
            reset_time = datetime.now() + timedelta(hours=reset_hours)
            
            if row:
                strikes, old_reset = row
                # Check if reset time passed
                if old_reset and datetime.now() > datetime.fromisoformat(old_reset):
                    strikes = 0
                strikes += 1
                
                await db.execute(
                    "UPDATE strikes SET strikes = ?, last_strike = ?, reset_at = ? WHERE guild_id = ? AND user_id = ?",
                    (strikes, datetime.now().isoformat(), reset_time.isoformat(), guild_id, user_id)
                )
            else:
                strikes = 1
                await db.execute(
                    "INSERT INTO strikes (guild_id, user_id, strikes, last_strike, reset_at) VALUES (?, ?, ?, ?, ?)",
                    (guild_id, user_id, strikes, datetime.now().isoformat(), reset_time.isoformat())
                )
            
            # Determine action based on strike count
            action_taken = "none"
            if strikes >= ban_threshold:
                action_taken = "ban"
            elif strikes >= kick_threshold:
                action_taken = "kick"
            elif strikes >= timeout_threshold:
                action_taken = "timeout"
            elif strikes >= delete_threshold:
                action_taken = "delete"
            
            # Log the strike
            await db.execute(
                "INSERT INTO strike_log (guild_id, user_id, reason, action_taken, strike_count, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (guild_id, user_id, reason, action_taken, strikes, datetime.now().isoformat())
            )
            
            await db.commit()
            return strikes, action_taken

    async def reset_strikes(self, guild_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM strikes WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            await db.commit()

    async def clear_strikes(self, guild_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE strikes SET strikes = 0, last_strike = NULL WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            await db.commit()

    @app_commands.command(name="strikes", description="⚠️ View a user's strike count")
    @app_commands.describe(user="User to check strikes for")
    @commands.has_permissions(moderate_members=True)
    async def strikes(self, interaction: discord.Interaction, user: discord.User):
        strike_count = await self.get_strike_count(interaction.guild_id, user.id)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT delete_threshold, timeout_threshold, kick_threshold, ban_threshold FROM strike_config WHERE guild_id = ?",
                (interaction.guild_id,)
            )
            config_row = await cursor.fetchone()
            
            if config_row:
                delete_threshold, timeout_threshold, kick_threshold, ban_threshold = config_row
            else:
                delete_threshold, timeout_threshold, kick_threshold, ban_threshold = 3, 5, 8, 10
        
        embed = discord.Embed(
            title=f"📊 Strike Information for {user.display_name}",
            color=0x00ff00
        )
        embed.add_field(name="Current Strikes", value=strike_count, inline=True)
        embed.add_field(name="Delete Threshold", value=delete_threshold, inline=True)
        embed.add_field(name="Timeout Threshold", value=timeout_threshold, inline=True)
        embed.add_field(name="Kick Threshold", value=kick_threshold, inline=True)
        embed.add_field(name="Ban Threshold", value=ban_threshold, inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="addstrike", description="➕ Add a strike to a user")
    @app_commands.describe(user="User to add strike to", reason="Reason for the strike")
    @commands.has_permissions(moderate_members=True)
    async def addstrike(self, interaction: discord.Interaction, user: discord.User, reason: str):
        strike_count, action_taken = await self.add_strike(interaction.guild_id, user.id, reason)
        
        # Execute the action if needed
        member = interaction.guild.get_member(user.id)
        if member and action_taken != "none":
            if action_taken == "ban":
                try:
                    await member.ban(reason=f"Strike threshold reached: {reason}")
                except discord.Forbidden:
                    await interaction.followup.send("Failed to ban user (missing permissions)", ephemeral=True)
            elif action_taken == "kick":
                try:
                    await member.kick(reason=f"Strike threshold reached: {reason}")
                except discord.Forbidden:
                    await interaction.followup.send("Failed to kick user (missing permissions)", ephemeral=True)
            elif action_taken == "timeout":
                try:
                    await member.timeout(timedelta(minutes=30), reason=f"Strike threshold reached: {reason}")
                except discord.Forbidden:
                    await interaction.followup.send("Failed to timeout user (missing permissions)", ephemeral=True)
        
        embed = discord.Embed(
            title="⚠️ Strike Added",
            description=f"Added strike to {user.mention}",
            color=0xff0000
        )
        embed.add_field(name="Total Strikes", value=strike_count, inline=True)
        embed.add_field(name="Action Taken", value=action_taken.upper(), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearstrikes", description="🧹 Clear all strikes for a user")
    @app_commands.describe(user="User to clear strikes for")
    @commands.has_permissions(administrator=True)
    async def clearstrikes(self, interaction: discord.Interaction, user: discord.User):
        await self.clear_strikes(interaction.guild_id, user.id)
        
        embed = discord.Embed(
            title="✅ Strikes Cleared",
            description=f"Cleared all strikes for {user.mention}",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="strikethreshold", description="⚙️ Configure strike thresholds")
    @app_commands.describe(delete="Strikes before delete action", timeout="Strikes before timeout action", kick="Strikes before kick action", ban="Strikes before ban action", reset_hours="Hours before strike reset")
    @commands.has_permissions(administrator=True)
    async def strikethreshold(self, interaction: discord.Interaction, delete: int = 3, timeout: int = 5, kick: int = 8, ban: int = 10, reset_hours: int = 24):
        if delete < 1 or timeout < 1 or kick < 1 or ban < 1 or reset_hours < 1:
            return await interaction.response.send_message("All values must be positive integers.", ephemeral=True)
        
        if not (delete < timeout < kick < ban):
            return await interaction.response.send_message("Thresholds must be in ascending order: delete < timeout < kick < ban", ephemeral=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO strike_config (guild_id, delete_threshold, timeout_threshold, kick_threshold, ban_threshold, reset_hours) VALUES (?, ?, ?, ?, ?, ?)",
                (interaction.guild_id, delete, timeout, kick, ban, reset_hours)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="⚙️ Strike Thresholds Updated",
            color=0x00ff00
        )
        embed.add_field(name="Delete Threshold", value=delete, inline=True)
        embed.add_field(name="Timeout Threshold", value=timeout, inline=True)
        embed.add_field(name="Kick Threshold", value=kick, inline=True)
        embed.add_field(name="Ban Threshold", value=ban, inline=True)
        embed.add_field(name="Reset Hours", value=reset_hours, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="strikelog", description="📜 View strike log for a user")
    @app_commands.describe(user="User to view strike log for")
    @commands.has_permissions(moderate_members=True)
    async def strikelog(self, interaction: discord.Interaction, user: discord.User):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT reason, action_taken, strike_count, timestamp FROM strike_log WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC LIMIT 10",
                (interaction.guild_id, user.id)
            )
            rows = await cursor.fetchall()
        
        if not rows:
            return await interaction.response.send_message("No strike history found for this user.", ephemeral=True)
        
        embed = discord.Embed(
            title=f"📜 Strike Log for {user.display_name}",
            color=0x00ff00
        )
        
        for reason, action, count, timestamp in rows:
            embed.add_field(
                name=f"{count} strikes - {action.upper()}",
                value=f"{reason}\n*{timestamp}*",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(StrikeSystem(bot))
