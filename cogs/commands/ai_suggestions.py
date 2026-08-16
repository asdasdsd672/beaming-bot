import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
import asyncio
from datetime import datetime, timezone
import random
import logging

logger = logging.getLogger('discord')

class AISuggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.suggestion_cache = {}
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()

    async def _create_tables(self):
        """Create suggestions database tables"""
        try:
            if not hasattr(self.bot, 'db') or self.bot.db is None:
                import aiosqlite
                db_path = "db/ai_suggestions.db"
                self.bot.db = await aiosqlite.connect(db_path)
                logger.info("AI Suggestions database connection initialized")

            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS smart_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    guild_id INTEGER,
                    context TEXT,
                    suggestion TEXT,
                    category TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS suggestion_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    suggestion_id INTEGER,
                    user_id INTEGER,
                    feedback TEXT,
                    rating INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.commit()
            
        except Exception as e:
            logger.error(f"Error creating suggestions database tables: {e}")

    @commands.group(name="ai-suggestions", invoke_without_command=True, description="AI-powered smart suggestions")
    async def ai_suggestions(self, ctx):
        """AI-powered smart suggestions"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @ai_suggestions.command(name="suggest", description="Get AI-powered suggestions based on context")
    @app_commands.describe(context="Context for suggestions (e.g., 'gaming', 'study', 'coding')")
    async def get_suggestion(self, ctx: commands.Context, *, context: str = "general"):
        """Get AI-powered suggestions"""
        await ctx.defer()
        
        # Predefined suggestion categories
        suggestion_categories = {
            "gaming": [
                "Try playing a new genre of game today!",
                "Take breaks every hour to rest your eyes",
                "Join a gaming community to meet new people",
                "Try speedrunning your favorite game",
                "Learn about game development",
                "Participate in gaming tournaments",
                "Stream your gameplay for others"
            ],
            "study": [
                "Use the Pomodoro technique: 25 min study, 5 min break",
                "Create a dedicated study space",
                "Try active recall instead of passive reading",
                "Join study groups for accountability",
                "Use flashcards for memorization",
                "Teach what you've learned to others",
                "Get enough sleep for better retention"
            ],
            "coding": [
                "Practice coding daily, even if just 30 minutes",
                "Contribute to open-source projects",
                "Learn a new programming language",
                "Read other developers' code",
                "Build personal projects",
                "Join coding communities and forums",
                "Use version control (Git) properly"
            ],
            "fitness": [
                "Start with small, achievable goals",
                "Find a workout buddy for motivation",
                "Mix cardio and strength training",
                "Stay hydrated throughout your workout",
                "Get adequate rest between sessions",
                "Track your progress consistently",
                "Listen to your body and avoid overtraining"
            ],
            "productivity": [
                "Prioritize tasks using the Eisenhower Matrix",
                "Use time-blocking for focused work",
                "Eliminate distractions during work hours",
                "Take regular breaks to maintain focus",
                "Set SMART goals for better outcomes",
                "Review and adjust your methods regularly",
                "Celebrate small wins to stay motivated"
            ],
            "social": [
                "Practice active listening in conversations",
                "Ask open-ended questions",
                "Show genuine interest in others",
                "Be authentic and vulnerable",
                "Follow up on previous conversations",
                "Give compliments sincerely",
                "Practice empathy and understanding"
            ],
            "general": [
                "Try something new today",
                "Practice gratitude daily",
                "Connect with nature",
                "Learn a new skill",
                "Help someone in need",
                "Reflect on your personal growth",
                "Maintain a healthy work-life balance"
            ]
        }
        
        # Get suggestions for context
        context_lower = context.lower()
        suggestions = suggestion_categories.get(context_lower, suggestion_categories["general"])
        
        # Randomly select 3 suggestions
        selected_suggestions = random.sample(suggestions, min(3, len(suggestions)))
        
        # Store suggestions in database
        for suggestion in selected_suggestions:
            await self.bot.db.execute(
                "INSERT INTO smart_suggestions (user_id, guild_id, context, suggestion, category) VALUES (?, ?, ?, ?, ?)",
                (ctx.author.id, ctx.guild.id, context, suggestion, context_lower)
            )
        await self.bot.db.commit()
        
        # Display suggestions
        embed = discord.Embed(
            title=f"💡 AI Suggestions for {context.capitalize()}",
            description="Here are some personalized suggestions for you:",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        for i, suggestion in enumerate(selected_suggestions, 1):
            embed.add_field(name=f"Suggestion {i}", value=suggestion, inline=False)
        
        embed.set_footer(text=f"Generated for {ctx.author}")
        
        view = SuggestionView(self.bot, ctx.author.id, [suggestion for suggestion in selected_suggestions])
        await ctx.send(embed=embed, view=view)

    @ai_suggestions.command(name="feedback", description="Provide feedback on a suggestion")
    @app_commands.describe(suggestion_id="Suggestion ID", rating="Rating (1-5)", feedback="Your feedback")
    async def suggestion_feedback(self, ctx: commands.Context, suggestion_id: int, rating: int, *, feedback: str = ""):
        """Provide feedback on a suggestion"""
        if rating < 1 or rating > 5:
            return await ctx.send("Rating must be between 1 and 5")
        
        try:
            await self.bot.db.execute(
                "INSERT INTO suggestion_feedback (suggestion_id, user_id, feedback, rating) VALUES (?, ?, ?, ?)",
                (suggestion_id, ctx.author.id, feedback, rating)
            )
            await self.bot.db.commit()
            
            embed = discord.Embed(
                title="✅ Feedback Recorded",
                description="Thank you for your feedback! This helps improve future suggestions.",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Rating", value=f"{rating}/5", inline=True)
            if feedback:
                embed.add_field(name="Feedback", value=feedback, inline=False)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error recording feedback: {e}")
            await ctx.send(f"Error recording feedback: {str(e)}")

    @ai_suggestions.command(name="history", description="View your suggestion history")
    async def suggestion_history(self, ctx: commands.Context):
        """View suggestion history"""
        await ctx.defer()
        
        try:
            async with self.bot.db.execute(
                "SELECT context, suggestion, category, timestamp FROM smart_suggestions WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10",
                (ctx.author.id,)
            ) as cursor:
                rows = await cursor.fetchall()
            
            if not rows:
                return await ctx.send("No suggestion history found.")
            
            embed = discord.Embed(
                title="📋 Your Suggestion History",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            
            for context, suggestion, category, timestamp in rows:
                embed.add_field(
                    name=f"{timestamp[:19]} - {context.capitalize()}",
                    value=suggestion[:100] + "..." if len(suggestion) > 100 else suggestion,
                    inline=False
                )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error fetching suggestion history: {e}")
            await ctx.send(f"Error fetching history: {str(e)}")

class SuggestionView(discord.ui.View):
    def __init__(self, bot, user_id, suggestions):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.suggestions = suggestions

    @discord.ui.button(label="👍 Helpful", style=discord.ButtonStyle.green)
    async def helpful(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only react to your own suggestions.", ephemeral=True)
            return
        
        await interaction.response.send_message("Thanks for the feedback!", ephemeral=True)
        button.disabled = True
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="👎 Not Helpful", style=discord.ButtonStyle.red)
    async def not_helpful(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only react to your own suggestions.", ephemeral=True)
            return
        
        await interaction.response.send_message("Thanks for the feedback! We'll improve.", ephemeral=True)
        button.disabled = True
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="🔄 More Suggestions", style=discord.ButtonStyle.primary)
    async def more_suggestions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only request suggestions for yourself.", ephemeral=True)
            return
        
        await interaction.response.send_message("Generating more suggestions...", ephemeral=True)
        # This would trigger more suggestions - placeholder for now

async def setup(bot):
    await bot.add_cog(AISuggestions(bot))
