import asyncio
import copy
import json
import urllib

import discord
import tabulate
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import *
from redbot.core.utils.menus import DEFAULT_CONTROLS, close_menu, menu, next_page, prev_page
from redbot.core.utils.predicates import MessagePredicate

from .abc import MixinMeta
from .functions import chunks, select_pokemon
from .statements import *

_ = Translator("Pokecord", __file__)


controls = {
    "⬅": prev_page,
    "❌": close_menu,
    "➡": next_page,
    "\N{WHITE HEAVY CHECK MARK}": select_pokemon,
}


class GeneralMixin(MixinMeta):
    """Pokecord General Commands"""

    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.command()
    async def list(self, ctx, user: discord.Member = None):
        """List a trainers or your own pokémon!"""
        user = user or ctx.author
        conf = await self.user_is_global(user)
        async with ctx.typing():
            result = self.cursor.execute(SELECT_POKEMON, (user.id,)).fetchall()
        pokemons = []
        for data in result:
            pokemons.append(json.loads(data[0]))
        if not pokemons:
            return await ctx.send(_("You don't have any pokémon, go get catching trainer!"))
        embeds = []
        for i, pokemon in enumerate(pokemons, 1):
            stats = pokemon["stats"]
            pokestats = tabulate.tabulate(
                [
                    [_("HP"), stats["HP"]],
                    [_("Attack"), stats["Attack"]],
                    [_("Defence"), stats["Defence"]],
                    [_("Sp. Atk"), stats["Sp. Atk"]],
                    [_("Sp. Def"), stats["Sp. Def"]],
                    [_("Speed"), stats["Speed"]],
                ],
                headers=[_("Ability"), _("Value")],
            )
            nick = pokemon.get("nickname")
            alias = _("**Nickname**: {nick}\n").format(nick=nick) if nick is not None else ""
            desc = _("{alias}**Level**: {level}\n**XP**: {xp}\n{stats}").format(
                alias=alias,
                level=pokemon["level"],
                xp=pokemon["xp"] / self.calc_xp(pokemon["level"]),
                stats=box(pokestats, lang="prolog"),
            )
            embed = discord.Embed(title=self.get_name(pokemon["name"], user), description=desc)
            if pokemon.get("id"):
                embed.set_thumbnail(
                    url=f"https://assets.pokemon.com/assets/cms2/img/pokedex/detail/{str(pokemon['id']).zfill(3)}.png"
                )
            embed.set_footer(
                text=_("Pokémon ID: {number}/{amount}").format(number=i, amount=len(pokemons))
            )
            embeds.append(embed)
        _id = await conf.pokeid()
        await menu(
            ctx, embeds, DEFAULT_CONTROLS if user != ctx.author else controls, page=_id - 1,
        )

    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.command()
    async def nick(self, ctx, id: int, *, nickname: str):
        """Set a pokémons nickname."""
        if id <= 0:
            return await ctx.send(_("The ID must be greater than 0!"))
        async with ctx.typing:
            result = self.cursor.execute(SELECT_POKEMON, (ctx.author.id,),).fetchall()
        pokemons = [None]
        for data in result:
            pokemons.append([json.loads(data[0]), data[1]])
        if not pokemons:
            return await ctx.send(_("You don't have any pokémon, trainer!"))
        if id > len(pokemons):
            return await ctx.send(_("You don't have a pokemon at that slot."))
        pokemon = pokemons[id]
        pokemon[0]["nickname"] = nickname
        self.cursor.execute(
            UPDATE_POKEMON, (ctx.author.id, pokemon[1], json.dumps(pokemon[0])),
        )
        await ctx.send(
            _("Your {pokemon} has been nicknamed `{nickname}`").format(
                pokemon=pokemon[0]["name"], nickname=nickname
            )
        )

    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.command(aliases=["free"])
    async def release(self, ctx, id: int):
        """Release a pokémon."""
        if id <= 0:
            return await ctx.send(_("The ID must be greater than 0!"))
        async with ctx.typing():
            result = self.cursor.execute(SELECT_POKEMON, (ctx.author.id,),).fetchall()
        pokemons = [None]
        for data in result:
            pokemons.append([json.loads(data[0]), data[1]])
        if not pokemons:
            return await ctx.send(_("You don't have any pokémon, trainer!"))
        if id >= len(pokemons):
            return await ctx.send(_("You don't have a pokemon at that slot."))
        pokemon = pokemons[id]
        name = self.get_name(pokemon[0]["name"], ctx.author)
        await ctx.send(
            _(
                "You are about to free {name}, if you wish to continue type `yes`, otherwise type `no`."
            ).format(name=name)
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
                msg += _(
                    "\nYour default pokemon may have changed. I have tried to account for this change."
                )
            elif id == pokeid:
                msg += _(
                    "\nYou have released your selected pokemon. I have reset your selected pokemon to your first pokemon."
                )
                await userconf.pokeid.set(1)
            self.cursor.execute(
                "DELETE FROM users where message_id = ?", (pokemon[1],),
            )
            await ctx.send(_("Your {name} has been freed.{msg}").format(name=name, msg=msg))
        else:
            await ctx.send(_("Operation cancelled."))

    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.command(usage="id_or_latest")
    @commands.guild_only()
    async def select(self, ctx, _id: Union[int, str]):
        """Select your default pokémon."""
        conf = await self.user_is_global(ctx.author)
        if not await conf.has_starter():
            return await ctx.send(
                _(
                    "You haven't chosen a starter pokemon yet, check out `{prefix}starter` for more information."
                ).format(prefix=ctx.clean_prefix)
            )
        async with ctx.typing():
            result = self.cursor.execute(
                """SELECT pokemon, message_id from users where user_id = ?""", (ctx.author.id,),
            ).fetchall()
            pokemons = [None]
            for data in result:
                pokemons.append([json.loads(data[0]), data[1]])
            if not pokemons:
                return await ctx.send(_("You don't have any pokemon to select."))
            if isinstance(_id, str):
                if _id == "latest":
                    _id = len(pokemons) - 1
                else:
                    await ctx.send(
                        _("Unidentified keyword, the only supported action is `latest` as of now.")
                    )
                    return
            if _id < 1 or _id > len(pokemons) - 1:
                return await ctx.send(_("You've specified an invalid ID."))
            await ctx.send(
                _("You have selected {pokemon} as your default pokémon.").format(
                    pokemon=self.get_name(pokemons[_id][0]["name"], ctx.author)
                )
            )
        conf = await self.user_is_global(ctx.author)
        await conf.pokeid.set(_id)
        await self.update_user_cache()

    @commands.command()
    @commands.max_concurrency(1, commands.BucketType.user)
    async def pokedex(self, ctx):
        """Check your caught pokémon!"""
        async with ctx.typing():
            result = self.cursor.execute(
                """SELECT pokemon, message_id from users where user_id = ?""", (ctx.author.id,),
            ).fetchall()
            pokemons = [None]
            for data in result:
                pokemons.append([json.loads(data[0]), data[1]])
            pokemonlist = copy.deepcopy(self.pokemonlist)
            for pokemon in pokemons[1:]:
                if isinstance(pokemon[0]["name"], str):
                    name = pokemon[0]["name"]
                else:
                    name = pokemon[0]["name"]["english"]
                if name in pokemonlist:
                    pokemonlist[name]["amount"] += 1
            a = [value for value in pokemonlist.items()]
            embeds = []
            total = 0
            page = 1
            for item in chunks(a, 20):
                embed = discord.Embed(
                    title=_("Pokédex"), color=await self.bot.get_embed_color(ctx.channel)
                )
                embed.set_footer(
                    text=_("Showing {page}-{lenpages} of {amount}.").format(
                        page=page, lenpages=page + len(item) - 1, amount=len(pokemonlist)
                    )
                )
                page += len(item)
                for pokemon in item:
                    if pokemon[1]["amount"] > 0:
                        total += 1
                        msg = _("{amount} caught! \N{WHITE HEAVY CHECK MARK}").format(
                            amount=pokemon[1]["amount"]
                        )
                    else:
                        msg = _("Not caught yet! \N{CROSS MARK}")
                    embed.add_field(name=f"{pokemon[0]} {pokemon[1]['id']}", value=msg)
                embeds.append(embed)
            embeds[0].description = _("You've caught {total} out of {amount} pokémon.").format(
                total=total, amount=len(pokemonlist)
            )
        await menu(ctx, embeds, DEFAULT_CONTROLS)
