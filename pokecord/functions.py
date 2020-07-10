from redbot.core.utils.menus import menu
from redbot.core import commands
import discord
import contextlib


async def select_pokemon(
    ctx: commands.Context,
    pages: list,
    controls: dict,
    message: discord.Message,
    page: int,
    timeout: float,
    emoji: str,
):
    perms = message.channel.permissions_for(ctx.me)
    if perms.manage_messages:  # Can manage messages, so remove react
        with contextlib.suppress(discord.NotFound):
            await message.remove_reaction(emoji, ctx.author)
    command = ctx.bot.get_command("select")
    await ctx.invoke(command, _id=page + 1)
    return await menu(ctx, pages, controls, message=message, page=page, timeout=timeout)


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i : i + n]