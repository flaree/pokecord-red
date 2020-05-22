import random

import discord
from redbot.core import Config, checks, commands
from redbot.core.data_manager import bundled_data_path
import json
import string
import logging

log = logging.getLogger("red.flare.pokecord")


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
        self.spawnedpokemon = {}

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
        if num > 2:
            return random.choice(self.pokemondata["normal"])
        return random.choice(self.pokemondata["mega"])

    @commands.command()
    async def test(self, ctx):
        """."""
        img = self.pokemon_choose()
        await ctx.send(img)
        await ctx.send(file=discord.File(f"{self.datapath}/{img['name']}.png"))

    @commands.command()
    async def catch(self, ctx, *, pokemon: str):
        """."""
        if self.spawnedpokemon.get(ctx.guild.id) is not None:
            pokemonspawn = self.spawnedpokemon[ctx.guild.id].get(ctx.channel.id) 
            if pokemonspawn is not None:
                if pokemon.lower() in [pokemonspawn["name"].lower(), pokemonspawn["name"].strip(string.punctuation).lower()]:
                    await ctx.send(f"Congratulations, you've caught {pokemonspawn['name']}.")
                    del self.spawnedpokemon[ctx.guild.id][ctx.channel.id]
                    # TODO: Persist data
                    return
                else:
                    return await ctx.send("That's not the correct pokemon")
        await ctx.send("No pokemon is ready to be caught.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.content == "spawn":
            if message.guild.id not in self.spawnedpokemon:
                self.spawnedpokemon[message.guild.id] = {}
            pokemon = self.pokemon_choose()
            log.info(pokemon)
            self.spawnedpokemon[message.guild.id][message.channel.id] = pokemon
            await message.channel.send(file=discord.File(f"{self.datapath}/{pokemon['name']}.png"))

        # TODO: Random delivery times
            

