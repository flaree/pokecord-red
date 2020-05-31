from .abc import MixinMeta
import discord

from redbot.core import commands


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
            await ctx.send("Pokécord levelling messages have been silenced.")
            return
        await ctx.send("Pokécord levelling messages have been re-enabled!")

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
            channels.append(channel.id)
        await self.update_guild_cache()
        await ctx.tick()

    @pokecordset.command()
    async def settings(self, ctx):
        """Overview of pokécord settings."""
        data = await self.config.guild(ctx.guild).all()
        await self.update_guild_cache()
        await ctx.send(data)
