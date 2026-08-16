import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button
from datetime import datetime, timezone
import asyncio

class VouchSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/vouch_system.db"
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()

    async def _create_tables(self):
        """Create vouch system database tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS vouches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        voucher_id INTEGER,
                        vouchee_id INTEGER,
                        rating INTEGER,
                        comment TEXT,
                        service_type TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS vouch_stats (
                        user_id INTEGER,
                        guild_id INTEGER,
                        total_vouches INTEGER DEFAULT 0,
                        average_rating REAL DEFAULT 0.0,
                        positive_vouches INTEGER DEFAULT 0,
                        negative_vouches INTEGER DEFAULT 0,
                        PRIMARY KEY (user_id, guild_id)
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS vouch_config (
                        guild_id INTEGER PRIMARY KEY,
                        channel_id INTEGER,
                        min_rating INTEGER DEFAULT 1,
                        max_rating INTEGER DEFAULT 5,
                        require_comment INTEGER DEFAULT 0
                    )
                """)
                
                await db.commit()
                
        except Exception as e:
            print(f"Error creating vouch system database: {e}")

    async def _update_vouch_stats(self, guild_id: int, vouchee_id: int):
        """Update vouch statistics for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get all vouches for the user
            cursor = await db.execute(
                "SELECT rating FROM vouches WHERE guild_id = ? AND vouchee_id = ?",
                (guild_id, vouchee_id)
            )
            rows = await cursor.fetchall()
            
            if not rows:
                return
            
            total_vouches = len(rows)
            total_rating = sum(row[0] for row in rows)
            average_rating = total_rating / total_vouches
            positive_vouches = sum(1 for row in rows if row[0] >= 4)
            negative_vouches = sum(1 for row in rows if row[0] <= 2)
            
            await db.execute("""
                INSERT OR REPLACE INTO vouch_stats (user_id, guild_id, total_vouches, average_rating, positive_vouches, negative_vouches)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (vouchee_id, guild_id, total_vouches, average_rating, positive_vouches, negative_vouches))
            await db.commit()

    @commands.group(name="vouch", invoke_without_command=True, description="⭐ Vouch system commands")
    async def vouch(self, ctx):
        """⭐ Vouch system commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @vouch.command(name="create", description="📝 Create a vouch for a user")
    @app_commands.describe(user="User to vouch for", rating="Rating (1-5)", comment="Optional comment", service="Type of service")
    async def create_vouch(self, ctx: commands.Context, user: discord.User, rating: int, comment: str = "", service: str = "General"):
        """Create a vouch for a user"""
        if user.id == ctx.author.id:
            return await ctx.send("You cannot vouch for yourself!")
        
        if rating < 1 or rating > 5:
            return await ctx.send("Rating must be between 1 and 5.")
        
        # Check config
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT require_comment FROM vouch_config WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            row = await cursor.fetchone()
            require_comment = row[0] if row else 0
            
            if require_comment and not comment:
                return await ctx.send("A comment is required for vouches in this server.")
        
        # Create vouch
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO vouches (guild_id, voucher_id, vouchee_id, rating, comment, service_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ctx.guild.id, ctx.author.id, user.id, rating, comment, service, datetime.now(timezone.utc).isoformat())
            )
            await db.commit()
        
        # Update stats
        await self._update_vouch_stats(ctx.guild.id, user.id)
        
        # Get updated stats
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT total_vouches, average_rating, positive_vouches, negative_vouches FROM vouch_stats WHERE user_id = ? AND guild_id = ?",
                (user.id, ctx.guild.id)
            )
            row = await cursor.fetchone()
        
        embed = discord.Embed(
            title="⭐ Vouch Created",
            description=f"{ctx.author.mention} vouched for {user.mention}",
            color=0x00ff00 if rating >= 4 else (0xff0000 if rating <= 2 else 0xffff00),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Rating", value=f"{'⭐' * rating} ({rating}/5)", inline=True)
        embed.add_field(name="Service", value=service, inline=True)
        if comment:
            embed.add_field(name="Comment", value=comment[:500], inline=False)
        if row:
            embed.add_field(name="New Stats", value=f"Total: {row[0]} | Avg: {row[1]:.1f}⭐", inline=False)
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Vouched by {ctx.author}")
        
        await ctx.send(embed=embed)

    @vouch.command(name="stats", description="📊 View vouch statistics")
    @app_commands.describe(user="User to check (defaults to you)")
    async def vouch_stats(self, ctx: commands.Context, user: discord.User = None):
        """View vouch statistics for a user"""
        user = user or ctx.author
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT total_vouches, average_rating, positive_vouches, negative_vouches FROM vouch_stats WHERE user_id = ? AND guild_id = ?",
                (user.id, ctx.guild.id)
            )
            row = await cursor.fetchone()
            
            if not row:
                embed = discord.Embed(
                    title="📊 No Vouches Yet",
                    description=f"{user.mention} hasn't received any vouches yet.",
                    color=0x00ff00,
                    timestamp=datetime.now(timezone.utc)
                )
                return await ctx.send(embed=embed)
            
            total_vouches, average_rating, positive_vouches, negative_vouches = row
            
            # Get recent vouches
            cursor = await db.execute(
                "SELECT rating, comment, service_type, created_at FROM vouches WHERE guild_id = ? AND vouchee_id = ? ORDER BY created_at DESC LIMIT 5",
                (ctx.guild.id, user.id)
            )
            recent_vouches = await cursor.fetchall()
        
        # Calculate reputation
        if average_rating >= 4.5:
            reputation = "⭐⭐⭐⭐⭐ Excellent"
        elif average_rating >= 4.0:
            reputation = "⭐⭐⭐⭐ Very Good"
        elif average_rating >= 3.0:
            reputation = "⭐⭐⭐ Good"
        elif average_rating >= 2.0:
            reputation = "⭐⭐ Fair"
        else:
            reputation = "⭐ Needs Improvement"
        
        embed = discord.Embed(
            title=f"📊 {user.display_name}'s Vouch Statistics",
            color=0x00ff00 if average_rating >= 4 else (0xff0000 if average_rating <= 2 else 0xffff00),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="Total Vouches", value=str(total_vouches), inline=True)
        embed.add_field(name="Average Rating", value=f"{average_rating:.1f}/5.0", inline=True)
        embed.add_field(name="Reputation", value=reputation, inline=True)
        embed.add_field(name="Positive Vouches", value=f"✅ {positive_vouches}", inline=True)
        embed.add_field(name="Negative Vouches", value=f"❌ {negative_vouches}", inline=True)
        
        # Add recent vouches
        if recent_vouches:
            recent_text = ""
            for rating, comment, service, created_at in recent_vouches:
                stars = "⭐" * rating
                recent_text += f"{stars} {service} - {created_at[:10]}\n"
                if comment:
                    recent_text += f"   *{comment[:30]}...*\n"
            
            embed.add_field(name="Recent Vouches", value=recent_text[:1024], inline=False)
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author}")
        
        await ctx.send(embed=embed)

    @vouch.command(name="leaderboard", description="🏆 View vouch leaderboard")
    async def vouch_leaderboard(self, ctx: commands.Context):
        """View vouch leaderboard"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id, total_vouches, average_rating FROM vouch_stats WHERE guild_id = ? ORDER BY total_vouches DESC, average_rating DESC LIMIT 10",
                (ctx.guild.id,)
            )
            rows = await cursor.fetchall()
        
        if not rows:
            return await ctx.send("No vouch data available yet.")
        
        embed = discord.Embed(
            title="🏆 Vouch Leaderboard",
            description="Top users by total vouches",
            color=0xffd700,
            timestamp=datetime.now(timezone.utc)
        )
        
        medals = ["🥇", "🥈", "🥉"]
        for i, (user_id, total_vouches, average_rating) in enumerate(rows):
            user = self.bot.get_user(user_id)
            user_name = user.name if user else f"Unknown ({user_id})"
            medal = medals[i] if i < 3 else f"#{i+1}"
            
            embed.add_field(
                name=f"{medal} {user_name}",
                value=f"**{total_vouches} vouches** | {average_rating:.1f}⭐ avg",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @vouch.command(name="delete", description="🗑️ Delete a vouch")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(vouch_id="Vouch ID to delete")
    async def delete_vouch(self, ctx: commands.Context, vouch_id: int):
        """Delete a vouch"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT vouchee_id FROM vouches WHERE id = ? AND guild_id = ?",
                (vouch_id, ctx.guild.id)
            )
            row = await cursor.fetchone()
            
            if not row:
                return await ctx.send("Vouch not found.")
            
            vouchee_id = row[0]
            
            await db.execute(
                "DELETE FROM vouches WHERE id = ? AND guild_id = ?",
                (vouch_id, ctx.guild.id)
            )
            await db.commit()
            
            # Update stats
            await self._update_vouch_stats(ctx.guild.id, vouchee_id)
        
        embed = discord.Embed(
            title="🗑️ Vouch Deleted",
            description=f"Vouch #{vouch_id} has been deleted.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @vouch.command(name="setchannel", description="📢 Set vouch notification channel")
    @commands.has_permissions(administrator=True)
    async def set_vouch_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the vouch notification channel"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO vouch_config (guild_id, channel_id) VALUES (?, ?)",
                (ctx.guild.id, channel.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Vouch Channel Set",
            description=f"Vouch notifications will be sent to {channel.mention}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @vouch.command(name="config", description="⚙️ Configure vouch system settings")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(min_rating="Minimum rating (1)", max_rating="Maximum rating (5)", require_comment="Require comments (true/false)")
    async def vouch_config(self, ctx: commands.Context, min_rating: int = 1, max_rating: int = 5, require_comment: bool = False):
        """Configure vouch system settings"""
        if min_rating < 1 or max_rating > 5 or min_rating > max_rating:
            return await ctx.send("Invalid rating range. Must be 1-5.")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO vouch_config (guild_id, min_rating, max_rating, require_comment) VALUES (?, ?, ?, ?)",
                (ctx.guild.id, min_rating, max_rating, 1 if require_comment else 0)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="⚙️ Vouch System Configured",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Rating Range", value=f"{min_rating}-{max_rating}", inline=True)
        embed.add_field(name="Require Comment", value="Yes" if require_comment else "No", inline=True)
        
        await ctx.send(embed=embed)

    @vouch.command(name="list", description="📋 List recent vouches")
    async def list_vouches(self, ctx: commands.Context):
        """List recent vouches"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT voucher_id, vouchee_id, rating, comment, service_type, created_at FROM vouches WHERE guild_id = ? ORDER BY created_at DESC LIMIT 10",
                (ctx.guild.id,)
            )
            rows = await cursor.fetchall()
        
        if not rows:
            return await ctx.send("No vouches found.")
        
        embed = discord.Embed(
            title="📋 Recent Vouches",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        for voucher_id, vouchee_id, rating, comment, service, created_at in rows:
            voucher = self.bot.get_user(voucher_id)
            vouchee = self.bot.get_user(vouchee_id)
            
            voucher_name = voucher.name if voucher else f"Unknown ({voucher_id})"
            vouchee_name = vouchee.name if vouchee else f"Unknown ({vouchee_id})"
            
            stars = "⭐" * rating
            embed.add_field(
                name=f"{stars} {voucher_name} → {vouchee_name}",
                value=f"**Service:** {service} | **Date:** {created_at[:10]}" + (f"\n**Comment:** {comment[:50]}..." if comment else ""),
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(VouchSystem(bot))
