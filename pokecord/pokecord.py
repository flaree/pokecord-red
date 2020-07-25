import asyncio
import concurrent.futures
import datetime
import json
import logging
import random
import string
from abc import ABC

import discord
from redbot.core import Config, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import escape

import apsw

from .general import GeneralMixin
from .settings import SettingsMixin
from .statements import *
from .trading import TradeMixin

log = logging.getLogger("red.flare.pokecord")

_ = Translator("Pokecord", __file__)


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's
    metaclass."""


@cog_i18n(_)
class Pokecord(
    TradeMixin, SettingsMixin, GeneralMixin, commands.Cog, metaclass=CompositeMetaClass
):
    """Pokecord adapted to use on Red."""

    __version__ = "0.0.1-realllllly-pre-alpha-12"
    __author__ = "flare"

    def format_help_for_context(self, ctx):
        """Thanks Sinbad."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\nAuthor: {self.__author__}\nCog Version: {self.__version__}"

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=95932766180343808, force_registration=True)
        self.config.register_global(
            isglobal=True,
            hashed=False,
            hashes={},
            spawnchance=[20, 120],
            hintcost=1000,
            spawnloop=False,
        )
        defaults_guild = {"activechannels": [], "toggle": False, "whitelist": [], "blacklist": []}
        self.config.register_guild(**defaults_guild)
        defaults_user = {
            "pokeids": {},
            "silence": False,
            "timestamp": 0,
            "pokeid": 1,
            "has_starter": False,
            "locale": "en",
        }
        self.config.register_user(**defaults_user)
        self.config.register_member(**defaults_user)
        self.datapath = f"{bundled_data_path(self)}"
        self.spawnedpokemon = {}
        self.maybe_spawn = {}
        self.guildcache = {}
        self.usercache = {}
        self.spawnchance = []
        self._connection = apsw.Connection(str(cog_data_path(self) / "pokemon.db"))
        self.cursor = self._connection.cursor()
        self.cursor.execute(PRAGMA_journal_mode)
        self.cursor.execute(PRAGMA_wal_autocheckpoint)
        self.cursor.execute(PRAGMA_read_uncommitted)
        self.cursor.execute(POKECORD_CREATE_POKECORD_TABLE)
        self._executor = concurrent.futures.ThreadPoolExecutor(1)
        self.bg_loop_task = None

    def cog_unload(self):
        self._executor.shutdown()
        if self.bg_loop_task:
            self.bg_loop_task.cancel()

    async def initalize(self):
        with open(f"{self.datapath}/pokedex.json", encoding="utf-8") as f:
            self.pokemondata = json.load(f)
            self.spawnchances = [x["spawnchance"] for x in self.pokemondata]
            self.pokemonlist = {
                pokemon["id"]: {
                    "name": pokemon["name"],
                    "amount": 0,
                    "id": f"#{str(pokemon['id']).zfill(3)}",
                }
                for pokemon in self.pokemondata
            }
        with open(f"{self.datapath}/evolve.json") as f:
            self.evolvedata = json.load(f)
        # if not await self.config.hashed():
        #     hashes = {}
        #     for file in os.listdir(f"{self.datapath}/pokemon/"):
        #         if file.endswith(".png"):
        #             cmd = (
        #                 base64.b64decode(
        #                     b"aGFzaGVzW2ZpbGVdID0gaGFzaGxpYi5tZDUoSW1hZ2Uub3BlbihyJ3tzZWxmLmRhdGFwYXRofS97ZmlsZX0nKS50b2J5dGVzKCkpLmhleGRpZ2VzdCgp"
        #                 )
        #                 .decode("utf-8")
        #                 .replace("'", '"')
        #                 .replace(r"{self.datapath}", f"{self.datapath}/pokemon/")
        #                 .replace(r"{file}", file)
        #             )
        #             exec(cmd)
        #     await self.config.hashes.set(hashes)
        #     await self.config.hashed.set(True)
        await self.update_guild_cache()
        await self.update_spawn_chance()
        await self.update_user_cache()
        if await self.config.spawnloop():
            self.bg_loop_task = self.bot.loop.create_task(self.random_spawn())

    async def random_spawn(self):
        await self.bot.wait_until_ready()
        log.debug("Starting loop for random spawns.")
        while True:
            try:
                for guild in self.guildcache:
                    if (
                        self.guildcache[guild]["toggle"]
                        and self.guildcache[guild]["activechannels"]
                    ):
                        if random.randint(1, 2) == 2:
                            continue
                        _guild = self.bot.get_guild(int(guild))
                        if _guild is None:
                            continue
                        channel = _guild.get_channel(
                            int(random.choice(self.guildcache[guild]["activechannels"]))
                        )
                        if channel is None:
                            continue
                        await self.spawn_pokemon(channel)
                await asyncio.sleep(2400)
            except Exception as exc:
                log.error("Exception in pokemon auto spawning: ", exc_info=exc)

    async def update_guild_cache(self):
        self.guildcache = await self.config.all_guilds()

    async def update_user_cache(self):
        self.usercache = await self.config.all_users()  # TODO: Support guild

    async def update_spawn_chance(self):
        self.spawnchance = await self.config.spawnchance()

    async def is_global(self, guild):
        toggle = await self.config.isglobal()
        if toggle:
            return self.config
        return self.config.guild(guild)

    async def user_is_global(self, user):
        toggle = await self.config.isglobal()
        if toggle:
            return self.config.user(user)
        return self.config.member(user)

    def pokemon_choose(self):
        # num = random.randint(1, 200)
        # if num > 2:
        return self.pokemondata[1]
        return random.choices(self.pokemondata, weights=self.spawnchances, k=1)[0]
        # return random.choice(self.pokemondata["mega"])

    def get_name(self, names, user):
        if isinstance(names, str):
            return names
        userconf = self.usercache.get(user.id)
        if userconf is None:
            return names["english"]
        localnames = {
            "en": names["english"],
            "fr": names["french"],
            "cn": names["chinese"],
            "jp": names["japanese"],
        }
        return localnames[self.usercache[user.id]["locale"]]

    @commands.command()
    async def starter(self, ctx, pokemon: str = None):
        """Choose your starter pokémon!"""
        conf = await self.user_is_global(ctx.author)
        if await conf.has_starter():
            return await ctx.send(_("You've already claimed your starter pokemon!"))
        if pokemon is None:
            msg = _(
                "Hey there trainer! Welcome to Pokecord. This is a ported plugin version of Pokecord adopted for use on Red.\n"
                "In order to get catchin' you must pick one of the starter Pokemon as listed below.\n"
                "**Generation 1**\nBulbasaur, Charmander and Squirtle\n"
                "**Generation 2**\nChikorita, Cyndaquil, Totodile\n"
                "**Generation 3**\nTreecko, Torchic, Mudkip\n"
                "**Generation 4**\nTurtwig, Chimchar, Piplup\n"
                "**Generation 5**\nSnivy, Tepig, Oshawott\n"
                "**Generation 6**\nChespin, Fennekin, Froakie\n"
                "**Generation 7**\nRowlet, Litten, Popplio\n"
                "**Generation 8**\nGrookey, Scorbunny, Sobble\n"
                "\nTo pick a pokemon, type {prefix}starter <pokemon>".format(
                    prefix=ctx.clean_prefix
                )
            )
            await ctx.send(msg)
            return
        starter_pokemon = {
            "bulbasaur": self.pokemondata[0],
            "charmander": self.pokemondata[3],
            "squirtle": self.pokemondata[6],
            "chikorita": self.pokemondata[151],
            "cyndaquil": self.pokemondata[154],
            "totodile": self.pokemondata[157],
            "treecko": self.pokemondata[251],
            "torchic": self.pokemondata[254],
            "mudkip": self.pokemondata[257],
            "turtwig": self.pokemondata[386],
            "chimchar": self.pokemondata[389],
            "piplup": self.pokemondata[392],
            "snivy": self.pokemondata[494],
            "tepig": self.pokemondata[497],
            "oshawott": self.pokemondata[500],
            "chespin": self.pokemondata[649],
            "fennekin": self.pokemondata[652],
            "froakie": self.pokemondata[655],
            "rowlet": self.pokemondata[721],
            "litten": self.pokemondata[724],
            "popplio": self.pokemondata[727],
            "grookey": self.pokemondata[809],
            "scorbunny": self.pokemondata[812],
            "sobble": self.pokemondata[815],
        }
        if pokemon.lower() not in starter_pokemon.keys():
            await ctx.send(_("That's not a valid starter pokémon, trainer!"))
            return
        await ctx.send(
            _("You've chosen {pokemon} as your starter pokémon!").format(pokemon=pokemon.title())
        )
        pokemon = starter_pokemon[pokemon.lower()]
        pokemon["level"] = 0
        pokemon["xp"] = 0

        self.cursor.execute(
            INSERT_POKEMON, (ctx.author.id, ctx.message.id, json.dumps(pokemon),),
        )
        await conf.has_starter.set(True)

    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.member)
    async def hint(self, ctx):
        """Get a hint on the pokémon!"""
        if self.spawnedpokemon.get(ctx.guild.id) is not None:
            pokemonspawn = self.spawnedpokemon[ctx.guild.id].get(ctx.channel.id)
            if pokemonspawn is not None:
                name = self.get_name(pokemonspawn["name"], ctx.author)
                inds = [i for i, _ in enumerate(name)]
                if len(name) > 6:
                    amount = len(name) - random.randint(2, 4)
                else:
                    amount = random.randint(3, 4)
                sam = random.sample(inds, amount)

                lst = list(name)
                for ind in sam:
                    if lst[ind] != " ":
                        lst[ind] = "_"
                word = "".join(lst)
                await ctx.send(
                    _("This wild pokemon is a {pokemonhint}.").format(
                        pokemonhint=escape(word, formatting=True)
                    )
                )
                return
        await ctx.send(_("No pokemon is ready to be caught."))

    @commands.command()
    async def catch(self, ctx, *, pokemon: str):
        """Catch a pokemon!"""
        conf = await self.user_is_global(ctx.author)
        if not await conf.has_starter():
            return await ctx.send(
                _(
                    "You haven't chosen a starter pokemon yet, check out `{prefix}starter` for more information."
                ).format(prefix=ctx.clean_prefix)
            )
        if self.spawnedpokemon.get(ctx.guild.id) is not None:
            pokemonspawn = self.spawnedpokemon[ctx.guild.id].get(ctx.channel.id)
            if pokemonspawn is not None:
                names = set(pokemonspawn["name"][name].lower() for name in pokemonspawn["name"])
                names.add(
                    pokemonspawn["name"]["english"]
                    .translate(str.maketrans("", "", string.punctuation))
                    .lower()
                )
                if pokemonspawn.get("alias"):
                    names.add(pokemonspawn["alias"])
                if pokemon.lower() in names:
                    if self.spawnedpokemon.get(ctx.guild.id) is not None and self.spawnedpokemon[
                        ctx.guild.id
                    ].get(ctx.channel.id):
                        del self.spawnedpokemon[ctx.guild.id][ctx.channel.id]
                    else:
                        await ctx.send("No pokemon is ready to be caught.")
                        return
                    lvl = random.randint(1, 13)
                    pokename = self.get_name(pokemonspawn["name"], ctx.author)
                    await ctx.send(
                        _(
                            "Congratulations {user}! You've caught a level {lvl} {pokename}!"
                        ).format(
                            user=ctx.author.mention, lvl=lvl, pokename=pokename,
                        )
                    )
                    async with conf.pokeids() as poke:
                        if str(pokemonspawn["id"]) not in poke:
                            await ctx.send(
                                _("{pokename} has been added to the pokédex.").format(
                                    pokename=pokename
                                )
                            )
                            poke[str(pokemonspawn["id"])] = 1
                        else:
                            poke[str(pokemonspawn["id"])] += 1
                    pokemonspawn["level"] = lvl
                    pokemonspawn["xp"] = 0
                    self.cursor.execute(
                        INSERT_POKEMON, (ctx.author.id, ctx.message.id, json.dumps(pokemonspawn)),
                    )
                    return
                else:
                    return await ctx.send(_("That's not the correct pokemon"))
        await ctx.send(_("No pokemon is ready to be caught."))

    def spawn_chance(self, guildid):
        return self.maybe_spawn[guildid]["amount"] > self.maybe_spawn[guildid]["spawnchance"]

    # async def get_hash(self, pokemon):
    #     return (await self.config.hashes()).get(pokemon, None)

    @commands.Cog.listener()
    async def on_message_without_command(self, message):
        if not message.guild:
            return
        if message.author.bot:
            return
        guildcache = self.guildcache.get(message.guild.id)
        if guildcache is None:
            return
        if not guildcache["toggle"]:
            return
        await self.exp_gain(message.channel, message.author)
        if guildcache["whitelist"]:
            if message.channel.id not in guildcache["whitelist"]:
                return
        elif guildcache["blacklist"]:
            if message.channel.id in guildcache["blacklist"]:
                return
        if message.guild.id not in self.maybe_spawn:
            self.maybe_spawn[message.guild.id] = {
                "amount": 1,
                "spawnchance": 3,  # random.randint(self.spawnchance[0], self.spawnchance[1]),
                "time": datetime.datetime.utcnow().timestamp(),
                "author": message.author.id,
            }  # TODO: big value
        # if (
        #     self.maybe_spawn[message.guild.id]["author"] == message.author.id
        # ):  # stop spamming to spawn
        #     if (
        #         datetime.datetime.utcnow().timestamp() - self.maybe_spawn[message.guild.id]["time"]
        #     ) < 5:
        #         return
        self.maybe_spawn[message.guild.id]["amount"] += 1
        should_spawn = self.spawn_chance(message.guild.id)
        if not should_spawn:
            return
        del self.maybe_spawn[message.guild.id]
        if not guildcache["activechannels"]:
            channel = message.channel
        else:
            channel = message.guild.get_channel(int(random.choice(guildcache["activechannels"])))
            if channel is None:
                return  # TODO: Remove channel from config
        await self.spawn_pokemon(channel)

    async def spawn_pokemon(self, channel):
        if channel.guild.id not in self.spawnedpokemon:
            self.spawnedpokemon[channel.guild.id] = {}
        pokemon = self.pokemon_choose()
        print(pokemon)
        self.spawnedpokemon[channel.guild.id][channel.id] = pokemon
        prefixes = await self.bot.get_valid_prefixes(guild=channel.guild)
        embed = discord.Embed(
            title=_("‌‌A wild pokémon has аppeаred!"),
            description=_(
                "Guess the pokémon аnd type {prefix}catch <pokémon> to cаtch it!"
            ).format(prefix=prefixes[0]),
            color=await self.bot.get_embed_color(channel),
        )
        # name = pokemon["name"] if pokemon["alias"] is None else pokemon["alias"]
        log.debug(f"{pokemon['name']['english']} has spawned in {channel} on {channel.guild}")
        # hashe = await self.get_hash(f"{name}.png")
        # if hashe is None:
        #     return
        embed.set_image(
            url=f"https://assets.pokemon.com/assets/cms2/img/pokedex/detail/{str(pokemon['id']).zfill(3)}.png"  # TODO: Hashed images again
        )
        await channel.send(embed=embed)

    def calc_xp(self, lvl):
        return 25 * lvl

    async def exp_gain(self, channel, user):
        # conf = await self.user_is_global(user) # TODO: guild based
        userconf = self.usercache.get(user.id)
        if userconf is None:
            return
        if datetime.datetime.utcnow().timestamp() - userconf["timestamp"] < 10:
            return
        self.usercache[user.id][
            "timestamp"
        ] = datetime.datetime.utcnow().timestamp()  # Try remove a race condition
        await self.config.user(user).timestamp.set(
            datetime.datetime.utcnow().timestamp()
        )  # TODO: guild based
        await self.update_user_cache()
        result = self.cursor.execute(SELECT_POKEMON, (user.id,)).fetchall()
        pokemons = []
        for data in result:
            pokemons.append([json.loads(data[0]), data[1]])
        if not pokemons:
            return
        index = userconf["pokeid"] - 1
        pokemon = None
        if userconf["pokeid"] > len(pokemons):
            index = 0
        if pokemons[index][0]["level"] < 100:
            pokemon = pokemons[index][0]
            msg_id = pokemons[index][1]
        else:
            for i, poke in enumerate(pokemons):
                if poke[0]["level"] < 100:
                    pokemon = poke[0]
                    msg_id = poke[1]
                    break
        if pokemon is None:
            return  # No pokemon available to lvl up
        xp = random.randint(5, 25) + (pokemon["level"] // 2)
        pokemon["xp"] += xp
        if pokemon["xp"] >= self.calc_xp(pokemon["level"]):
            pokemon["level"] += 1
            pokemon["xp"] = 0
            if isinstance(pokemon["name"], str):
                pokename = pokemon["name"]
            else:
                pokename = pokemon["name"]["english"]
            evolve = self.evolvedata.get(pokename)
            name = (
                self.get_name(pokemon["name"], user)
                if pokemon.get("nickname") is None
                else f'"{pokemon.get("nickname")}"'
            )
            if evolve is not None and (pokemon["level"] >= int(evolve["level"])):
                lvl = pokemon["level"]
                nick = pokemon.get("nickname")
                pokemon = next(
                    (
                        item
                        for item in self.pokemondata
                        if item["name"]["english"] == evolve["evolution"]
                    ),
                    None,
                )  # Make better
                if nick is not None:
                    pokemon["nickname"] = nick
                if pokemon is None:
                    log.info(
                        f"Error occured trying to find {evolve['evolution']} for an evolution."
                    )
                    return
                pokemon["xp"] = 0
                pokemon["level"] = lvl
                if not userconf["silence"]:
                    embed = discord.Embed(
                        title=_("Congratulations {user}!").format(user=user),
                        description=_("Your {name} has evolved into {evolvename}!").format(
                            name=name, evolvename=self.get_name(pokemon["name"], user)
                        ),
                        color=await self.bot.get_embed_color(channel),
                    )
                    if channel.permissions_for(channel.guild.me).send_messages:
                        await channel.send(embed=embed)
                log.debug(f"{name} has evolved into {pokemon['name']} for {user}.")
            else:
                log.debug(f"{pokemon['name']} levelled up for {user}")
                for stat in pokemon["stats"]:
                    pokemon["stats"][stat] = int(pokemon["stats"][stat]) + random.randint(1, 3)
                if not userconf["silence"]:
                    embed = discord.Embed(
                        title=_("Congratulations {user}!").format(user=user),
                        description=_("Your {name} has levelled up to level {level}!").format(
                            name=name, level=pokemon["level"]
                        ),
                        color=await self.bot.get_embed_color(channel),
                    )
                    if channel.permissions_for(channel.guild.me).send_messages:
                        await channel.send(embed=embed)
        self.cursor.execute(
            UPDATE_POKEMON, (user.id, msg_id, json.dumps(pokemon)),
        )
