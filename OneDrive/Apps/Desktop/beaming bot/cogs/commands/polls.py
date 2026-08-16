import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
import aiosqlite
from typing import Optional

class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/polls.db"

    async def cog_load(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS polls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    message_id INTEGER,
                    question TEXT,
                    options TEXT,
                    votes TEXT,
                    author_id INTEGER,
                    created_at TIMESTAMP
                )
            """)
            await db.commit()

    @app_commands.command(name="poll", description="📊 Create a poll with up to 5 options")
    @app_commands.describe(question="The poll question", option1="Option 1", option2="Option 2", option3="Option 3", option4="Option 4", option5="Option 5")
    async def poll(self, interaction: discord.Interaction, question: str, option1: str, option2: str, option3: Optional[str] = None, option4: Optional[str] = None, option5: Optional[str] = None):
        options = [opt for opt in [option1, option2, option3, option4, option5] if opt is not None]
        
        if len(options) < 2:
            return await interaction.response.send_message("At least 2 options are required.", ephemeral=True)
        if len(options) > 5:
            return await interaction.response.send_message("Maximum 5 options allowed.", ephemeral=True)

        class PollView(View):
            def __init__(self, options, question, author_id, bot):
                super().__init__(timeout=None)
                self.options = options
                self.question = question
                self.author_id = author_id
                self.bot = bot
                self.votes = {i: 0 for i in range(len(options))}
                self.voted_users = set()

                emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
                for i, option in enumerate(options):
                    button = Button(
                        label=option[:20],
                        emoji=emojis[i],
                        style=discord.ButtonStyle.secondary,
                        custom_id=f"poll_{i}"
                    )
                    button.callback = lambda b, idx=i: self.vote_callback(b, idx)
                    self.add_item(button)

            async def vote_callback(self, interaction: discord.Interaction, index: int):
                user_id = interaction.user.id
                
                if user_id in self.voted_users:
                    return await interaction.response.send_message("You have already voted in this poll.", ephemeral=True)
                
                self.votes[index] += 1
                self.voted_users.add(user_id)
                
                # Update the embed with new vote counts
                embed = self.create_embed()
                await interaction.message.edit(embed=embed)
                
                # Save to database
                async with aiosqlite.connect("db/polls.db") as db:
                    votes_str = ",".join(str(self.votes[i]) for i in range(len(self.options)))
                    await db.execute(
                        "UPDATE polls SET votes = ? WHERE message_id = ?",
                        (votes_str, interaction.message.id)
                    )
                    await db.commit()
                
                await interaction.response.send_message("Vote recorded!", ephemeral=True)

            def create_embed(self):
                emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
                total_votes = sum(self.votes.values())
                
                embed = discord.Embed(
                    title=f"📊 {self.question}",
                    color=0x00ff00
                )
                embed.set_footer(text=f"Total votes: {total_votes} | Created by: {self.bot.get_user(self.author_id)}")
                
                for i, option in enumerate(self.options):
                    votes = self.votes[i]
                    percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                    bar = "█" * int(percentage / 10) if percentage > 0 else "░"
                    embed.add_field(
                        name=f"{emojis[i]} {option}",
                        value=f"{votes} votes ({percentage:.1f}%) {bar}",
                        inline=False
                    )
                
                return embed

        view = PollView(options, question, interaction.user.id, self.bot)
        embed = view.create_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        
        # Save poll to database
        message = await interaction.original_response()
        options_str = "|".join(options)
        votes_str = ",".join("0" for _ in options)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO polls (guild_id, channel_id, message_id, question, options, votes, author_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (interaction.guild_id, interaction.channel_id, message.id, question, options_str, votes_str, interaction.user.id, discord.utils.utcnow())
            )
            await db.commit()

    @app_commands.command(name="endpoll", description="⏹️ End a poll and show final results")
    @app_commands.describe(message_id="Message ID of the poll to end")
    @commands.has_permissions(manage_messages=True)
    async def endpoll(self, interaction: discord.Interaction, message_id: str):
        try:
            msg_id = int(message_id)
        except ValueError:
            return await interaction.response.send_message("Invalid message ID.", ephemeral=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT question, options, votes FROM polls WHERE guild_id = ? AND message_id = ?",
                (interaction.guild_id, msg_id)
            )
            row = await cursor.fetchone()
            
            if not row:
                return await interaction.response.send_message("Poll not found.", ephemeral=True)
            
            question, options_str, votes_str = row
            options = options_str.split("|")
            votes = [int(v) for v in votes_str.split(",")]
        
        try:
            message = await interaction.channel.fetch_message(msg_id)
            
            emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            total_votes = sum(votes)
            
            embed = discord.Embed(
                title=f"📊 {question} (ENDED)",
                color=0xff0000
            )
            embed.set_footer(text=f"Total votes: {total_votes}")
            
            for i, option in enumerate(options):
                vote_count = votes[i]
                percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
                bar = "█" * int(percentage / 10) if percentage > 0 else "░"
                embed.add_field(
                    name=f"{emojis[i]} {option}",
                    value=f"{vote_count} votes ({percentage:.1f}%) {bar}",
                    inline=False
                )
            
            await message.edit(embed=embed, view=None)
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM polls WHERE message_id = ?",
                    (msg_id,)
                )
                await db.commit()
            
            await interaction.response.send_message("Poll ended.", ephemeral=True)
            
        except discord.NotFound:
            await interaction.response.send_message("Message not found.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="pollstats", description="📈 View poll statistics for active polls")
    @commands.has_permissions(manage_guild=True)
    async def pollstats(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*), SUM(CAST(votes as INTEGER)) FROM polls WHERE guild_id = ?",
                (interaction.guild_id,)
            )
            row = await cursor.fetchone()
            
            total_polls = row[0] or 0
            total_votes = row[1] or 0
        
        embed = discord.Embed(
            title="📊 Poll Statistics",
            color=0x00ff00
        )
        embed.add_field(name="Active Polls", value=total_polls, inline=True)
        embed.add_field(name="Total Votes Cast", value=total_votes, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Polls(bot))
