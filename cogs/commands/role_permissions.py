import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from typing import List, Dict
import json

class RolePermissions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_hierarchy = {
            "Owner": 100,
            "Co-Owner": 95,
            "Bot": 90,
            "Admin": 85,
            "Head Mod": 80,
            "Senior Mod": 75,
            "Moderator": 70,
            "Trial Mod": 65,
            "Helper": 60,
            "Staff": 55,
            "Trial Staff": 50,
            "Developer": 88,
            "Creator": 98,
            "VIP": 40,
            "Early Supporter": 35,
            "Buyer": 30,
            "Member": 20,
            "Unverified": 10,
            "BEZM BOT": 90,
            "Zyrox X Supreme™": 85,
            "Verified": 45,
            "@everyone": 0
        }
        
        self.permission_categories = {
            "bot_admin": ["Owner", "Co-Owner", "Creator", "Developer", "Bot", "BEZM BOT"],
            "moderation": ["Owner", "Co-Owner", "Admin", "Head Mod", "Senior Mod", "Moderator", "Trial Mod"],
            "giveaway": ["Owner", "Co-Owner", "Admin", "Head Mod", "Senior Mod", "Moderator", "Helper", "Staff"],
            "cookie_giveaway": ["Owner", "Co-Owner", "Creator", "Admin", "Head Mod"],
            "management": ["Owner", "Co-Owner", "Admin", "Head Mod", "Senior Mod"],
            "music": ["Owner", "Co-Owner", "Admin", "Head Mod", "Senior Mod", "Moderator", "VIP", "Verified"],
            "economy": ["Owner", "Co-Owner", "Admin", "Head Mod", "Senior Mod", "Moderator", "VIP"],
            "fun": ["Owner", "Co-Owner", "Admin", "Head Mod", "Senior Mod", "Moderator", "Helper", "Staff", "VIP", "Member", "Verified"],
            "ai": ["Owner", "Co-Owner", "Admin", "Head Mod", "Senior Mod", "Moderator", "VIP", "Developer", "Verified"],
            "general": ["Owner", "Co-Owner", "Admin", "Head Mod", "Senior Mod", "Moderator", "Helper", "Staff", "Trial Staff", "VIP", "Early Supporter", "Buyer", "Member", "Verified", "@everyone"]
        }
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()

    async def _create_tables(self):
        """Create role permissions database tables"""
        try:
            if not hasattr(self.bot, 'db') or self.bot.db is None:
                import aiosqlite
                db_path = "db/role_permissions.db"
                self.bot.db = await aiosqlite.connect(db_path)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    guild_id INTEGER,
                    role_name TEXT,
                    permission_category TEXT,
                    has_access INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, role_name, permission_category)
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS custom_role_hierarchy (
                    guild_id INTEGER,
                    role_name TEXT,
                    priority INTEGER,
                    PRIMARY KEY (guild_id, role_name)
                )
            """)
            
            await self.bot.db.commit()
            
        except Exception as e:
            print(f"Error creating role permissions database: {e}")

    def has_permission(self, user: discord.Member, category: str) -> bool:
        """Check if user has permission for a category"""
        if not user.guild:
            return False
        
        # Get user's highest role by priority
        user_roles = [role.name for role in user.roles if role.name != "@everyone"]
        user_priority = 0
        
        for role_name in user_roles:
            if role_name in self.role_hierarchy:
                user_priority = max(user_priority, self.role_hierarchy[role_name])
        
        # Check if any of user's roles are in the permission category
        allowed_roles = self.permission_categories.get(category, [])
        
        for role_name in user_roles:
            if role_name in allowed_roles:
                return True
        
        return False

    def get_role_priority(self, role_name: str) -> int:
        """Get priority level for a role"""
        return self.role_hierarchy.get(role_name, 0)

    def get_highest_role(self, user: discord.Member) -> str:
        """Get user's highest role by priority"""
        highest_role = "@everyone"
        highest_priority = 0
        
        for role in user.roles:
            if role.name in self.role_hierarchy:
                if self.role_hierarchy[role.name] > highest_priority:
                    highest_priority = self.role_hierarchy[role.name]
                    highest_role = role.name
        
        return highest_role

    @commands.group(name="roleperms", invoke_without_command=True, description="🔐 Manage role permissions")
    @commands.has_permissions(administrator=True)
    async def roleperms(self, ctx):
        """🔐 Role permissions management"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @roleperms.command(name="check", description="🔍 Check your permissions")
    async def check_permissions(self, ctx: commands.Context):
        """Check your role permissions"""
        user = ctx.author
        highest_role = self.get_highest_role(user)
        priority = self.get_role_priority(highest_role)
        
        embed = discord.Embed(
            title=f"🔍 {user.display_name}'s Permissions",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="Highest Role", value=highest_role, inline=True)
        embed.add_field(name="Priority Level", value=str(priority), inline=True)
        
        permissions_status = ""
        for category, roles in self.permission_categories.items():
            has_access = self.has_permission(user, category)
            emoji = "✅" if has_access else "❌"
            permissions_status += f"{emoji} **{category.replace('_', ' ').title()}**\n"
        
        embed.add_field(name="Permission Categories", value=permissions_status, inline=False)
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author}")
        
        await ctx.send(embed=embed)

    @roleperms.command(name="hierarchy", description="📊 View role hierarchy")
    async def view_hierarchy(self, ctx: commands.Context):
        """View the role hierarchy"""
        sorted_roles = sorted(self.role_hierarchy.items(), key=lambda x: x[1], reverse=True)
        
        embed = discord.Embed(
            title="📊 Role Hierarchy",
            description="Roles ordered by priority (highest to lowest)",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        
        hierarchy_text = ""
        for role_name, priority in sorted_roles:
            bar_length = int(priority / 10)
            bar = "█" * bar_length
            hierarchy_text += f"**{role_name}** (Level {priority})\n{bar}\n\n"
        
        embed.description = hierarchy_text
        
        await ctx.send(embed=embed)

    @roleperms.command(name="add", description="➕ Add role to permission category")
    @commands.has_permissions(administrator=True)
    async def add_role_permission(self, ctx: commands.Context, role: discord.Role, category: str):
        """Add a role to a permission category"""
        if category not in self.permission_categories:
            return await ctx.send(f"Invalid category. Available: {', '.join(self.permission_categories.keys())}")
        
        if role.name not in self.permission_categories[category]:
            self.permission_categories[category].append(role.name)
            
            # Save to database
            await self.bot.db.execute(
                "INSERT OR REPLACE INTO role_permissions (guild_id, role_name, permission_category, has_access) VALUES (?, ?, ?, 1)",
                (ctx.guild.id, role.name, category)
            )
            await self.bot.db.commit()
            
            embed = discord.Embed(
                title="✅ Permission Added",
                description=f"Added **{role.name}** to **{category}** permissions",
                color=0x00ff00,
                timestamp=discord.utils.utcnow()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"{role.name} already has {category} permissions.")

    @roleperms.command(name="remove", description="➖ Remove role from permission category")
    @commands.has_permissions(administrator=True)
    async def remove_role_permission(self, ctx: commands.Context, role: discord.Role, category: str):
        """Remove a role from a permission category"""
        if category not in self.permission_categories:
            return await ctx.send(f"Invalid category. Available: {', '.join(self.permission_categories.keys())}")
        
        if role.name in self.permission_categories[category]:
            self.permission_categories[category].remove(role.name)
            
            # Remove from database
            await self.bot.db.execute(
                "DELETE FROM role_permissions WHERE guild_id = ? AND role_name = ? AND permission_category = ?",
                (ctx.guild.id, role.name, category)
            )
            await self.bot.db.commit()
            
            embed = discord.Embed(
                title="➖ Permission Removed",
                description=f"Removed **{role.name}** from **{category}** permissions",
                color=0x00ff00,
                timestamp=discord.utils.utcnow()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"{role.name} doesn't have {category} permissions.")

    @roleperms.command(name="categories", description="📋 List all permission categories")
    async def list_categories(self, ctx: commands.Context):
        """List all permission categories and their roles"""
        embed = discord.Embed(
            title="📋 Permission Categories",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        
        for category, roles in self.permission_categories.items():
            role_list = ", ".join(roles) if roles else "None"
            embed.add_field(
                name=category.replace("_", " ").title(),
                value=role_list[:1024],
                inline=False
            )
        
        await ctx.send(embed=embed)

    @roleperms.command(name="user", description="👤 Check a user's permissions")
    @commands.has_permissions(administrator=True)
    async def check_user_permissions(self, ctx: commands.Context, user: discord.User):
        """Check a specific user's permissions"""
        member = ctx.guild.get_member(user.id)
        if not member:
            return await ctx.send("User not found in this server.")
        
        highest_role = self.get_highest_role(member)
        priority = self.get_role_priority(highest_role)
        
        embed = discord.Embed(
            title=f"🔍 {member.display_name}'s Permissions",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="Highest Role", value=highest_role, inline=True)
        embed.add_field(name="Priority Level", value=str(priority), inline=True)
        
        permissions_status = ""
        for category, roles in self.permission_categories.items():
            has_access = self.has_permission(member, category)
            emoji = "✅" if has_access else "❌"
            permissions_status += f"{emoji} **{category.replace('_', ' ').title()}**\n"
        
        embed.add_field(name="Permission Categories", value=permissions_status, inline=False)
        
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Checked by {ctx.author}")
        
        await ctx.send(embed=embed)

# Custom check decorator for role permissions
def has_role_permission(category: str):
    """Decorator to check if user has role permission for category"""
    async def predicate(ctx):
        cog = ctx.bot.get_cog('RolePermissions')
        if not cog:
            return False
        return cog.has_permission(ctx.author, category)
    return commands.check(predicate)

async def setup(bot):
    await bot.add_cog(RolePermissions(bot))
