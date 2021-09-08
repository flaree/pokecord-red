import json

import discord
import tabulate
from typing import Optional
import ast
import pprint
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

    async def get_pokemon(self, ctx, *, user: discord.Member, pokeid: int) -> list:
        """Returns pokemons from user list if exists"""
        if pokeid <= 0:
            return await ctx.send("The ID must be greater than 0!")
        async with ctx.typing():
            result = await self.cursor.fetch_all(query=SELECT_POKEMON, values={"user_id": user.id})
        pokemons = [None]
        for data in result:
            pokemons.append([json.loads(data[0]), data[1]])
        if not pokemons:
            return await ctx.send("You don't have any pokémon, trainer!")
        if pokeid >= len(pokemons):
            return await ctx.send("There's no pokemon at that slot.")
        return pokemons[pokeid]

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
            result = await self.cursor.fetch_all(query=SELECT_POKEMON, values={"user_id": user.id})
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
        await self.cursor.execute(
            query=UPDATE_POKEMON,
            values={
                "user_id": user.id,
                "message_id": pokemon[1],
                "pokemon": json.dumps(pokemon[0]),
            },
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
        """Manually set a pokemons stats"""
        if pokeid <= 0:
            return await ctx.send("The ID must be greater than 0!")
        async with ctx.typing():
            result = await self.cursor.fetch_all(query=SELECT_POKEMON, values={"user_id": user.id})
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
        await self.cursor.execute(
            query=UPDATE_POKEMON,
            values={
                "user_id": user.id,
                "message_id": pokemon[1],
                "pokemon": json.dumps(pokemon[0]),
            },
        )
        await ctx.tick()

    @dev.command(name="level")
    async def dev_lvl(self, ctx, user: discord.Member, pokeid: int, lvl: int):
        """Manually set a pokemons level"""
        if pokeid <= 0:
            return await ctx.send("The ID must be greater than 0!")
        async with ctx.typing():
            result = await self.cursor.fetch_all(query=SELECT_POKEMON, values={"user_id": user.id})
        pokemons = [None]
        for data in result:
            pokemons.append([json.loads(data[0]), data[1]])
        if not pokemons:
            return await ctx.send("You don't have any pokémon, trainer!")
        if pokeid >= len(pokemons):
            return await ctx.send("There's no pokemon at that slot.")
        pokemon = pokemons[pokeid]
        pokemon[0]["level"] = lvl
        await self.cursor.execute(
            query=UPDATE_POKEMON,
            values={
                "user_id": user.id,
                "message_id": pokemon[1],
                "pokemon": json.dumps(pokemon[0]),
            },
        )
        await ctx.tick()

    @dev.command(name="reveal")
    async def dev_reveal(self, ctx, user: Optional[discord.Member], pokeid: int):
        """Shows raw info for an owned pokemon"""
        if user is None:
            user = ctx.author
        if not isinstance(
            pokemon := await self.get_pokemon(
                ctx,
                user=user,
                pokeid=pokeid
            ),
            list
        ):
            return
        await ctx.send(content=pprint.pformat(pokemon[0]))

    @dev.command(name="set")
    async def dev_set(self, ctx, pokeid: int, *args):
        """delete this later"""
        if not isinstance(
            pokemon := await self.get_pokemon(
                ctx,
                user=ctx.author,
                pokeid=pokeid
            ),
            list
        ):
            return
        try:
            data = ' '.join(args)
        except TypeError as terr:
            return await ctx.send("Argument Error: {terr}")
        except Exception as err:
            return await ctx.send("Unexpected Error: {err}")

        if not isinstance(data := ast.literal_eval(data), dict):
            return await ctx.send("Argument Error, expecting data type `dict`")

        await ctx.send(data)


