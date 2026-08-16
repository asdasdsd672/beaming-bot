import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button
from datetime import datetime, timezone
import asyncio

class WelcomeGoodbye(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/welcome_goodbye.db"
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()

    async def _create_tables(self):
        """Create welcome/goodbye database tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS welcome_config (
                        guild_id INTEGER PRIMARY KEY,
                        welcome_channel_id INTEGER,
                        goodbye_channel_id INTEGER,
                        welcome_message TEXT,
                        goodbye_message TEXT,
                        welcome_enabled BOOLEAN DEFAULT 1,
                        goodbye_enabled BOOLEAN DEFAULT 1,
                        welcome_image_url TEXT,
                        goodbye_image_url TEXT
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS welcome_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        user_id INTEGER,
                        username TEXT,
                        join_time TIMESTAMP,
                        leave_time TIMESTAMP
                    )
                """)
                
                await db.commit()
                
        except Exception as e:
            print(f"Error creating welcome/goodbye database: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member join events"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT welcome_channel_id, welcome_message, welcome_enabled, welcome_image_url FROM welcome_config WHERE guild_id = ?",
                    (member.guild.id,)
                )
                config = await cursor.fetchone()
                
                if not config or not config[2]:
                    return
                
                welcome_channel_id, welcome_message, welcome_enabled, welcome_image_url = config
                
                if welcome_channel_id:
                    channel = member.guild.get_channel(welcome_channel_id)
                    if channel:
                        # Create welcome embed
                        embed = discord.Embed(
                            title="👋 Welcome to the Server!",
                            description=f"Welcome {member.mention} to **{member.guild.name}**!",
                            color=0x00ff00,
                            timestamp=datetime.now(timezone.utc)
                        )
                        
                        # Add member count
                        member_count = len(member.guild.members)
                        embed.add_field(name="Member Count", value=f"#{member_count}", inline=True)
                        
                        # Add custom message
                        if welcome_message:
                            formatted_message = welcome_message.replace("{user}", member.mention).replace("{server}", member.guild.name).replace("{count}", str(member_count))
                            embed.add_field(name="Message", value=formatted_message[:1024], inline=False)
                        
                        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
                        embed.set_thumbnail(url=member.display_avatar.url)
                        
                        if welcome_image_url:
                            embed.set_image(url=welcome_image_url)
                        
                        embed.set_footer(text=f"User ID: {member.id}")
                        
                        await channel.send(embed=embed)
                
                # Log to history
                await db.execute(
                    "INSERT INTO welcome_history (guild_id, user_id, username, join_time) VALUES (?, ?, ?, ?)",
                    (member.guild.id, member.id, member.name, datetime.now(timezone.utc).isoformat())
                )
                await db.commit()
                
        except Exception as e:
            print(f"Error handling member join: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member leave events"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT goodbye_channel_id, goodbye_message, goodbye_enabled, goodbye_image_url FROM welcome_config WHERE guild_id = ?",
                    (member.guild.id,)
                )
                config = await cursor.fetchone()
                
                if not config or not config[2]:
                    return
                
                goodbye_channel_id, goodbye_message, goodbye_enabled, goodbye_image_url = config
                
                if goodbye_channel_id:
                    channel = member.guild.get_channel(goodbye_channel_id)
                    if channel:
                        # Calculate time spent in server
                        cursor = await db.execute(
                            "SELECT join_time FROM welcome_history WHERE guild_id = ? AND user_id = ? ORDER BY join_time DESC LIMIT 1",
                            (member.guild.id, member.id)
                        )
                        join_data = await cursor.fetchone()
                        
                        time_spent = "Unknown"
                        if join_data:
                            join_time = datetime.fromisoformat(join_data[0])
                            time_spent = str(datetime.now(timezone.utc) - join_time).split('.')[0]
                        
                        # Create goodbye embed
                        embed = discord.Embed(
                            title="👋 Goodbye!",
                            description=f"{member.name} has left **{member.guild.name}**.",
                            color=0xff0000,
                            timestamp=datetime.now(timezone.utc)
                        )
                        
                        embed.add_field(name="Time in Server", value=time_spent, inline=True)
                        
                        if goodbye_message:
                            formatted_message = goodbye_message.replace("{user}", member.name).replace("{server}", member.guild.name).replace("{time}", time_spent)
                            embed.add_field(name="Message", value=formatted_message[:1024], inline=False)
                        
                        embed.set_thumbnail(url=member.display_avatar.url)
                        
                        if goodbye_image_url:
                            embed.set_image(url=goodbye_image_url)
                        
                        embed.set_footer(text=f"User ID: {member.id}")
                        
                        await channel.send(embed=embed)
                
                # Update history
                await db.execute(
                    "UPDATE welcome_history SET leave_time = ? WHERE guild_id = ? AND user_id = ? AND leave_time IS NULL",
                    (datetime.now(timezone.utc).isoformat(), member.guild.id, member.id)
                )
                await db.commit()
                
        except Exception as e:
            print(f"Error handling member leave: {e}")

    @commands.group(name="welcome", invoke_without_command=True, description="👋 Welcome system commands")
    async def welcome(self, ctx):
        """👋 Welcome system commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @welcome.command(name="setup", description="⚙️ Set up the welcome system")
    @commands.has_permissions(administrator=True)
    async def welcome_setup(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set up the welcome system"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO welcome_config (guild_id, welcome_channel_id) VALUES (?, ?)",
                (ctx.guild.id, channel.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Welcome System Configured",
            description=f"Welcome messages will be sent to {channel.mention}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @welcome.command(name="message", description="💬 Set the welcome message")
    @commands.has_permissions(administrator=True)
    async def set_welcome_message(self, ctx: commands.Context, *, message: str):
        """Set the welcome message"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE welcome_config SET welcome_message = ? WHERE guild_id = ?",
                (message, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Welcome Message Set",
            description="Welcome message updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Message", value=message[:1024], inline=False)
        embed.add_field(name="Variables", value="{user} - User mention\n{server} - Server name\n{count} - Member count", inline=False)
        
        await ctx.send(embed=embed)

    @welcome.command(name="image", description="🖼️ Set the welcome image")
    @commands.has_permissions(administrator=True)
    async def set_welcome_image(self, ctx: commands.Context, url: str):
        """Set the welcome image URL"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE welcome_config SET welcome_image_url = ? WHERE guild_id = ?",
                (url, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Welcome Image Set",
            description="Welcome image URL updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_image(url=url)
        
        await ctx.send(embed=embed)

    @welcome.command(name="toggle", description="🔧 Toggle welcome messages")
    @commands.has_permissions(administrator=True)
    async def toggle_welcome(self, ctx: commands.Context):
        """Toggle welcome messages"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT welcome_enabled FROM welcome_config WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            
            current = result[0] if result else 1
            new_value = 0 if current else 1
            
            await db.execute(
                "UPDATE welcome_config SET welcome_enabled = ? WHERE guild_id = ?",
                (new_value, ctx.guild.id)
            )
            await db.commit()
        
        status = "enabled" if new_value else "disabled"
        embed = discord.Embed(
            title="🔧 Welcome Messages Toggled",
            description=f"Welcome messages have been {status}.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @commands.group(name="goodbye", invoke_without_command=True, description="👋 Goodbye system commands")
    async def goodbye(self, ctx):
        """👋 Goodbye system commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @goodbye.command(name="setup", description="⚙️ Set up the goodbye system")
    @commands.has_permissions(administrator=True)
    async def goodbye_setup(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set up the goodbye system"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO welcome_config (guild_id, goodbye_channel_id) VALUES (?, ?)",
                (ctx.guild.id, channel.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Goodbye System Configured",
            description=f"Goodbye messages will be sent to {channel.mention}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @goodbye.command(name="message", description="💬 Set the goodbye message")
    @commands.has_permissions(administrator=True)
    async def set_goodbye_message(self, ctx: commands.Context, *, message: str):
        """Set the goodbye message"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE welcome_config SET goodbye_message = ? WHERE guild_id = ?",
                (message, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Goodbye Message Set",
            description="Goodbye message updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Message", value=message[:1024], inline=False)
        embed.add_field(name="Variables", value="{user} - User name\n{server} - Server name\n{time} - Time spent", inline=False)
        
        await ctx.send(embed=embed)

    @goodbye.command(name="image", description="🖼️ Set the goodbye image")
    @commands.has_permissions(administrator=True)
    async def set_goodbye_image(self, ctx: commands.Context, url: str):
        """Set the goodbye image URL"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE welcome_config SET goodbye_image_url = ? WHERE guild_id = ?",
                (url, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Goodbye Image Set",
            description="Goodbye image URL updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_image(url=url)
        
        await ctx.send(embed=embed)

    @goodbye.command(name="toggle", description="🔧 Toggle goodbye messages")
    @commands.has_permissions(administrator=True)
    async def toggle_goodbye(self, ctx: commands.Context):
        """Toggle goodbye messages"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT goodbye_enabled FROM welcome_config WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            
            current = result[0] if result else 1
            new_value = 0 if current else 1
            
            await db.execute(
                "UPDATE welcome_config SET goodbye_enabled = ? WHERE guild_id = ?",
                (new_value, ctx.guild.id)
            )
            await db.commit()
        
        status = "enabled" if new_value else "disabled"
        embed = discord.Embed(
            title="🔧 Goodbye Messages Toggled",
            description=f"Goodbye messages have been {status}.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @commands.command(name="joins", description="📊 View join history")
    @commands.has_permissions(administrator=True)
    async def join_history(self, ctx: commands.Context, limit: int = 10):
        """View join history"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id, username, join_time, leave_time FROM welcome_history WHERE guild_id = ? ORDER BY join_time DESC LIMIT ?",
                (ctx.guild.id, limit)
            )
            history = await cursor.fetchall()
        
        if not history:
            embed = discord.Embed(
                title="📊 Join History",
                description="No join history found.",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"📊 Recent Joins ({len(history)})",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        history_text = ""
        for user_id, username, join_time, leave_time in history:
            status = "🟢 Active" if not leave_time else "🔴 Left"
            join_date = datetime.fromisoformat(join_time).strftime("%Y-%m-%d %H:%M")
            history_text += f"**{username}** - {status}\n"
            history_text += f"   Joined: {join_date}\n"
            if leave_time:
                leave_date = datetime.fromisoformat(leave_time).strftime("%Y-%m-%d %H:%M")
                history_text += f"   Left: {leave_date}\n"
            history_text += "\n"
        
        embed.description = history_text[:4096]
        embed.set_footer(text=f"Requested by {ctx.author}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(WelcomeGoodbye(bot))
