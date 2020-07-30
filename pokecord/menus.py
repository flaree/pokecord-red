import asyncio
import contextlib
from typing import Any, Dict, Iterable, List, Optional, Union

import discord
import tabulate
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box
from redbot.vendored.discord.ext import menus

_ = Translator("Pokecord", __file__)


class PokeMenu(menus.MenuPages, inherit_buttons=False):
    def __init__(
        self,
        source: menus.PageSource,
        cog: Optional[commands.Cog] = None,
        ctx=None,
        user=None,
        clear_reactions_after: bool = True,
        delete_message_after: bool = True,
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
        return not self.ctx.author == self.user

    @menus.button("\N{BLACK LEFT-POINTING TRIANGLE}", position=menus.First(0))
    async def prev(self, payload: discord.RawReactionActionEvent):
        if self.current_page == 0:
            await self.show_page(self._source.get_max_pages() - 1)
        else:
            await self.show_checked_page(self.current_page - 1)

    @menus.button("\N{CROSS MARK}", position=menus.First(1))
    async def stop_pages_default(self, payload: discord.RawReactionActionEvent) -> None:
        self.stop()

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
            msg = await self.bot.wait_for(
                "message_without_command",
                check=lambda m: m.author.id in (*self.bot.owner_ids, self._author_id),
                timeout=10.0,
            )
            jump_page = int(msg.content)
            if int(msg.content) > self._source.get_max_pages():
                await self.ctx.send(_("Invalid Pokémon ID, jumping to the end."), delete_after=5)
                jump_page = self._source.get_max_pages()
            await self.show_checked_page(jump_page - 1)
            await cleanup([prompt, msg])
        except (ValueError, asyncio.TimeoutError):
            await cleanup([prompt, msg])

    @menus.button("\N{WHITE HEAVY CHECK MARK}", position=menus.First(3), skip_if=_cant_select)
    async def select(self, payload: discord.RawReactionActionEvent):
        command = self.ctx.bot.get_command("select")
        await self.ctx.invoke(command, _id=self.current_page + 1)


class PokeList(menus.ListPageSource):
    def __init__(self, entries: Iterable[str]):
        super().__init__(entries, per_page=1)

    async def format_page(self, menu: PokeMenu, pokemon: Dict) -> str:
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
            headers=[_("Stats"), _("Value")],
        )
        nick = pokemon.get("nickname")
        alias = _("**Nickname**: {nick}\n").format(nick=nick) if nick is not None else ""
        variant = (
            _("**Variant**: {variant}\n").format(variant=pokemon.get("variant"))
            if pokemon.get("variant")
            else ""
        )
        desc = _(
            "**ID**: {id}\n{alias}**Level**: {level}\n**XP**: {xp}/{totalxp}\n{variant}{stats}"
        ).format(
            id=f"#{pokemon.get('id')}" if pokemon.get("id") else "0",
            alias=alias,
            level=pokemon["level"],
            variant=variant,
            xp=pokemon["xp"],
            totalxp=menu.cog.calc_xp(pokemon["level"]),
            stats=box(pokestats, lang="prolog"),
        )
        embed = discord.Embed(
            title=menu.cog.get_name(pokemon["name"], menu.ctx.author), description=desc
        )
        if pokemon.get("id"):
            embed.set_thumbnail(
                url=f"https://assets.pokemon.com/assets/cms2/img/pokedex/detail/{str(pokemon['id']).zfill(3)}.png"
                if not pokemon.get("url")
                else pokemon.get("url")
            )
        embed.set_footer(
            text=_("Pokémon ID: {number}/{amount}").format(
                number=pokemon["sid"], amount=self.get_max_pages()
            )
        )
        return embed
