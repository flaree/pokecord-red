import asyncio
import base64
import concurrent.futures
import datetime
import functools
import hashlib
import json
import logging
import os
import random
import re
import string
import urllib
from abc import ABC
from typing import Union

import discord
import tabulate
from PIL import Image
from redbot.core import Config, bank, checks, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils.chat_formatting import box, escape, humanize_list
from redbot.core.utils.predicates import MessagePredicate

import apsw

from .settings import SettingsMixin
from .general import GeneralMixin
from .statements import *

log = logging.getLogger("red.flare.pokecord")


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's
    metaclass."""


class Pokecord(SettingsMixin, GeneralMixin, commands.Cog, metaclass=CompositeMetaClass):
    """Pokecord adapted to use on Red."""

    __version__ = "0.0.1-realllllly-pre-alpha-9"
    __author__ = "flare"

    def format_help_for_context(self, ctx):
        """Thanks Sinbad."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\nAuthor: {self.__author__}\nCog Version: {self.__version__}"

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=95932766180343808, force_registration=True
        )
        self.config.register_global(
            isglobal=True,
            hashed=False,
            hashes={},
            spawnchance=[20, 120],
            hintcost=1000,
            spawnloop=False,
        )
        defaults_guild = {"activechannels": [], "toggle": False}
        self.config.register_guild(**defaults_guild)
        defaults_user = {
            "pokemon": [],
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
        return random.choice(self.pokemondata)
        # return random.choice(self.pokemondata["mega"])

    def get_name(self, names, user):
        if isinstance(names, str):
            return names
        localnames = {
            "en": names["english"],
            "fr": names["french"],
            "cn": names["chinese"],
            "jp": names["japanese"],
        }
        return localnames[self.usercache[user.id]["locale"]]

    @commands.command()
    async def starter(self, ctx, pokemon: str = None):
        """Choose your starter pokemon"""
        conf = await self.user_is_global(ctx.author)
        if await conf.has_starter():
            return await ctx.send(f"You've already claimed your starter pokemon!")
        if pokemon is None:
            msg = (
                "Hey there trainer! Welcome to Pokecord. This is a ported plugin version of Pokecord adopted for use on Red.\n"
                "In order to get catchin' you must pick one of the starter Pokemon as listed below.\n"
                "Bulbasaur, Charmander and Squirtle\n"
                f"To pick a pokemon, type {ctx.clean_prefix}starter <pokemon>"
            )
            await ctx.send(msg)
            return
        if pokemon.lower() not in ["bulbasaur", "charmander", "squirtle"]:
            await ctx.send("That's not a valid starter pokémon, trainer!")
            return
        await ctx.send(f"You've chosen {pokemon.title()} as your starter pokémon!")
        starter_pokemon = {
            "bulbasaur": {
                "name": {
                    "english": "Bulbasaur",
                    "japanese": "フシギダネ",
                    "chinese": "妙蛙种子",
                    "french": "Bulbizarre",
                },
                "types": ["Grass", "Poison"],
                "stats": {
                    "HP": "45",
                    "Attack": "49",
                    "Defence": "49",
                    "Sp. Atk": "65",
                    "Sp. Def": "65",
                    "Speed": "45",
                },
                "id": 1,
                "level": 1,
                "xp": 0,
            },
            "charmander": {
                "name": {
                    "english": "Charmander",
                    "japanese": "ヒトカゲ",
                    "chinese": "小火龙",
                    "french": "Salamèche",
                },
                "types": ["Fire"],
                "stats": {
                    "HP": "39",
                    "Attack": "52",
                    "Defence": "43",
                    "Sp. Atk": "60",
                    "Sp. Def": "50",
                    "Speed": "65",
                },
                "id": 4,
                "level": 1,
                "xp": 0,
            },
            "squirtle": {
                "name": {
                    "english": "Squirtle",
                    "japanese": "ゼニガメ",
                    "chinese": "杰尼龟",
                    "french": "Carapuce",
                },
                "types": ["Water"],
                "stats": {
                    "HP": "44",
                    "Attack": "48",
                    "Defence": "65",
                    "Sp. Atk": "50",
                    "Sp. Def": "64",
                    "Speed": "43",
                },
                "id": 7,
                "level": 1,
                "xp": 0,
            },
        }

        self.cursor.execute(
            INSERT_POKEMON,
            (
                ctx.author.id,
                ctx.message.id,
                json.dumps(starter_pokemon[pokemon.lower()]),
            ),
        )
        await conf.has_starter.set(True)

    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.member)
    async def hint(self, ctx):
        """Get a hint on the pokemon!"""
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
                    "This wild pokemon is a {}".format(escape(word, formatting=True))
                )
                return
        await ctx.send("No pokemon is ready to be caught.")

    @commands.command()
    async def catch(self, ctx, *, pokemon: str):
        """Catch a pokemon!"""
        conf = await self.user_is_global(ctx.author)
        if not await conf.has_starter():
            return await ctx.send(
                f"You haven't chosen a starter pokemon yet, check out `{ctx.clean_prefix}starter` for more information."
            )
        if self.spawnedpokemon.get(ctx.guild.id) is not None:
            pokemonspawn = self.spawnedpokemon[ctx.guild.id].get(ctx.channel.id)
            if pokemonspawn is not None:
                names = set(
                    pokemonspawn["name"][name].lower() for name in pokemonspawn["name"]
                )
                names.add(
                    pokemonspawn["name"]["english"]
                    .translate(str.maketrans("", "", string.punctuation))
                    .lower()
                )
                if pokemon.lower() in names:
                    if self.spawnedpokemon.get(
                        ctx.guild.id
                    ) is not None and self.spawnedpokemon[ctx.guild.id].get(
                        ctx.channel.id
                    ):
                        del self.spawnedpokemon[ctx.guild.id][ctx.channel.id]
                    else:
                        await ctx.send("No pokemon is ready to be caught.")
                        return
                    lvl = random.randint(1, 13)
                    await ctx.send(
                        f"Congratulations {ctx.author.mention}! You've caught a level {lvl} {self.get_name(pokemonspawn['name'], ctx.author)}!"
                    )
                    pokemonspawn["level"] = lvl
                    pokemonspawn["xp"] = 0
                    self.cursor.execute(
                        INSERT_POKEMON,
                        (ctx.author.id, ctx.message.id, json.dumps(pokemonspawn)),
                    )
                    return
                else:
                    return await ctx.send("That's not the correct pokemon")
        await ctx.send("No pokemon is ready to be caught.")

    def spawn_chance(self, guildid):
        return (
            self.maybe_spawn[guildid]["amount"]
            > self.maybe_spawn[guildid]["spawnchance"]
        )

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
        if message.guild.id not in self.maybe_spawn:
            self.maybe_spawn[message.guild.id] = {
                "amount": 0,
                "spawnchance": random.randint(self.spawnchance[0], self.spawnchance[1]),
            }  # TODO: big value
        self.maybe_spawn[message.guild.id]["amount"] += 1
        should_spawn = self.spawn_chance(message.guild.id)
        if not should_spawn:
            return
        del self.maybe_spawn[message.guild.id]
        if not guildcache["activechannels"]:
            channel = message.channel
        else:
            channel = message.guild.get_channel(
                int(random.choice(guildcache["activechannels"]))
            )
            if channel is None:
                return  # TODO: Remove channel from config
        await self.spawn_pokemon(channel)

    async def spawn_pokemon(self, channel):
        if channel.guild.id not in self.spawnedpokemon:
            self.spawnedpokemon[channel.guild.id] = {}
        pokemon = self.pokemon_choose()
        self.spawnedpokemon[channel.guild.id][channel.id] = pokemon
        prefixes = await self.bot.get_valid_prefixes(guild=channel.guild)
        embed = discord.Embed(
            title="‌‌A wild pokémon has аppeаred!",
            description=f"Guess the pokémon аnd type {prefixes[0]}catch <pokémon> to cаtch it!",
            color=await self.bot.get_embed_color(channel),
        )
        # name = pokemon["name"] if pokemon["alias"] is None else pokemon["alias"]
        log.debug(
            f"{pokemon['name']['english']} has spawned in {channel} on {channel.guild}"
        )
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
            evolve = self.evolvedata.get(pokemon.get("alias") or pokemon["name"])
            name = (
                self.get_name(pokemon["name"], user)
                if pokemon.get("nickname") is None
                else f'"{pokemon.get("nickname")}"'
            )
            if evolve is not None and (pokemon["level"] >= int(evolve["level"])):
                lvl = pokemon["level"]
                pokemon = self.pokemondata["all"][evolve["evolution"]]
                pokemon["xp"] = 0
                pokemon["level"] = lvl
                if not userconf["silence"]:
                    embed = discord.Embed(
                        title=f"Congratulations {user}!",
                        description=f"Your {name} has evolved into {pokemon['name']}!",
                        color=await self.bot.get_embed_color(channel),
                    )
                    await channel.send(embed=embed)
                log.debug(f"{name} has evolved into {pokemon['name']} for {user}.")
            else:
                log.debug(f"{pokemon['name']} levelled up for {user}")
                for stat in pokemon["stats"]:
                    pokemon["stats"][stat] = int(
                        pokemon["stats"][stat]
                    ) + random.randint(1, 3)
                if not userconf["silence"]:
                    embed = discord.Embed(
                        title=f"Congratulations {user}!",
                        description=f"Your {name} has levelled up to level {pokemon['level']}!",
                        color=await self.bot.get_embed_color(channel),
                    )
                    await channel.send(embed=embed)
        self.cursor.execute(
            UPDATE_POKEMON, (user.id, msg_id, json.dumps(pokemon)),
        )
