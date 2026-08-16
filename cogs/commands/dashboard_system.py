import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from datetime import datetime, timezone, timedelta
import asyncio
import json
import secrets
import base64

class DashboardSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/dashboard_system.db"
        self.auth_tokens = {}
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()

    async def _create_tables(self):
        """Create dashboard system database tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        discriminator TEXT,
                        avatar_url TEXT,
                        bio TEXT,
                        banner_url TEXT,
                        custom_badges TEXT,
                        xp INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 1,
                        coins INTEGER DEFAULT 0,
                        theme_color TEXT DEFAULT '#00ff00',
                        profile_style TEXT DEFAULT 'default',
                        social_links TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_stats (
                        user_id INTEGER PRIMARY KEY,
                        messages_sent INTEGER DEFAULT 0,
                        voice_minutes INTEGER DEFAULT 0,
                        commands_used INTEGER DEFAULT 0,
                        tickets_created INTEGER DEFAULT 0,
                        applications_submitted INTEGER DEFAULT 0,
                        suggestions_made INTEGER DEFAULT 0,
                        polls_created INTEGER DEFAULT 0,
                        reactions_given INTEGER DEFAULT 0,
                        boosts_given INTEGER DEFAULT 0,
                        reputation INTEGER DEFAULT 0,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS auth_tokens (
                        token TEXT PRIMARY KEY,
                        user_id INTEGER,
                        guild_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        is_valid BOOLEAN DEFAULT 1
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS server_stats (
                        guild_id INTEGER PRIMARY KEY,
                        total_members INTEGER DEFAULT 0,
                        active_members INTEGER DEFAULT 0,
                        total_messages INTEGER DEFAULT 0,
                        total_commands INTEGER DEFAULT 0,
                        total_tickets INTEGER DEFAULT 0,
                        total_boosts INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_achievements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        achievement_name TEXT,
                        achievement_description TEXT,
                        achievement_icon TEXT,
                        unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS profile_cards (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        card_url TEXT,
                        card_style TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS social_connections (
                        user_id INTEGER PRIMARY KEY,
                        youtube_url TEXT,
                        twitter_url TEXT,
                        instagram_url TEXT,
                        github_url TEXT,
                        website_url TEXT,
                        discord_url TEXT,
                        twitch_url TEXT
                    )
                """)
                
                await db.commit()
                
        except Exception as e:
            print(f"Error creating dashboard system database: {e}")

    @commands.group(name="profile", invoke_without_command=True, description="👤 User profile commands")
    async def profile(self, ctx):
        """👤 User profile commands"""
        if ctx.invoked_subcommand is None:
            await self.show_profile(ctx, ctx.author)

    @profile.command(name="show", description="👤 Show your profile")
    async def show_profile(self, ctx: commands.Context, user: discord.Member = None):
        """Show user profile"""
        target = user or ctx.author
        
        # Get or create profile
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM user_profiles WHERE user_id = ?",
                (target.id,)
            )
            profile = await cursor.fetchone()
            
            if not profile:
                # Create profile
                await db.execute(
                    "INSERT INTO user_profiles (user_id, username, discriminator, avatar_url) VALUES (?, ?, ?, ?)",
                    (target.id, target.name, target.discriminator, str(target.display_avatar.url))
                )
                await db.commit()
                
                cursor = await db.execute(
                    "SELECT * FROM user_profiles WHERE user_id = ?",
                    (target.id,)
                )
                profile = await cursor.fetchone()
            
            # Get stats
            cursor = await db.execute(
                "SELECT * FROM user_stats WHERE user_id = ?",
                (target.id,)
            )
            stats = await cursor.fetchone() or (target.id, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, datetime.now(timezone.utc).isoformat())
            
            # Get achievements
            cursor = await db.execute(
                "SELECT achievement_name, achievement_description, achievement_icon, unlocked_at FROM user_achievements WHERE user_id = ? ORDER BY unlocked_at DESC LIMIT 5",
                (target.id,)
            )
            achievements = await cursor.fetchall()
            
            # Get social connections
            cursor = await db.execute(
                "SELECT * FROM social_connections WHERE user_id = ?",
                (target.id,)
            )
            social = await cursor.fetchone()
        
        # Parse theme color
        theme_color = profile[10] if len(profile) > 10 else '#00ff00'
        try:
            color = int(theme_color.replace('#', ''), 16)
        except:
            color = 0x00ff00
        
        # Create profile embed with beamse.pro style
        embed = discord.Embed(
            title=f"👤 {target.display_name}",
            description=profile[4] or "No bio set yet. Use `>profile bio` to set one!",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Add banner if available
        if profile[5]:
            embed.set_image(url=profile[5])
        
        embed.set_thumbnail(url=target.display_avatar.url)
        
        # Main stats
        embed.add_field(name="📊 Level", value=f"**{profile[7]}**", inline=True)
        embed.add_field(name="⭐ XP", value=f"**{profile[6]}**", inline=True)
        embed.add_field(name="💰 Coins", value=f"**{profile[8]}**", inline=True)
        
        # Activity stats
        embed.add_field(name="💬 Messages", value=str(stats[1]), inline=True)
        embed.add_field(name="🎤 Voice", value=f"{stats[2]}m", inline=True)
        embed.add_field(name="⚡ Commands", value=str(stats[3]), inline=True)
        
        # Additional stats
        embed.add_field(name="🎫 Tickets", value=str(stats[4]), inline=True)
        embed.add_field(name="📋 Applications", value=str(stats[5]), inline=True)
        embed.add_field(name="💡 Suggestions", value=str(stats[6]), inline=True)
        
        # Reputation
        if len(stats) > 10:
            embed.add_field(name="⭐ Reputation", value=str(stats[10]), inline=True)
        
        # Social connections
        if social:
            social_links = []
            social_fields = {
                'youtube_url': ('📺 YouTube', 1),
                'twitter_url': ('🐦 Twitter', 2),
                'instagram_url': ('📷 Instagram', 3),
                'github_url': ('💻 GitHub', 4),
                'website_url': ('🌐 Website', 5),
                'discord_url': ('💬 Discord', 6),
                'twitch_url': ('📺 Twitch', 7)
            }
            
            for field, (emoji, index) in social_fields.items():
                if social[index]:
                    social_links.append(f"{emoji} [Link]({social[index]})")
            
            if social_links:
                embed.add_field(name="🔗 Social Links", value=" | ".join(social_links), inline=False)
        
        # Achievements
        if achievements:
            achievement_text = ""
            for name, description, icon, unlocked_at in achievements:
                achievement_text += f"{icon or '🏆'} **{name}**: {description}\n"
            embed.add_field(name="🏆 Recent Achievements", value=achievement_text[:1024], inline=False)
        
        # Custom badges
        if profile[6]:
            badges = json.loads(profile[6]) if profile[6] else []
            if badges:
                badge_text = " ".join(badges)
                embed.add_field(name="🎖️ Badges", value=badge_text, inline=False)
        
        # Profile style info
        if len(profile) > 11:
            embed.add_field(name="🎨 Style", value=profile[11].title(), inline=True)
        
        embed.set_footer(text=f"Profile created: {profile[12][:10]} • ID: {target.id}")
        
        await ctx.send(embed=embed)

    @profile.command(name="theme", description="🎨 Set your profile theme color")
    async def set_theme(self, ctx: commands.Context, color: str):
        """Set your profile theme color (hex code)"""
        if not color.startswith('#') or len(color) != 7:
            return await ctx.send("Please provide a valid hex color code (e.g., #00ff00)")
        
        try:
            int(color.replace('#', ''), 16)
        except:
            return await ctx.send("Invalid hex color code.")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_profiles SET theme_color = ?, last_updated = ? WHERE user_id = ?",
                (color, datetime.now(timezone.utc).isoformat(), ctx.author.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Theme Color Updated",
            description="Your profile theme color has been updated!",
            color=int(color.replace('#', ''), 16),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="New Color", value=color, inline=True)
        
        await ctx.send(embed=embed)

    @profile.command(name="style", description="🎨 Set your profile style")
    async def set_style(self, ctx: commands.Context, style: str):
        """Set your profile style"""
        valid_styles = ['default', 'modern', 'minimal', 'gradient', 'dark']
        if style.lower() not in valid_styles:
            return await ctx.send(f"Invalid style. Available styles: {', '.join(valid_styles)}")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_profiles SET profile_style = ?, last_updated = ? WHERE user_id = ?",
                (style.lower(), datetime.now(timezone.utc).isoformat(), ctx.author.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Profile Style Updated",
            description="Your profile style has been updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="New Style", value=style.title(), inline=True)
        
        await ctx.send(embed=embed)

    @profile.command(name="social", description="🔗 Set your social media links")
    async def set_social(self, ctx: commands.Context, platform: str, url: str):
        """Set your social media link"""
        valid_platforms = ['youtube', 'twitter', 'instagram', 'github', 'website', 'discord', 'twitch']
        if platform.lower() not in valid_platforms:
            return await ctx.send(f"Invalid platform. Available: {', '.join(valid_platforms)}")
        
        platform_map = {
            'youtube': 'youtube_url',
            'twitter': 'twitter_url', 
            'instagram': 'instagram_url',
            'github': 'github_url',
            'website': 'website_url',
            'discord': 'discord_url',
            'twitch': 'twitch_url'
        }
        
        field = platform_map[platform.lower()]
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"INSERT OR REPLACE INTO social_connections (user_id, {field}) VALUES (?, ?)",
                (ctx.author.id, url)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Social Link Updated",
            description=f"Your {platform.title()} link has been updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Platform", value=platform.title(), inline=True)
        embed.add_field(name="URL", value=url[:100], inline=True)
        
        await ctx.send(embed=embed)

    @profile.command(name="card", description="🎴 Generate your profile card")
    async def generate_card(self, ctx: commands.Context):
        """Generate a profile card image"""
        # Get profile data
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM user_profiles WHERE user_id = ?",
                (ctx.author.id,)
            )
            profile = await cursor.fetchone()
        
        if not profile:
            return await ctx.send("You don't have a profile yet. Use `>profile show` to create one.")
        
        # Create a text-based card representation
        embed = discord.Embed(
            title=f"🎴 {ctx.author.display_name}'s Profile Card",
            description="Profile Card Generated",
            color=int(profile[10].replace('#', ''), 16) if len(profile) > 10 else 0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="📊 Level", value=str(profile[7]), inline=True)
        embed.add_field(name="⭐ XP", value=str(profile[6]), inline=True)
        embed.add_field(name="💰 Coins", value=str(profile[8]), inline=True)
        
        embed.add_field(name="📝 Bio", value=profile[4][:100] if profile[4] else "No bio", inline=False)
        
        if profile[5]:
            embed.set_image(url=profile[5])
        
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        # Save card to database
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO profile_cards (user_id, card_url, card_style) VALUES (?, ?, ?)",
                (ctx.author.id, f"card_{ctx.author.id}.png", profile[11] if len(profile) > 11 else 'default')
            )
            await db.commit()
        
        await ctx.send(embed=embed)

    @profile.command(name="reputation", description="⭐ Give reputation to a user")
    async def give_reputation(self, ctx: commands.Context, user: discord.Member):
        """Give reputation to a user"""
        if user == ctx.author:
            return await ctx.send("You cannot give reputation to yourself.")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)",
                (user.id,)
            )
            await db.execute(
                "UPDATE user_stats SET reputation = reputation + 1 WHERE user_id = ?",
                (user.id,)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="⭐ Reputation Given",
            description=f"{ctx.author.mention} gave reputation to {user.mention}!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        await ctx.send(embed=embed)

    @profile.command(name="bio", description="📝 Set your profile bio")
    async def set_bio(self, ctx: commands.Context, *, bio: str):
        """Set your profile bio"""
        if len(bio) > 500:
            return await ctx.send("Bio must be less than 500 characters.")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_profiles SET bio = ?, last_updated = ? WHERE user_id = ?",
                (bio, datetime.now(timezone.utc).isoformat(), ctx.author.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Bio Updated",
            description="Your profile bio has been updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="New Bio", value=bio[:1024], inline=False)
        
        await ctx.send(embed=embed)

    @profile.command(name="badges", description="🎖️ Set your custom badges")
    async def set_badges(self, ctx: commands.Context, *, badges: str):
        """Set your custom badges (emoji separated by spaces)"""
        badge_list = badges.split()
        if len(badge_list) > 10:
            return await ctx.send("You can only have up to 10 badges.")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_profiles SET custom_badges = ?, last_updated = ? WHERE user_id = ?",
                (json.dumps(badge_list), datetime.now(timezone.utc).isoformat(), ctx.author.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Badges Updated",
            description="Your profile badges have been updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Badges", value=" ".join(badge_list), inline=False)
        
        await ctx.send(embed=embed)

    @profile.command(name="banner", description="🖼️ Set your profile banner")
    async def set_banner(self, ctx: commands.Context, url: str):
        """Set your profile banner"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_profiles SET banner_url = ?, last_updated = ? WHERE user_id = ?",
                (url, datetime.now(timezone.utc).isoformat(), ctx.author.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Banner Updated",
            description="Your profile banner has been updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_image(url=url)
        
        await ctx.send(embed=embed)

    @profile.command(name="rank", description="📊 View your rank")
    async def view_rank(self, ctx: commands.Context):
        """View your rank on each server"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id, xp FROM user_profiles ORDER BY xp DESC"
            )
            all_users = await cursor.fetchall()
            
            user_rank = None
            for i, (user_id, xp) in enumerate(all_users):
                if user_id == ctx.author.id:
                    user_rank = i + 1
                    break
        
        if user_rank:
            embed = discord.Embed(
                title="📊 Your Global Rank",
                description=f"You are ranked **#{user_rank}** out of **{len(all_users)}** users!",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Show top 10
            top_users = all_users[:10]
            top_text = ""
            for i, (user_id, xp) in enumerate(top_users):
                user = self.bot.get_user(user_id)
                user_name = user.name if user else f"Unknown ({user_id})"
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
                top_text += f"{medal} **{user_name}**: {xp} XP\n"
            
            embed.add_field(name="🏆 Top 10", value=top_text, inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("You don't have a profile yet. Use `>profile show` to create one.")

    @commands.group(name="dashboard", invoke_without_command=True, description="📊 Dashboard commands")
    async def dashboard(self, ctx):
        """📊 Dashboard commands"""
        if ctx.invoked_subcommand is None:
            await self.show_dashboard(ctx)

    @dashboard.command(name="show", description="📊 Show server dashboard")
    async def show_dashboard(self, ctx: commands.Context):
        """Show server dashboard"""
        # Get or create server stats
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM server_stats WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            stats = await cursor.fetchone()
            
            if not stats:
                # Create stats
                await db.execute(
                    "INSERT INTO server_stats (guild_id, total_members, active_members) VALUES (?, ?, ?)",
                    (ctx.guild.id, len(ctx.guild.members), len([m for m in ctx.guild.members if m.status != discord.Status.offline]))
                )
                await db.commit()
                
                cursor = await db.execute(
                    "SELECT * FROM server_stats WHERE guild_id = ?",
                    (ctx.guild.id,)
                )
                stats = await cursor.fetchone()
            
            # Get top users
            cursor = await db.execute(
                "SELECT user_id, xp, level FROM user_profiles ORDER BY xp DESC LIMIT 5"
            )
            top_users = await cursor.fetchall()
        
        # Create dashboard embed
        embed = discord.Embed(
            title=f"📊 {ctx.guild.name} Dashboard",
            description="Server statistics and overview",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        # Server stats
        embed.add_field(name="👥 Total Members", value=str(len(ctx.guild.members)), inline=True)
        embed.add_field(name="🟢 Active Members", value=str(len([m for m in ctx.guild.members if m.status != discord.Status.offline])), inline=True)
        embed.add_field(name="💬 Total Messages", value=str(stats[3] or 0), inline=True)
        
        embed.add_field(name="⚡ Total Commands", value=str(stats[4] or 0), inline=True)
        embed.add_field(name="🎫 Total Tickets", value=str(stats[5] or 0), inline=True)
        embed.add_field(name="🚀 Total Boosts", value=str(stats[6] or 0), inline=True)
        
        # Top users
        if top_users:
            top_text = ""
            for i, (user_id, xp, level) in enumerate(top_users):
                user = self.bot.get_user(user_id)
                user_name = user.name if user else f"Unknown ({user_id})"
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
                top_text += f"{medal} **{user_name}**: Level {level} ({xp} XP)\n"
            
            embed.add_field(name="🏆 Top Users", value=top_text, inline=False)
        
        embed.set_footer(text=f"Last updated: {stats[7][:19] if stats else 'Never'}")
        
        await ctx.send(embed=embed)

    @commands.command(name="auth", description="🔐 Generate authentication token for external dashboard")
    async def generate_auth_token(self, ctx: commands.Context):
        """Generate authentication token for external dashboard"""
        # Generate secure token
        token = secrets.token_urlsafe(32)
        
        # Store token
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO auth_tokens (token, user_id, guild_id, expires_at) VALUES (?, ?, ?, ?)",
                (token, ctx.author.id, ctx.guild.id, (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat())
            )
            await db.commit()
        
        embed = discord.Embed(
            title="🔐 Authentication Token Generated",
            description="Use this token to authenticate with the external dashboard.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Token", value=f"`{token}`", inline=False)
        embed.add_field(name="Expires", value="24 hours", inline=True)
        embed.add_field(name="⚠️ Warning", value="Keep this token secret! Anyone with this token can access your account.", inline=False)
        
        await ctx.author.send(embed=embed)
        await ctx.send("Authentication token sent to your DMs!")

    @commands.command(name="leaderboard", description="🏆 View the leaderboard")
    async def leaderboard(self, ctx: commands.Context, category: str = "xp"):
        """View the leaderboard"""
        category = category.lower()
        
        if category == "xp":
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT user_id, xp, level FROM user_profiles ORDER BY xp DESC LIMIT 10"
                )
                users = await cursor.fetchall()
            
            title = "🏆 XP Leaderboard"
            field_name = "Level"
            value_field = "XP"
        elif category == "messages":
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT user_id, messages_sent FROM user_stats ORDER BY messages_sent DESC LIMIT 10"
                )
                users = await cursor.fetchall()
            
            title = "💬 Messages Leaderboard"
            field_name = "Messages"
            value_field = "Count"
        elif category == "voice":
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT user_id, voice_minutes FROM user_stats ORDER BY voice_minutes DESC LIMIT 10"
                )
                users = await cursor.fetchall()
            
            title = "🎤 Voice Leaderboard"
            field_name = "Minutes"
            value_field = "Time"
        else:
            return await ctx.send("Invalid category. Use: xp, messages, or voice")
        
        embed = discord.Embed(
            title=title,
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        leaderboard_text = ""
        for i, (user_id, value1, value2) in enumerate(users):
            user = self.bot.get_user(user_id)
            user_name = user.name if user else f"Unknown ({user_id})"
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
            
            if category == "xp":
                leaderboard_text += f"{medal} **{user_name}**: Level {value2} ({value1} XP)\n"
            else:
                leaderboard_text += f"{medal} **{user_name}**: {value1} {value_field}\n"
        
        embed.description = leaderboard_text
        embed.set_footer(text=f"Requested by {ctx.author}")
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Track user statistics"""
        if message.author.bot:
            return
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Update profile
                await db.execute(
                    "INSERT OR IGNORE INTO user_profiles (user_id, username, discriminator, avatar_url) VALUES (?, ?, ?, ?)",
                    (message.author.id, message.author.name, message.author.discriminator, str(message.author.display_avatar.url))
                )
                
                # Update stats
                await db.execute(
                    "INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)",
                    (message.author.id,)
                )
                await db.execute(
                    "UPDATE user_stats SET messages_sent = messages_sent + 1, last_activity = ? WHERE user_id = ?",
                    (datetime.now(timezone.utc).isoformat(), message.author.id)
                )
                
                # Add XP
                await db.execute(
                    "UPDATE user_profiles SET xp = xp + 1 WHERE user_id = ?",
                    (message.author.id,)
                )
                
                # Level up check
                cursor = await db.execute("SELECT xp, level FROM user_profiles WHERE user_id = ?", (message.author.id,))
                xp, level = await cursor.fetchone()
                
                new_level = int((xp / 100) ** 0.5) + 1
                if new_level > level:
                    await db.execute(
                        "UPDATE user_profiles SET level = ? WHERE user_id = ?",
                        (new_level, message.author.id)
                    )
                    
                    # Send level up message
                    try:
                        await message.channel.send(f"🎉 {message.author.mention} leveled up to **Level {new_level}**!")
                    except:
                        pass
                
                # Update server stats
                await db.execute(
                    "INSERT OR IGNORE INTO server_stats (guild_id) VALUES (?)",
                    (message.guild.id,)
                )
                await db.execute(
                    "UPDATE server_stats SET total_messages = total_messages + 1, last_updated = ? WHERE guild_id = ?",
                    (datetime.now(timezone.utc).isoformat(), message.guild.id)
                )
                
                await db.commit()
                
        except Exception as e:
            print(f"Error tracking message stats: {e}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        """Track command usage"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)",
                    (ctx.author.id,)
                )
                await db.execute(
                    "UPDATE user_stats SET commands_used = commands_used + 1, last_activity = ? WHERE user_id = ?",
                    (datetime.now(timezone.utc).isoformat(), ctx.author.id)
                )
                
                # Update server stats
                await db.execute(
                    "INSERT OR IGNORE INTO server_stats (guild_id) VALUES (?)",
                    (ctx.guild.id,)
                )
                await db.execute(
                    "UPDATE server_stats SET total_commands = total_commands + 1, last_updated = ? WHERE guild_id = ?",
                    (datetime.now(timezone.utc).isoformat(), ctx.guild.id)
                )
                
                await db.commit()
                
        except Exception as e:
            print(f"Error tracking command stats: {e}")

async def setup(bot):
    await bot.add_cog(DashboardSystem(bot))
