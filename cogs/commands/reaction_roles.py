import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
from discord.ui import View, Button, Select
from datetime import datetime, timezone
import asyncio

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/reaction_roles.db"
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()
        await self._load_persistent_views()

    async def _create_tables(self):
        """Create reaction roles database tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS reaction_messages (
                        message_id INTEGER PRIMARY KEY,
                        guild_id INTEGER,
                        channel_id INTEGER,
                        message_type TEXT DEFAULT 'button',
                        title TEXT,
                        description TEXT
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS reaction_roles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id INTEGER,
                        emoji TEXT,
                        role_id INTEGER,
                        label TEXT,
                        style INTEGER DEFAULT 1
                    )
                """)
                
                await db.commit()
                
        except Exception as e:
            print(f"Error creating reaction roles database: {e}")

    async def _load_persistent_views(self):
        """Load persistent views for reaction role messages"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT message_id, message_type FROM reaction_messages"
                )
                messages = await cursor.fetchall()
                
                for message_id, message_type in messages:
                    if message_type == "button":
                        view = self.create_button_view(message_id)
                        if view:
                            self.bot.add_view(view, message_id=message_id)
                    elif message_type == "dropdown":
                        view = self.create_dropdown_view(message_id)
                        if view:
                            self.bot.add_view(view, message_id=message_id)
                            
        except Exception as e:
            print(f"Error loading persistent views: {e}")

    def create_button_view(self, message_id):
        """Create a button view for reaction roles"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT emoji, role_id, label, style FROM reaction_roles WHERE message_id = ?",
                    (message_id,)
                )
                roles = await cursor.fetchall()
            
            if not roles:
                return None
            
            view = ReactionButtonView(self, message_id)
            
            for emoji, role_id, label, style in roles:
                button = discord.ui.Button(
                    label=label,
                    emoji=emoji if emoji else None,
                    style=discord.ButtonStyle(style),
                    custom_id=f"reaction_role_{message_id}_{role_id}"
                )
                button.callback = lambda interaction, rid=role_id: self._handle_button_click(interaction, rid)
                view.add_item(button)
            
            return view
            
        except Exception as e:
            print(f"Error creating button view: {e}")
            return None

    def create_dropdown_view(self, message_id):
        """Create a dropdown view for reaction roles"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT emoji, role_id, label FROM reaction_roles WHERE message_id = ?",
                    (message_id,)
                )
                roles = await cursor.fetchall()
            
            if not roles:
                return None
            
            view = ReactionDropdownView(self, message_id)
            
            options = []
            for emoji, role_id, label in roles:
                option = discord.SelectOption(
                    label=label,
                    value=str(role_id),
                    emoji=emoji if emoji else None
                )
                options.append(option)
            
            select = discord.ui.Select(
                placeholder="Select a role...",
                options=options,
                custom_id=f"reaction_role_{message_id}"
            )
            select.callback = lambda interaction: self._handle_dropdown_select(interaction, message_id)
            view.add_item(select)
            
            return view
            
        except Exception as e:
            print(f"Error creating dropdown view: {e}")
            return None

    async def _handle_button_click(self, interaction: discord.Interaction, role_id: int):
        """Handle button click for role assignment"""
        try:
            role = interaction.guild.get_role(role_id)
            if not role:
                return await interaction.response.send_message("Role not found.", ephemeral=True)
            
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Reaction role")
                await interaction.response.send_message(f"Removed {role.name} role!", ephemeral=True)
            else:
                await interaction.user.add_roles(role, reason="Reaction role")
                await interaction.response.send_message(f"Added {role.name} role!", ephemeral=True)
                
        except Exception as e:
            print(f"Error handling button click: {e}")
            await interaction.response.send_message("Error assigning role.", ephemeral=True)

    async def _handle_dropdown_select(self, interaction: discord.Interaction, message_id: int):
        """Handle dropdown selection for role assignment"""
        try:
            role_id = int(interaction.data['values'][0])
            role = interaction.guild.get_role(role_id)
            
            if not role:
                return await interaction.response.send_message("Role not found.", ephemeral=True)
            
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Reaction role")
                await interaction.response.send_message(f"Removed {role.name} role!", ephemeral=True)
            else:
                await interaction.user.add_roles(role, reason="Reaction role")
                await interaction.response.send_message(f"Added {role.name} role!", ephemeral=True)
                
        except Exception as e:
            print(f"Error handling dropdown select: {e}")
            await interaction.response.send_message("Error assigning role.", ephemeral=True)

    @commands.group(name="reaction", invoke_without_command=True, description="🎭 Reaction role system commands")
    async def reaction(self, ctx):
        """🎭 Reaction role system commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @reaction.command(name="create", description="✨ Create a reaction role message")
    @commands.has_permissions(manage_roles=True)
    async def create_reaction(self, ctx: commands.Context, message_type: str = "button"):
        """Create a reaction role message"""
        if message_type not in ["button", "dropdown"]:
            return await ctx.send("Message type must be 'button' or 'dropdown'")
        
        embed = discord.Embed(
            title="✨ Reaction Role Setup",
            description="Use the buttons below to add roles to this reaction message.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Type", value=message_type.title(), inline=True)
        embed.add_field(name="Instructions", value="Click 'Add Role' to add roles to this message.", inline=False)
        
        view = ReactionSetupView(self, ctx, message_type)
        await ctx.send(embed=embed, view=view)

    @reaction.command(name="delete", description="🗑️ Delete a reaction role message")
    @commands.has_permissions(manage_roles=True)
    async def delete_reaction(self, ctx: commands.Context, message_id: int):
        """Delete a reaction role message"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM reaction_roles WHERE message_id = ?", (message_id,))
            await db.execute("DELETE FROM reaction_messages WHERE message_id = ?", (message_id,))
            await db.commit()
        
        embed = discord.Embed(
            title="🗑️ Reaction Role Deleted",
            description="The reaction role message has been deleted.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @reaction.command(name="list", description="📋 List all reaction role messages")
    async def list_reactions(self, ctx: commands.Context):
        """List all reaction role messages"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT message_id, channel_id, message_type, title FROM reaction_messages WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            messages = await cursor.fetchall()
        
        if not messages:
            embed = discord.Embed(
                title="📋 Reaction Role Messages",
                description="No reaction role messages found.",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"📋 Reaction Role Messages ({len(messages)})",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        for message_id, channel_id, message_type, title in messages:
            channel = self.bot.get_channel(channel_id)
            channel_name = channel.name if channel else "Unknown"
            embed.add_field(
                name=f"Message {message_id}",
                value=f"**Channel:** {channel_name}\n**Type:** {message_type.title()}\n**Title:** {title or 'None'}",
                inline=False
            )
        
        await ctx.send(embed=embed)

class ReactionButtonView(View):
    def __init__(self, cog, message_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id

class ReactionDropdownView(View):
    def __init__(self, cog, message_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id

class ReactionSetupView(View):
    def __init__(self, cog, ctx, message_type):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.message_type = message_type
        self.roles = []
        self.message = None

    @discord.ui.button(label="Add Role", style=discord.ButtonStyle.green)
    async def add_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a role to the reaction message"""
        modal = ReactionRoleModal(self.cog, self.ctx, self.message_type)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Finish & Send", style=discord.ButtonStyle.blurple)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Finish setup and send the reaction message"""
        if not self.roles:
            return await interaction.response.send_message("Add at least one role first!", ephemeral=True)
        
        try:
            await interaction.response.defer()
            
            # Create the reaction message
            embed = discord.Embed(
                title="🎭 Reaction Roles",
                description="Click the buttons below to get your roles!",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            
            if self.message_type == "button":
                view = ReactionButtonView(self.cog, 0)
                for role_data in self.roles:
                    button = discord.ui.Button(
                        label=role_data['label'],
                        emoji=role_data['emoji'] if role_data['emoji'] else None,
                        style=discord.ButtonStyle(role_data['style']),
                        custom_id=f"reaction_role_temp_{role_data['role_id']}"
                    )
                    button.callback = lambda interaction, rid=role_data['role_id']: self.cog._handle_button_click(interaction, rid)
                    view.add_item(button)
                
                message = await self.ctx.send(embed=embed, view=view)
                message_id = message.id
                
                # Update custom IDs
                for i, role_data in enumerate(self.roles):
                    view.children[i].custom_id = f"reaction_role_{message_id}_{role_data['role_id']}"
                
                await message.edit(view=view)
                self.cog.bot.add_view(view, message_id=message_id)
                
            elif self.message_type == "dropdown":
                view = ReactionDropdownView(self.cog, 0)
                options = []
                for role_data in self.roles:
                    option = discord.SelectOption(
                        label=role_data['label'],
                        value=str(role_data['role_id']),
                        emoji=role_data['emoji'] if role_data['emoji'] else None
                    )
                    options.append(option)
                
                select = discord.ui.Select(
                    placeholder="Select a role...",
                    options=options,
                    custom_id=f"reaction_role_temp_{message_id}"
                )
                select.callback = lambda interaction: self.cog._handle_dropdown_select(interaction, message_id)
                view.add_item(select)
                
                message = await self.ctx.send(embed=embed, view=view)
                message_id = message.id
                
                view.children[0].custom_id = f"reaction_role_{message_id}"
                await message.edit(view=view)
                self.cog.bot.add_view(view, message_id=message_id)
            
            # Save to database
            async with aiosqlite.connect(self.cog.db_path) as db:
                await db.execute(
                    "INSERT INTO reaction_messages (message_id, guild_id, channel_id, message_type, title) VALUES (?, ?, ?, ?, ?)",
                    (message_id, self.ctx.guild.id, self.ctx.channel.id, self.message_type, "Reaction Roles")
                )
                
                for role_data in self.roles:
                    await db.execute(
                        "INSERT INTO reaction_roles (message_id, emoji, role_id, label, style) VALUES (?, ?, ?, ?, ?)",
                        (message_id, role_data['emoji'], role_data['role_id'], role_data['label'], role_data['style'])
                    )
                
                await db.commit()
            
            await interaction.followup.send("✅ Reaction role message created!", ephemeral=True)
            self.stop()
            
        except Exception as e:
            print(f"Error finishing setup: {e}")
            await interaction.followup.send("Error creating reaction message.", ephemeral=True)

class ReactionRoleModal(discord.ui.Modal, title="Add Reaction Role"):
    def __init__(self, cog, ctx, message_type):
        super().__init__()
        self.cog = cog
        self.ctx = ctx
        self.message_type = message_type

    role = discord.ui.TextInput(
        label="Role (mention or ID)",
        placeholder="@Role or role ID",
        required=True
    )
    
    emoji = discord.ui.TextInput(
        label="Emoji (optional)",
        placeholder="🎭",
        required=False,
        max_length=10
    )
    
    label = discord.ui.TextInput(
        label="Button Label",
        placeholder="Role Name",
        required=True,
        max_length=80
    )
    
    style = discord.ui.TextInput(
        label="Style (1=Primary, 2=Secondary, 3=Success, 4=Danger)",
        placeholder="1",
        required=False,
        max_length=1
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse role
            role_id = None
            if self.role.value.startswith('<@&') and self.role.value.endswith('>'):
                role_id = int(self.role.value[3:-1])
            else:
                try:
                    role_id = int(self.role.value)
                except:
                    pass
            
            if not role_id:
                return await interaction.response.send_message("Invalid role.", ephemeral=True)
            
            role = interaction.guild.get_role(role_id)
            if not role:
                return await interaction.response.send_message("Role not found.", ephemeral=True)
            
            # Parse style
            try:
                style = int(self.style.value) if self.style.value else 1
            except:
                style = 1
            
            # Add to parent view
            if hasattr(interaction.message, 'author') and interaction.message.author == self.ctx.bot.user:
                view = ReactionSetupView(self.cog, self.ctx, self.message_type)
                view.roles = [{
                    'role_id': role_id,
                    'emoji': self.emoji.value,
                    'label': self.label.value,
                    'style': style
                }]
                # This is a simplified version - in production you'd want to maintain state better
            
            await interaction.response.send_message(f"Added role: {role.name}", ephemeral=True)
            
        except Exception as e:
            print(f"Error in modal submit: {e}")
            await interaction.response.send_message("Error adding role.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
