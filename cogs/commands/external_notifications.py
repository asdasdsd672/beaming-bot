import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button
from discord import ButtonStyle
from datetime import datetime, timezone
import asyncio
import json
from aiohttp import web

class ExternalNotifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/external_notifications.db"
        self.webhook_server = None
        self.runner = None
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database and webhook server after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()
        await self._start_webhook_server()

    async def _create_tables(self):
        """Create external notifications database tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS notification_config (
                        guild_id INTEGER PRIMARY KEY,
                        youtube_channel_id INTEGER,
                        youtube_api_key TEXT,
                        youtube_channel_ids TEXT,
                        ticket_notification_channel_id INTEGER,
                        application_notification_channel_id INTEGER,
                        suggestion_notification_channel_id INTEGER,
                        webhook_url TEXT,
                        webhook_enabled BOOLEAN DEFAULT 0
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS notification_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        platform TEXT,
                        content TEXT,
                        url TEXT,
                        notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.commit()
                
        except Exception as e:
            print(f"Error creating external notifications database: {e}")

    async def _start_webhook_server(self):
        """Start the webhook server for external notifications"""
        try:
            app = web.Application()
            app.add_routes([
                web.post('/webhook/youtube', self._handle_youtube_webhook),
                web.post('/webhook/ticket', self._handle_ticket_webhook),
                web.post('/webhook/application', self._handle_application_webhook),
                web.post('/webhook/general', self._handle_general_webhook),
            ])
            
            self.runner = web.AppRunner(app)
            await self.runner.setup()
            site = web.TCPSite(self.runner, '0.0.0.0', 8080)
            await site.start()
            
            print("Webhook server started on port 8080")
            
        except Exception as e:
            print(f"Error starting webhook server: {e}")

    async def _handle_youtube_webhook(self, request):
        """Handle YouTube webhook notifications"""
        try:
            data = await request.json()
            
            # Extract video information
            video_id = data.get('video_id')
            video_title = data.get('video_title')
            video_url = data.get('video_url')
            channel_name = data.get('channel_name')
            thumbnail_url = data.get('thumbnail_url')
            guild_id = data.get('guild_id')
            
            if not all([video_id, video_title, video_url, guild_id]):
                return web.json_response({'status': 'error', 'message': 'Missing required fields'})
            
            # Get notification channel
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT youtube_channel_id FROM notification_config WHERE guild_id = ?",
                    (int(guild_id),)
                )
                config = await cursor.fetchone()
            
            if not config or not config[0]:
                return web.json_response({'status': 'error', 'message': 'YouTube notifications not configured'})
            
            channel = self.bot.get_channel(config[0])
            if not channel:
                return web.json_response({'status': 'error', 'message': 'Channel not found'})
            
            # Create notification embed
            embed = discord.Embed(
                title="🎬 New YouTube Video!",
                description=video_title,
                color=0xff0000,
                url=video_url,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Channel", value=channel_name, inline=True)
            embed.add_field(name="Video ID", value=video_id, inline=True)
            embed.set_image(url=thumbnail_url)
            embed.set_footer(text="Click the title to watch!")
            
            await channel.send(embed=embed)
            
            # Log to history
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO notification_history (guild_id, platform, content, url) VALUES (?, ?, ?, ?)",
                    (int(guild_id), 'youtube', video_title, video_url)
                )
                await db.commit()
            
            return web.json_response({'status': 'success'})
            
        except Exception as e:
            print(f"Error handling YouTube webhook: {e}")
            return web.json_response({'status': 'error', 'message': str(e)})

    async def _handle_ticket_webhook(self, request):
        """Handle ticket webhook notifications"""
        try:
            data = await request.json()
            
            ticket_id = data.get('ticket_id')
            ticket_title = data.get('ticket_title')
            ticket_user = data.get('ticket_user')
            ticket_category = data.get('ticket_category')
            guild_id = data.get('guild_id')
            
            if not all([ticket_id, ticket_title, guild_id]):
                return web.json_response({'status': 'error', 'message': 'Missing required fields'})
            
            # Get notification channel
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT ticket_notification_channel_id FROM notification_config WHERE guild_id = ?",
                    (int(guild_id),)
                )
                config = await cursor.fetchone()
            
            if not config or not config[0]:
                return web.json_response({'status': 'error', 'message': 'Ticket notifications not configured'})
            
            channel = self.bot.get_channel(config[0])
            if not channel:
                return web.json_response({'status': 'error', 'message': 'Channel not found'})
            
            # Create notification embed
            embed = discord.Embed(
                title="🎫 New Ticket Created",
                description=f"Ticket #{ticket_id}: {ticket_title}",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="User", value=ticket_user or "Unknown", inline=True)
            embed.add_field(name="Category", value=ticket_category or "General", inline=True)
            embed.add_field(name="Ticket ID", value=str(ticket_id), inline=True)
            embed.set_footer(text="A new ticket has been created!")
            
            await channel.send(embed=embed)
            
            # Log to history
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO notification_history (guild_id, platform, content) VALUES (?, ?, ?)",
                    (int(guild_id), 'ticket', f"Ticket #{ticket_id}: {ticket_title}")
                )
                await db.commit()
            
            return web.json_response({'status': 'success'})
            
        except Exception as e:
            print(f"Error handling ticket webhook: {e}")
            return web.json_response({'status': 'error', 'message': str(e)})

    async def _handle_application_webhook(self, request):
        """Handle application webhook notifications"""
        try:
            data = await request.json()
            
            application_id = data.get('application_id')
            application_type = data.get('application_type')
            applicant_name = data.get('applicant_name')
            guild_id = data.get('guild_id')
            
            if not all([application_id, application_type, guild_id]):
                return web.json_response({'status': 'error', 'message': 'Missing required fields'})
            
            # Get notification channel
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT application_notification_channel_id FROM notification_config WHERE guild_id = ?",
                    (int(guild_id),)
                )
                config = await cursor.fetchone()
            
            if not config or not config[0]:
                return web.json_response({'status': 'error', 'message': 'Application notifications not configured'})
            
            channel = self.bot.get_channel(config[0])
            if not channel:
                return web.json_response({'status': 'error', 'message': 'Channel not found'})
            
            # Create notification embed
            embed = discord.Embed(
                title="📋 New Application Submitted",
                description=f"Application #{application_id}: {application_type}",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Applicant", value=applicant_name or "Unknown", inline=True)
            embed.add_field(name="Application Type", value=application_type, inline=True)
            embed.add_field(name="Application ID", value=str(application_id), inline=True)
            embed.set_footer(text="A new application has been submitted!")
            
            await channel.send(embed=embed)
            
            # Log to history
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO notification_history (guild_id, platform, content) VALUES (?, ?, ?)",
                    (int(guild_id), 'application', f"Application #{application_id}")
                )
                await db.commit()
            
            return web.json_response({'status': 'success'})
            
        except Exception as e:
            print(f"Error handling application webhook: {e}")
            return web.json_response({'status': 'error', 'message': str(e)})

    async def _handle_general_webhook(self, request):
        """Handle general webhook notifications"""
        try:
            data = await request.json()
            
            title = data.get('title')
            description = data.get('description')
            color = data.get('color', 0x00ff00)
            guild_id = data.get('guild_id')
            
            if not all([title, guild_id]):
                return web.json_response({'status': 'error', 'message': 'Missing required fields'})
            
            # Get webhook URL from config
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT webhook_url, webhook_enabled FROM notification_config WHERE guild_id = ?",
                    (int(guild_id),)
                )
                config = await cursor.fetchone()
            
            if not config or not config[1]:
                return web.json_response({'status': 'error', 'message': 'Webhook notifications not enabled'})
            
            # Send to webhook if configured
            if config[0]:
                async with self.bot.session.post(config[0], json={
                    'embeds': [{
                        'title': title,
                        'description': description,
                        'color': color,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }]
                }) as response:
                    if response.status == 200:
                        return web.json_response({'status': 'success'})
                    else:
                        return web.json_response({'status': 'error', 'message': 'Webhook failed'})
            
            return web.json_response({'status': 'error', 'message': 'No webhook configured'})
            
        except Exception as e:
            print(f"Error handling general webhook: {e}")
            return web.json_response({'status': 'error', 'message': str(e)})

    @commands.group(name="notifications", invoke_without_command=True, description="🔔 External notification system commands")
    async def notifications(self, ctx):
        """🔔 External notification system commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @notifications.command(name="youtube", description="🎬 Set up YouTube notifications")
    @commands.has_permissions(administrator=True)
    async def setup_youtube(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set up YouTube notifications"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE notification_config SET youtube_channel_id = ? WHERE guild_id = ?",
                (channel.id, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ YouTube Notifications Configured",
            description=f"YouTube notifications will be sent to {channel.mention}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Webhook URL", value=f"http://your-server-ip:8080/webhook/youtube", inline=False)
        embed.add_field(name="Required Fields", value="video_id, video_title, video_url, channel_name, thumbnail_url, guild_id", inline=False)
        
        await ctx.send(embed=embed)

    @notifications.command(name="ticket", description="🎫 Set up ticket notifications")
    @commands.has_permissions(administrator=True)
    async def setup_ticket(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set up ticket notifications"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE notification_config SET ticket_notification_channel_id = ? WHERE guild_id = ?",
                (channel.id, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Ticket Notifications Configured",
            description=f"Ticket notifications will be sent to {channel.mention}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Webhook URL", value=f"http://your-server-ip:8080/webhook/ticket", inline=False)
        embed.add_field(name="Required Fields", value="ticket_id, ticket_title, ticket_user, ticket_category, guild_id", inline=False)
        
        await ctx.send(embed=embed)

    @notifications.command(name="application", description="📋 Set up application notifications")
    @commands.has_permissions(administrator=True)
    async def setup_application(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set up application notifications"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE notification_config SET application_notification_channel_id = ? WHERE guild_id = ?",
                (channel.id, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Application Notifications Configured",
            description=f"Application notifications will be sent to {channel.mention}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Webhook URL", value=f"http://your-server-ip:8080/webhook/application", inline=False)
        embed.add_field(name="Required Fields", value="application_id, application_type, applicant_name, guild_id", inline=False)
        
        await ctx.send(embed=embed)

    @notifications.command(name="webhook", description="🔗 Set up general webhook")
    @commands.has_permissions(administrator=True)
    async def setup_webhook(self, ctx: commands.Context, webhook_url: str):
        """Set up general webhook"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE notification_config SET webhook_url = ?, webhook_enabled = 1 WHERE guild_id = ?",
                (webhook_url, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Webhook Configured",
            description="General webhook has been configured.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Webhook URL", value=webhook_url[:100], inline=False)
        embed.add_field(name="Endpoint", value="http://your-server-ip:8080/webhook/general", inline=False)
        
        await ctx.send(embed=embed)

    @notifications.command(name="history", description="📜 View notification history")
    @commands.has_permissions(administrator=True)
    async def notification_history(self, ctx: commands.Context, limit: int = 10):
        """View notification history"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT platform, content, url, notified_at FROM notification_history WHERE guild_id = ? ORDER BY notified_at DESC LIMIT ?",
                (ctx.guild.id, limit)
            )
            history = await cursor.fetchall()
        
        if not history:
            embed = discord.Embed(
                title="📜 Notification History",
                description="No notification history found.",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"📜 Notification History ({len(history)})",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        for platform, content, url, notified_at in history:
            platform_emoji = {"youtube": "🎬", "ticket": "🎫", "application": "📋", "general": "🔔"}.get(platform, "📢")
            field_text = f"{platform_emoji} **{platform.upper()}**: {content[:50]}..."
            if url:
                field_text += f"\n🔗 {url}"
            embed.add_field(name=notified_at[:19], value=field_text, inline=False)
        
        await ctx.send(embed=embed)

    @notifications.command(name="test", description="🧪 Test notification system")
    @commands.has_permissions(administrator=True)
    async def test_notification(self, ctx: commands.Context):
        """Test the notification system"""
        embed = discord.Embed(
            title="🧪 Notification Test",
            description="This is a test notification from the external notification system.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Test Time", value=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="Guild", value=ctx.guild.name, inline=True)
        
        await ctx.send(embed=embed)
        
        # Log test
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO notification_history (guild_id, platform, content) VALUES (?, ?, ?)",
                (ctx.guild.id, 'test', 'Test notification')
            )
            await db.commit()

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        if self.runner:
            asyncio.create_task(self.runner.cleanup())

async def setup(bot):
    await bot.add_cog(ExternalNotifications(bot))
