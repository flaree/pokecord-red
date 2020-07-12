import asyncio
import json
import urllib

import discord
import tabulate
from redbot.core import commands
from redbot.core.utils.chat_formatting import *
from redbot.core.utils.menus import DEFAULT_CONTROLS, close_menu, menu, next_page, prev_page
from redbot.core.utils.predicates import MessagePredicate

from .abc import MixinMeta
from .functions import select_pokemon
from .statements import *


class TradeMixin(MixinMeta):
    """Pokecord Trading Commands"""

    @commands.command()
    async def trade(self, ctx):
        """Pokecord Trading"""
        pass
