import random

import discord
from redbot.core import Config, checks, commands
from redbot.core.data_manager import bundled_data_path
import json
import string


class Pokecord(commands.Cog):
    """Pokecord adapted to use on Red."""

    __version__ = "0.0.1a"
    __author__ = "flare"

    def format_help_for_context(self, ctx):
        """Thanks Sinbad."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\nAuthor: {self.__author__}\nCog Version: {self.__version__}"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=95932766180343808, force_registration=True)
        self.config.register_global(isglobal=True)
        self.config.register_guild
        self.datapath = f"{bundled_data_path(self)}"

    async def initalize(self):
        with open(f"{self.datapath}/pokemon.json") as f:
            self.pokemondata = json.load(f)

    async def is_global(self, ctx):
        toggle = await self.config.isglobal()
        if toggle:
            return self.config
        return self.config.guild(ctx.guild)

    def pokemon_choose(self):
        num = random.randint(1, 200)
        print(self.pokemondata["normal"])
        if num > 2:
            return random.choice(self.pokemondata["normal"])
        return random.choice(self.pokemondata["mega"])

    @commands.command()
    async def test(self, ctx):
        """."""
        img = self.pokemon_choose()
        await ctx.send(img)
        await ctx.send(file=discord.File(f"{self.datapath}/{img['name']}.png"))
