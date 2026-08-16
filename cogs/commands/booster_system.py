import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from datetime import datetime, timezone, timedelta
import asyncio

class BoosterSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/booster_system.db"
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()

    async def _create_tables(self):
        """Create booster system database tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS booster_config (
                        guild_id INTEGER PRIMARY KEY,
                        booster_role_id INTEGER,
                        reward_xp INTEGER DEFAULT 1000,
                        reward_coins INTEGER DEFAULT 500,
                        notification_channel_id INTEGER,
                        auto_role BOOLEAN DEFAULT 1,
                        welcome_message TEXT
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS booster_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        user_id INTEGER,
                        boost_start TIMESTAMP,
                        boost_end TIMESTAMP,
                        months_boosted INTEGER DEFAULT 1,
                        total_boosts INTEGER DEFAULT 1
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS booster_rewards (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        reward_name TEXT,
                        reward_type TEXT,
                        reward_value INTEGER,
                        required_months INTEGER DEFAULT 1,
                        role_id INTEGER,
                        channel_id INTEGER
                    )
                """)
                
                await db.commit()
                
        except Exception as e:
            print(f"Error creating booster system database: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Handle member boost status changes"""
        if before.premium_since == after.premium_since:
            return
            
        # Member started boosting
        if after.premium_since and not before.premium_since:
            await self._handle_boost_start(after)
        # Member stopped boosting
        elif before.premium_since and not after.premium_since:
            await self._handle_boost_end(after)

    async def _handle_boost_start(self, member: discord.Member):
        """Handle when a member starts boosting"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get config
                cursor = await db.execute(
                    "SELECT booster_role_id, reward_xp, reward_coins, notification_channel_id, auto_role, welcome_message FROM booster_config WHERE guild_id = ?",
                    (member.guild.id,)
                )
                config = await cursor.fetchone()
                
                if not config:
                    return
                
                booster_role_id, reward_xp, reward_coins, notification_channel_id, auto_role, welcome_message = config
                
                # Assign booster role if enabled
                if auto_role and booster_role_id:
                    booster_role = member.guild.get_role(booster_role_id)
                    if booster_role:
                        await member.add_roles(booster_role, reason="Server booster role")
                
                # Log boost history
                await db.execute(
                    "INSERT INTO booster_history (guild_id, user_id, boost_start, boost_end, months_boosted, total_boosts) VALUES (?, ?, ?, ?, ?, ?)",
                    (member.guild.id, member.id, datetime.now(timezone.utc).isoformat(), (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(), 1, 1)
                )
                await db.commit()
                
                # Send notification
                if notification_channel_id:
                    channel = member.guild.get_channel(notification_channel_id)
                    if channel:
                        embed = discord.Embed(
                            title="🎉 New Server Booster!",
                            description=f"{member.mention} has just boosted the server!",
                            color=0xff73e6,
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.add_field(name="User", value=member.name, inline=True)
                        embed.add_field(name="Boost Duration", value="30 days", inline=True)
                        embed.add_field(name="Total Boosts", value="1", inline=True)
                        embed.set_thumbnail(url=member.display_avatar.url)
                        
                        if welcome_message:
                            embed.add_field(name="Message", value=welcome_message[:1024], inline=False)
                        
                        await channel.send(embed=embed)
                
                # Check for milestone rewards
                await self._check_milestone_rewards(member, 1)
                
        except Exception as e:
            print(f"Error handling boost start: {e}")

    async def _handle_boost_end(self, member: discord.Member):
        """Handle when a member stops boosting"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get config
                cursor = await db.execute(
                    "SELECT booster_role_id, auto_role FROM booster_config WHERE guild_id = ?",
                    (member.guild.id,)
                )
                config = await cursor.fetchone()
                
                if not config:
                    return
                
                booster_role_id, auto_role = config
                
                # Remove booster role if enabled
                if auto_role and booster_role_id:
                    booster_role = member.guild.get_role(booster_role_id)
                    if booster_role and booster_role in member.roles:
                        await member.remove_roles(booster_role, reason="Server boost ended")
                
                # Update boost history
                await db.execute(
                    "UPDATE booster_history SET boost_end = ? WHERE guild_id = ? AND user_id = ? AND boost_end IS NULL",
                    (datetime.now(timezone.utc).isoformat(), member.guild.id, member.id)
                )
                await db.commit()
                
        except Exception as e:
            print(f"Error handling boost end: {e}")

    async def _check_milestone_rewards(self, member: discord.Member, total_boosts: int):
        """Check if user qualifies for milestone rewards"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT id, reward_name, reward_type, reward_value, role_id, channel_id FROM booster_rewards WHERE guild_id = ? AND required_months <= ?",
                    (member.guild.id, total_boosts)
                )
                rewards = await cursor.fetchall()
                
                for reward_id, reward_name, reward_type, reward_value, role_id, channel_id in rewards:
                    # Check if user already received this reward
                    check_cursor = await db.execute(
                        "SELECT id FROM booster_claimed_rewards WHERE guild_id = ? AND user_id = ? AND reward_id = ?",
                        (member.guild.id, member.id, reward_id)
                    )
                    if await check_cursor.fetchone():
                        continue
                    
                    # Award reward
                    if reward_type == "role" and role_id:
                        role = member.guild.get_role(role_id)
                        if role:
                            await member.add_roles(role, reason=f"Milestone reward: {reward_name}")
                    
                    elif reward_type == "channel" and channel_id:
                        channel = member.guild.get_channel(channel_id)
                        if channel:
                            await channel.set_permissions(member, view_channel=True, send_messages=True, reason=f"Milestone reward: {reward_name}")
                    
                    # Log claimed reward
                    await db.execute(
                        "INSERT INTO booster_claimed_rewards (guild_id, user_id, reward_id, claimed_at) VALUES (?, ?, ?, ?)",
                        (member.guild.id, member.id, reward_id, datetime.now(timezone.utc).isoformat())
                    )
                    await db.commit()
                    
                    # Notify user
                    try:
                        await member.send(f"🎁 You've unlocked the **{reward_name}** reward for boosting {total_boosts} month(s)!")
                    except:
                        pass
                        
        except Exception as e:
            print(f"Error checking milestone rewards: {e}")

    @commands.group(name="booster", invoke_without_command=True, description="🚀 Server booster system commands")
    async def booster(self, ctx):
        """🚀 Server booster system commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @booster.command(name="setup", description="⚙️ Set up the booster system")
    @commands.has_permissions(administrator=True)
    async def booster_setup(self, ctx: commands.Context, booster_role: discord.Role = None, notification_channel: discord.TextChannel = None):
        """Set up the booster system"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO booster_config (guild_id, booster_role_id, notification_channel_id) VALUES (?, ?, ?)",
                (ctx.guild.id, booster_role.id if booster_role else None, notification_channel.id if notification_channel else None)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="⚙️ Booster System Configured",
            description="The server booster system has been set up!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Booster Role", value=booster_role.mention if booster_role else "None", inline=True)
        embed.add_field(name="Notification Channel", value=notification_channel.mention if notification_channel else "None", inline=True)
        
        await ctx.send(embed=embed)

    @booster.command(name="role", description="🎭 Set the booster role")
    @commands.has_permissions(administrator=True)
    async def set_booster_role(self, ctx: commands.Context, role: discord.Role):
        """Set the booster role"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE booster_config SET booster_role_id = ? WHERE guild_id = ?",
                (role.id, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Booster Role Set",
            description=f"Booster role set to {role.mention}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @booster.command(name="channel", description="📢 Set the booster notification channel")
    @commands.has_permissions(administrator=True)
    async def set_notification_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the notification channel"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE booster_config SET notification_channel_id = ? WHERE guild_id = ?",
                (channel.id, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Notification Channel Set",
            description=f"Booster notifications will be sent to {channel.mention}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @booster.command(name="message", description="💬 Set the welcome message for new boosters")
    @commands.has_permissions(administrator=True)
    async def set_welcome_message(self, ctx: commands.Context, *, message: str):
        """Set the welcome message"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE booster_config SET welcome_message = ? WHERE guild_id = ?",
                (message, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Welcome Message Set",
            description=f"Welcome message updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Message", value=message[:1024], inline=False)
        
        await ctx.send(embed=embed)

    @booster.command(name="stats", description="📊 View booster statistics")
    async def booster_stats(self, ctx: commands.Context):
        """View booster statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get current boosters
            current_boosters = len([m for m in ctx.guild.members if m.premium_since])
            
            # Get total boost history
            cursor = await db.execute(
                "SELECT COUNT(*), SUM(months_boosted) FROM booster_history WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            total_boosts, total_months = await cursor.fetchone()
            
            # Get top boosters
            cursor = await db.execute(
                "SELECT user_id, SUM(months_boosted) as total FROM booster_history WHERE guild_id = ? GROUP BY user_id ORDER BY total DESC LIMIT 5",
                (ctx.guild.id,)
            )
            top_boosters = await cursor.fetchall()
        
        embed = discord.Embed(
            title="📊 Server Booster Statistics",
            color=0xff73e6,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Current Boosters", value=str(current_boosters), inline=True)
        embed.add_field(name="Total Boosts", value=str(total_boosts or 0), inline=True)
        embed.add_field(name="Total Months", value=str(total_months or 0), inline=True)
        
        if top_boosters:
            top_text = ""
            for i, (user_id, months) in enumerate(top_boosters):
                user = self.bot.get_user(user_id)
                user_name = user.name if user else f"Unknown ({user_id})"
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
                top_text += f"{medal} **{user_name}**: {months} months\n"
            
            embed.add_field(name="Top Boosters", value=top_text, inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.send(embed=embed)

    @booster.command(name="list", description="📋 List current boosters")
    async def list_boosters(self, ctx: commands.Context):
        """List current boosters"""
        boosters = [m for m in ctx.guild.members if m.premium_since]
        
        if not boosters:
            embed = discord.Embed(
                title="📋 Current Boosters",
                description="No one is currently boosting the server.",
                color=0xff73e6,
                timestamp=datetime.now(timezone.utc)
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"📋 Current Boosters ({len(boosters)})",
            color=0xff73e6,
            timestamp=datetime.now(timezone.utc)
        )
        
        booster_text = ""
        for booster in boosters:
            boost_duration = datetime.now(timezone.utc) - booster.premium_since.replace(tzinfo=timezone.utc)
            days = boost_duration.days
            booster_text += f"• {booster.mention} - Boosting for {days} day(s)\n"
        
        embed.description = booster_text[:4096]
        embed.set_footer(text=f"Requested by {ctx.author}")
        
        await ctx.send(embed=embed)

    @booster.command(name="reward", description="🎁 Add a milestone reward")
    @commands.has_permissions(administrator=True)
    async def add_reward(self, ctx: commands.Context, name: str, reward_type: str, required_months: int, role: discord.Role = None, channel: discord.TextChannel = None):
        """Add a milestone reward"""
        if reward_type not in ["role", "channel"]:
            return await ctx.send("Reward type must be 'role' or 'channel'")
        
        if reward_type == "role" and not role:
            return await ctx.send("You must specify a role for role rewards")
        
        if reward_type == "channel" and not channel:
            return await ctx.send("You must specify a channel for channel rewards")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO booster_rewards (guild_id, reward_name, reward_type, required_months, role_id, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
                (ctx.guild.id, name, reward_type, required_months, role.id if role else None, channel.id if channel else None)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="🎁 Reward Added",
            description=f"Milestone reward '{name}' has been added!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Name", value=name, inline=True)
        embed.add_field(name="Type", value=reward_type.title(), inline=True)
        embed.add_field(name="Required Months", value=str(required_months), inline=True)
        embed.add_field(name="Reward", value=role.mention if role else channel.mention, inline=False)
        
        await ctx.send(embed=embed)

    @booster.command(name="rewards", description="🎁 List milestone rewards")
    async def list_rewards(self, ctx: commands.Context):
        """List milestone rewards"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT reward_name, reward_type, required_months, role_id, channel_id FROM booster_rewards WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                rewards = await cursor.fetchall()
        
        if not rewards:
            embed = discord.Embed(
                title="🎁 Milestone Rewards",
                description="No milestone rewards have been set up yet.",
                color=0xff73e6,
                timestamp=datetime.now(timezone.utc)
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title="🎁 Milestone Rewards",
            color=0xff73e6,
            timestamp=datetime.now(timezone.utc)
        )
        
        for name, reward_type, required_months, role_id, channel_id in rewards:
            reward_text = f"**{name}** - {required_months} month(s)\n"
            reward_text += f"Type: {reward_type.title()}\n"
            if role_id:
                role = ctx.guild.get_role(role_id)
                reward_text += f"Reward: {role.mention if role else 'Unknown role'}\n"
            if channel_id:
                channel = ctx.guild.get_channel(channel_id)
                reward_text += f"Reward: {channel.mention if channel else 'Unknown channel'}\n"
            
            embed.add_field(name=name, value=reward_text, inline=False)
        
        await ctx.send(embed=embed)

    @booster.command(name="toggle", description="🔧 Toggle auto-role assignment")
    @commands.has_permissions(administrator=True)
    async def toggle_auto_role(self, ctx: commands.Context):
        """Toggle auto-role assignment"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT auto_role FROM booster_config WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            
            current = result[0] if result else 1
            new_value = 0 if current else 1
            
            await db.execute(
                "UPDATE booster_config SET auto_role = ? WHERE guild_id = ?",
                (new_value, ctx.guild.id)
            )
            await db.commit()
        
        status = "enabled" if new_value else "disabled"
        embed = discord.Embed(
            title="🔧 Auto-Role Toggled",
            description=f"Auto-role assignment has been {status}.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @booster.command(name="myboosts", description="📊 View your boost history")
    async def my_boosts(self, ctx: commands.Context):
        """View your boost history"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT boost_start, boost_end, months_boosted, total_boosts FROM booster_history WHERE guild_id = ? AND user_id = ? ORDER BY boost_start DESC",
                (ctx.guild.id, ctx.author.id)
            )
            history = await cursor.fetchall()
        
        if not history:
            embed = discord.Embed(
                title="📊 Your Boost History",
                description="You haven't boosted this server yet.",
                color=0xff73e6,
                timestamp=datetime.now(timezone.utc)
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"📊 {ctx.author.display_name}'s Boost History",
            color=0xff73e6,
            timestamp=datetime.now(timezone.utc)
        )
        
        history_text = ""
        total_months = 0
        for boost_start, boost_end, months, total in history:
            start_date = datetime.fromisoformat(boost_start).strftime("%Y-%m-%d")
            history_text += f"• **{start_date}**: {months} month(s)\n"
            total_months += months
        
        embed.add_field(name="Total Boosts", value=str(history[0][3]), inline=True)
        embed.add_field(name="Total Months", value=str(total_months), inline=True)
        embed.add_field(name="Current Status", value="🚀 Currently Boosting" if ctx.author.premium_since else "⏰ Not Boosting", inline=True)
        
        if history_text:
            embed.add_field(name="Boost History", value=history_text[:1024], inline=False)
        
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(BoosterSystem(bot))
