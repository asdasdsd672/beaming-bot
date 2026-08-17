import discord
from discord.ext import commands
from discord.ui import Select, View, Button
from typing import Dict, List
import json
from pathlib import Path

CATALOG_PATH = Path("data/command_catalog.json")


class HelpView(View):
    def __init__(self, bot, author_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.author_id = author_id
        self.current_category = None
        self.category_select = None

    async def generate_help_embed(self, category: str = None) -> discord.Embed:
        """Generate help embed based on category"""
        
        # Load command catalog
        try:
            with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            commands_list = catalog.get('commands', [])
        except Exception as e:
            # Fallback to bot.walk_commands if catalog doesn't exist
            print(f"Help command: Could not load catalog ({e}), using fallback")
            commands_list = []
            for cmd in self.bot.walk_commands():
                if not cmd.hidden:
                    commands_list.append({
                        'name': cmd.qualified_name,
                        'description': cmd.help or cmd.description or 'No description',
                        'usage': f">{cmd.qualified_name} {cmd.signature}".rstrip(),
                        'category': cmd.cog.qualified_name if cmd.cog else 'General',
                        'permissions': 'Permission checks enforced' if cmd.checks else 'Everyone',
                        'aliases': list(cmd.aliases)
                    })
            print(f"Help command: Found {len(commands_list)} commands via fallback")

        # Group by category
        categories: Dict[str, List[dict]] = {}
        for cmd in commands_list:
            cat = cmd.get('category', 'General')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(cmd)

        # If specific category requested
        if category and category in categories:
            cmds = categories[category]
            embed = discord.Embed(
                title=f"📚 {category} Commands",
                description=f"Showing {len(cmds)} commands in {category}",
                color=0xFF0000
            )
            
            for cmd in cmds[:10]:  # Show first 10 to avoid embed limits
                usage = cmd.get('usage', cmd['name'])
                perms = cmd.get('permissions', 'Everyone')
                aliases = ', '.join(cmd.get('aliases', []))
                
                value = f"**Usage:** `{usage}`\n"
                if aliases:
                    value += f"**Aliases:** {aliases}\n"
                value += f"**Permissions:** {perms}\n"
                value += f"**Description:** {cmd['description']}"
                
                embed.add_field(name=f"`{cmd['name']}`", value=value, inline=False)
            
            if len(cmds) > 10:
                embed.set_footer(text=f"And {len(cmds) - 10} more commands in this category...")
            
            return embed

        # Main help menu - show all categories
        embed = discord.Embed(
            title="⚡ BeZmerz Help Menu",
            description="Welcome to BeZmerz! Select a category to view commands.",
            color=0xFF0000
        )
        
        embed.add_field(
            name="📊 Statistics",
            value=f"**Total Commands:** {len(commands_list)}\n**Categories:** {len(categories)}",
            inline=False
        )
        
        # Show categories with command counts
        category_list = []
        for cat, cmds in sorted(categories.items()):
            category_list.append(f"**{cat}:** {len(cmds)} commands")
        
        embed.add_field(
            name="📁 Categories",
            value="\n".join(category_list[:10]) if len(category_list) > 10 else "\n".join(category_list),
            inline=False
        )
        
        embed.add_field(
            name="🔧 How to Use",
            value="Use the dropdown menu below to select a category, or use `>help <command>` for specific command info.",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {self.bot.get_user(self.author_id)}", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        
        return embed

    async def category_select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your help menu!", ephemeral=True)
            return

        category = select.values[0]
        embed = await self.generate_help_embed(category)
        
        # Update select options
        self.clear_items()
        
        # Recreate select menu with current selection
        new_select = Select(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            row=0
        )
        
        categories = self.get_categories()
        for cat in categories:
            new_select.add_option(label=cat, value=cat)
        
        new_select.callback = lambda interaction: self.category_select_callback(interaction, new_select)
        self.category_select = new_select
        self.add_item(new_select)
        self.add_item(self.back_button)
        self.add_item(self.home_button)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏠 Home", style=discord.ButtonStyle.blurple, row=1)
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your help menu!", ephemeral=True)
            return

        embed = await self.generate_help_embed()
        self.clear_items()
        
        # Recreate select menu
        select = Select(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            row=0
        )
        
        categories = self.get_categories()
        for cat in categories:
            select.add_option(label=cat, value=cat)
        
        select.callback = lambda interaction: self.category_select_callback(interaction, select)
        self.category_select = select
        self.add_item(select)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your help menu!", ephemeral=True)
            return

        embed = await self.generate_help_embed()
        self.clear_items()
        
        # Recreate select menu
        select = Select(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            row=0
        )
        
        categories = self.get_categories()
        for cat in categories:
            select.add_option(label=cat, value=cat)
        
        select.callback = lambda interaction: self.category_select_callback(interaction, select)
        self.category_select = select
        self.add_item(select)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF0000

    def get_categories(self) -> List[str]:
        """Get list of command categories"""
        try:
            with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            commands_list = catalog.get('commands', [])
        except Exception as e:
            print(f"Help get_categories: Could not load catalog ({e}), using fallback")
            commands_list = []
            for cmd in self.bot.walk_commands():
                if not cmd.hidden:
                    commands_list.append({
                        'category': cmd.cog.qualified_name if cmd.cog else 'General'
                    })
            print(f"Help get_categories: Found {len(commands_list)} commands via fallback")

        categories = set()
        for cmd in commands_list:
            categories.add(cmd.get('category', 'General'))
        
        print(f"Help get_categories: Categories: {sorted(list(categories))}")
        return sorted(list(categories))

    @commands.command(name='help', aliases=['h', 'commands'])
    async def help_command(self, ctx, *, command_name: str = None):
        """Shows help about bot, a command, or a category"""
        
        # If specific command requested
        if command_name:
            command = self.bot.get_command(command_name)
            if command:
                embed = discord.Embed(
                    title=f"❓ Command: {command.qualified_name}",
                    color=self.color
                )
                
                embed.add_field(name="Description", value=command.help or command.description or "No description", inline=False)
                embed.add_field(name="Usage", value=f"`>{command.qualified_name} {command.signature}`".rstrip(), inline=False)
                
                if command.aliases:
                    embed.add_field(name="Aliases", value=", ".join(command.aliases), inline=False)
                
                if command.cog:
                    embed.add_field(name="Category", value=command.cog.qualified_name, inline=False)
                
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ Command `{command_name}` not found.")
            return

        # Show interactive help menu
        categories = self.get_categories()
        print(f"Help command: Total categories found: {len(categories)}")
        
        # Create select menu with categories
        select = Select(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            row=0
        )
        
        for category in categories:
            select.add_option(label=category, value=category)
        
        view = HelpView(self.bot, ctx.author.id)
        
        # Set the callback for the select menu
        select.callback = lambda interaction: view.category_select_callback(interaction, select)
        view.category_select = select
        
        embed = await view.generate_help_embed()
        view.add_item(select)
        
        print(f"Help command: Sending help embed with {len(categories)} categories")
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name='help', description='Shows help about bot commands')
    async def help_slash(self, ctx: discord.Interaction, command: str = None):
        """Shows help about bot commands"""
        # This is a placeholder for slash command support
        await ctx.response.send_message("Please use the prefix command `>help` for the full interactive help menu.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))
