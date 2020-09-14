import asyncio
import json

import discord
import tabulate
from redbot.core import bank
from redbot.core.errors import BalanceTooHigh
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import *
from redbot.core.utils.predicates import MessagePredicate

from .abc import MixinMeta
from .pokemixin import poke
from .statements import *

_ = Translator("Pokecord", __file__)


class TradeMixin(MixinMeta):
    """Pokecord Trading Commands"""

    @poke.command(usage="<user> <pokemon ID>")
    async def trade(self, ctx, user: discord.Member, *, id: int):
        """Pokecord Trading

        Currently a work in progress."""
        async with ctx.typing():
            result = self.cursor.execute(
                """SELECT pokemon, message_id from users where user_id = ?""",
                (ctx.author.id,),
            ).fetchall()
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
                "You are about to trade {name}, if you wish to continue type `yes`, otherwise type `no`."
            ).format(name=name)
        )
        try:
            pred = MessagePredicate.yes_or_no(ctx, user=ctx.author)
            await ctx.bot.wait_for("message", check=pred, timeout=20)
        except asyncio.TimeoutError:
            await ctx.send(_("Exiting operation."))
            return

        if pred.result:
            await ctx.send(
                _("How many credits would you like to recieve for {name}?").format(name=name)
            )
            try:
                amount = MessagePredicate.valid_int(ctx, user=ctx.author)
                await ctx.bot.wait_for("message", check=amount, timeout=20)
            except asyncio.TimeoutError:
                await ctx.send(_("Exiting operation."))
                return
            bal = amount.result
            if not await bank.can_spend(user, amount.result):
                await ctx.send(
                    _("{user} does not have {amount} {currency} available.").format(
                        user=user,
                        amount=amount.result,
                        currency=await bank.get_currency_name(ctx.guild if ctx.guild else None),
                    )
                )
                return
            await ctx.send(
                _(
                    "{user}, {author} would like to trade their {pokemon} for {amount} {currency}. Type `yes` to accept, otherwise type `no`."
                ).format(
                    user=user.mention,
                    author=ctx.author,
                    pokemon=name,
                    amount=bal,
                    currency=await bank.get_currency_name(ctx.guild if ctx.guild else None),
                )
            )
            try:
                authorconfirm = MessagePredicate.yes_or_no(ctx, user=user)
                await ctx.bot.wait_for("message", check=authorconfirm, timeout=30)
            except asyncio.TimeoutError:
                await ctx.send(_("Exiting operation."))
                return

            if authorconfirm.result:
                self.cursor.execute(
                    "DELETE FROM users where message_id = ?",
                    (pokemon[1],),
                )
                self.cursor.execute(
                    INSERT_POKEMON,
                    (user.id, ctx.message.id, json.dumps(pokemon[0])),
                )
                userconf = await self.user_is_global(ctx.author)
                pokeid = await userconf.pokeid()
                msg = ""
                if id < pokeid:
                    msg += _(
                        "{user}, your default pokemon may have changed. I have tried to account for this change."
                    ).format(user=ctx.author)
                    await userconf.pokeid.set(pokeid - 1)
                elif id == pokeid:
                    msg += _(
                        "{user}, You have traded your selected pokemon. I have reset your selected pokemon to your first pokemon."
                    ).format(user=user)
                    await userconf.pokeid.set(1)

                await bank.withdraw_credits(user, bal)
                try:
                    await bank.deposit_credits(ctx.author, bal)
                except BalanceTooHigh as e:
                    bal = e.max_balance - await bank.get_balance(ctx.author)
                    bal = _("{balance} (balance too high)").format(balanace=bal)
                    await bank.set_balance(ctx.author, e.max_balance)
                lst = [
                    ["-- {pokemon}".format(pokemon=name), bal],
                    [_("++ {balance} credits").format(balance=bal), name],
                ]
                await ctx.send(
                    box(tabulate.tabulate(lst, headers=[ctx.author, user]), lang="diff")
                )
                if msg:
                    await ctx.send(msg)

            else:
                await ctx.send(_("{user} has denied the trade request.").format(user=user))
                return

        else:
            await ctx.send(_("Trade cancelled."))
