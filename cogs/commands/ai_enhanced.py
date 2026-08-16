import os
import discord
import aiosqlite
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from discord import app_commands
import random
import aiohttp
import logging
import io
from PIL import Image
import json
import re

logger = logging.getLogger('discord')
logger.setLevel(logging.WARNING)

class AIModel:
    """AI Model Configuration"""
    def __init__(self, name: str, api_endpoint: str, requires_key: bool, default_temp: float = 0.7):
        self.name = name
        self.api_endpoint = api_endpoint
        self.requires_key = requires_key
        self.default_temp = default_temp

class ConversationMode:
    """AI Conversation Modes"""
    CREATIVE = "creative"
    BALANCED = "balanced"
    PRECISE = "precise"
    
    @staticmethod
    def get_settings(mode: str) -> dict:
        settings = {
            "creative": {"temperature": 0.9, "top_p": 0.95, "max_tokens": 2000},
            "balanced": {"temperature": 0.7, "top_p": 0.9, "max_tokens": 1500},
            "precise": {"temperature": 0.3, "top_p": 0.8, "max_tokens": 1000}
        }
        return settings.get(mode.lower(), settings["balanced"])

class EnhancedAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_keys = {
            "openai": os.getenv("OPENAI_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
            "cohere": os.getenv("COHERE_API_KEY"),
            "groq": os.getenv("GROQ_API_KEY"),
            "gemini": os.getenv("GOOGLE_API_KEY"),
            "huggingface": os.getenv("HUGGINGFACE_API_KEY")
        }
        
        self.available_models = {
            "gpt-4": AIModel("GPT-4", "https://api.openai.com/v1/chat/completions", True, 0.7),
            "gpt-3.5-turbo": AIModel("GPT-3.5 Turbo", "https://api.openai.com/v1/chat/completions", True, 0.7),
            "claude-3-opus": AIModel("Claude 3 Opus", "https://api.anthropic.com/v1/messages", True, 0.7),
            "claude-3-sonnet": AIModel("Claude 3 Sonnet", "https://api.anthropic.com/v1/messages", True, 0.7),
            "command": AIModel("Cohere Command", "https://api.cohere.ai/v1/chat", True, 0.7),
            "llama-3-70b": AIModel("Llama 3 70B", "https://api.groq.com/openai/v1/chat/completions", True, 0.7),
            "gemini-pro": AIModel("Gemini Pro", "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent", True, 0.7),
        }
        
        self.user_settings = {}  # user_id -> {model, mode, personality}
        self.conversation_memory = {}  # user_id -> list of messages
        self.active_streams = {}  # message_id -> stream task
        
        asyncio.create_task(self._delayed_init())

    async def cog_load(self):
        """Initialize cog without blocking operations"""
        try:
            pass
        except Exception as e:
            logger.error(f"Error loading Enhanced AI cog: {e}")

