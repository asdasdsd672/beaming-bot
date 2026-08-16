import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button
from datetime import datetime, timezone, timedelta
import asyncio

class LeaveSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/leave_system.db"
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()

    async def _create_tables(self):
        """Create leave system database tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS leave_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        user_id INTEGER,
                        reason TEXT,
                        status TEXT DEFAULT 'pending',
                        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        reviewed_at TIMESTAMP,
                        reviewer_id INTEGER,
                        reviewer_note TEXT
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS leave_config (
                        guild_id INTEGER PRIMARY KEY,
                        channel_id INTEGER,
                        require_reason INTEGER DEFAULT 1,
                        auto_approve_hours INTEGER DEFAULT 24
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS leave_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        user_id INTEGER,
                        reason TEXT,
                        left_at TIMESTAMP,
                        returned_at TIMESTAMP
                    )
                """)
                
                await db.commit()
                
        except Exception as e:
            print(f"Error creating leave system database: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member leave events"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Check if there's a pending leave request
                cursor = await db.execute(
                    "SELECT reason FROM leave_requests WHERE guild_id = ? AND user_id = ? AND status = 'pending'",
                    (member.guild.id, member.id)
                )
                row = await cursor.fetchone()
                
                if row:
                    reason = row[0]
                    # Update status to left
                    await db.execute(
                        "UPDATE leave_requests SET status = 'left' WHERE guild_id = ? AND user_id = ?",
                        (member.guild.id, member.id)
                    )
                    await db.commit()
                    
                    # Add to history
                    await db.execute(
                        "INSERT INTO leave_history (guild_id, user_id, reason, left_at) VALUES (?, ?, ?, ?)",
                        (member.guild.id, member.id, reason, datetime.now(timezone.utc).isoformat())
                    )
                    await db.commit()
                    
                    # Try to send to leave channel
                    cursor = await db.execute(
                        "SELECT channel_id FROM leave_config WHERE guild_id = ?",
                        (member.guild.id,)
                    )
                    config_row = await cursor.fetchone()
                    
                    if config_row:
                        channel_id = config_row[0]
                        channel = member.guild.get_channel(channel_id)
                        if channel:
                            embed = discord.Embed(
                                title="👋 Member Left",
                                description=f"{member.mention} has left the server.",
                                color=0xff0000,
                                timestamp=datetime.now(timezone.utc)
                            )
                            embed.add_field(name="Reason", value=reason if reason else "No reason provided", inline=False)
                            embed.add_field(name="Member ID", value=str(member.id), inline=True)
                            embed.add_field(name="Joined", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
                            embed.set_thumbnail(url=member.display_avatar.url)
                            
                            await channel.send(embed=embed)
                            
        except Exception as e:
            print(f"Error handling member leave: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member join events"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Check if user has leave history
                cursor = await db.execute(
                    "SELECT reason, left_at FROM leave_history WHERE guild_id = ? AND user_id = ? ORDER BY left_at DESC LIMIT 1",
                    (member.guild.id, member.id)
                )
                row = await cursor.fetchone()
                
                if row:
                    reason, left_at = row
                    # Update return time
                    await db.execute(
                        "UPDATE leave_history SET returned_at = ? WHERE guild_id = ? AND user_id = ? AND left_at = ?",
                        (datetime.now(timezone.utc).isoformat(), member.guild.id, member.id, left_at)
                    )
                    await db.commit()
                    
                    # Try to send to leave channel
                    cursor = await db.execute(
                        "SELECT channel_id FROM leave_config WHERE guild_id = ?",
                        (member.guild.id,)
                    )
                    config_row = await cursor.fetchone()
                    
                    if config_row:
                        channel_id = config_row[0]
                        channel = member.guild.get_channel(channel_id)
                        if channel:
                            embed = discord.Embed(
                                title="🎉 Member Returned",
                                description=f"{member.mention} has returned to the server!",
                                color=0x00ff00,
                                timestamp=datetime.now(timezone.utc)
                            )
                            embed.add_field(name="Previous Leave Reason", value=reason if reason else "No reason", inline=False)
                            embed.add_field(name="Time Away", value=self._calculate_time_away(left_at), inline=True)
                            embed.set_thumbnail(url=member.display_avatar.url)
                            
                            await channel.send(embed=embed)
                            
        except Exception as e:
            print(f"Error handling member join: {e}")

    def _calculate_time_away(self, left_at: str) -> str:
        """Calculate how long a member was away"""
        try:
            left_time = datetime.fromisoformat(left_at)
            time_away = datetime.now(timezone.utc) - left_time
            
            days = time_away.days
            hours = time_away.seconds // 3600
            
            if days > 0:
                return f"{days} day(s)"
            elif hours > 0:
                return f"{hours} hour(s)"
            else:
                return "Less than an hour"
        except:
            return "Unknown"

    @commands.group(name="leave", invoke_without_command=True, description="👋 Leave system commands")
    async def leave(self, ctx):
        """👋 Leave system commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @leave.command(name="request", description="📝 Submit a leave request")
    async def leave_request(self, ctx: commands.Context):
        """Submit a leave request"""
        # Check if leave system is configured
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT require_reason FROM leave_config WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            row = await cursor.fetchone()
            
            require_reason = row[0] if row else 1
            
        if require_reason:
            # Show modal for reason
            modal = LeaveReasonModal()
            await ctx.interaction.response.send_modal(modal) if hasattr(ctx, 'interaction') else await ctx.send("Please use the slash command: /leave request")
        else:
            # Simple leave request
            await self._process_leave_request(ctx, "No reason provided")

    async def _process_leave_request(self, ctx, reason: str):
        """Process the leave request"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check for existing pending request
            cursor = await db.execute(
                "SELECT id FROM leave_requests WHERE guild_id = ? AND user_id = ? AND status = 'pending'",
                (ctx.guild.id, ctx.author.id)
            )
            existing = await cursor.fetchone()
            
            if existing:
                embed = discord.Embed(
                    title="⚠️ Pending Request Exists",
                    description="You already have a pending leave request.",
                    color=0xff0000,
                    timestamp=datetime.now(timezone.utc)
                )
                return await ctx.send(embed=embed)
            
            # Create new leave request
            await db.execute(
                "INSERT INTO leave_requests (guild_id, user_id, reason, submitted_at) VALUES (?, ?, ?, ?)",
                (ctx.guild.id, ctx.author.id, reason, datetime.now(timezone.utc).isoformat())
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Leave Request Submitted",
            description=f"Your leave request has been submitted.\n**Reason:** {reason}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Status", value="Pending Review", inline=True)
        embed.set_footer(text="Staff will review your request shortly")
        
        await ctx.send(embed=embed)

    @leave.command(name="setchannel", description="📢 Set the leave notification channel")
    @commands.has_permissions(administrator=True)
    async def set_leave_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the leave notification channel"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO leave_config (guild_id, channel_id) VALUES (?, ?)",
                (ctx.guild.id, channel.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Leave Channel Set",
            description=f"Leave notifications will be sent to {channel.mention}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @leave.command(name="review", description="👀 Review pending leave requests")
    @commands.has_permissions(administrator=True)
    async def review_leaves(self, ctx: commands.Context):
        """Review pending leave requests"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, user_id, reason, submitted_at FROM leave_requests WHERE guild_id = ? AND status = 'pending' ORDER BY submitted_at DESC",
                (ctx.guild.id,)
            )
            rows = await cursor.fetchall()
        
        if not rows:
            embed = discord.Embed(
                title="📋 No Pending Leave Requests",
                description="There are no pending leave requests to review.",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title="📋 Pending Leave Requests",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        for leave_id, user_id, reason, submitted_at in rows:
            user = self.bot.get_user(user_id)
            user_name = user.name if user else f"Unknown ({user_id})"
            
            embed.add_field(
                name=f"Request #{leave_id}",
                value=f"**User:** {user_name}\n**Reason:** {reason[:50]}...\n**Submitted:** {submitted_at[:10]}",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @leave.command(name="approve", description="✅ Approve a leave request")
    @commands.has_permissions(administrator=True)
    async def approve_leave(self, ctx: commands.Context, leave_id: int):
        """Approve a leave request"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id, reason FROM leave_requests WHERE id = ? AND guild_id = ? AND status = 'pending'",
                (leave_id, ctx.guild.id)
            )
            row = await cursor.fetchone()
            
            if not row:
                return await ctx.send("Leave request not found or already processed.")
            
            user_id, reason = row
            
            await db.execute(
                "UPDATE leave_requests SET status = 'approved', reviewed_at = ?, reviewer_id = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), ctx.author.id, leave_id)
            )
            await db.commit()
        
        user = self.bot.get_user(user_id)
        
        embed = discord.Embed(
            title="✅ Leave Request Approved",
            description=f"Leave request #{leave_id} has been approved.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="User", value=user.name if user else f"Unknown ({user_id})", inline=True)
        embed.add_field(name="Reason", value=reason[:100], inline=False)
        
        await ctx.send(embed=embed)

    @leave.command(name="deny", description="❌ Deny a leave request")
    @commands.has_permissions(administrator=True)
    async def deny_leave(self, ctx: commands.Context, leave_id: int):
        """Deny a leave request"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id, reason FROM leave_requests WHERE id = ? AND guild_id = ? AND status = 'pending'",
                (leave_id, ctx.guild.id)
            )
            row = await cursor.fetchone()
            
            if not row:
                return await ctx.send("Leave request not found or already processed.")
            
            user_id, reason = row
            
            await db.execute(
                "UPDATE leave_requests SET status = 'denied', reviewed_at = ?, reviewer_id = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), ctx.author.id, leave_id)
            )
            await db.commit()
        
        user = self.bot.get_user(user_id)
        
        embed = discord.Embed(
            title="❌ Leave Request Denied",
            description=f"Leave request #{leave_id} has been denied.",
            color=0xff0000,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="User", value=user.name if user else f"Unknown ({user_id})", inline=True)
        
        await ctx.send(embed=embed)

    @leave.command(name="history", description="📜 View leave history")
    async def leave_history(self, ctx: commands.Context):
        """View leave history"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT reason, left_at, returned_at FROM leave_history WHERE guild_id = ? ORDER BY left_at DESC LIMIT 10",
                (ctx.guild.id,)
            )
            rows = await cursor.fetchall()
        
        if not rows:
            return await ctx.send("No leave history found.")
        
        embed = discord.Embed(
            title="📜 Leave History",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        for reason, left_at, returned_at in rows:
            return_status = "Returned" if returned_at else "Still away"
            embed.add_field(
                name=f"Left: {left_at[:10]}",
                value=f"**Reason:** {reason[:50]}...\n**Status:** {return_status}",
                inline=False
            )
        
        await ctx.send(embed=embed)

class LeaveReasonModal(Modal, title="📝 Leave Reason"):
    reason = TextInput(
        label="Reason for leaving",
        placeholder="Please let us know why you're leaving...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog('LeaveSystem')
        if cog:
            await cog._process_leave_request(interaction, self.reason.value)
            await interaction.response.send_message("Leave request submitted!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(LeaveSystem(bot))
