import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from datetime import datetime, timezone
import asyncio

class PartnerSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/partner_system.db"
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()

    async def _create_tables(self):
        """Create partner system database tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS partner_config (
                        guild_id INTEGER PRIMARY KEY,
                        partner_channel_id INTEGER,
                        partner_role_id INTEGER,
                        min_members INTEGER DEFAULT 50,
                        auto_accept BOOLEAN DEFAULT 0
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS partners (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        partner_guild_id INTEGER,
                        partner_guild_name TEXT,
                        partner_guild_icon TEXT,
                        partner_invite_code TEXT,
                        partner_description TEXT,
                        partner_owner_id INTEGER,
                        status TEXT DEFAULT 'pending',
                        clicks INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        accepted_at TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS partner_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        requesting_guild_id INTEGER,
                        requesting_guild_name TEXT,
                        requesting_guild_icon TEXT,
                        requesting_owner_id INTEGER,
                        target_guild_id INTEGER,
                        description TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.commit()
                
        except Exception as e:
            print(f"Error creating partner system database: {e}")

    @commands.group(name="partner", invoke_without_command=True, description="🤝 Partner system commands")
    async def partner(self, ctx):
        """🤝 Partner system commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @partner.command(name="setup", description="⚙️ Set up the partner system")
    @commands.has_permissions(administrator=True)
    async def partner_setup(self, ctx: commands.Context, channel: discord.TextChannel, role: discord.Role = None):
        """Set up the partner system"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO partner_config (guild_id, partner_channel_id, partner_role_id) VALUES (?, ?, ?)",
                (ctx.guild.id, channel.id, role.id if role else None)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="⚙️ Partner System Configured",
            description="The partner system has been set up!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Partner Channel", value=channel.mention, inline=True)
        embed.add_field(name="Partner Role", value=role.mention if role else "None", inline=True)
        
        await ctx.send(embed=embed)

    @partner.command(name="add", description="➕ Add a partner server")
    @commands.has_permissions(administrator=True)
    async def add_partner(self, ctx: commands.Context, guild_id: int, invite_code: str, *, description: str):
        """Add a partner server"""
        try:
            # Try to get guild info
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return await ctx.send("I'm not in that server. Make sure I'm added to the partner server first.")
            
            async with aiosqlite.connect(self.db_path) as db:
                # Check if already partnered
                cursor = await db.execute(
                    "SELECT id FROM partners WHERE guild_id = ? AND partner_guild_id = ?",
                    (ctx.guild.id, guild_id)
                )
                if await cursor.fetchone():
                    return await ctx.send("This server is already your partner.")
                
                # Add partner
                await db.execute(
                    "INSERT INTO partners (guild_id, partner_guild_id, partner_guild_name, partner_guild_icon, partner_invite_code, partner_description, partner_owner_id, status, accepted_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'accepted', ?)",
                    (ctx.guild.id, guild_id, guild.name, str(guild.icon.url) if guild.icon else None, invite_code, description, guild.owner.id, datetime.now(timezone.utc).isoformat())
                )
                await db.commit()
            
            embed = discord.Embed(
                title="✅ Partner Added",
                description=f"Successfully partnered with **{guild.name}**!",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Server", value=guild.name, inline=True)
            embed.add_field(name="Invite", value=f"https://discord.gg/{invite_code}", inline=True)
            embed.add_field(name="Description", value=description[:1024], inline=False)
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            
            await ctx.send(embed=embed)
            
            # Send partner message to partner channel
            await self._send_partner_message(ctx.guild, guild_id, invite_code, description)
            
        except Exception as e:
            print(f"Error adding partner: {e}")
            await ctx.send("Error adding partner. Make sure the guild ID is correct.")

    async def _send_partner_message(self, guild: discord.Guild, partner_guild_id: int, invite_code: str, description: str):
        """Send partner message to partner channel"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT partner_channel_id FROM partner_config WHERE guild_id = ?",
                    (guild.id,)
                )
                config = await cursor.fetchone()
                
                if not config or not config[0]:
                    return
                
                channel = guild.get_channel(config[0])
                if not channel:
                    return
                
                partner_guild = self.bot.get_guild(partner_guild_id)
                if not partner_guild:
                    return
                
                embed = discord.Embed(
                    title="🤝 Partner Server",
                    description=f"Check out our partner server **{partner_guild.name}**!",
                    color=0x00ff00,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Members", value=str(len(partner_guild.members)), inline=True)
                embed.add_field(name="Invite", value=f"https://discord.gg/{invite_code}", inline=True)
                embed.add_field(name="Description", value=description[:1024], inline=False)
                embed.set_thumbnail(url=partner_guild.icon.url if partner_guild.icon else None)
                embed.set_footer(text="Click the invite to join!")
                
                view = PartnerInviteView(invite_code)
                await channel.send(embed=embed, view=view)
                
        except Exception as e:
            print(f"Error sending partner message: {e}")

    @partner.command(name="remove", description="➖ Remove a partner")
    @commands.has_permissions(administrator=True)
    async def remove_partner(self, ctx: commands.Context, partner_id: int):
        """Remove a partner"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT partner_guild_name FROM partners WHERE id = ? AND guild_id = ?",
                (partner_id, ctx.guild.id)
            )
            result = await cursor.fetchone()
            
            if not result:
                return await ctx.send("Partner not found.")
            
            await db.execute(
                "DELETE FROM partners WHERE id = ? AND guild_id = ?",
                (partner_id, ctx.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="➖ Partner Removed",
            description=f"Removed partnership with **{result[0]}**.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @partner.command(name="list", description="📋 List all partners")
    async def list_partners(self, ctx: commands.Context):
        """List all partners"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, partner_guild_name, partner_invite_code, partner_description, clicks, status FROM partners WHERE guild_id = ? AND status = 'accepted'",
                (ctx.guild.id,)
            )
            partners = await cursor.fetchall()
        
        if not partners:
            embed = discord.Embed(
                title="📋 Partners",
                description="No partners yet. Use `>partner add` to add partners!",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"📋 Partners ({len(partners)})",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        for partner_id, name, invite, description, clicks, status in partners:
            embed.add_field(
                name=f"#{partner_id} - {name}",
                value=f"**Invite:** https://discord.gg/{invite}\n**Clicks:** {clicks}\n**Description:** {description[:50]}...",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @partner.command(name="request", description="📨 Request partnership with another server")
    async def request_partner(self, ctx: commands.Context, target_guild_id: int, *, description: str):
        """Request partnership with another server"""
        if len(ctx.guild.members) < 50:
            return await ctx.send("Your server needs at least 50 members to request partnerships.")
        
        async with aiosqlite.connect(self.db_path) as db:
            # Check if already requested
            cursor = await db.execute(
                "SELECT id FROM partner_requests WHERE requesting_guild_id = ? AND target_guild_id = ? AND status = 'pending'",
                (ctx.guild.id, target_guild_id)
            )
            if await cursor.fetchone():
                return await ctx.send("You already have a pending request to this server.")
            
            # Create request
            await db.execute(
                "INSERT INTO partner_requests (requesting_guild_id, requesting_guild_name, requesting_guild_icon, requesting_owner_id, target_guild_id, description) VALUES (?, ?, ?, ?, ?, ?)",
                (ctx.guild.id, ctx.guild.name, str(ctx.guild.icon.url) if ctx.guild.icon else None, ctx.guild.owner.id, target_guild_id, description)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="📨 Partnership Request Sent",
            description=f"Partnership request sent to server ID: {target_guild_id}",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Your Server", value=ctx.guild.name, inline=True)
        embed.add_field(name="Members", value=str(len(ctx.guild.members)), inline=True)
        embed.add_field(name="Description", value=description[:1024], inline=False)
        
        await ctx.send(embed=embed)

    @partner.command(name="requests", description="📨 View partnership requests")
    @commands.has_permissions(administrator=True)
    async def view_requests(self, ctx: commands.Context):
        """View partnership requests"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, requesting_guild_name, requesting_owner_id, description, status, created_at FROM partner_requests WHERE target_guild_id = ? ORDER BY created_at DESC",
                (ctx.guild.id,)
            )
            requests = await cursor.fetchall()
        
        if not requests:
            embed = discord.Embed(
                title="📨 Partnership Requests",
                description="No partnership requests.",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"📨 Partnership Requests ({len(requests)})",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        for request_id, name, owner_id, description, status, created_at in requests:
            owner = self.bot.get_user(owner_id)
            owner_name = owner.name if owner else f"Unknown ({owner_id})"
            embed.add_field(
                name=f"Request #{request_id} - {status.upper()}",
                value=f"**Server:** {name}\n**Owner:** {owner_name}\n**Description:** {description[:50]}...",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @partner.command(name="accept", description="✅ Accept a partnership request")
    @commands.has_permissions(administrator=True)
    async def accept_request(self, ctx: commands.Context, request_id: int):
        """Accept a partnership request"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT requesting_guild_id, requesting_guild_name, requesting_guild_icon, description FROM partner_requests WHERE id = ? AND target_guild_id = ? AND status = 'pending'",
                (request_id, ctx.guild.id)
            )
            result = await cursor.fetchone()
            
            if not result:
                return await ctx.send("Request not found or already processed.")
            
            requesting_guild_id, requesting_guild_name, requesting_guild_icon, description = result
            
            # Update request status
            await db.execute(
                "UPDATE partner_requests SET status = 'accepted' WHERE id = ?",
                (request_id,)
            )
            
            # Add as partner
            await db.execute(
                "INSERT INTO partners (guild_id, partner_guild_id, partner_guild_name, partner_guild_icon, partner_description, partner_owner_id, status, accepted_at) VALUES (?, ?, ?, ?, ?, ?, 'accepted', ?)",
                (ctx.guild.id, requesting_guild_id, requesting_guild_name, requesting_guild_icon, description, ctx.guild.owner.id, datetime.now(timezone.utc).isoformat())
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Partnership Accepted",
            description=f"Partnership with **{requesting_guild_name}** has been accepted!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @partner.command(name="decline", description="❌ Decline a partnership request")
    @commands.has_permissions(administrator=True)
    async def decline_request(self, ctx: commands.Context, request_id: int):
        """Decline a partnership request"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT requesting_guild_name FROM partner_requests WHERE id = ? AND target_guild_id = ? AND status = 'pending'",
                (request_id, ctx.guild.id)
            )
            result = await cursor.fetchone()
            
            if not result:
                return await ctx.send("Request not found or already processed.")
            
            await db.execute(
                "UPDATE partner_requests SET status = 'declined' WHERE id = ?",
                (request_id,)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="❌ Partnership Declined",
            description=f"Partnership request from **{result[0]}** has been declined.",
            color=0xff0000,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @partner.command(name="stats", description="📊 View partner statistics")
    @commands.has_permissions(administrator=True)
    async def partner_stats(self, ctx: commands.Context):
        """View partner statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*), SUM(clicks) FROM partners WHERE guild_id = ? AND status = 'accepted'",
                (ctx.guild.id,)
            )
            total_partners, total_clicks = await cursor.fetchone()
            
            cursor = await db.execute(
                "SELECT partner_guild_name, clicks FROM partners WHERE guild_id = ? AND status = 'accepted' ORDER BY clicks DESC LIMIT 5",
                (ctx.guild.id,)
            )
            top_partners = await cursor.fetchall()
        
        embed = discord.Embed(
            title="📊 Partner Statistics",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Total Partners", value=str(total_partners or 0), inline=True)
        embed.add_field(name="Total Clicks", value=str(total_clicks or 0), inline=True)
        
        if top_partners:
            top_text = ""
            for i, (name, clicks) in enumerate(top_partners):
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
                top_text += f"{medal} **{name}**: {clicks} clicks\n"
            
            embed.add_field(name="Top Partners", value=top_text, inline=False)
        
        await ctx.send(embed=embed)

    @partner.command(name="config", description="⚙️ Configure partner system settings")
    @commands.has_permissions(administrator=True)
    async def partner_config(self, ctx: commands.Context, min_members: int = 50, auto_accept: bool = False):
        """Configure partner system settings"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO partner_config (guild_id, min_members, auto_accept) VALUES (?, ?, ?)",
                (ctx.guild.id, min_members, 1 if auto_accept else 0)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="⚙️ Partner System Configured",
            description="Partner system settings updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Minimum Members", value=str(min_members), inline=True)
        embed.add_field(name="Auto Accept", value="Enabled" if auto_accept else "Disabled", inline=True)
        
        await ctx.send(embed=embed)

class PartnerInviteView(View):
    def __init__(self, invite_code: str):
        super().__init__(timeout=None)
        self.invite_code = invite_code

    @discord.ui.button(label="Join Server", style=discord.ButtonStyle.green, url=f"https://discord.gg/{invite_code}")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Opening invite link...", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PartnerSystem(bot))
