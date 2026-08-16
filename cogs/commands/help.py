import discord
from discord.ext import commands
from discord import app_commands, Interaction
from difflib import get_close_matches
from contextlib import suppress
from core import Context
from core.zyrox import zyrox
from core.Cog import Cog
from utils.Tools import getConfig
from itertools import chain
import json
from utils import help as vhelp
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
import asyncio
from utils.config import serverLink
from utils.Tools import *

color = 0xFF0000
client = zyrox()

class HelpCommand(commands.HelpCommand):

  async def send_ignore_message(self, ctx, ignore_type: str):
    if ignore_type == "channel":
      await ctx.reply(f"This channel is ignored.", mention_author=False)
    elif ignore_type == "command":
      await ctx.reply(f"{ctx.author.mention} This Command, Channel, or You have been ignored here.", delete_after=6)
    elif ignore_type == "user":
      await ctx.reply(f"You are ignored.", mention_author=False)

  async def on_help_command_error(self, ctx, error):
    errors = [
      commands.CommandOnCooldown, commands.CommandNotFound,
      discord.HTTPException, commands.CommandInvokeError
    ]
    if not type(error) in errors:
      await self.context.reply(f"Unknown Error Occurred\n{error.original}",
                               mention_author=False)
    else:
      if type(error) == commands.CommandOnCooldown:
        return
    return await super().on_help_command_error(ctx, error)

  async def command_not_found(self, string: str) -> None:
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
        return

    if not check_ignore:
        await self.send_ignore_message(ctx, "command")
        return

    cmds = (str(cmd) for cmd in self.context.bot.walk_commands())
    matches = get_close_matches(string, cmds)

    embed = discord.Embed(
        title="BeZmerz Help Menu",
        description=f">>> **Ops! Command not found with the name** `{string}`.",
        color=0xFF0000
    )
                          
    #if matches:
        #match_list = "\n".join([f"{index}. `{match}`" for index, match in enumerate(matches, start=1)])
        #embed.add_field(name="Did you mean:", value=match_list, inline=True)

    await ctx.reply(embed=embed, mention_author=True)

  async def send_bot_help(self, mapping):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    # Show loading embed
    loading_embed = discord.Embed(
      description="<a:loadingred:1448966488865247232> Loading help Menu...",
      color=0xFF0000
    )
    loading_msg = await ctx.reply(embed=loading_embed)

    # Wait 2 seconds
    await asyncio.sleep(2)

    # Delete loading message
    with suppress(discord.NotFound):
      await loading_msg.delete()

    data = await getConfig(self.context.guild.id)
    prefix = data["prefix"]
    filtered = await self.filter_commands(self.context.bot.walk_commands(), sort=True)

    embed = discord.Embed(
        description=(
         f"**<a:ArrowRed:1448951520077811806> __Start BeZmerz Today__**\n"        
         f"**<:zArrow:1448951532837015643> Type {prefix}antinuke enable**\n"
         f"**<:zArrow:1448951532837015643> Server Prefix:** `{prefix}`\n"
         f"**<:zArrow:1448951532837015643> Total Commands:** `{len(set(self.context.bot.walk_commands()))}`\n"),         
        color=0xFF0000)
    embed.set_author(name=f"{ctx.author}", 
                     icon_url=ctx.author.display_avatar.url)
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    
    embed.add_field(
        name="<:zCloud:1448951498213032036> __**Main Features**__",
        value=">>> \n <:zSafe:1448951403434479626> `»` Security\n" 
              " <:zbot:1448951393216888905> `»` Automoderation\n"
              " <:zwrench:1448951382597177495> `»` Utility\n" 
              " <:zmusic:1448951372707008533> `»` Music\n"
              " <:zwifi:1448951466931912715> `»` Autoreact & responder\n"
              " <:zsowrd:1448951362238021682> `»` Moderation\n"
              " <:zpeople:1448951456861519962> `»` Autorole & Invc\n"
              " <:zrocket:1448951445989888010> `»` Fun\n"
              " <:games:1448951285498777641> `»` Games\n" 
              " <:zban:1448951424665784373> `»` Ignore Channels\n"
              " <:zwifi:1448951466931912715> `»` Server\n"
              " <:zunmute:1448951487970414694> `»` Voice\n"
              " <:zseed:1448951477640101929> `»` Welcomer\n"  
              " <:ztada:1448951329664925717> `»` Giveaway\n"
              " <:zticket:1448951318713470987> `»` Ticket <:New:1448949337395695616>\n"
              " <:zpeople:1448951456861519962> `»` Invite Tracker <:New:1448949337395695616>\n"
    )
    
    embed.add_field(
        name=" <:zmodule:1448951340716785744> __**Extra Features**__",
        value=">>> \n <:zcast:1448951414301655175> `»` Advance Logging\n"
              " <:starr:1448951307707748395> `»` Vanityroles\n"
              
              " <:zcounting:1448949348103749713> `»` Counting <:New:1448949337395695616>\n"
              " <:zyrox_system:1448949359159939143> `»` J2C <:New:1448949337395695616>\n"
              " <:zai:1448949821611446302> `»` AI <:New:1448949337395695616>\n"
              " <:boost:1448966463586041906> `»` Boost <:New:1448949337395695616>\n"
              " <:zlevelup:1448964376504696943> `»` Leveling <:New:1448949337395695616>\n"
              " <:zpin:1448949810462855249> `»` Sticky <:New:1448949337395695616>\n"
              " <:zyroxthunder:1448949415200034907> `»` Verification <:New:1448949337395695616>\n"
              " <:lock:1448949549455511685> `»` Encryption <:New:1448949337395695616>\n" 
              " <:zmc:1448964387426537474> `»` Minecraft <:New:1448949337395695616>\n"
              " <:zmsg:1448964399166394483> `»` Joindm <:New:1448949337395695616>\n"
              " <:zcircle:1448964410155470848> `»` Birthday <:New:1448949337395695616>\n"
              " <:zcircle:1448951351601270814> `»` Customrole\n"           
    )

    embed.set_footer(
      text=f"Requested By {self.context.author} | [Support](https://discord.gg/P9UXgfMT6P)",
    )
    
    view = vhelp.View(mapping=mapping, ctx=self.context, homeembed=embed, ui=2)
    await ctx.reply(embed=embed, view=view)

  async def send_command_help(self, command):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    zyrox = f">>> {command.help}" if command.help else '>>> No Help Provided...'
    embed = discord.Embed(
        description=f"""{zyrox}""",
        color=color)
    alias = ' & '.join(command.aliases)

    embed.add_field(name="**Alt cmd**",
                      value=f"```{alias}```" if command.aliases else "No Alt cmd",
                      inline=False)
    embed.add_field(name="**Usage**",
                      value=f"```{self.context.prefix}{command.signature}```\n")
    embed.set_author(name=f"{command.qualified_name.title()} Command")
    embed.set_footer(text="<[] = optional | < > = required • Use Prefix Before Commands.")
    await self.context.reply(embed=embed, mention_author=False)

  def get_command_signature(self, command: commands.Command) -> str:
    parent = command.full_parent_name
    if len(command.aliases) > 0:
      aliases = ' | '.join(command.aliases)
      fmt = f'[{command.name} | {aliases}]'
      if parent:
        fmt = f'{parent}'
      alias = f'[{command.name} | {aliases}]'
    else:
      alias = command.name if not parent else f'{parent} {command.name}'
    return f'{alias} {command.signature}'

  def common_command_formatting(self, embed_like, command):
    embed_like.title = self.get_command_signature(command)
    if command.description:
      embed_like.description = f'{command.description}\n\n{command.help}'
    else:
      embed_like.description = command.help or 'No help found...'

  async def send_group_help(self, group):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    entries = [
        (
            f"`{self.context.prefix}{cmd.qualified_name}`\n",
            f"{cmd.short_doc if cmd.short_doc else ''}\n\u200b"
        )
        for cmd in group.commands
      ]

    count = len(group.commands)

    embeds = FieldPagePaginator(
      entries=entries,
      title=f"{group.qualified_name.title()} [{count}]",
      description="< > Duty | [ ] Optional\n",
      per_page=4
    ).get_pages()   
    
    paginator = Paginator(ctx, embeds)
    await paginator.paginate()

  async def send_cog_help(self, cog):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    entries = [(
      f"> `{self.context.prefix}{cmd.qualified_name}`",
      f"-# Description : {cmd.short_doc if cmd.short_doc else ''}"
      f"\n\u200b",
    ) for cmd in cog.get_commands()]
    paginator = Paginator(source=FieldPagePaginator(
      entries=entries,
      title=f"Zyrox's {cog.qualified_name.title()} ({len(cog.get_commands())})",
      description="`<..> Required | [..] Optional`\n\n",
      color=0xFF0000,
      per_page=4),
                          ctx=self.context)
    await paginator.paginate()


class Help(Cog, name="help"):

  def __init__(self, client: zyrox):
    self._original_help_command = client.help_command
    attributes = {
      'name': "help",
      'aliases': ['h'],
      'cooldown': commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user),
      'help': 'Shows help about bot, a command, or a category'
    }
    client.help_command = HelpCommand(command_attrs=attributes)
    client.help_command.cog = self

  async def cog_unload(self):
    self.help_command = self._original_help_command