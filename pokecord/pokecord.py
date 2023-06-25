import asyncio
import concurrent.futures
import datetime
import json
import logging
import random
import string
from abc import ABC

import apsw
import discord
from databases import Database
from redbot.core import Config, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import escape, humanize_list

from .dev import Dev
from .general import GeneralMixin
from .settings import SettingsMixin
from .statements import *
from .trading import TradeMixin

log = logging.getLogger("red.flare.pokecord")

PUNCT = string.punctuation + "’"
_ = Translator("Pokecord", __file__)
GENDERS = [
    "Male \N{MALE SIGN}\N{VARIATION SELECTOR-16}",
    "Female \N{FEMALE SIGN}\N{VARIATION SELECTOR-16}",
]
_MIGRATION_VERSION = 9


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's
    metaclass."""


@cog_i18n(_)
class Pokecord(
    Dev,
    TradeMixin,
    SettingsMixin,
    GeneralMixin,
    commands.Cog,
    metaclass=CompositeMetaClass,
):
    """Pokecord adapted to use on Red."""

    __version__ = "0.0.1-alpha-23"
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
            migration=1,
        )
        defaults_guild = {
            "activechannels": [],
            "toggle": False,
            "whitelist": [],
            "blacklist": [],
            "levelup_messages": False,
        }
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
        self.config.register_channel(pokemon=None)
        self.datapath = f"{bundled_data_path(self)}"
        self.maybe_spawn = {}
        self.guildcache = {}
        self.usercache = {}
        self.spawnchance = []
        self.cursor = Database(f"sqlite:///{cog_data_path(self)}/pokemon.db")
        self._executor = concurrent.futures.ThreadPoolExecutor(1)
        self.bg_loop_task = None

    def cog_unload(self):
        self._executor.shutdown()
        if self.bg_loop_task:
            self.bg_loop_task.cancel()

    async def initalize(self):
        await self.cursor.connect()
        await self.cursor.execute(PRAGMA_journal_mode)
        await self.cursor.execute(PRAGMA_wal_autocheckpoint)
        await self.cursor.execute(PRAGMA_read_uncommitted)
        await self.cursor.execute(POKECORD_CREATE_POKECORD_TABLE)
        with open(f"{self.datapath}/pokedex.json", encoding="utf-8") as f:
            pdata = json.load(f)
        with open(f"{self.datapath}/evolve.json", encoding="utf-8") as f:
            self.evolvedata = json.load(f)
        with open(f"{self.datapath}/genders.json", encoding="utf-8") as f:
            self.genderdata = json.load(f)
        with open(f"{self.datapath}/shiny.json", encoding="utf-8") as f:
            sdata = json.load(f)
        with open(f"{self.datapath}/legendary.json", encoding="utf-8") as f:
            ldata = json.load(f)
        with open(f"{self.datapath}/mythical.json", encoding="utf-8") as f:
            mdata = json.load(f)
        with open(f"{self.datapath}/galarian.json", encoding="utf-8") as f:
            gdata = json.load(f)
        with open(f"{self.datapath}/hisuian.json", encoding="utf-8") as f:
            gdata = json.load(f)
        with open(f"{self.datapath}/alolan.json", encoding="utf-8") as f:
            adata = json.load(f)
        with open(f"{self.datapath}/megas.json", encoding="utf-8") as f:
            megadata = json.load(f)
        self.pokemondata = pdata + sdata + ldata + mdata + gdata + adata + megadata
        with open(f"{self.datapath}/url.json", encoding="utf-8") as f:
            url = json.load(f)
        for pokemon in self.pokemondata:
            name = (
                pokemon["name"]["english"]
                if not pokemon.get("variant")
                else pokemon.get("alias")
                if pokemon.get("alias")
                else pokemon["name"]["english"]
            )
            if "shiny" in name.lower():
                continue
            link = url[name]
            if isinstance(link, list):
                link = link[0]
            pokemon["url"] = link

        self.spawnchances = [x["spawnchance"] for x in self.pokemondata]
        self.pokemonlist = {
            pokemon["id"]: {
                "name": pokemon["name"],
                "amount": 0,
                "id": f"#{str(pokemon['id']).zfill(3)}",
            }
            for pokemon in sorted((self.pokemondata), key=lambda x: x["id"])
        }
        if await self.config.migration() < _MIGRATION_VERSION:
            self.usercache = await self.config.all_users()
            for user in self.usercache:
                await self.config.user_from_id(user).pokeids.clear()
                result = await self.cursor.fetch_all(
                    query=SELECT_POKEMON,
                    values={"user_id": user},
                )
                async with self.config.user_from_id(user).pokeids() as pokeids:
                    for data in result:
                        poke = json.loads(data[0])
                        if str(poke["id"]) not in pokeids:

                            pokeids[str(poke["id"])] = 1
                        else:
                            pokeids[str(poke["id"])] += 1

                        if not poke.get("gender", False):
                            if isinstance(poke["name"], str):
                                poke["gender"] = self.gender_choose(poke["name"])
                            else:
                                poke["gender"] = self.gender_choose(poke["name"]["english"])

                        if not poke.get("ivs", False):
                            poke["ivs"] = {
                                "HP": random.randint(0, 31),
                                "Attack": random.randint(0, 31),
                                "Defence": random.randint(0, 31),
                                "Sp. Atk": random.randint(0, 31),
                                "Sp. Def": random.randint(0, 31),
                                "Speed": random.randint(0, 31),
                            }

                        await self.cursor.execute(
                            query=UPDATE_POKEMON,
                            values={
                                "user_id": user,
                                "message_id": data[1],
                                "pokemon": json.dumps(poke),
                            },
                        )
                await self.config.migration.set(_MIGRATION_VERSION)
            log.info("Pokecord Migration complete.")

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
        return random.choices(self.pokemondata, weights=self.spawnchances, k=1)[0]

    def gender_choose(self, name):
        poke = self.genderdata.get(name, None)
        if poke is None:
            return "N/A"
        if poke == -1:
            return "Genderless"
        weights = [1 - (poke / 8), poke / 8]
        return random.choices(GENDERS, weights=weights)[0]

    def get_name(self, names, user):
        if isinstance(names, str):
            return names
        userconf = self.usercache.get(user.id)
        if userconf is None:
            return names["english"]
        localnames = {
            "en": names["english"],
            "fr": names["french"],
            "tw": names["chinese"],
            "jp": names["japanese"],
        }
        return (
            localnames[self.usercache[user.id]["locale"]]
            if localnames[self.usercache[user.id]["locale"]] is not None
            else localnames["en"]
        )

    def get_pokemon_name(self, pokemon: dict) -> set:
        """function returns all name for specified pokemon"""
        return {
            pokemon["name"][name].lower()
            for name in pokemon["name"]
            if pokemon["name"][name] is not None
        }

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
                "**Generation 9**\nSprigatito, Fuecoco, Quaxly\n"
            )
            msg += _("\nTo pick a pokemon, type {prefix}starter <pokemon>").format(
                prefix=ctx.clean_prefix
            )
            await ctx.send(msg)
            return
        starter_pokemon = {
            "bulbasaur": self.pokemondata[0],
            "charmander": self.pokemondata[3],
            "squirtle": self.pokemondata[6],
            "chikorita": self.pokemondata[146],
            "cyndaquil": self.pokemondata[149],
            "totodile": self.pokemondata[152],
            "treecko": self.pokemondata[240],
            "torchic": self.pokemondata[243],
            "mudkip": self.pokemondata[246],
            "turtwig": self.pokemondata[365],
            "chimchar": self.pokemondata[368],
            "piplup": self.pokemondata[371],
            "snivy": self.pokemondata[458],
            "tepig": self.pokemondata[461],
            "oshawott": self.pokemondata[464],
            "chespin": self.pokemondata[601],
            "fennekin": self.pokemondata[604],
            "froakie": self.pokemondata[607],
            "rowlet": self.pokemondata[668],
            "litten": self.pokemondata[671],
            "popplio": self.pokemondata[674],
            "grookey": self.pokemondata[740],
            "scorbunny": self.pokemondata[743],
            "sobble": self.pokemondata[746],
            "sprigatito": self.pokemondata[906],
            "fuecoco": self.pokemondata[909],
            "quaxly": self.pokemondata[912],
        }

        for starter in starter_pokemon.values():
            if pokemon.lower() in self.get_pokemon_name(starter):
                break

        else:
            return await ctx.send(_("That's not a valid starter pokémon, trainer!"))

        await ctx.send(
            _("You've chosen {pokemon} as your starter pokémon!").format(pokemon=pokemon.title())
        )

        # starter dict
        starter["level"] = 1
        starter["xp"] = 0
        starter["ivs"] = {
            "HP": random.randint(0, 31),
            "Attack": random.randint(0, 31),
            "Defence": random.randint(0, 31),
            "Sp. Atk": random.randint(0, 31),
            "Sp. Def": random.randint(0, 31),
            "Speed": random.randint(0, 31),
        }
        starter["gender"] = self.gender_choose(starter["name"]["english"])

        await self.cursor.execute(
            query=INSERT_POKEMON,
            values={
                "user_id": ctx.author.id,
                "message_id": ctx.message.id,
                "pokemon": json.dumps(starter),
            },
        )
        await conf.has_starter.set(True)

    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.member)
    async def hint(self, ctx):
        """Get a hint on the pokémon!"""
        pokemonspawn = await self.config.channel(ctx.channel).pokemon()
        if pokemonspawn is not None:
            name = self.get_name(pokemonspawn["name"], ctx.author)
            inds = [i for i, _ in enumerate(name)]
            if len(name) > 6:
                amount = len(name) - random.randint(2, 4)
            elif len(name) < 4:
                amount = random.randint(1, 2)
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
        pokemonspawn = await self.config.channel(ctx.channel).pokemon()
        if pokemonspawn is not None:
            names = self.get_pokemon_name(pokemonspawn)
            names.add(
                pokemonspawn["name"]["english"].translate(str.maketrans("", "", PUNCT)).lower()
            )
            if pokemonspawn.get("alias"):
                names.add(pokemonspawn["alias"].lower())
            if pokemon.lower() not in names:
                return await ctx.send(_("That's not the correct pokemon"))
            if await self.config.channel(ctx.channel).pokemon() is not None:
                await self.config.channel(ctx.channel).pokemon.clear()
            else:
                await ctx.send("No pokemon is ready to be caught.")
                return
            lvl = random.randint(1, 13)
            pokename = self.get_name(pokemonspawn["name"], ctx.author)
            variant = f'{pokemonspawn.get("variant")} ' if pokemonspawn.get("variant") else ""
            msg = _(
                "Congratulations {user}! You've caught a level {lvl} {variant}{pokename}!"
            ).format(
                user=ctx.author.mention,
                lvl=lvl,
                variant=variant,
                pokename=pokename,
            )

            async with conf.pokeids() as poke:
                if str(pokemonspawn["id"]) not in poke:
                    msg += _("\n{pokename} has been added to the pokédex.").format(
                        pokename=pokename
                    )

                    poke[str(pokemonspawn["id"])] = 1
                else:
                    poke[str(pokemonspawn["id"])] += 1
            pokemonspawn["level"] = lvl
            pokemonspawn["xp"] = 0
            pokemonspawn["gender"] = self.gender_choose(pokemonspawn["name"]["english"])
            pokemonspawn["ivs"] = {
                "HP": random.randint(0, 31),
                "Attack": random.randint(0, 31),
                "Defence": random.randint(0, 31),
                "Sp. Atk": random.randint(0, 31),
                "Sp. Def": random.randint(0, 31),
                "Speed": random.randint(0, 31),
            }
            await self.cursor.execute(
                query=INSERT_POKEMON,
                values={
                    "user_id": ctx.author.id,
                    "message_id": ctx.message.id,
                    "pokemon": json.dumps(pokemonspawn),
                },
            )
            await ctx.send(msg)
            return
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
                "spawnchance": random.randint(self.spawnchance[0], self.spawnchance[1]),
                "time": datetime.datetime.utcnow().timestamp(),
                "author": message.author.id,
            }  # TODO: big value
        if (
            self.maybe_spawn[message.guild.id]["author"] == message.author.id
        ):  # stop spamming to spawn
            if (
                datetime.datetime.utcnow().timestamp() - self.maybe_spawn[message.guild.id]["time"]
            ) < 5:
                return
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

    async def spawn_pokemon(self, channel, *, pokemon=None):
        if pokemon is None:
            pokemon = self.pokemon_choose()
        prefixes = await self.bot.get_valid_prefixes(guild=channel.guild)
        embed = discord.Embed(
            title=_("‌‌A wild pokémon has аppeаred!"),
            description=_(
                "Guess the pokémon аnd type {prefix}catch <pokémon> to cаtch it!"
            ).format(prefix=prefixes[0]),
            color=await self.bot.get_embed_color(channel),
        )
        log.debug(f"{pokemon['name']['english']} has spawned in {channel} on {channel.guild}")
        _file = discord.File(
            self.datapath
            + f'/pokemon/{pokemon["name"]["english"] if not pokemon.get("variant") else pokemon.get("alias") if pokemon.get("alias") else pokemon["name"]["english"]}.png'.replace(
                ":", ""
            ),
            filename="pokemonspawn.png",
        )
        embed.set_image(url="attachment://pokemonspawn.png")
        embed.set_footer(
            text=_("Supports: {languages}").format(
                languages=humanize_list(
                    list(
                        [
                            x.title()
                            for x in pokemon["name"].keys()
                            if pokemon["name"][x] is not None
                        ]
                    )
                )
            )
        )
        await channel.send(embed=embed, file=_file)
        await self.config.channel(channel).pokemon.set(pokemon)

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
        result = await self.cursor.fetch_all(query=SELECT_POKEMON, values={"user_id": user.id})
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
        embed = None
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
                ivs = pokemon["ivs"]
                gender = pokemon.get("gender")
                if gender is None:
                    gender = self.gender_choose(pokemon["name"]["english"])
                if ivs is None:
                    ivs = {
                        "HP": random.randint(0, 31),
                        "Attack": random.randint(0, 31),
                        "Defence": random.randint(0, 31),
                        "Sp. Atk": random.randint(0, 31),
                        "Sp. Def": random.randint(0, 31),
                        "Speed": random.randint(0, 31),
                    }
                stats = pokemon["stats"]
                if pokemon.get("variant", None) is not None:
                    pokemon = next(
                        (
                            item
                            for item in self.pokemondata
                            if (item["name"]["english"] == evolve["evolution"])
                            and item.get("variant", "") == pokemon.get("variant", "")
                        ),
                        None,
                    )
                else:
                    pokemon = next(
                        (
                            item
                            for item in self.pokemondata
                            if (item["name"]["english"] == evolve["evolution"])
                        ),
                        None,
                    )  # Make better
                if pokemon is None:
                    # log.debug(
                    #     f"Error occured trying to find {evolve['evolution']} for an evolution."
                    # )
                    return
                if nick is not None:
                    pokemon["nickname"] = nick
                pokemon["xp"] = 0
                pokemon["level"] = lvl
                pokemon["ivs"] = ivs
                pokemon["gender"] = gender
                pokemon["stats"] = stats
                if not userconf["silence"]:
                    embed = discord.Embed(
                        title=_("Congratulations {user}!").format(user=user.display_name),
                        description=_("Your {name} has evolved into {evolvename}!").format(
                            name=name, evolvename=self.get_name(pokemon["name"], user)
                        ),
                        color=await self.bot.get_embed_color(channel),
                    )
                log.debug(f"{name} has evolved into {pokemon['name']} for {user}.")
                async with self.config.user(user).pokeids() as poke:
                    if str(pokemon["id"]) not in poke:
                        poke[str(pokemon["id"])] = 1
                    else:
                        poke[str(pokemon["id"])] += 1
            else:
                log.debug(f"{pokemon['name']} levelled up for {user}")
                for stat in pokemon["stats"]:
                    pokemon["stats"][stat] = int(pokemon["stats"][stat]) + random.randint(1, 3)
                if not userconf["silence"]:
                    embed = discord.Embed(
                        title=_("Congratulations {user}!").format(user=user.display_name),
                        description=_("Your {name} has levelled up to level {level}!").format(
                            name=name, level=pokemon["level"]
                        ),
                        color=await self.bot.get_embed_color(channel),
                    )
            if embed is not None:
                if (
                    self.guildcache[channel.guild.id].get("levelup_messages")
                    and channel.id in self.guildcache[channel.guild.id]["activechannels"]
                ):
                    channel = channel
                elif (
                    self.guildcache[channel.guild.id].get("levelup_messages")
                    and not self.guildcache[channel.guild.id]["activechannels"]
                ):
                    channel = channel
                else:
                    channel = None
                if channel is not None:
                    await channel.send(embed=embed)
        # data = (user.id, msg_id, json.dumps(pokemon))
        await self.cursor.execute(
            query=UPDATE_POKEMON,
            values={"user_id": user.id, "message_id": msg_id, "pokemon": json.dumps(pokemon)},
        )
        # task = functools.partial(self.safe_write, UPDATE_POKEMON, data)
        # await self.bot.loop.run_in_executor(self._executor, task)

    @commands.command(hidden=True)
    async def pokesim(self, ctx, amount: int = 1000000):
        """Sim pokemon spawning - This is blocking."""
        a = {}
        for _ in range(amount):
            pokemon = self.pokemon_choose()
            variant = pokemon.get("variant", "Normal")
            if variant not in a:
                a[variant] = 1
            else:
                a[variant] += 1
        await ctx.send(a)
