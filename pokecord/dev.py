import json

import discord
import tabulate
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import *

from .abc import MixinMeta
from .pokemixin import poke
from .statements import *

_ = Translator("Pokecord", __file__)


class Dev(MixinMeta):
    """Pokecord Development Commands"""

    @poke.group(hidden=True)
    @commands.is_owner()
    async def dev(self, ctx):
        """Pokecord Development Commands"""

    @dev.command(name="spawn")
    async def dev_spawn(self, ctx, *, pokemon: str = None):
        """Spawn a pokemon by name or random"""
        if pokemon is None:
            await self.spawn_pokemon(ctx.channel)
            return
        else:
            for i, pokemondata in enumerate(self.pokemondata):
                name = (
                    pokemondata.get("alias").lower()
                    if pokemondata.get("alias")
                    else pokemondata["name"]["english"].lower()
                )
                if name == pokemon:
                    await self.spawn_pokemon(ctx.channel, pokemon=self.pokemondata[i])
                    return
        await ctx.send("No pokemon found.")

    @dev.command(name="ivs")
    async def dev_ivs(
        self,
        ctx,
        user: discord.Member,
        pokeid: int,
        hp: int,
        attack: int,
        defence: int,
        spatk: int,
        spdef: int,
        speed: int,
    ):
        """Manually set a pokemons IVs"""
        if pokeid <= 0:
            return await ctx.send("The ID must be greater than 0!")
        async with ctx.typing():
            result = self.cursor.execute(
                SELECT_POKEMON,
                (user.id,),
            ).fetchall()
        pokemons = [None]
        for data in result:
            pokemons.append([json.loads(data[0]), data[1]])
        if not pokemons:
            return await ctx.send("You don't have any pokémon, trainer!")
        if pokeid >= len(pokemons):
            return await ctx.send("There's no pokemon at that slot.")
        pokemon = pokemons[pokeid]
        pokemon[0]["ivs"] = {
            "HP": hp,
            "Attack": attack,
            "Defence": defence,
            "Sp. Atk": spatk,
            "Sp. Def": spdef,
            "Speed": speed,
        }
        self.cursor.execute(
            UPDATE_POKEMON,
            (user.id, pokemon[1], json.dumps(pokemon[0])),
        )
        await ctx.tick()

    @dev.command(name="stats")
    async def dev_stats(
        self,
        ctx,
        user: discord.Member,
        pokeid: int,
        hp: int,
        attack: int,
        defence: int,
        spatk: int,
        spdef: int,
        speed: int,
    ):
        """Manually set a pokemons statss"""
        if pokeid <= 0:
            return await ctx.send("The ID must be greater than 0!")
        async with ctx.typing():
            result = self.cursor.execute(
                SELECT_POKEMON,
                (user.id,),
            ).fetchall()
        pokemons = [None]
        for data in result:
            pokemons.append([json.loads(data[0]), data[1]])
        if not pokemons:
            return await ctx.send("You don't have any pokémon, trainer!")
        if pokeid >= len(pokemons):
            return await ctx.send("There's no pokemon at that slot.")
        pokemon = pokemons[pokeid]
        pokemon[0]["stats"] = {
            "HP": hp,
            "Attack": attack,
            "Defence": defence,
            "Sp. Atk": spatk,
            "Sp. Def": spdef,
            "Speed": speed,
        }
        self.cursor.execute(
            UPDATE_POKEMON,
            (user.id, pokemon[1], json.dumps(pokemon[0])),
        )
        await ctx.tick()
