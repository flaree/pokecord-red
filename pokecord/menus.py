import asyncio
import contextlib
from typing import Any, Dict, Iterable, List, Optional

import discord
import tabulate
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.predicates import MessagePredicate
from redbot.vendored.discord.ext import menus

from .functions import poke_embed

_ = Translator("Pokecord", __file__)


class PokeListMenu(menus.MenuPages, inherit_buttons=False):
    def __init__(
        self,
        source: menus.PageSource,
        cog: Optional[commands.Cog] = None,
        ctx=None,
        user=None,
        clear_reactions_after: bool = True,
        delete_message_after: bool = False,
        add_reactions: bool = True,
        using_custom_emoji: bool = False,
        using_embeds: bool = False,
        keyword_to_reaction_mapping: Dict[str, str] = None,
        timeout: int = 180,
        message: discord.Message = None,
        **kwargs: Any,
    ) -> None:
        self.cog = cog
        self.ctx = ctx
        self.user = user
        super().__init__(
            source,
            clear_reactions_after=clear_reactions_after,
            delete_message_after=delete_message_after,
            check_embeds=using_embeds,
            timeout=timeout,
            message=message,
            **kwargs,
        )

    def reaction_check(self, payload):
        """The function that is used to check whether the payload should be processed.
        This is passed to :meth:`discord.ext.commands.Bot.wait_for <Bot.wait_for>`.

        There should be no reason to override this function for most users.

        Parameters
        ------------
        payload: :class:`discord.RawReactionActionEvent`
            The payload to check.

        Returns
        ---------
        :class:`bool`
            Whether the payload should be processed.
        """
        if payload.message_id != self.message.id:
            return False
        if payload.user_id not in (*self.bot.owner_ids, self._author_id):
            return False

        return payload.emoji in self.buttons

    def _cant_select(self):
        return self.ctx.author != self.user

    @menus.button("\N{BLACK LEFT-POINTING TRIANGLE}", position=menus.First(0))
    async def prev(self, payload: discord.RawReactionActionEvent):
        if self.current_page == 0:
            await self.show_page(self._source.get_max_pages() - 1)
        else:
            await self.show_checked_page(self.current_page - 1)

    @menus.button("\N{CROSS MARK}", position=menus.First(1))
    async def stop_pages_default(self, payload: discord.RawReactionActionEvent) -> None:
        self.stop()
        with contextlib.suppress(discord.NotFound):
            await self.message.delete()

    @menus.button("\N{BLACK RIGHT-POINTING TRIANGLE}", position=menus.First(2))
    async def next(self, payload: discord.RawReactionActionEvent):
        if self.current_page == self._source.get_max_pages() - 1:
            await self.show_page(0)
        else:
            await self.show_checked_page(self.current_page + 1)

    @menus.button("\N{LEFT-POINTING MAGNIFYING GLASS}", position=menus.First(4))
    async def number_page(self, payload: discord.RawReactionActionEvent):
        async def cleanup(messages: List[discord.Message]):
            with contextlib.suppress(discord.HTTPException):
                for msg in messages:
                    await msg.delete()

        prompt = await self.ctx.send(_("Please select the Pokémon ID number to jump to."))
        try:
            pred = MessagePredicate.valid_int(self.ctx)
            msg = await self.bot.wait_for(
                "message_without_command",
                check=pred,
                timeout=10.0,
            )
            if pred.result:
                jump_page = int(msg.content)
                if jump_page > self._source.get_max_pages():
                    await self.ctx.send(
                        _("Invalid Pokémon ID, jumping to the end."), delete_after=5
                    )
                    jump_page = self._source.get_max_pages()
                await self.show_checked_page(jump_page - 1)
                await cleanup([prompt, msg])
        except (asyncio.TimeoutError):
            await cleanup([prompt])

    @menus.button("\N{WHITE HEAVY CHECK MARK}", position=menus.First(3), skip_if=_cant_select)
    async def select(self, payload: discord.RawReactionActionEvent):
        command = self.ctx.bot.get_command("select")
        await self.ctx.invoke(command, _id=self.current_page + 1)


class PokeList(menus.ListPageSource):
    def __init__(self, entries: Iterable[str]):
        super().__init__(entries, per_page=1)

    async def format_page(self, menu: PokeListMenu, pokemon: Dict) -> str:
        embed = await poke_embed(menu.cog, menu.ctx, pokemon, menu=self)
        return embed


