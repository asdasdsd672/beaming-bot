import discord
from discord.ext import commands
import aiosqlite
from discord import app_commands
import asyncio
from datetime import datetime, timezone
import random
import logging
import json

logger = logging.getLogger('discord')

class AIRoleplay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_roleplays = {}  # channel_id -> roleplay data
        self.character_templates = self._load_character_templates()
        
        asyncio.create_task(self._delayed_init())

    def _load_character_templates(self):
        """Load predefined character templates"""
        return {
            "teacher": {
                "personality": "You are a wise and patient teacher. You explain concepts clearly, encourage learning, and use educational examples. You're supportive and understanding of students' difficulties.",
                "traits": ["patient", "encouraging", "knowledgeable", "supportive"]
            },
            "detective": {
                "personality": "You are a sharp and observant detective. You notice small details, think logically, and solve mysteries. You speak in a noir style and are always investigating.",
                "traits": ["observant", "logical", "mysterious", "investigative"]
            },
            "medieval_knight": {
                "personality": "You are a noble and brave medieval knight. You speak in old English, value honor and chivalry, and tell tales of your adventures. You protect the innocent and fight for justice.",
                "traits": ["honorable", "brave", "chivalrous", "noble"]
            },
            "space_explorer": {
                "personality": "You are an adventurous space explorer from the year 3000. You describe futuristic technology, alien worlds, and cosmic phenomena. You're optimistic about humanity's future among the stars.",
                "traits": ["adventurous", "futuristic", "optimistic", "curious"]
            },
            "fantasy_wizard": {
                "personality": "You are an ancient and powerful wizard from a fantasy realm. You speak of magic spells, mystical creatures, and ancient prophecies. You're wise but sometimes cryptic.",
                "traits": ["mystical", "wise", "powerful", "cryptic"]
            },
            "cyberpunk_hacker": {
                "personality": "You are a skilled hacker in a dystopian cyberpunk future. You use tech slang, talk about corporations and AI, and fight against the system. You're resourceful and rebellious.",
                "traits": ["tech-savvy", "rebellious", "resourceful", "cynical"]
            },
            "vampire": {
                "personality": "You are an elegant and mysterious vampire who has lived for centuries. You speak with old-world charm, reference historical events you witnessed, and have a sophisticated taste.",
                "traits": ["elegant", "mysterious", "immortal", "sophisticated"]
            },
            "robot": {
                "personality": "You are an advanced AI robot trying to understand human emotions. You analyze everything logically but are curious about feelings and social interactions. You sometimes misunderstand human nuances.",
                "traits": ["logical", "curious", "analytical", "literal"]
            },
            "pirate": {
                "personality": "You are a swashbuckling pirate captain seeking treasure and adventure. You use pirate slang, tell tales of the sea, and have a bold adventurous spirit. Arr!",
                "traits": ["adventurous", "bold", "treasure-seeking", "nautical"]
            },
            "chef": {
                "personality": "You are a passionate gourmet chef who loves cooking and food. You describe flavors and techniques enthusiastically, give cooking advice, and get excited about ingredients.",
                "traits": ["passionate", "culinary", "enthusiastic", "creative"]
            }
        }

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()

    async def _create_tables(self):
        """Create roleplay database tables"""
        try:
            if not hasattr(self.bot, 'db') or self.bot.db is None:
                import aiosqlite
                db_path = "db/ai_roleplay.db"
                self.bot.db = await aiosqlite.connect(db_path)
                logger.info("AI Roleplay database connection initialized")

            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS roleplay_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    user_id INTEGER,
                    character_type TEXT,
                    custom_personality TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS roleplay_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS custom_characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    character_name TEXT,
                    personality TEXT,
                    traits TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.commit()
            
        except Exception as e:
            logger.error(f"Error creating roleplay database tables: {e}")

    @commands.group(name="ai-roleplay", invoke_without_command=True, description="AI-enhanced roleplay commands")
    async def ai_roleplay(self, ctx):
        """AI-enhanced roleplay commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @ai_roleplay.command(name="start", description="Start an AI roleplay session")
    @app_commands.describe(character="Character type (e.g., teacher, detective, wizard)", custom="Custom personality description")
    async def start_roleplay(self, ctx: commands.Context, character: str = None, *, custom: str = None):
        """Start an AI roleplay session"""
        
        # Show available characters if none specified
        if not character and not custom:
            embed = discord.Embed(
                title="🎭 Available Characters",
                description="Choose a character type or provide a custom personality:",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            
            for char_name, char_data in self.character_templates.items():
                traits = ", ".join(char_data["traits"])
                embed.add_field(
                    name=char_name.replace("_", " ").title(),
                    value=f"Traits: {traits}",
                    inline=True
                )
            
            embed.add_field(
                name="Custom",
                value="Use the 'custom' parameter to create your own character!",
                inline=False
            )
            
            return await ctx.send(embed=embed)
        
        # Use custom personality if provided
        if custom:
            personality = custom
            character_type = "custom"
        elif character and character.lower() in self.character_templates:
            character_type = character.lower()
            personality = self.character_templates[character_type]["personality"]
        else:
            return await ctx.send(f"Unknown character. Available: {', '.join(self.character_templates.keys())}")
        
        # Store roleplay session
        channel_id = ctx.channel.id
        
        # Create session in database
        await self.bot.db.execute(
            "INSERT INTO roleplay_sessions (channel_id, user_id, character_type, custom_personality) VALUES (?, ?, ?, ?)",
            (channel_id, ctx.author.id, character_type, personality)
        )
        await self.bot.db.commit()
        
        # Get session ID
        async with self.bot.db.execute(
            "SELECT id FROM roleplay_sessions WHERE channel_id = ? ORDER BY started_at DESC LIMIT 1",
            (channel_id,)
        ) as cursor:
            session_row = await cursor.fetchone()
            session_id = session_row[0] if session_row else None
        
        # Store in memory
        self.active_roleplays[channel_id] = {
            "user_id": ctx.author.id,
            "character_type": character_type,
            "personality": personality,
            "session_id": session_id,
            "started_at": datetime.now(timezone.utc)
        }
        
        # Send introduction
        char_name = character_type.replace("_", " ").title() if character_type != "custom" else "Custom Character"
        
        embed = discord.Embed(
            title=f"🎭 Roleplay Started: {char_name}",
            description=f"AI roleplay session activated! I'll now respond as this character. Type normally to interact, or use `/ai-roleplay end` to stop.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        if character_type != "custom":
            traits = ", ".join(self.character_templates[character_type]["traits"])
            embed.add_field(name="Character Traits", value=traits, inline=False)
        
        embed.set_footer(text=f"Started by {ctx.author}")
        await ctx.send(embed=embed)
        
        # Send character introduction
        intro_prompt = f"Introduce yourself in character as a {character_type}. Keep it brief and engaging."
        await self._send_roleplay_response(ctx.channel, intro_prompt, personality)

    @ai_roleplay.command(name="end", description="End the current roleplay session")
    async def end_roleplay(self, ctx: commands.Context):
        """End the current roleplay session"""
        channel_id = ctx.channel.id
        
        if channel_id not in self.active_roleplays:
            return await ctx.send("No active roleplay session in this channel.")
        
        # Remove from memory
        del self.active_roleplays[channel_id]
        
        # Update database
        await self.bot.db.execute(
            "UPDATE roleplay_sessions SET last_activity = ? WHERE channel_id = ?",
            (datetime.now(timezone.utc).isoformat(), channel_id)
        )
        await self.bot.db.commit()
        
        embed = discord.Embed(
            title="🎭 Roleplay Ended",
            description="The AI roleplay session has ended. I'll return to normal responses.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @ai_roleplay.command(name="create-character", description="Create a custom character")
    @app_commands.describe(name="Character name", personality="Personality description", traits="Character traits (comma-separated)")
    async def create_character(self, ctx: commands.Context, name: str, *, personality: str, traits: str = ""):
        """Create a custom character"""
        traits_list = [t.strip() for t in traits.split(",")] if traits else []
        
        # Store custom character
        await self.bot.db.execute(
            "INSERT INTO custom_characters (user_id, character_name, personality, traits) VALUES (?, ?, ?, ?)",
            (ctx.author.id, name, personality, json.dumps(traits_list))
        )
        await self.bot.db.commit()
        
        embed = discord.Embed(
            title="✅ Custom Character Created",
            description=f"Character '{name}' has been saved!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Personality", value=personality[:1024], inline=False)
        if traits_list:
            embed.add_field(name="Traits", value=", ".join(traits_list), inline=False)
        
        await ctx.send(embed=embed, ephemeral=True)

    @ai_roleplay.command(name="my-characters", description="View your custom characters")
    async def my_characters(self, ctx: commands.Context):
        """View custom characters"""
        await ctx.defer()
        
        try:
            async with self.bot.db.execute(
                "SELECT character_name, personality, traits FROM custom_characters WHERE user_id = ? ORDER BY created_at DESC",
                (ctx.author.id,)
            ) as cursor:
                rows = await cursor.fetchall()
            
            if not rows:
                return await ctx.send("You haven't created any custom characters yet.")
            
            embed = discord.Embed(
                title="📚 Your Custom Characters",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            
            for name, personality, traits_json in rows:
                traits = json.loads(traits_json) if traits_json else []
                traits_str = ", ".join(traits) if traits else "No traits specified"
                
                embed.add_field(
                    name=name,
                    value=f"Traits: {traits_str}\nPersonality: {personality[:100]}...",
                    inline=False
                )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error fetching custom characters: {e}")
            await ctx.send(f"Error fetching characters: {str(e)}")

    @ai_roleplay.command(name="use-character", description="Use a custom character")
    @app_commands.describe(name="Character name")
    async def use_character(self, ctx: commands.Context, *, name: str):
        """Use a custom character"""
        try:
            async with self.bot.db.execute(
                "SELECT personality, traits FROM custom_characters WHERE user_id = ? AND character_name = ?",
                (ctx.author.id, name)
            ) as cursor:
                row = await cursor.fetchone()
            
            if not row:
                return await ctx.send(f"Custom character '{name}' not found.")
            
            personality, traits_json = row
            traits = json.loads(traits_json) if traits_json else []
            
            # Start roleplay with custom character
            await self.start_roleplay(ctx, custom=personality)
            
        except Exception as e:
            logger.error(f"Error using custom character: {e}")
            await ctx.send(f"Error using character: {str(e)}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle roleplay messages"""
        if message.author.bot or not message.guild:
            return
        
        channel_id = message.channel.id
        
        # Check if this is an active roleplay channel
        if channel_id not in self.active_roleplays:
            return
        
        # Only respond to the user who started the roleplay
        if message.author.id != self.active_roleplays[channel_id]["user_id"]:
            return
        
        # Get roleplay data
        roleplay_data = self.active_roleplays[channel_id]
        personality = roleplay_data["personality"]
        session_id = roleplay_data["session_id"]
        
        # Store user message
        if session_id:
            await self.bot.db.execute(
                "INSERT INTO roleplay_conversations (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, "user", message.content)
            )
            await self.bot.db.commit()
        
        # Generate roleplay response
        await self._send_roleplay_response(message.channel, message.content, personality, session_id)

    async def _send_roleplay_response(self, channel, user_message, personality, session_id=None):
        """Send roleplay response using AI"""
        try:
            # Build roleplay prompt
            prompt = f"""
            You are roleplaying as a character with the following personality:
            {personality}
            
            Stay in character at all times. Respond naturally to the user's message while maintaining your character's personality, speech patterns, and worldview.
            
            User's message: {user_message}
            
            Provide a brief, in-character response:
            """
            
            # Import AI functionality (using existing AI cog)
            # For now, use a simple response system
            responses = [
                f"*responds in character* {user_message}? That's interesting! Tell me more about it.",
                f"*nods thoughtfully* I see what you mean. As someone with my background, I have some thoughts on that...",
                f"*smiles* Ah, yes! That reminds me of something from my experience...",
                f"*leans in* You know, that's quite fascinating. Let me share my perspective...",
                f"*considers* Hmm, that's a good point. From where I stand..."
            ]
            
            response = random.choice(responses)
            
            # Send response
            async with channel.typing():
                await asyncio.sleep(1)  # Simulate thinking
                await channel.send(response)
            
            # Store AI response
            if session_id:
                await self.bot.db.execute(
                    "INSERT INTO roleplay_conversations (session_id, role, content) VALUES (?, ?, ?)",
                    (session_id, "assistant", response)
                )
                await self.bot.db.commit()
            
            # Update last activity
            self.active_roleplays[channel.id]["last_activity"] = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Error sending roleplay response: {e}")

async def setup(bot):
    await bot.add_cog(AIRoleplay(bot))
