import discord
from discord.ext import commands, tasks
import random
from datetime import datetime
import asyncio
from utils.config_loader import load_current_language, config

class DynamicStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.status_index = 0
        self.status_types = [
            discord.ActivityType.playing,
            discord.ActivityType.watching,
            discord.ActivityType.listening,
            discord.ActivityType.competing
        ]
        self.custom_presences = []
        self.presence_change_delay = config.get('PRESENCES_CHANGE_DELAY', 8)
        self.server_name = config.get('SERVER_NAME', 'BeZmerz')
        self.invite_link = config.get('Discord', 'https://discord.gg/hQfSRGsQa7')
        
        # Enhanced status messages
        self.status_messages = [
            "🎮 {server_name} Server",
            "🤖 AI-powered Discord bot",
            "✨ {invite_link}",
            "🛡️ Advanced moderation",
            "🎵 Music & entertainment",
            "💬 Smart AI conversations",
            "📊 {guild_count} servers",
            "👥 {user_count} users",
            "⚡ 24/7 uptime",
            "🔧 Server management",
            "🎯 Leveling & rewards",
            "🎨 Custom commands"
        ]
        
        if not config.get('DISABLE_PRESENCE', False):
            self.status_rotation.start()

    def cog_unload(self):
        self.status_rotation.cancel()

    @tasks.loop(seconds=8)
    async def status_rotation(self):
        """Rotate through different bot statuses"""
        try:
            # Get current stats
            guild_count = len(self.bot.guilds)
            user_count = sum(guild.member_count for guild in self.bot.guilds if guild.member_count)
            
            # Format status message
            status_template = random.choice(self.status_messages)
            status_message = status_template.format(
                server_name=self.server_name,
                invite_link=self.invite_link,
                guild_count=guild_count,
                user_count=user_count
            )
            
            # Random activity type
            activity_type = random.choice(self.status_types)
            
            # Set the status
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=activity_type,
                    name=status_message
                ),
                status=discord.Status.online
            )
            
        except Exception as e:
            print(f"Error rotating status: {e}")

    @status_rotation.before_loop
    async def before_status_rotation(self):
        """Wait for bot to be ready before starting status rotation"""
        await self.bot.wait_until_ready()

    @commands.group(name="botstatus", invoke_without_command=True, description="🎮 Manage bot status")
    @commands.has_permissions(administrator=True)
    async def botstatus(self, ctx):
        """🎮 Bot status management commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @botstatus.command(name="set", description="⚙️ Set custom bot status")
    @commands.has_permissions(administrator=True)
    async def set_status(self, ctx, *, status: str):
        """Set a custom bot status"""
        try:
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.playing,
                    name=status
                ),
                status=discord.Status.online
            )
            
            embed = discord.Embed(
                title="✅ Status Updated",
                description=f"Bot status set to: **{status}**",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error setting status: {e}")

    @botstatus.command(name="reset", description="🔄 Reset to automatic status rotation")
    @commands.has_permissions(administrator=True)
    async def reset_status(self, ctx):
        """Reset to automatic status rotation"""
        if not self.status_rotation.is_running():
            self.status_rotation.start()
        
        embed = discord.Embed(
            title="🔄 Status Rotation Reset",
            description="Automatic status rotation has been re-enabled.",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        await ctx.send(embed=embed)

    @botstatus.command(name="stop", description="⏸️ Stop automatic status rotation")
    @commands.has_permissions(administrator=True)
    async def stop_status(self, ctx):
        """Stop automatic status rotation"""
        if self.status_rotation.is_running():
            self.status_rotation.stop()
        
        embed = discord.Embed(
            title="⏸️ Status Rotation Stopped",
            description="Automatic status rotation has been paused. Use `/botstatus reset` to resume.",
            color=0xff0000,
            timestamp=datetime.now()
        )
        await ctx.send(embed=embed)

    @botstatus.command(name="add", description="➕ Add a custom status to rotation")
    @commands.has_permissions(administrator=True)
    async def add_status(self, ctx, *, status: str):
        """Add a custom status to the rotation"""
        if status not in self.status_messages:
            self.status_messages.append(status)
            
            embed = discord.Embed(
                title="➕ Status Added",
                description=f"Added to rotation: **{status}**",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("This status is already in the rotation.")

    @botstatus.command(name="remove", description="➖ Remove a status from rotation")
    @commands.has_permissions(administrator=True)
    async def remove_status(self, ctx, status_id: int):
        """Remove a status from rotation by index"""
        if 0 <= status_id < len(self.status_messages):
            removed = self.status_messages.pop(status_id)
            
            embed = discord.Embed(
                title="➖ Status Removed",
                description=f"Removed from rotation: **{removed}**",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Invalid status ID. Current range: 0-{len(self.status_messages)-1}")

    @botstatus.command(name="list", description="📋 List all status messages")
    @commands.has_permissions(administrator=True)
    async def list_statuses(self, ctx):
        """List all status messages in rotation"""
        embed = discord.Embed(
            title="📋 Status Rotation List",
            description=f"Current rotation delay: {self.presence_change_delay} seconds",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        for i, status in enumerate(self.status_messages):
            embed.add_field(
                name=f"#{i}",
                value=status,
                inline=False
            )
        
        await ctx.send(embed=embed)

    @botstatus.command(name="stats", description="📊 Show bot statistics")
    async def show_stats(self, ctx):
        """Show comprehensive bot statistics"""
        guild_count = len(self.bot.guilds)
        user_count = sum(guild.member_count for guild in self.bot.guilds if guild.member_count)
        channel_count = sum(len(guild.channels) for guild in self.bot.guilds)
        role_count = sum(len(guild.roles) for guild in self.bot.guilds)
        
        # Calculate uptime
        uptime = datetime.now() - self.bot.start_time if hasattr(self.bot, 'start_time') else "Unknown"
        
        embed = discord.Embed(
            title=f"📊 {self.server_name} Bot Statistics",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="🌐 Servers", value=f"{guild_count:,}", inline=True)
        embed.add_field(name="👥 Total Users", value=f"{user_count:,}", inline=True)
        embed.add_field(name="💬 Channels", value=f"{channel_count:,}", inline=True)
        embed.add_field(name="🎭 Roles", value=f"{role_count:,}", inline=True)
        embed.add_field(name="⏱️ Uptime", value=str(uptime).split('.')[0] if isinstance(uptime, datetime.timedelta) else uptime, inline=True)
        embed.add_field(name="🔗 Invite", value=f"[Join {self.server_name}]({self.invite_link})", inline=False)
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author}")
        
        await ctx.send(embed=embed)

    @botstatus.command(name="info", description="ℹ️ Show bot information")
    async def show_info(self, ctx):
        """Show detailed bot information"""
        embed = discord.Embed(
            title=f"ℹ️ {self.server_name} Bot Information",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="🤖 Bot Name", value=self.bot.user.name, inline=True)
        embed.add_field(name="🆔 Bot ID", value=self.bot.user.id, inline=True)
        embed.add_field(name="📅 Created", value=self.bot.user.created_at.strftime("%B %d, %Y"), inline=True)
        embed.add_field(name="🏷️ Server Name", value=self.server_name, inline=True)
        embed.add_field(name="🔗 Invite Link", value=self.invite_link, inline=False)
        embed.add_field(name="📚 Library", value="discord.py", inline=True)
        embed.add_field(name="👨‍💻 Developer", value=". Evil ! Rexy .!", inline=True)
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author}")
        
        await ctx.send(embed=embed)

    @botstatus.command(name="invite", description="🔗 Get the bot invite link")
    async def show_invite(self, ctx):
        """Generate and send bot invite link"""
        permissions = discord.Permissions(
            administrator=True,
            manage_channels=True,
            manage_messages=True,
            manage_roles=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            add_reactions=True,
            use_external_emojis=True,
            connect=True,
            speak=True,
            use_application_commands=True
        )
        
        invite_url = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=permissions,
            scopes=("bot", "applications.commands")
        )
        
        embed = discord.Embed(
            title=f"🔗 Invite {self.server_name} Bot",
            description=f"Add this bot to your server!",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="Bot Invite", value=f"[Click Here]({invite_url})", inline=False)
        embed.add_field(name="Support Server", value=f"[Join {self.server_name}]({self.invite_link})", inline=False)
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author}")
        
        view = InviteView(invite_url, self.invite_link, self.server_name)
        await ctx.send(embed=embed, view=view)

class InviteView(discord.ui.View):
    def __init__(self, bot_invite: str, server_invite: str, server_name: str):
        super().__init__(timeout=None)
        self.bot_invite = bot_invite
        self.server_invite = server_invite
        self.server_name = server_name

    @discord.ui.button(label="🤖 Invite Bot", style=discord.ButtonStyle.primary)
    async def invite_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"Bot invite link: {self.bot_invite}", ephemeral=True)

    @discord.ui.button(label="🏠 Join Server", style=discord.ButtonStyle.success)
    async def join_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"Server invite link: {self.server_invite}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(DynamicStatus(bot))
