import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import aiosqlite
import asyncio
from typing import Optional, List
from datetime import datetime
import csv
import io

class Application(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/applications.db"

    async def cog_load(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    application_name TEXT,
                    answers TEXT,
                    status TEXT DEFAULT 'pending',
                    submitted_at TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    reviewer_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS application_forms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    name TEXT UNIQUE,
                    questions TEXT,
                    channel_id INTEGER,
                    category_id INTEGER
                )
            """)
            await db.commit()

    @app_commands.command(name="createapplication", description="📋 Create a new application form")
    @app_commands.describe(name="Name of the application form", questions="Questions separated by | (max 10)")
    @commands.has_permissions(administrator=True)
    async def createapplication(self, interaction: discord.Interaction, name: str, questions: str):
        question_list = [q.strip() for q in questions.split("|") if q.strip()]
        if len(question_list) > 10:
            return await interaction.response.send_message("Maximum 10 questions allowed.", ephemeral=True)
        if len(question_list) < 1:
            return await interaction.response.send_message("At least 1 question required.", ephemeral=True)

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO application_forms (guild_id, name, questions) VALUES (?, ?, ?)",
                    (interaction.guild_id, name, "|".join(question_list))
                )
                await db.commit()
            except aiosqlite.IntegrityError:
                return await interaction.response.send_message("An application with this name already exists.", ephemeral=True)

        embed = discord.Embed(
            title=f"✅ Application Form Created",
            description=f"**Name:** {name}\n**Questions:** {len(question_list)}",
            color=0x00ff00
        )
        for i, q in enumerate(question_list, 1):
            embed.add_field(name=f"Question {i}", value=q, inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="apply", description="✍️ Submit an application using an application form")
    @app_commands.describe(name="Name of the application form to apply for")
    async def apply(self, interaction: discord.Interaction, name: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT questions FROM application_forms WHERE guild_id = ? AND name = ?",
                (interaction.guild_id, name)
            )
            row = await cursor.fetchone()
            if not row:
                return await interaction.response.send_message("Application form not found.", ephemeral=True)
        
        questions = row[0].split("|")
        
        class ApplicationModal(Modal, title=f"{name} Application"):
            def __init__(self, questions):
                super().__init__()
                for i, q in enumerate(questions):
                    self.add_item(TextInput(label=f"Q{i+1}: {q[:50]}...", style=discord.TextStyle.paragraph, required=True))

        try:
            modal = ApplicationModal(questions)
            await interaction.response.send_modal(modal)
        except Exception as e:
            await interaction.response.send_message(f"Error creating modal: {e}", ephemeral=True)

    @app_commands.command(name="setapplicationchannel", description="📢 Set the application channel for application submissions")
    @app_commands.describe(channel="Channel where applications will be sent")
    @commands.has_permissions(administrator=True)
    async def setapplicationchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE application_forms SET channel_id = ? WHERE guild_id = ?",
                (channel.id, interaction.guild_id)
            )
            await db.commit()
        
        await interaction.response.send_message(f"Application channel set to {channel.mention}", ephemeral=True)

    @app_commands.command(name="setapplicationcategory", description="📁 Set the category for accepted applications")
    @app_commands.describe(category="Category where accepted applications are posted")
    @commands.has_permissions(administrator=True)
    async def setapplicationcategory(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE application_forms SET category_id = ? WHERE guild_id = ?",
                (category.id, interaction.guild_id)
            )
            await db.commit()
        
        await interaction.response.send_message(f"Application category set to {category.name}", ephemeral=True)

    @app_commands.command(name="reviewapplication", description="👀 Review pending applications")
    @app_commands.describe(user="User to review application for")
    @commands.has_permissions(administrator=True)
    async def reviewapplication(self, interaction: discord.Interaction, user: discord.User):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, application_name, answers, submitted_at FROM applications WHERE guild_id = ? AND user_id = ? AND status = 'pending'",
                (interaction.guild_id, user.id)
            )
            row = await cursor.fetchone()
        
        if not row:
            return await interaction.response.send_message("No pending application found for this user.", ephemeral=True)
        
        app_id, app_name, answers, submitted_at = row
        answer_list = answers.split("|")
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT questions FROM application_forms WHERE guild_id = ? AND name = ?",
                (interaction.guild_id, app_name)
            )
            row = await cursor.fetchone()
            questions = row[0].split("|") if row else ["Question"]
        
        embed = discord.Embed(
            title=f"Application: {app_name}",
            description=f"**User:** {user.mention}\n**Submitted:** {submitted_at}",
            color=0xffff00
        )
        
        for i, (q, a) in enumerate(zip(questions, answer_list)):
            embed.add_field(name=q, value=a or "No answer", inline=False)
        
        class ReviewView(View):
            def __init__(self, app_id, user_id, bot):
                super().__init__(timeout=None)
                self.app_id = app_id
                self.user_id = user_id
                self.bot = bot

            @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
            async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
                async with aiosqlite.connect("db/applications.db") as db:
                    await db.execute(
                        "UPDATE applications SET status = 'accepted', reviewed_at = ?, reviewer_id = ? WHERE id = ?",
                        (datetime.now(), interaction.user.id, self.app_id)
                    )
                    await db.commit()
                
                await interaction.response.send_message(f"Application from <@{self.user_id}> has been accepted.", ephemeral=True)

            @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.red)
            async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
                async with aiosqlite.connect("db/applications.db") as db:
                    await db.execute(
                        "UPDATE applications SET status = 'denied', reviewed_at = ?, reviewer_id = ? WHERE id = ?",
                        (datetime.now(), interaction.user.id, self.app_id)
                    )
                    await db.commit()
                
                await interaction.response.send_message(f"Application from <@{self.user_id}> has been denied.", ephemeral=True)

            @discord.ui.button(label="⏸️ Hold", style=discord.ButtonStyle.blurple)
            async def hold(self, interaction: discord.Interaction, button: discord.ui.Button):
                async with aiosqlite.connect("db/applications.db") as db:
                    await db.execute(
                        "UPDATE applications SET status = 'hold', reviewed_at = ?, reviewer_id = ? WHERE id = ?",
                        (datetime.now(), interaction.user.id, self.app_id)
                    )
                    await db.commit()
                
                await interaction.response.send_message(f"Application from <@{self.user_id}> has been put on hold.", ephemeral=True)

        view = ReviewView(app_id, user.id, self.bot)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="exportapplications", description="📤 Export applications to CSV")
    @commands.has_permissions(administrator=True)
    async def exportapplications(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id, application_name, answers, status, submitted_at, reviewed_at FROM applications WHERE guild_id = ?",
                (interaction.guild_id,)
            )
            rows = await cursor.fetchall()
        
        if not rows:
            return await interaction.response.send_message("No applications to export.", ephemeral=True)
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["User ID", "Application Name", "Answers", "Status", "Submitted At", "Reviewed At"])
        
        for row in rows:
            writer.writerow(row)
        
        output.seek(0)
        file = discord.File(io.BytesIO(output.getvalue().encode()), filename="applications.csv")
        
        await interaction.response.send_message("Here is the CSV export:", file=file, ephemeral=True)

    @app_commands.command(name="listapplications", description="📚 List all application forms")
    @commands.has_permissions(administrator=True)
    async def listapplications(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT name, questions FROM application_forms WHERE guild_id = ?",
                (interaction.guild_id,)
            )
            rows = await cursor.fetchall()
        
        if not rows:
            return await interaction.response.send_message("No application forms found.", ephemeral=True)
        
        embed = discord.Embed(title="Application Forms", color=0x00ff00)
        
        for name, questions in rows:
            question_count = len(questions.split("|"))
            embed.add_field(name=name, value=f"{question_count} questions", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="deleteapplication", description="🗑️ Delete an application form")
    @app_commands.describe(name="Name of the application form to delete")
    @commands.has_permissions(administrator=True)
    async def deleteapplication(self, interaction: discord.Interaction, name: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM application_forms WHERE guild_id = ? AND name = ?",
                (interaction.guild_id, name)
            )
            await db.commit()
        
        if cursor.rowcount == 0:
            return await interaction.response.send_message("Application form not found.", ephemeral=True)
        
        await interaction.response.send_message(f"Application form '{name}' has been deleted.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Application(bot))
