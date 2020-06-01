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

import discord
import tabulate
from PIL import Image
from redbot.core import Config, checks, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils.chat_formatting import humanize_list, box
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

import apsw

from .settings import SettingsMixin
from .statements import *

log = logging.getLogger("red.flare.pokecord")


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's
    metaclass."""


class Pokecord(SettingsMixin, commands.Cog, metaclass=CompositeMetaClass):
    """Pokecord adapted to use on Red."""

    __version__ = "0.0.1a"
    __author__ = "flare"

    def format_help_for_context(self, ctx):
        """Thanks Sinbad."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\nAuthor: {self.__author__}\nCog Version: {self.__version__}"

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=95932766180343808, force_registration=True)
        self.config.register_global(isglobal=True, hashed=False, hashes={}, spawnchance=[20, 120])
        defaults_guild = {"activechannels": [], "toggle": False}
        self.config.register_guild(**defaults_guild)
        defaults_user = {"pokemon": [], "silence": False, "timestamp": 0}
        self.config.register_user(**defaults_user)
        self.config.register_member(**defaults_user)
        self.datapath = f"{bundled_data_path(self)}"
        self.spawnedpokemon = {}
        self.maybe_spawn = {}
        self.guildcache = {}
        self.spawnchance = []
        self._connection = apsw.Connection(str(cog_data_path(self) / "pokemon.db"))
        self.cursor = self._connection.cursor()
        self.cursor.execute(PRAGMA_journal_mode)
        self.cursor.execute(PRAGMA_wal_autocheckpoint)
        self.cursor.execute(PRAGMA_read_uncommitted)
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "user_id INTEGER NOT NULL,"
            "message_id INTEGER NOT NULL UNIQUE,"
            "pokemon JSON,"
            "PRIMARY KEY (user_id, message_id)"
            ");"  # TODO: members table instead
        )
        self._executor = concurrent.futures.ThreadPoolExecutor(1)

    def cog_unload(self):
        self._executor.shutdown()

    async def initalize(self):
        with open(f"{self.datapath}/pokemon.json") as f:
            self.pokemondata = json.load(f)
        if await self.config.hashed():
            log.info("hashing...")
            hashes = {}
            for file in os.listdir(f"{self.datapath}/pokemon/"):
                if file.endswith(".png"):
                    cmd = (
                        base64.b64decode(
                            b"aGFzaGVzW2ZpbGVdID0gaGFzaGxpYi5tZDUoSW1hZ2Uub3BlbihyJ3tzZWxmLmRhdGFwYXRofS97ZmlsZX0nKS50b2J5dGVzKCkpLmhleGRpZ2VzdCgp"
                        )
                        .decode("utf-8")
                        .replace("'", '"')
                        .replace(r"{self.datapath}", f"{self.datapath}/pokemon/")
                        .replace(r"{file}", file)
                    )
                    exec(cmd)
            await self.config.hashes.set(hashes)
            await self.config.hashed.set(True)
            log.info("Hashing complete")
        await self.update_guild_cache()
        await self.update_spawn_chance()

    async def update_guild_cache(self):
        self.guildcache = await self.config.all_guilds()
        
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
        num = random.randint(1, 200)
        if num > 2:
            return random.choice(self.pokemondata["normal"])
        return random.choice(self.pokemondata["mega"])

    @commands.command()
    async def list(self, ctx):
        """List your pokémon!"""
        conf = await self.user_is_global(ctx.author)
        result = self.cursor.execute(
            """SELECT pokemon from users where user_id = ?""", (ctx.author.id,)
        ).fetchall()
        pokemons = []
        for data in result:
            pokemons.append(json.loads(data[0]))
        if not pokemons:
            return await ctx.send("You don't have any pokémon, go get catching trainer!")
        embeds = []
        for i, pokemon in enumerate(pokemons, 1):
            stats = pokemon["stats"]
            pokestats = tabulate.tabulate([["HP", stats["HP"]], ["Attack", stats["Attack"]], ["Defence", stats["Defence"]], ["Sp. Atk", stats["Sp. Atk"]], ["Sp. Def", stats["Sp. Def"]], ["Speed", stats["Speed"]]], headers=["Ability", "Value"])
            desc = f"**Level**: {pokemon['level']}\n**XP**: {pokemon['xp']}/{self.calc_xp(pokemon['level'])}\n{box(pokestats, lang='prolog')}"
            embed = discord.Embed(title=pokemon["name"], description=desc)
            embed.set_image(url=f"https://flaree.xyz/data/{urllib.parse.quote(pokemon['name'])}.png")
            embed.set_footer(text=f"Pokémon ID: {i}/{len(pokemons)}")
            embeds.append(embed)
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    def safe_write(self, query, data):
        """Func for safely writing in another thread."""
        cursor = self._connection.cursor()
        cursor.executemany(query, data)

    @commands.command()
    async def catch(self, ctx, *, pokemon: str):
        """Catch a pokemon!"""
        if self.spawnedpokemon.get(ctx.guild.id) is not None:
            pokemonspawn = self.spawnedpokemon[ctx.guild.id].get(ctx.channel.id)
            if pokemonspawn is not None:
                names = [pokemonspawn["name"].lower(), pokemonspawn["name"].strip(string.punctuation).lower()]
                if pokemonspawn["alias"] is not None:
                    names.append(pokemonspawn["alias"].lower())
                    names.append(pokemonspawn["alias"].strip(string.punctuation).lower())
                if pokemon.lower() in names:
                    await ctx.send(f"Congratulations, you've caught {pokemonspawn['name']}.")
                    pokemonspawn["level"] = random.randint(1, 13)
                    pokemonspawn["xp"] = 0
                    self.cursor.execute(
                        "INSERT INTO users (user_id, message_id, pokemon)" "VALUES (?, ?, ?)",
                        (ctx.author.id, ctx.message.id, json.dumps(pokemonspawn)),
                    )
                    del self.spawnedpokemon[ctx.guild.id][ctx.channel.id]
                    return
                else:
                    return await ctx.send("That's not the correct pokemon")
        await ctx.send("No pokemon is ready to be caught.")

    def spawn_chance(self, guildid):
        return self.maybe_spawn[guildid]["amount"] > self.maybe_spawn[guildid]["spawnchance"]

    async def get_hash(self, pokemon):
        return (await self.config.hashes())[pokemon]

    @commands.Cog.listener()
    async def on_message(self, message):
        # if message.author.id == 95932766180343808:
        #     if message.content == "spawn":
        #         await self.spawn_pokemon(message.channel)

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
            channel = message.guild.get_channel(int(random.choice(guildcache["activechannels"])))
            if channel is None:
                return  # TODO: Remove channel from config
        await self.spawn_pokemon(channel)
    
    async def spawn_pokemon(self, channel):
        if channel.guild.id not in self.spawnedpokemon:
            self.spawnedpokemon[channel.guild.id] = {}
        pokemon = self.pokemon_choose()
        # log.info(pokemon)
        self.spawnedpokemon[channel.guild.id][channel.id] = pokemon
        prefixes = await self.bot.get_valid_prefixes(guild=channel.guild)
        embed = discord.Embed(
            title="‌‌A wild pokémon has аppeаred!",
            description=f"Guess the pokémon аnd type {prefixes[0]}catch <pokémon> to cаtch it!",
        )
        hashe = await self.get_hash(f"{pokemon['name']}.png")
        embed.set_image(url=f"https://flaree.xyz/data/{urllib.parse.quote(hashe)}.png")
        await channel.send(embed=embed)

    def calc_xp(self, lvl):
        return 5 * lvl * 5

    async def exp_gain(self, channel, user):
        conf = await self.user_is_global(user)
        userconf = await conf.all()
        if datetime.datetime.utcnow().timestamp() - userconf["timestamp"] < 120:
            return
        await conf.timestamp.set(datetime.datetime.utcnow().timestamp())
        result = self.cursor.execute(
            """SELECT pokemon, message_id from users where user_id = ?""", (user.id,)
        ).fetchall()
        pokemons = []
        for data in result:
            pokemons.append([json.loads(data[0]), data[1]])
        if not pokemons:
            return
        pokemon = None
        for i, poke in enumerate(pokemons):
            if poke[0]["level"] < 100:
                pokemon = poke[0]
                xp = random.randint(1, 4)
                pokemon["xp"] += xp
                if pokemon["xp"] >= self.calc_xp(pokemon["level"]):
                    pokemon["level"] += 1
                    pokemon["xp"] = 0
                    log.info(f"{pokemon['name']} levelled up for {user}")
                    for stat in pokemon["stats"]:
                        pokemon["stats"][stat] = int(pokemon["stats"][stat]) + random.randint(1, 3)
                    if not userconf["toggle"]:
                        embed = discord.Embed(
                            title=f"Congratulations {user}!",
                            description=f"Your {pokemon['name']} has levelled up to level {pokemon['level']}!",
                        )
                        await channel.send(embed=embed)
                self.cursor.execute(
                    "INSERT INTO users (user_id, message_id, pokemon)"
                    "VALUES (?, ?, ?)"
                    "ON CONFLICT (message_id) DO UPDATE SET "
                    "pokemon = excluded.pokemon;",
                    (user.id, poke[1], json.dumps(pokemon)),
                )
                return
