import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
import aiosqlite
from typing import Optional

class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/suggestions.db"

    async def cog_load(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    message_id INTEGER,
                    user_id INTEGER,
                    content TEXT,
                    status TEXT DEFAULT 'pending',
                    upvotes INTEGER DEFAULT 0,
                    downvotes INTEGER DEFAULT 0,
                    thread_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS suggestion_config (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    slowmode INTEGER DEFAULT 0
                )
            """)
            await db.commit()

    @app_commands.command(name="suggest", description="💡 Submit a suggestion")
    @app_commands.describe(suggestion="Your suggestion")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT channel_id FROM suggestion_config WHERE guild_id = ?",
                (interaction.guild_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return await interaction.response.send_message("Suggestion channel not set. Ask an admin to set it up.", ephemeral=True)
            
            channel_id = row[0]
            channel = self.bot.get_channel(channel_id)
            
            if not channel:
                return await interaction.response.send_message("Suggestion channel not found.", ephemeral=True)

        embed = discord.Embed(
            title="💡 New Suggestion",
            description=suggestion,
            color=0x00ff00
        )
        embed.set_author(name=interaction.author.display_name, icon_url=interaction.author.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.author.id}")
        embed.timestamp = discord.utils.utcnow()

        class SuggestionView(View):
            def __init__(self, message_id, user_id, bot):
                super().__init__(timeout=None)
                self.message_id = message_id
                self.user_id = user_id
                self.bot = bot

            @discord.ui.button(label="👍 Upvote", style=discord.ButtonStyle.green)
            async def upvote(self, interaction: discord.Interaction, button: discord.ui.Button):
                async with aiosqlite.connect("db/suggestions.db") as db:
                    await db.execute(
                        "UPDATE suggestions SET upvotes = upvotes + 1 WHERE message_id = ?",
                        (self.message_id,)
                    )
                    await db.commit()
                
                await interaction.response.send_message("Upvoted!", ephemeral=True)

            @discord.ui.button(label="👎 Downvote", style=discord.ButtonStyle.red)
            async def downvote(self, interaction: discord.Interaction, button: discord.ui.Button):
                async with aiosqlite.connect("db/suggestions.db") as db:
                    await db.execute(
                        "UPDATE suggestions SET downvotes = downvotes + 1 WHERE message_id = ?",
                        (self.message_id,)
                    )
                    await db.commit()
                
                await interaction.response.send_message("Downvoted!", ephemeral=True)

        try:
            message = await channel.send(embed=embed)
            view = SuggestionView(message.id, interaction.user.id, self.bot)
            await message.edit(view=view)
            
            thread = await message.create_thread(
                name=f"Suggestion by {interaction.author.name}",
                auto_archive_duration=1440
            )
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO suggestions (guild_id, message_id, user_id, content, thread_id) VALUES (?, ?, ?, ?, ?)",
                    (interaction.guild_id, message.id, interaction.user.id, suggestion, thread.id)
                )
                await db.commit()
            
            await interaction.response.send_message(f"Suggestion submitted! {message.jump_url}", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error submitting suggestion: {e}", ephemeral=True)

    @app_commands.command(name="setsuggestions", description="📢 Set the suggestion channel")
    @app_commands.describe(channel="Channel for suggestions")
    @commands.has_permissions(manage_guild=True)
    async def setsuggestions(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO suggestion_config (guild_id, channel_id) VALUES (?, ?)",
                (interaction.guild_id, channel.id)
            )
            await db.commit()
        
        await interaction.response.send_message(f"Suggestion channel set to {channel.mention}", ephemeral=True)

    @app_commands.command(name="removesuggestions", description="🗑️ Remove the suggestion channel")
    @commands.has_permissions(manage_guild=True)
    async def removesuggestions(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM suggestion_config WHERE guild_id = ?",
                (interaction.guild_id,)
            )
            await db.commit()
        
        await interaction.response.send_message("Suggestion channel removed.", ephemeral=True)

    @app_commands.command(name="threadconfig", description="⏱️ Set slowmode for suggestion threads")
    @app_commands.describe(seconds="Slowmode in seconds (0 to disable)")
    @commands.has_permissions(manage_channels=True)
    async def threadconfig(self, interaction: discord.Interaction, seconds: int = 0):
        if seconds < 0 or seconds > 21600:
            return await interaction.response.send_message("Slowmode must be between 0 and 21600 seconds.", ephemeral=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO suggestion_config (guild_id, slowmode) VALUES (?, ?)",
                (interaction.guild_id, seconds)
            )
            await db.commit()
        
        await interaction.response.send_message(f"Thread slowmode set to {seconds} seconds.", ephemeral=True)

    @app_commands.command(name="moderate", description="🛡️ Moderate a suggestion")
    @app_commands.describe(message_id="Message ID of the suggestion", status="Status: approve, deny, or consider")
    @commands.has_permissions(manage_messages=True)
    async def moderate(self, interaction: discord.Interaction, message_id: str, status: str):
        if status.lower() not in ["approve", "deny", "consider"]:
            return await interaction.response.send_message("Status must be: approve, deny, or consider", ephemeral=True)
        
        try:
            msg_id = int(message_id)
        except ValueError:
            return await interaction.response.send_message("Invalid message ID.", ephemeral=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT message_id, content FROM suggestions WHERE guild_id = ? AND message_id = ?",
                (interaction.guild_id, msg_id)
            )
            row = await cursor.fetchone()
            
            if not row:
                return await interaction.response.send_message("Suggestion not found.", ephemeral=True)
            
            await db.execute(
                "UPDATE suggestions SET status = ? WHERE message_id = ?",
                (status.lower(), msg_id)
            )
            await db.commit()
        
        channel = interaction.channel
        try:
            message = await channel.fetch_message(msg_id)
            
            status_colors = {
                "approve": 0x00ff00,
                "deny": 0xff0000,
                "consider": 0xffff00
            }
            
            status_emojis = {
                "approve": "✅",
                "deny": "❌",
                "consider": "🤔"
            }
            
            embed = message.embeds[0] if message.embeds else discord.Embed(description=row[1])
            embed.title = f"{status_emojis[status.lower()]} Suggestion {status.title()}ed"
            embed.color = status_colors[status.lower()]
            
            await message.edit(embed=embed)
            await interaction.response.send_message(f"Suggestion marked as {status}.", ephemeral=True)
            
        except discord.NotFound:
            await interaction.response.send_message("Message not found.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="suggestionstats", description="📊 View suggestion statistics")
    @commands.has_permissions(manage_guild=True)
    async def suggestionstats(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*), SUM(upvotes), SUM(downvotes) FROM suggestions WHERE guild_id = ?",
                (interaction.guild_id,)
            )
            row = await cursor.fetchone()
            
            total = row[0] or 0
            upvotes = row[1] or 0
            downvotes = row[2] or 0
        
        embed = discord.Embed(
            title="📊 Suggestion Statistics",
            color=0x00ff00
        )
        embed.add_field(name="Total Suggestions", value=total, inline=True)
        embed.add_field(name="Total Upvotes", value=upvotes, inline=True)
        embed.add_field(name="Total Downvotes", value=downvotes, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Suggestions(bot))