    async def _delayed_init(self):
        """Initialize database and load data after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()
        await self._load_user_settings()

    async def _create_tables(self):
        """Create enhanced AI database tables"""
        try:
            if not hasattr(self.bot, 'db') or self.bot.db is None:
                import aiosqlite
                db_path = "db/ai_enhanced.db"
                self.bot.db = await aiosqlite.connect(db_path)
                logger.info("Enhanced AI database connection initialized")

            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS ai_user_settings (
                    user_id INTEGER,
                    guild_id INTEGER,
                    preferred_model TEXT DEFAULT 'llama-3-70b',
                    conversation_mode TEXT DEFAULT 'balanced',
                    personality TEXT,
                    memory_limit INTEGER DEFAULT 50,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS enhanced_conversation_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    guild_id INTEGER,
                    role TEXT,
                    content TEXT,
                    tokens INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS ai_image_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    prompt TEXT,
                    style TEXT,
                    model TEXT,
                    image_url TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS ai_code_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    code TEXT,
                    language TEXT,
                    analysis TEXT,
                    suggestions TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS ai_translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    source_text TEXT,
                    source_lang TEXT,
                    target_text TEXT,
                    target_lang TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.commit()
            
        except Exception as e:
            logger.error(f"Error creating enhanced AI database tables: {e}")

    async def _load_user_settings(self):
        """Load user settings from database"""
        try:
            async with self.bot.db.execute("SELECT user_id, guild_id, preferred_model, conversation_mode, personality, memory_limit FROM ai_user_settings") as cursor:
                async for row in cursor:
                    user_id, guild_id, model, mode, personality, memory_limit = row
                    key = f"{user_id}_{guild_id}"
                    self.user_settings[key] = {
                        "model": model,
                        "mode": mode,
                        "personality": personality,
                        "memory_limit": memory_limit
                    }
        except Exception as e:
            logger.error(f"Error loading user settings: {e}")

    async def _save_user_setting(self, user_id: int, guild_id: int, setting: str, value):
        """Save user setting to database"""
        key = f"{user_id}_{guild_id}"
        if key not in self.user_settings:
            self.user_settings[key] = {
                "model": "llama-3-70b",
                "mode": "balanced",
                "personality": None,
                "memory_limit": 50
            }
        self.user_settings[key][setting] = value
        
        await self.bot.db.execute("""
            INSERT OR REPLACE INTO ai_user_settings (user_id, guild_id, preferred_model, conversation_mode, personality, memory_limit, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, guild_id,
            self.user_settings[key]["model"],
            self.user_settings[key]["mode"],
            self.user_settings[key]["personality"],
            self.user_settings[key]["memory_limit"],
            datetime.now(timezone.utc)
        ))
        await self.bot.db.commit()

    async def _get_user_setting(self, user_id: int, guild_id: int, setting: str, default=None):
        """Get user setting"""
        key = f"{user_id}_{guild_id}"
        if key in self.user_settings:
            return self.user_settings[key].get(setting, default)
        return default

    async def _call_ai_api(self, model_name: str, messages: list, **kwargs) -> str:
        """Call AI API with specified model"""
        if model_name not in self.available_models:
            return f"Model {model_name} not available."
        
        model = self.available_models[model_name]
        
        # Get API key
        if model_name.startswith("gpt"):
            api_key = self.api_keys["openai"]
        elif model_name.startswith("claude"):
            api_key = self.api_keys["anthropic"]
        elif model_name.startswith("command"):
            api_key = self.api_keys["cohere"]
        elif model_name.startswith("llama"):
            api_key = self.api_keys["groq"]
        elif model_name.startswith("gemini"):
            api_key = self.api_keys["gemini"]
        else:
            return f"No API key configured for {model_name}"
        
        if not api_key:
            return f"API key not configured for {model_name}"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Apply conversation mode settings
        mode = kwargs.get("mode", "balanced")
        mode_settings = ConversationMode.get_settings(mode)
        
        data = {
            "model": model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", mode_settings["temperature"]),
            "max_tokens": kwargs.get("max_tokens", mode_settings["max_tokens"]),
            "top_p": kwargs.get("top_p", mode_settings["top_p"])
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(model.api_endpoint, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Parse response based on API format
                        if "choices" in result:
                            return result["choices"][0]["message"]["content"]
                        elif "content" in result:
                            return result["content"][0]["text"]
                        else:
                            return str(result)
                    else:
                        error_text = await response.text()
                        return f"API Error {response.status}: {error_text}"
        except Exception as e:
            logger.error(f"AI API call error: {e}")
            return f"Error calling AI API: {str(e)}"

    async def _store_conversation(self, user_id: int, guild_id: int, role: str, content: str, metadata: dict = None):
        """Store conversation in enhanced memory"""
        try:
            metadata_json = json.dumps(metadata) if metadata else None
            await self.bot.db.execute(
                "INSERT INTO enhanced_conversation_memory (user_id, guild_id, role, content, metadata) VALUES (?, ?, ?, ?, ?)",
                (user_id, guild_id, role, content, metadata_json)
            )
            await self.bot.db.commit()
            
            # Update in-memory cache
            key = f"{user_id}_{guild_id}"
            if key not in self.conversation_memory:
                self.conversation_memory[key] = []
            
            memory_limit = await self._get_user_setting(user_id, guild_id, "memory_limit", 50)
            self.conversation_memory[key].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc)
            })
            
            # Keep only recent messages
            if len(self.conversation_memory[key]) > memory_limit:
                self.conversation_memory[key] = self.conversation_memory[key][-memory_limit:]
                
        except Exception as e:
            logger.error(f"Error storing conversation: {e}")

    async def _get_conversation_history(self, user_id: int, guild_id: int, limit: int = 20) -> list:
        """Get conversation history for user"""
        key = f"{user_id}_{guild_id}"
        if key in self.conversation_memory:
            return [{"role": msg["role"], "content": msg["content"]} for msg in self.conversation_memory[key][-limit:]]
        return []

    @commands.group(name="enhanced-ai", invoke_without_command=True, description="🤖 Enhanced AI commands")
    async def enhanced_ai(self, ctx):
        """🤖 Enhanced AI commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @enhanced_ai.command(name="chat", description="💬 Chat with enhanced AI")
    @app_commands.describe(message="Your message to the AI", model="AI model to use", mode="Conversation mode")
    async def enhanced_chat(self, ctx: commands.Context, *, message: str, model: str = None, mode: str = None):
        """Chat with enhanced AI"""
        await ctx.defer()
        
        user_id = ctx.author.id
        guild_id = ctx.guild.id
        
        # Get user settings
        selected_model = model or await self._get_user_setting(user_id, guild_id, "model", "llama-3-70b")
        selected_mode = mode or await self._get_user_setting(user_id, guild_id, "mode", "balanced")
        personality = await self._get_user_setting(user_id, guild_id, "personality")
        
        # Build conversation context
        history = await self._get_conversation_history(user_id, guild_id)
        
        # Build system prompt
        system_prompt = "You are Zyrox, an intelligent Discord bot assistant."
        if personality:
            system_prompt += f"\n\nPersonality: {personality}"
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        # Get AI response
        response = await self._call_ai_api(selected_model, messages, mode=selected_mode)
        
        # Store conversation
        await self._store_conversation(user_id, guild_id, "user", message)
        await self._store_conversation(user_id, guild_id, "assistant", response, {"model": selected_model, "mode": selected_mode})
        
        # Send response
        embed = discord.Embed(
            title=f"🎯 AI Response ({selected_model})",
            description=response[:4000],
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Mode", value=selected_mode.capitalize(), inline=True)
        embed.set_footer(text=f"Responded to {ctx.author}")
        
        await ctx.send(embed=embed)

    @enhanced_ai.command(name="stream", description="⚡ Stream AI response in real-time")
    @app_commands.describe(message="Your message to the AI")
    async def enhanced_stream(self, ctx: commands.Context, *, message: str):
        """Stream AI response in real-time"""
        user_id = ctx.author.id
        guild_id = ctx.guild.id
        
        selected_model = await self._get_user_setting(user_id, guild_id, "model", "llama-3-70b")
        
        # Send initial message
        initial_msg = await ctx.send("🤖 *Thinking...*")
        
        # Build conversation context
        history = await self._get_conversation_history(user_id, guild_id)
        personality = await self._get_user_setting(user_id, guild_id, "personality")
        
        system_prompt = "You are Zyrox, an intelligent Discord bot assistant."
        if personality:
            system_prompt += f"\n\nPersonality: {personality}"
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        # Get AI response (simulated streaming for now)
        response = await self._call_ai_api(selected_model, messages)
        
        # Simulate streaming by updating message
        words = response.split()
        current_text = ""
        
        for i, word in enumerate(words):
            current_text += word + " "
            if i % 3 == 0:  # Update every 3 words
                await initial_msg.edit(content=f"🤖 {current_text}...")
                await asyncio.sleep(0.1)
        
        await initial_msg.edit(content=f"🤖 {current_text}")
        
        # Store conversation
        await self._store_conversation(user_id, guild_id, "user", message)
        await self._store_conversation(user_id, guild_id, "assistant", response, {"streamed": True})

    @enhanced_ai.command(name="image", description="🎨 Generate AI images with multiple styles")
    @app_commands.describe(prompt="Image description", style="Art style", model="Image model")
    async def enhanced_image(self, ctx: commands.Context, prompt: str, style: str = "realistic", model: str = "pollinations"):
        """Generate AI images with enhanced options"""
        await ctx.defer()
        
        styles = {
            "realistic": "photorealistic, high detail, 8k",
            "anime": "anime style, vibrant colors, detailed",
            "digital-art": "digital art, modern, artistic",
            "oil-painting": "oil painting, classical, textured",
            "watercolor": "watercolor painting, soft, artistic",
            "3d-render": "3D render, CGI, detailed",
            "pixel-art": "pixel art, retro, detailed",
            "cyberpunk": "cyberpunk, neon, futuristic"
        }
        
        style_prompt = styles.get(style.lower(), styles["realistic"])
        full_prompt = f"{prompt}, {style_prompt}"
        
        try:
            if model == "pollinations":
                # Use Pollinations AI
                seed = random.randint(1, 100000)
                encoded_prompt = full_prompt.replace(" ", "%20")
                image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?seed={seed}&width=1024&height=1024"
                
                embed = discord.Embed(
                    title="🎨 AI Generated Image",
                    description=f"**Style:** {style.capitalize()}\n**Prompt:** {prompt}",
                    color=0x00ff00,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_image(url=image_url)
                embed.set_footer(text=f"Generated for {ctx.author}")
                
                await ctx.send(embed=embed)
                
                # Store generation
                await self.bot.db.execute(
                    "INSERT INTO ai_image_generations (user_id, prompt, style, model, image_url) VALUES (?, ?, ?, ?, ?)",
                    (ctx.author.id, prompt, style, model, image_url)
                )
                await self.bot.db.commit()
                
            else:
                await ctx.send("Currently only pollinations model is supported for image generation.")
                
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            await ctx.send(f"Error generating image: {str(e)}")

    @enhanced_ai.command(name="code-analyze", description="🔍 Analyze and debug code with AI")
    @app_commands.describe(code="Code to analyze", language="Programming language")
    async def code_analyze(self, ctx: commands.Context, *, code: str, language: str = "python"):
        """Analyze code with AI"""
        await ctx.defer()
        
        prompt = f"""Analyze this {language} code for:
