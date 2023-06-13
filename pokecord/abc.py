from abc import ABC, abstractmethod

from redbot.core import Config, commands
from redbot.core.bot import Red


class MixinMeta(ABC):
    """Base class for well behaved type hint detection with composite class.
    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    def __init__(self, *_args):
        self.config: Config
        self.bot: Red
        self.datapath: str
        self.spawnedpokemon: dict
        self.maybe_spawn: dict
        self.guildcache: dict

    @abstractmethod
    async def is_global(self):
        raise NotImplementedError

    @abstractmethod
    async def user_is_global(self):
        raise NotImplementedError

    @abstractmethod
    def pokemon_choose(self):
        raise NotImplementedError

    @abstractmethod
    def get_name(self):
        raise NotImplementedError

    @commands.group(name="poke")
    async def poke(self, ctx: commands.Context):
        """
        Pokecord commands
        """
