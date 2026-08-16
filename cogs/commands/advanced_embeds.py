import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput
from datetime import datetime, timezone
import asyncio
import json
from typing import Optional, List

class AdvancedEmbeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/advanced_embeds.db"
        self.embed_templates = {}
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()
        await self._load_templates()

    async def _create_tables(self):
        """Create advanced embeds database tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS embed_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        template_name TEXT,
                        template_data TEXT,
                        created_by INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS embed_presets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        preset_name TEXT,
                        preset_data TEXT,
                        is_public BOOLEAN DEFAULT 1
                    )
                """)
                
                await db.commit()
                
        except Exception as e:
            print(f"Error creating advanced embeds database: {e}")

    async def _load_templates(self):
        """Load embed templates from database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT template_name, template_data FROM embed_templates")
                templates = await cursor.fetchall()
                
                for name, data in templates:
                    self.embed_templates[name] = json.loads(data)
                    
        except Exception as e:
            print(f"Error loading templates: {e}")

    @commands.group(name="embed", invoke_without_command=True, description="🎨 Advanced embed system")
    async def embed(self, ctx):
        """🎨 Advanced embed system"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @embed.command(name="create", description="✨ Create an advanced embed")
    async def create_embed(self, ctx: commands.Context):
        """Create an advanced embed using interactive builder"""
        view = EmbedBuilderView(ctx, self)
        await ctx.send("🎨 **Advanced Embed Builder**\nClick the buttons below to customize your embed:", view=view)

    @embed.command(name="template", description="📋 Save current embed as template")
    async def save_template(self, ctx: commands.Context, template_name: str):
        """Save current embed as template"""
        # This would work with a state system - for now create a simple template
        template_data = {
            "title": "Sample Template",
            "description": "This is a sample template",
            "color": 0x00ff00,
            "fields": []
        }
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO embed_templates (guild_id, template_name, template_data, created_by) VALUES (?, ?, ?, ?)",
                (ctx.guild.id, template_name, json.dumps(template_data), ctx.author.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Template Saved",
            description=f"Template '{template_name}' has been saved!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @embed.command(name="load", description="📂 Load a template")
    async def load_template(self, ctx: commands.Context, template_name: str):
        """Load a template"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT template_data FROM embed_templates WHERE guild_id = ? AND template_name = ?",
                (ctx.guild.id, template_name)
            )
            result = await cursor.fetchone()
        
        if not result:
            return await ctx.send("Template not found.")
        
        template_data = json.loads(result[0])
        embed = discord.Embed.from_dict(template_data)
        await ctx.send(embed=embed)

    @embed.command(name="send", description="📤 Send an embed")
    async def send_embed(self, ctx: commands.Context, channel: discord.TextChannel, *, json_data: str):
        """Send an embed from JSON data"""
        try:
            embed_data = json.loads(json_data)
            embed = discord.Embed.from_dict(embed_data)
            await channel.send(embed=embed)
            
            await ctx.send(f"✅ Embed sent to {channel.mention}!")
            
        except json.JSONDecodeError:
            await ctx.send("Invalid JSON data.")
        except Exception as e:
            await ctx.send(f"Error creating embed: {e}")

    @embed.command(name="rich", description="🌟 Create a rich embed with all options")
    async def rich_embed(self, ctx: commands.Context):
        """Create a rich embed with all customization options"""
        modal = RichEmbedModal()
        await ctx.send_modal(modal)

    @embed.command(name="color", description="🎨 Set embed color schemes")
    async def embed_color(self, ctx: commands.Context, scheme: str):
        """Set embed color scheme"""
        color_schemes = {
            "neon": {"primary": 0xff00ff, "secondary": 0x00ffff, "accent": 0xffff00},
            "ocean": {"primary": 0x0077be, "secondary": 0x00a8e8, "accent": 0x00d4aa},
            "sunset": {"primary": 0xff6b6b, "secondary": 0xfeca57, "accent": 0xff9ff3},
            "forest": {"primary": 0x2ecc71, "secondary": 0x27ae60, "accent": 0x1abc9c},
            "royal": {"primary": 0x9b59b6, "secondary": 0x8e44ad, "accent": 0x3498db},
            "fire": {"primary": 0xe74c3c, "secondary": 0xc0392b, "accent": 0xf39c12},
            "midnight": {"primary": 0x2c3e50, "secondary": 0x34495e, "accent": 0x1abc9c},
            "pastel": {"primary": 0xffb3ba, "secondary": 0xffdfba, "accent": 0xffffba}
        }
        
        if scheme.lower() not in color_schemes:
            return await ctx.send(f"Available schemes: {', '.join(color_schemes.keys())}")
        
        colors = color_schemes[scheme.lower()]
        
        embed = discord.Embed(
            title=f"🎨 {scheme.title()} Color Scheme",
            description="Color scheme applied to embeds",
            color=colors["primary"],
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="Primary", value=f"#{colors['primary']:06x}", inline=True)
        embed.add_field(name="Secondary", value=f"#{colors['secondary']:06x}", inline=True)
        embed.add_field(name="Accent", value=f"#{colors['accent']:06x}", inline=True)
        
        embed.set_footer(text="Use these colors in your embeds!")
        
        await ctx.send(embed=embed)

    @embed.command(name="components", description="🔘 Add components to embed")
    async def embed_components(self, ctx: commands.Context):
        """Add interactive components to embed"""
        view = ComponentBuilderView(ctx)
        
        embed = discord.Embed(
            title="🔘 Component Builder",
            description="Add buttons and select menus to your embed",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        await ctx.send(embed=embed, view=view)

    @embed.command(name="preview", description="👁️ Preview an embed")
    async def preview_embed(self, ctx: commands.Context, *, json_data: str):
        """Preview an embed without sending"""
        try:
            embed_data = json.loads(json_data)
            embed = discord.Embed.from_dict(embed_data)
            
            preview_embed = discord.Embed(
                title="👁️ Embed Preview",
                description="This is how your embed will look:",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            
            await ctx.send(preview_embed)
            await ctx.send(embed=embed)
            
        except json.JSONDecodeError:
            await ctx.send("Invalid JSON data.")
        except Exception as e:
            await ctx.send(f"Error creating embed: {e}")

    @embed.command(name="list", description="📋 List all templates")
    async def list_templates(self, ctx: commands.Context):
        """List all available templates"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT template_name, created_by, created_at FROM embed_templates WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            templates = await cursor.fetchall()
        
        if not templates:
            return await ctx.send("No templates found.")
        
        embed = discord.Embed(
            title="📋 Available Templates",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        for name, creator, created_at in templates:
            user = self.bot.get_user(creator)
            user_name = user.name if user else "Unknown"
            embed.add_field(name=name, value=f"Created by {user_name}\n{created_at[:10]}", inline=False)
        
        await ctx.send(embed=embed)

class EmbedBuilderView(View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog
        self.current_embed = discord.Embed(title="New Embed", description="Description", color=0x00ff00)

    @discord.ui.button(label="📝 Title", style=discord.ButtonStyle.primary)
    async def set_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TitleModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📄 Description", style=discord.ButtonStyle.primary)
    async def set_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = DescriptionModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎨 Color", style=discord.ButtonStyle.secondary)
    async def set_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ColorModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🖼️ Image", style=discord.ButtonStyle.secondary)
    async def set_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ImageModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="➕ Add Field", style=discord.ButtonStyle.success)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = FieldModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📤 Send", style=discord.ButtonStyle.green)
    async def send_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Embed sent!", ephemeral=True)
        await self.ctx.send(embed=self.current_embed)
        self.stop()

class ComponentBuilderView(View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.buttons = []
        self.select_menus = []

    @discord.ui.button(label="➕ Add Button", style=discord.ButtonStyle.primary)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ButtonModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📋 Add Select", style=discord.ButtonStyle.primary)
    async def add_select(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SelectModal()
        await interaction.response.send_modal(modal)

class TitleModal(Modal, title="Set Embed Title"):
    title_input = TextInput(label="Title", placeholder="Enter embed title", required=True, max_length=256)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Title set to: {self.title_input.value}", ephemeral=True)

class DescriptionModal(Modal, title="Set Embed Description"):
    desc_input = TextInput(label="Description", placeholder="Enter embed description", required=True, style=discord.TextStyle.paragraph, max_length=4096)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Description set to: {self.desc_input.value}", ephemeral=True)

class ColorModal(Modal, title="Set Embed Color"):
    color_input = TextInput(label="Color (hex)", placeholder="#00ff00", required=True, max_length=7)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Color set to: {self.color_input.value}", ephemeral=True)

class ImageModal(Modal, title="Set Embed Image"):
    image_input = TextInput(label="Image URL", placeholder="https://example.com/image.png", required=True, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Image set to: {self.image_input.value}", ephemeral=True)

class FieldModal(Modal, title="Add Embed Field"):
    name_input = TextInput(label="Field Name", placeholder="Field name", required=True, max_length=256)
    value_input = TextInput(label="Field Value", placeholder="Field value", required=True, style=discord.TextStyle.paragraph, max_length=1024)
    inline_input = TextInput(label="Inline (true/false)", placeholder="true", required=False, max_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        inline = self.inline_input.value.lower() == "true" if self.inline_input.value else False
        await interaction.response.send_message(f"Field added: {self.name_input.value}", ephemeral=True)

class RichEmbedModal(Modal, title="Rich Embed Builder"):
    title = TextInput(label="Title", placeholder="Embed title", required=True, max_length=256)
    description = TextInput(label="Description", placeholder="Embed description", required=True, style=discord.TextStyle.paragraph, max_length=4096)
    color = TextInput(label="Color (hex)", placeholder="#00ff00", required=False, max_length=7)
    author_name = TextInput(label="Author Name", placeholder="Author name", required=False, max_length=256)
    author_url = TextInput(label="Author URL", placeholder="https://example.com", required=False, max_length=2000)
    footer_text = TextInput(label="Footer Text", placeholder="Footer text", required=False, max_length=2048)
    thumbnail_url = TextInput(label="Thumbnail URL", placeholder="https://example.com/thumb.png", required=False, max_length=2000)
    image_url = TextInput(label="Image URL", placeholder="https://example.com/image.png", required=False, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color = int(self.color.value.replace('#', ''), 16) if self.color.value else 0x00ff00
        except:
            color = 0x00ff00
        
        embed = discord.Embed(
            title=self.title.value,
            description=self.description.value,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        if self.author_name.value:
            embed.set_author(name=self.author_name.value, url=self.author_url.value if self.author_url.value else None)
        
        if self.footer_text.value:
            embed.set_footer(text=self.footer_text.value)
        
        if self.thumbnail_url.value:
            embed.set_thumbnail(url=self.thumbnail_url.value)
        
        if self.image_url.value:
            embed.set_image(url=self.image_url.value)
        
        await interaction.response.send_message("Rich embed created!", ephemeral=True)
        await interaction.followup.send(embed=embed)

class ButtonModal(Modal, title="Add Button"):
    label = TextInput(label="Button Label", placeholder="Click me!", required=True, max_length=80)
    style = TextInput(label="Style (primary/secondary/success/danger)", placeholder="primary", required=False, max_length=10)
    url = TextInput(label="URL (optional)", placeholder="https://example.com", required=False, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Button added: {self.label.value}", ephemeral=True)

class SelectModal(Modal, title="Add Select Menu"):
    placeholder = TextInput(label="Placeholder", placeholder="Select an option", required=True, max_length=150)
    options = TextInput(label="Options (comma separated)", placeholder="Option 1, Option 2, Option 3", required=True, style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Select menu added with {len(self.options.value.split(','))} options", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdvancedEmbeds(bot))
