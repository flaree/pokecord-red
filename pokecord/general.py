import asyncio
import json
import urllib

import discord
import tabulate
from redbot.core import commands
from redbot.core.utils.chat_formatting import *
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.predicates import MessagePredicate

from .abc import MixinMeta
from .statements import *


class GeneralMixin(MixinMeta):
    """Pokecord General Commands"""
    
    @commands.command()
    async def list(self, ctx):
        """List your pokémon!"""
        conf = await self.user_is_global(ctx.author)
        result = self.cursor.execute(
            SELECT_POKEMON, (ctx.author.id,)
        ).fetchall()
        pokemons = []
        for data in result:
            pokemons.append(json.loads(data[0]))
        if not pokemons:
            return await ctx.send(
                "You don't have any pokémon, go get catching trainer!"
            )
        embeds = []
        for i, pokemon in enumerate(pokemons, 1):
            stats = pokemon["stats"]
            pokestats = tabulate.tabulate(
                [
                    ["HP", stats["HP"]],
                    ["Attack", stats["Attack"]],
                    ["Defence", stats["Defence"]],
                    ["Sp. Atk", stats["Sp. Atk"]],
                    ["Sp. Def", stats["Sp. Def"]],
                    ["Speed", stats["Speed"]],
                ],
                headers=["Ability", "Value"],
            )
            nick = pokemon.get("nickname")
            alias = f"**Nickname**: {nick}\n" if nick is not None else ""
            desc = f"{alias}**Level**: {pokemon['level']}\n**XP**: {pokemon['xp']}/{self.calc_xp(pokemon['level'])}\n{box(pokestats, lang='prolog')}"
            embed = discord.Embed(title=pokemon["name"], description=desc)
            embed.set_image(
                url=f"https://i.flaree.xyz/pokecord/{urllib.parse.quote(pokemon['name'])}.png"
            )
            embed.set_footer(text=f"Pokémon ID: {i}/{len(pokemons)}")
            embeds.append(embed)
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.command()
    async def nick(self, ctx, id: int, *, nickname: str):
        """Set a pokemons nickname."""
        if id <= 0:
            return await ctx.send("The ID must be greater than 0!")
        result = self.cursor.execute(
            SELECT_POKEMON,
            (ctx.author.id,),
        ).fetchall()
        pokemons = [None]
        for data in result:
            pokemons.append([json.loads(data[0]), data[1]])
        if not pokemons:
            return await ctx.send("You don't have any pokémon, trainer!")
        if id > len(pokemons):
            return await ctx.send("You don't have a pokemon at that slot.")
        pokemon = pokemons[id]
        pokemon[0]["nickname"] = nickname
        self.cursor.execute(
            UPDATE_POKEMON,
            (ctx.author.id, pokemon[1], json.dumps(pokemon[0])),
        )
        await ctx.send(f"Your {pokemon[0]['name']} has been named `{nickname}`")

    @commands.command()
    async def free(self, ctx, id: int):
        """Free a pokemon."""
        if id <= 0:
            return await ctx.send("The ID must be greater than 0!")
        result = self.cursor.execute(
            SELECT_POKEMON,
            (ctx.author.id,),
        ).fetchall()
        pokemons = [None]
        for data in result:
            pokemons.append([json.loads(data[0]), data[1]])
        if not pokemons:
            return await ctx.send("You don't have any pokémon, trainer!")
        if id > len(pokemons):
            return await ctx.send("You don't have a pokemon at that slot.")
        pokemon = pokemons[id]
        name = self.get_name(pokemon[0]["name"], pokemon[0]["alias"])
        await ctx.send(
            f"You are about to free {name}, if you wish to continue type `yes`, otherwise type `no`."
        )
        try:
            pred = MessagePredicate.yes_or_no(ctx, user=ctx.author)
            await ctx.bot.wait_for("message", check=pred, timeout=20)
        except asyncio.TimeoutError:
            await ctx.send("Exiting operation.")
            return

        if pred.result:
            msg = ""
            userconf = await self.user_is_global(ctx.author)
            pokeid = await userconf.pokeid()
            if id < pokeid:
                msg += "\nYour default pokemon may have changed. I have tried to account for this change."
            elif id == pokeid:
                msg += "\nYou have released your selected pokemon. I have reset your selected pokemon to your first pokemon."
                await userconf.pokeid.set(1)
            self.cursor.execute(
                "DELETE FROM users where message_id = ?", (pokemon[1],),
            )
            await ctx.send(f"Your {name} has been freed.{msg}")
        else:
            await ctx.send("Operation cancelled.")
