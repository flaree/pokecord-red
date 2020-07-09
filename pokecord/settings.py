from .abc import MixinMeta
import discord
import json

from redbot.core import commands
from redbot.core.utils.chat_formatting import humanize_list
from typing import Union

LOCALES = {
    "english": "en",
    "en": "en",
    "eng": "en",
    "chinese": "cn",
    "cn": "cn",
    "japan": "jp",
    "japanese": "jp",
    "fr": "fr",
    "french": "fr",
}


class SettingsMixin(MixinMeta):
    """Pokecord Settings"""

    @commands.command(usage="type")
    @commands.guild_only()
    async def silence(self, ctx, _type: bool = None):
        """Toggle pokecord levelling messages on or off."""
        conf = await self.user_is_global(ctx.author)
        if _type is None:
            _type = not await conf.silence()
        await conf.silence.set(_type)
        if _type:
            await ctx.send("Your pokécord levelling messages have been silenced.")
        else:
            await ctx.send("Your pokécord levelling messages have been re-enabled!")
        await self.update_user_cache()

    @commands.command()
    @commands.guild_only()
    async def locale(self, ctx, locale: str):
        """Set the Pokecord locale to use for yourself."""
        if locale.lower() not in LOCALES:
            await ctx.send(
                "You've specified an invalid locale. Pokecord only supports English, Japanese, Chinese and French."
            )
            return
        conf = await self.user_is_global(ctx.author)
        await conf.locale.set(LOCALES[locale.lower()])
        await ctx.tick()
        await self.update_user_cache()

    @commands.group(aliases=["pokeset"])
    @commands.admin()
    @commands.guild_only()
    async def pokecordset(self, ctx):
        """Manage pokecord settings"""
        pass

    @pokecordset.command(usage="type")
    async def toggle(self, ctx, _type: bool = None):
        """Toggle pokecord on or off."""
        if _type is None:
            _type = not await self.config.guild(ctx.guild).toggle()
        await self.config.guild(ctx.guild).toggle.set(_type)
        if _type:
            await ctx.send("Pokécord has been toggled on!")
            return
        await ctx.send("Pokécord has been toggled off!")
        await self.update_guild_cache()

    @pokecordset.command()
    async def channel(self, ctx, channel: discord.TextChannel):
        """Set the channel that pokemon are to spawn in."""
        async with self.config.guild(ctx.guild).activechannels() as channels:
            if channel.id in channels:
                channels.remove(channel.id)
                await ctx.send("Channel has been removed.")
                return
            channels.append(channel.id)
        await self.update_guild_cache()
        await ctx.tick()

    @pokecordset.command()
    async def settings(self, ctx):
        """Overview of pokécord settings."""
        data = await self.config.guild(ctx.guild).all()
        await self.update_guild_cache()
        msg = f"**Toggle**: {data['toggle']}\n**Active Channels**: {humanize_list(data['activechannels']) if data['activechannels'] else 'All' if data['toggle'] else 'None'}"
        await ctx.send(msg)

    @pokecordset.command(usage="<min amount of messages> <max amount of messages>")
    @commands.is_owner()
    async def spawnchance(self, ctx, _min: int, _max: int):
        """Change the range of messages required for a spawn."""
        if _min < 15:
            return await ctx.send("Min must be more than 15.")
        if _max < _min:
            return await ctx.send("Max must be more than the minimum.")
        await self.config.spawnchance.set([_min, _max])
        await self.update_spawn_chance()
        await ctx.tick()

    @pokecordset.command()
    @commands.is_owner()
    async def spawnloop(self, ctx, state: bool):
        """Turn the bot loop on or off."""
        if state:
            await ctx.send(
                "Random spawn loop has been enabled, please reload the cog for this change to take effect."
            )
        else:
            await ctx.send(
                "Random spawn loop has been disabled, please reload the cog for this change to take effect."
            )
        await self.config.spawnloop.set(state)
        await ctx.tick()
