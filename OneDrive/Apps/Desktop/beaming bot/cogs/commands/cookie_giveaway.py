import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import asyncio
import random
from datetime import datetime, timezone, timedelta
import json
import hashlib

class CookieGiveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_giveaways = {}  # giveaway_id -> giveaway data
        self.cookie_security = True
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()
        await self._load_active_giveaways()

    async def _create_tables(self):
        """Create cookie giveaway database tables"""
        try:
            if not hasattr(self.bot, 'db') or self.bot.db is None:
                import aiosqlite
                db_path = "db/cookie_giveaways.db"
                self.bot.db = await aiosqlite.connect(db_path)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS cookie_giveaways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    message_id INTEGER,
                    host_id INTEGER,
                    cookie_hash TEXT,
                    prize_description TEXT,
                    end_time TIMESTAMP,
                    winner_id INTEGER,
                    participants TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS cookie_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    giveaway_id INTEGER,
                    user_id INTEGER,
                    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (giveaway_id, user_id)
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS cookie_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    action TEXT,
                    giveaway_id INTEGER,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.commit()
            
        except Exception as e:
            print(f"Error creating cookie giveaway database: {e}")

    async def _load_active_giveaways(self):
        """Load active giveaways from database"""
        try:
            async with self.bot.db.execute(
                "SELECT id, guild_id, channel_id, message_id, host_id, cookie_hash, prize_description, end_time, participants, status FROM cookie_giveaways WHERE status = 'active'"
            ) as cursor:
                rows = await cursor.fetchall()
            
            for row in rows:
                giveaway_id, guild_id, channel_id, message_id, host_id, cookie_hash, prize_description, end_time, participants, status = row
                self.active_giveaways[giveaway_id] = {
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "host_id": host_id,
                    "cookie_hash": cookie_hash,
                    "prize_description": prize_description,
                    "end_time": end_time,
                    "participants": json.loads(participants) if participants else [],
                    "status": status
                }
            
            # Start background task to check for ended giveaways
            self.bot.loop.create_task(self._check_giveaway_endings())
            
        except Exception as e:
            print(f"Error loading active giveaways: {e}")

    async def _check_giveaway_endings(self):
        """Background task to check for ended giveaways"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                current_time = datetime.now(timezone.utc)
                ended_giveaways = []
                
                for giveaway_id, data in self.active_giveaways.items():
                    end_time = datetime.fromisoformat(data["end_time"])
                    if current_time >= end_time:
                        ended_giveaways.append(giveaway_id)
                
                for giveaway_id in ended_giveaways:
                    await self._end_giveaway(giveaway_id)
                    
            except Exception as e:
                print(f"Error checking giveaway endings: {e}")

    async def _end_giveaway(self, giveaway_id: int):
        """End a giveaway and pick winner"""
        try:
            if giveaway_id not in self.active_giveaways:
                return
            
            data = self.active_giveaways[giveaway_id]
            participants = data["participants"]
            
            if not participants:
                # No participants
                await self._announce_no_winner(giveaway_id, data)
                return
            
            # Pick random winner
            winner_id = random.choice(participants)
            
            # Update database
            await self.bot.db.execute(
                "UPDATE cookie_giveaways SET winner_id = ?, status = 'ended' WHERE id = ?",
                (winner_id, giveaway_id)
            )
            await self.bot.db.commit()
            
            # Announce winner
            await self._announce_winner(giveaway_id, data, winner_id)
            
            # Remove from active giveaways
            del self.active_giveaways[giveaway_id]
            
        except Exception as e:
            print(f"Error ending giveaway {giveaway_id}: {e}")

    async def _announce_winner(self, giveaway_id: int, data: dict, winner_id: int):
        """Announce the giveaway winner"""
        try:
            channel = self.bot.get_channel(data["channel_id"])
            if not channel:
                return
            
            message = await channel.fetch_message(data["message_id"])
            winner = self.bot.get_user(winner_id)
            
            if winner:
                embed = discord.Embed(
                    title="🎉 Cookie Giveaway Ended!",
                    description=f"**Winner:** {winner.mention}\n\n**Prize:** {data['prize_description']}",
                    color=0x00ff00,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Giveaway ID", value=str(giveaway_id), inline=True)
                embed.add_field(name="Total Entries", value=str(len(data["participants"])), inline=True)
                embed.set_footer(text=f"Hosted by: <@{data['host_id']}>")
                
                await message.edit(embed=embed, view=None)
                
                # Send DM to winner with cookie
                try:
                    # Get the actual cookie (in production, this should be securely stored and retrieved)
                    # For security, we're not storing actual cookies, just hashes
                    dm_embed = discord.Embed(
                        title="🍪 You Won the Cookie Giveaway!",
                        description="Congratulations! You won the Roblox cookie giveaway. Please contact the giveaway host to receive your prize.",
                        color=0x00ff00
                    )
                    dm_embed.add_field(name="Giveaway ID", value=str(giveaway_id), inline=True)
                    dm_embed.add_field(name="Prize", value=data["prize_description"], inline=True)
                    
                    await winner.send(embed=dm_embed)
                    
                except discord.Forbidden:
                    await channel.send(f"Could not DM {winner.mention}. They have DMs disabled.")
                    
            else:
                await channel.send("Winner account not found.")
                
        except Exception as e:
            print(f"Error announcing winner: {e}")

    async def _announce_no_winner(self, giveaway_id: int, data: dict):
        """Announce that giveaway had no participants"""
        try:
            channel = self.bot.get_channel(data["channel_id"])
            if not channel:
                return
            
            message = await channel.fetch_message(data["message_id"])
            
            embed = discord.Embed(
                title="😢 Cookie Giveaway Ended",
                description="No participants entered the giveaway.",
                color=0xff0000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Giveaway ID", value=str(giveaway_id), inline=True)
            
            await message.edit(embed=embed, view=None)
            
            # Update database
            await self.bot.db.execute(
                "UPDATE cookie_giveaways SET status = 'ended' WHERE id = ?",
                (giveaway_id,)
            )
            await self.bot.db.commit()
            
            del self.active_giveaways[giveaway_id]
            
        except Exception as e:
            print(f"Error announcing no winner: {e}")

    def _hash_cookie(self, cookie: str) -> str:
        """Hash a cookie for secure storage"""
        return hashlib.sha256(cookie.encode()).hexdigest()

    @commands.group(name="cookie", invoke_without_command=True, description="🍪 Roblox cookie giveaway commands")
    async def cookie(self, ctx):
        """🍪 Cookie giveaway commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @cookie.command(name="giveaway", description="🎁 Start a Roblox cookie giveaway")
    @app_commands.describe(duration="Duration in minutes", prize="Description of the prize", cookie="Roblox cookie (will be securely hashed)")
    async def start_giveaway(self, ctx: commands.Context, duration: int, prize: str, cookie: str):
        """Start a cookie giveaway"""
        # Check permissions using role permissions system
        role_perms_cog = self.bot.get_cog('RolePermissions')
        if role_perms_cog and not role_perms_cog.has_permission(ctx.author, 'cookie_giveaway'):
            return await ctx.send("You don't have permission to start cookie giveaways. Required: Owner, Co-Owner, Creator, Admin, or Head Mod role.")
        
        if duration < 1 or duration > 10080:  # Max 1 week
            return await ctx.send("Duration must be between 1 and 10080 minutes (1 week).")
        
        if not cookie.strip():
            return await ctx.send("Please provide a valid Roblox cookie.")
        
        await ctx.defer()
        
        try:
            # Calculate end time
            end_time = datetime.now(timezone.utc) + timedelta(minutes=duration)
            
            # Hash the cookie for secure storage
            cookie_hash = self._hash_cookie(cookie)
            
            # Create giveaway embed
            embed = discord.Embed(
                title="🍪 Roblox Cookie Giveaway",
                description=f"**Prize:** {prize}\n\n**Ends:** <t:{int(end_time.timestamp())}:R>\n**Hosted by:** {ctx.author.mention}",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="How to Enter", value="Click the button below to enter the giveaway!", inline=False)
            embed.set_footer(text=f"Giveaway ID will be assigned • BeZmerz Bot")
            
            # Create view with enter button
            view = CookieGiveawayView(self.bot, ctx.author.id)
            
            # Send message
            message = await ctx.send(embed=embed, view=view)
            
            # Store in database
            await self.bot.db.execute(
                """INSERT INTO cookie_giveaways 
                   (guild_id, channel_id, message_id, host_id, cookie_hash, prize_description, end_time, participants, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                (ctx.guild.id, ctx.channel.id, message.id, ctx.author.id, cookie_hash, prize, end_time.isoformat(), json.dumps([]))
            )
            await self.bot.db.commit()
            
            # Get giveaway ID
            async with self.bot.db.execute("SELECT id FROM cookie_giveaways WHERE message_id = ?", (message.id,)) as cursor:
                row = await cursor.fetchone()
                giveaway_id = row[0] if row else None
            
            # Store in active giveaways
            if giveaway_id:
                self.active_giveaways[giveaway_id] = {
                    "guild_id": ctx.guild.id,
                    "channel_id": ctx.channel.id,
                    "message_id": message.id,
                    "host_id": ctx.author.id,
                    "cookie_hash": cookie_hash,
                    "prize_description": prize,
                    "end_time": end_time.isoformat(),
                    "participants": [],
                    "status": "active"
                }
                
                # Log audit
                await self.bot.db.execute(
                    "INSERT INTO cookie_audit_log (admin_id, action, giveaway_id, details) VALUES (?, ?, ?, ?)",
                    (ctx.author.id, "start_giveaway", giveaway_id, f"Prize: {prize}, Duration: {duration}min")
                )
                await self.bot.db.commit()
            
            # Update embed with giveaway ID
            embed.set_footer(text=f"Giveaway ID: {giveaway_id} • BeZmerz Bot")
            await message.edit(embed=embed)
            
            success_embed = discord.Embed(
                title="✅ Cookie Giveaway Started",
                description=f"Giveaway ID: **{giveaway_id}**\nEnds: <t:{int(end_time.timestamp())}:R>",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            await ctx.send(embed=success_embed)
            
        except Exception as e:
            await ctx.send(f"Error starting giveaway: {str(e)}")

    @cookie.command(name="end", description="⏹️ End a cookie giveaway early")
    @app_commands.describe(giveaway_id="Giveaway ID to end")
    async def end_giveaway(self, ctx: commands.Context, giveaway_id: int):
        """End a giveaway early"""
        # Check permissions
        role_perms_cog = self.bot.get_cog('RolePermissions')
        if role_perms_cog and not role_perms_cog.has_permission(ctx.author, 'cookie_giveaway'):
            return await ctx.send("You don't have permission to end cookie giveaways.")
        
        if giveaway_id not in self.active_giveaways:
            return await ctx.send(f"Giveaway {giveaway_id} not found or already ended.")
        
        await self._end_giveaway(giveaway_id)
        
        embed = discord.Embed(
            title="⏸️ Giveaway Ended",
            description=f"Giveaway {giveaway_id} has been ended early.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @cookie.command(name="list", description="📋 List active cookie giveaways")
    async def list_giveaways(self, ctx: commands.Context):
        """List all active cookie giveaways"""
        await ctx.defer()
        
        if not self.active_giveaways:
            return await ctx.send("No active cookie giveaways.")
        
        embed = discord.Embed(
            title="🍪 Active Cookie Giveaways",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        for giveaway_id, data in self.active_giveaways.items():
            end_time = datetime.fromisoformat(data["end_time"])
            participants_count = len(data["participants"])
            
            embed.add_field(
                name=f"ID: {giveaway_id}",
                value=f"**Prize:** {data['prize_description'][:50]}...\n**Ends:** <t:{int(end_time.timestamp())}:R>\n**Entries:** {participants_count}",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @cookie.command(name="reroll", description="🎲 Reroll giveaway winner")
    @app_commands.describe(giveaway_id="Giveaway ID to reroll")
    async def reroll_giveaway(self, ctx: commands.Context, giveaway_id: int):
        """Reroll a giveaway winner"""
        # Check permissions
        role_perms_cog = self.bot.get_cog('RolePermissions')
        if role_perms_cog and not role_perms_cog.has_permission(ctx.author, 'cookie_giveaway'):
            return await ctx.send("You don't have permission to reroll cookie giveaways.")
        
        # Get giveaway data from database
        async with self.bot.db.execute(
            "SELECT participants, status FROM cookie_giveaways WHERE id = ?",
            (giveaway_id,)
        ) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            return await ctx.send(f"Giveaway {giveaway_id} not found.")
        
        participants_json, status = row
        if status != 'ended':
            return await ctx.send("Can only reroll ended giveaways.")
        
        participants = json.loads(participants_json) if participants_json else []
        if not participants:
            return await ctx.send("No participants to reroll.")
        
        # Pick new winner
        new_winner_id = random.choice(participants)
        
        # Update database
        await self.bot.db.execute(
            "UPDATE cookie_giveaways SET winner_id = ? WHERE id = ?",
            (new_winner_id, giveaway_id)
        )
        await self.bot.db.commit()
        
        new_winner = self.bot.get_user(new_winner_id)
        
        embed = discord.Embed(
            title="🎲 Giveaway Rerolled",
            description=f"**New Winner:** {new_winner.mention if new_winner else 'Unknown User'}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Giveaway ID", value=str(giveaway_id), inline=True)
        
        await ctx.send(embed=embed)

class CookieGiveawayView(View):
    def __init__(self, bot, host_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.host_id = host_id

    @discord.ui.button(label="🍪 Enter Giveaway", style=discord.ButtonStyle.primary, emoji="🍪")
    async def enter_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        # Find the giveaway ID from the message
        async with self.bot.db.execute(
            "SELECT id, participants, end_time FROM cookie_giveaways WHERE message_id = ? AND status = 'active'",
            (interaction.message.id,)
        ) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await interaction.response.send_message("This giveaway is no longer active.", ephemeral=True)
            return
        
        giveaway_id, participants_json, end_time = row
        participants = json.loads(participants_json) if participants_json else []
        
        # Check if already entered
        if user_id in participants:
            await interaction.response.send_message("You've already entered this giveaway!", ephemeral=True)
            return
        
        # Check if giveaway has ended
        if datetime.now(timezone.utc) >= datetime.fromisoformat(end_time):
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return
        
        # Add user to participants
        participants.append(user_id)
        
        # Update database
        await self.bot.db.execute(
            "UPDATE cookie_giveaways SET participants = ? WHERE id = ?",
            (json.dumps(participants), giveaway_id)
        )
        await self.bot.db.commit()
        
        # Add entry to entries table
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO cookie_entries (giveaway_id, user_id) VALUES (?, ?)",
            (giveaway_id, user_id)
        )
        await self.bot.db.commit()
        
        # Update active giveaways in memory
        cog = self.bot.get_cog('CookieGiveaway')
        if cog and giveaway_id in cog.active_giveaways:
            cog.active_giveaways[giveaway_id]["participants"] = participants
        
        await interaction.response.send_message("🍪 You've entered the giveaway! Good luck!", ephemeral=True)
        
        # Update message embed with new participant count
        embed = interaction.message.embeds[0]
        embed.add_field(name="Total Entries", value=str(len(participants)), inline=True)
        await interaction.message.edit(embed=embed)

async def setup(bot):
    await bot.add_cog(CookieGiveaway(bot))