1. Bugs and errors
2. Performance issues
3. Security vulnerabilities
4. Best practices violations
5. Improvement suggestions

Code:
```{language}
{code}
```

Provide detailed analysis with specific line references and fixes."""
        
        messages = [{"role": "user", "content": prompt}]
        analysis = await self._call_ai_api("llama-3-70b", messages)
        
        # Store analysis
        await self.bot.db.execute(
            "INSERT INTO ai_code_analysis (user_id, code, language, analysis) VALUES (?, ?, ?, ?)",
            (ctx.author.id, code, language, analysis)
        )
        await self.bot.db.commit()
        
        # Send analysis in chunks if too long
        if len(analysis) <= 4000:
            embed = discord.Embed(
                title="🔍 Code Analysis",
                description=analysis,
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Language", value=language.capitalize(), inline=True)
            await ctx.send(embed=embed)
        else:
            # Split into chunks
            chunks = [analysis[i:i+4000] for i in range(0, len(analysis), 4000)]
            for i, chunk in enumerate(chunks):
                embed = discord.Embed(
                    title=f"🔍 Code Analysis (Part {i+1}/{len(chunks)})",
                    description=chunk,
                    color=0x00ff00,
                    timestamp=datetime.now(timezone.utc)
                )
                if i == 0:
                    embed.add_field(name="Language", value=language.capitalize(), inline=True)
                await ctx.send(embed=embed)

    @enhanced_ai.command(name="translate", description="🌐 Translate text with AI")
    @app_commands.describe(text="Text to translate", target_lang="Target language")
    async def enhanced_translate(self, ctx: commands.Context, *, text: str, target_lang: str = "English"):
        """Translate text using AI"""
        await ctx.defer()
        
        prompt = f"Translate the following text to {target_lang}. Only provide the translation, no explanations:\n\n{text}"
        
        messages = [{"role": "user", "content": prompt}]
        translation = await self._call_ai_api("llama-3-70b", messages)
        
        # Store translation
        await self.bot.db.execute(
            "INSERT INTO ai_translations (user_id, source_text, target_text, target_lang) VALUES (?, ?, ?, ?)",
            (ctx.author.id, text, translation, target_lang)
        )
        await self.bot.db.commit()
        
        embed = discord.Embed(
            title="🌐 Translation",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Original", value=text[:1024], inline=False)
        embed.add_field(name=f"Translated to {target_lang}", value=translation[:1024], inline=False)
        embed.set_footer(text=f"Translated for {ctx.author}")
        
        await ctx.send(embed=embed)

    @enhanced_ai.command(name="set-model", description="⚙️ Set your preferred AI model")
    @app_commands.describe(model="AI model to use")
    async def set_model(self, ctx: commands.Context, model: str):
        """Set preferred AI model"""
        available = list(self.available_models.keys())
        if model not in available:
            return await ctx.send(f"Available models: {', '.join(available)}")
        
        await self._save_user_setting(ctx.author.id, ctx.guild.id, "model", model)
        
        embed = discord.Embed(
            title="⚙️ Model Updated",
            description=f"Your preferred AI model is now **{model}**",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed, ephemeral=True)

    @enhanced_ai.command(name="set-mode", description="🎛️ Set conversation mode")
    @app_commands.describe(mode="Conversation mode (creative/balanced/precise)")
    async def set_mode(self, ctx: commands.Context, mode: str):
        """Set conversation mode"""
        if mode.lower() not in [ConversationMode.CREATIVE, ConversationMode.BALANCED, ConversationMode.PRECISE]:
            return await ctx.send("Available modes: creative, balanced, precise")
        
        await self._save_user_setting(ctx.author.id, ctx.guild.id, "mode", mode.lower())
        
        embed = discord.Embed(
            title="⚙️ Mode Updated",
            description=f"Conversation mode set to **{mode.capitalize()}**",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed, ephemeral=True)

    @enhanced_ai.command(name="set-personality", description="🎭 Set AI personality")
    @app_commands.describe(personality="Personality description")
    async def set_personality(self, ctx: commands.Context, *, personality: str):
        """Set AI personality"""
        await self._save_user_setting(ctx.author.id, ctx.guild.id, "personality", personality)
        
        embed = discord.Embed(
            title="🎭 Personality Updated",
            description="Your AI personality has been updated!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Personality", value=personality[:1024], inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    @enhanced_ai.command(name="settings", description="📋 View your AI settings")
    async def view_settings(self, ctx: commands.Context):
        """View AI settings"""
        user_id = ctx.author.id
        guild_id = ctx.guild.id
        
        model = await self._get_user_setting(user_id, guild_id, "model", "llama-3-70b")
        mode = await self._get_user_setting(user_id, guild_id, "mode", "balanced")
        personality = await self._get_user_setting(user_id, guild_id, "personality")
        memory_limit = await self._get_user_setting(user_id, guild_id, "memory_limit", 50)
        
        embed = discord.Embed(
            title="⚙️ Your AI Settings",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Model", value=model, inline=True)
        embed.add_field(name="Mode", value=mode.capitalize(), inline=True)
        embed.add_field(name="Memory Limit", value=f"{memory_limit} messages", inline=True)
        
        if personality:
            embed.add_field(name="Personality", value=personality[:1024], inline=False)
        
        await ctx.send(embed=embed, ephemeral=True)

    @enhanced_ai.command(name="clear-memory", description="🧹 Clear conversation memory")
    async def clear_memory(self, ctx: commands.Context):
        """Clear conversation memory"""
        user_id = ctx.author.id
        guild_id = ctx.guild.id
        
        key = f"{user_id}_{guild_id}"
        if key in self.conversation_memory:
            del self.conversation_memory[key]
        
        await self.bot.db.execute(
            "DELETE FROM enhanced_conversation_memory WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        await self.bot.db.commit()
        
        embed = discord.Embed(
            title="🧹 Memory Cleared",
            description="Your conversation memory has been cleared.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(EnhancedAI(bot))
