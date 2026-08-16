import os
import discord
import aiosqlite
from discord.ext import commands
import asyncio
from datetime import datetime, timezone
from discord import app_commands
import aiohttp
import logging
import io
from gtts import gTTS
from langdetect import detect
import speech_recognition as sr
import tempfile

logger = logging.getLogger('discord')

class AIVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_sessions = {}  # user_id -> voice session data
        
        asyncio.create_task(self._delayed_init())

    async def _delayed_init(self):
        """Initialize database after bot is ready"""
        await self.bot.wait_until_ready()
        await self._create_tables()

    async def _create_tables(self):
        """Create voice-related tables"""
        try:
            if not hasattr(self.bot, 'db') or self.bot.db is None:
                import aiosqlite
                db_path = "db/ai_voice.db"
                self.bot.db = await aiosqlite.connect(db_path)
                logger.info("AI Voice database connection initialized")

            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS voice_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    text TEXT,
                    language TEXT,
                    voice_style TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    audio_url TEXT,
                    transcribed_text TEXT,
                    language TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.bot.db.commit()
            
        except Exception as e:
            logger.error(f"Error creating voice database tables: {e}")

    @commands.group(name="ai-voice", invoke_without_command=True, description="AI voice and speech commands")
    async def ai_voice(self, ctx):
        """AI voice and speech commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @ai_voice.command(name="tts", description="Convert text to speech using AI")
    @app_commands.describe(text="Text to convert to speech", language="Language code (e.g., en, es, fr)", voice="Voice style")
    async def text_to_speech(self, ctx: commands.Context, *, text: str, language: str = "en", voice: str = "default"):
        """Convert text to speech"""
        await ctx.defer()
        
        try:
            # Detect language if not specified
            if language == "auto":
                try:
                    detected_lang = detect(text)
                    language = detected_lang
                except:
                    language = "en"
            
            # Generate speech
            tts = gTTS(text=text, lang=language, slow=False)
            
            # Save to bytes
            audio_bytes = io.BytesIO()
            tts.write_to_fp(audio_bytes)
            audio_bytes.seek(0)
            
            # Create audio file
            audio_file = discord.File(audio_bytes, filename="speech.mp3")
            
            # Store generation
            await self.bot.db.execute(
                "INSERT INTO voice_generations (user_id, text, language, voice_style) VALUES (?, ?, ?, ?)",
                (ctx.author.id, text[:500], language, voice)
            )
            await self.bot.db.commit()
            
            # Send audio
            embed = discord.Embed(
                title="🎙️ Text to Speech",
                description=f"**Text:** {text[:200]}...\n**Language:** {language.upper()}",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=f"Generated for {ctx.author}")
            
            await ctx.send(embed=embed, file=audio_file)
            
        except Exception as e:
            logger.error(f"Error in TTS: {e}")
            await ctx.send(f"Error generating speech: {str(e)}")

    @ai_voice.command(name="stt", description="Convert speech to text (transcription)")
    @app_commands.describe(audio_url="URL of audio file to transcribe")
    async def speech_to_text(self, ctx: commands.Context, audio_url: str):
        """Transcribe audio to text"""
        await ctx.defer()
        
        try:
            # Download audio
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                    else:
                        return await ctx.send("Failed to download audio file")
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                # Transcribe using speech recognition
                recognizer = sr.Recognizer()
                with sr.AudioFile(temp_path) as source:
                    audio = recognizer.record(source)
                
                # Try Google Speech Recognition
                try:
                    text = recognizer.recognize_google(audio)
                    language = "en-US"
                except:
                    try:
                        text = recognizer.recognize_sphinx(audio)
                        language = "en-US (offline)"
                    except:
                        text = "Could not transcribe audio"
                        language = "unknown"
                
                # Store transcription
                await self.bot.db.execute(
                    "INSERT INTO transcriptions (user_id, audio_url, transcribed_text, language) VALUES (?, ?, ?, ?)",
                    (ctx.author.id, audio_url, text[:1000], language)
                )
                await self.bot.db.commit()
                
                embed = discord.Embed(
                    title="🎧 Speech to Text",
                    description=f"**Transcribed Text:**\n{text}",
                    color=0x00ff00,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Language", value=language, inline=True)
                embed.set_footer(text=f"Transcribed for {ctx.author}")
                
                await ctx.send(embed=embed)
                
            finally:
                # Clean up temp file
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"Error in STT: {e}")
            await ctx.send(f"Error transcribing audio: {str(e)}")

    @ai_voice.command(name="voice-chat", description="Start AI voice chat in a voice channel")
    @app_commands.describe(channel="Voice channel to join")
    async def voice_chat(self, ctx: commands.Context, channel: discord.VoiceChannel = None):
        """Start AI voice chat"""
        if not channel:
            if ctx.author.voice:
                channel = ctx.author.voice.channel
            else:
                return await ctx.send("You need to be in a voice channel or specify one")
        
        try:
            # Join voice channel
            voice_client = await channel.connect()
            
            embed = discord.Embed(
                title="🎤 AI Voice Chat",
                description=f"Joined {channel.mention}\nVoice chat is now active! Speak to interact with the AI.",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            await ctx.send(embed=embed)
            
            # Store voice session
            self.voice_sessions[ctx.author.id] = {
                "voice_client": voice_client,
                "channel": channel,
                "started_at": datetime.now(timezone.utc)
            }
            
            # Note: Full voice chat implementation would require audio processing
            # This is a placeholder for the voice chat functionality
            
        except Exception as e:
            logger.error(f"Error joining voice channel: {e}")
            await ctx.send(f"Error joining voice channel: {str(e)}")

    @ai_voice.command(name="leave-voice", description="Leave voice channel")
    async def leave_voice(self, ctx: commands.Context):
        """Leave voice channel"""
        user_id = ctx.author.id
        
        if user_id not in self.voice_sessions:
            return await ctx.send("You're not in an active voice session")
        
        try:
            voice_client = self.voice_sessions[user_id]["voice_client"]
            await voice_client.disconnect()
            
            del self.voice_sessions[user_id]
            
            embed = discord.Embed(
                title="👋 Left Voice Channel",
                description="AI voice chat has ended.",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error leaving voice channel: {e}")
            await ctx.send(f"Error leaving voice channel: {str(e)}")

    @ai_voice.command(name="voice-history", description="View your voice generation history")
    async def voice_history(self, ctx: commands.Context):
        """View voice generation history"""
        await ctx.defer()
        
        try:
            async with self.bot.db.execute(
                "SELECT text, language, voice_style, timestamp FROM voice_generations WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10",
                (ctx.author.id,)
            ) as cursor:
                rows = await cursor.fetchall()
            
            if not rows:
                return await ctx.send("No voice generation history found.")
            
            embed = discord.Embed(
                title="🎙️ Voice Generation History",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            
            for text, language, voice_style, timestamp in rows:
                embed.add_field(
                    name=f"{timestamp[:19]} - {language.upper()}",
                    value=text[:100] + "..." if len(text) > 100 else text,
                    inline=False
                )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error fetching voice history: {e}")
            await ctx.send(f"Error fetching history: {str(e)}")

async def setup(bot):
    await bot.add_cog(AIVoice(bot))