class GenericMenu(menus.MenuPages, inherit_buttons=False):
    def __init__(
        self,
        source: menus.PageSource,
        cog: Optional[commands.Cog] = None,
        len_poke: Optional[int] = 0,
        clear_reactions_after: bool = True,
        delete_message_after: bool = False,
        add_reactions: bool = True,
        using_custom_emoji: bool = False,
        using_embeds: bool = False,
        keyword_to_reaction_mapping: Dict[str, str] = None,
        timeout: int = 180,
        message: discord.Message = None,
        **kwargs: Any,
    ) -> None:
        self.cog = cog
        self.len_poke = len_poke
        super().__init__(
            source,
            clear_reactions_after=clear_reactions_after,
            delete_message_after=delete_message_after,
            check_embeds=using_embeds,
            timeout=timeout,
            message=message,
            **kwargs,
        )

    def reaction_check(self, payload):
        """The function that is used to check whether the payload should be processed.
        This is passed to :meth:`discord.ext.commands.Bot.wait_for <Bot.wait_for>`.
        There should be no reason to override this function for most users.
        Parameters
        ------------
        payload: :class:`discord.RawReactionActionEvent`
            The payload to check.
        Returns
        ---------
        :class:`bool`
            Whether the payload should be processed.
        """
        if payload.message_id != self.message.id:
            return False
        if payload.user_id not in (*self.bot.owner_ids, self._author_id):
            return False

        return payload.emoji in self.buttons

    def _skip_single_arrows(self):
        max_pages = self._source.get_max_pages()
        if max_pages is None:
            return True
        return max_pages == 1

    def _skip_double_triangle_buttons(self):
        max_pages = self._source.get_max_pages()
        if max_pages is None:
            return True
        return max_pages <= 2

    # left
    @menus.button(
        "\N{BLACK LEFT-POINTING TRIANGLE}",
        position=menus.First(1),
        skip_if=_skip_single_arrows,
    )
    async def prev(self, payload: discord.RawReactionActionEvent):
        if self.current_page == 0:
            await self.show_page(self._source.get_max_pages() - 1)
        else:
            await self.show_checked_page(self.current_page - 1)

    @menus.button("\N{CROSS MARK}", position=menus.First(2))
    async def stop_pages_default(self, payload: discord.RawReactionActionEvent) -> None:
        self.stop()
        with contextlib.suppress(discord.NotFound):
            await self.message.delete()

    @menus.button(
        "\N{BLACK RIGHT-POINTING TRIANGLE}",
        position=menus.First(2),
        skip_if=_skip_single_arrows,
    )
    async def next(self, payload: discord.RawReactionActionEvent):
        if self.current_page == self._source.get_max_pages() - 1:
            await self.show_page(0)
        else:
            await self.show_checked_page(self.current_page + 1)

    @menus.button(
        "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
        position=menus.First(0),
        skip_if=_skip_double_triangle_buttons,
    )
    async def go_to_first_page(self, payload):
        """go to the first page"""
        await self.show_page(0)

    @menus.button(
        "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
        position=menus.Last(1),
        skip_if=_skip_double_triangle_buttons,
    )
    async def go_to_last_page(self, payload):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(self._source.get_max_pages() - 1)


class SearchFormat(menus.ListPageSource):
    def __init__(self, entries: Iterable[str]):
        super().__init__(entries, per_page=1)

    async def format_page(self, menu: GenericMenu, string: str) -> str:
        embed = discord.Embed(
            title="Pokemon Search",
            color=await menu.ctx.embed_color(),
            description=string,
        )
        embed.set_footer(
            text=_("Page {page}/{amount}").format(
                page=menu.current_page + 1, amount=menu._source.get_max_pages()
            )
        )
        return embed


class PokedexFormat(menus.ListPageSource):
    def __init__(self, entries: Iterable[str]):
        super().__init__(entries, per_page=1)

    async def format_page(self, menu: GenericMenu, item: List) -> str:
        embed = discord.Embed(title=_("Pokédex"), color=await menu.ctx.embed_colour())
        embed.set_footer(
            text=_("Showing {page}-{lenpages} of {amount}.").format(
                page=item[0][0], lenpages=item[-1][0], amount=menu.len_poke
            )
        )
        for pokemon in item:
            if pokemon[1]["amount"] > 0:
                msg = _("{amount} caught! \N{WHITE HEAVY CHECK MARK}").format(
                    amount=pokemon[1]["amount"]
                )
            else:
                msg = _("Not caught yet! \N{CROSS MARK}")
            embed.add_field(
                name="{pokemonname} {pokemonid}".format(
                    pokemonname=menu.cog.get_name(pokemon[1]["name"], menu.ctx.author),
                    pokemonid=pokemon[1]["id"],
                ),
                value=msg,
            )
        if menu.current_page == 0:
            embed.description = _("You've caught {total} out of {amount} pokémon.").format(
                total=len(await menu.cog.config.user(menu.ctx.author).pokeids()),
                amount=menu.len_poke,
            )
        return embed
