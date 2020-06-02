from .pokecord import Pokecord


async def setup(bot):
    cog = Pokecord(bot)
    await cog.initalize()
    bot.add_cog(cog)
