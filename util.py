import bs4
import aiohttp
import asyncio
from io import BytesIO
import random
import copy

from selenium import webdriver
from bs4 import BeautifulSoup
import html5lib
import os

# driver = webdriver.Chrome(executable_path=r"chromedriver.exe")
import json

URL = "https://pokemondb.net/pokedex/all"
CDNURL = "https://assets.pokemon.com/assets/cms2/img/pokedex/detail/{}.png"
POKEDEX = "https://img.pokemondb.net/artwork/{}"
EVOLVE = "https://pokemondb.net/evolution/level"
SHINY = "https://pokemondb.net/pokedex/shiny"


# DOESNT DO MEGAS ETC.


async def main():
    # a = {"mega": [], "normal": [], "all": {}}
    driver.get(SHINY)
    await asyncio.sleep(10)
    soup = bs4.BeautifulSoup(driver.page_source, "html.parser")
    da = soup.find_all("div", {"class": "infocard-list infocard-list-pkmn-lg"})
    a = []
    for div in da:
        tags = div.find_all("div", {"class": "infocard"})
        for poke in tags:
            if len(poke.find_all("small")) == 2:
                num = int(poke.find("small").get_text().replace("#", ""))
                print(num)
                img = poke.find_all("img")
                if not img:
                    print(img)
                img = img[1].attrs["src"]
                a.append([num, img])
    # await write(a, "shiny")

    # with open(f"pokecord/data/shiny.json", "r", encoding="utf-8") as f:
    #     a = json.load(f)
    with open(f"pokecord/data/pokedex.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    b = []
    for poke in a:
        for pokemon in data:
            if pokemon["id"] == poke[0]:
                newpoke = copy.deepcopy(pokemon)

                newpoke["url"] = poke[1]
                newpoke["spawnchance"] = 0.01
                newpoke["variant"] = "Shiny"
                newpoke["alias"] = f"Shiny {newpoke['name']['english']}"
                b.append(newpoke)
    await write(b, "shiny")


async def get_img():
    session = aiohttp.ClientSession()
    with open(f"pokecord/data/pokedex.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    for pokemon in data:
        img = await session.get(
            f"https://assets.pokemon.com/assets/cms2/img/pokedex/detail/{str(pokemon['id']).zfill(3)}.png"
        )
        name = f"pokecord/data/pokemon/{pokemon['name']['english']}.png"
        with open(name, "wb") as f:
            f.write(BytesIO(await img.read()).getbuffer())
    with open(f"pokecord/data/shiny.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    for pokemon in data:
        img = await session.get(pokemon["url"])
        name = f"pokecord/data/pokemon/{pokemon['alias']}.png"
        with open(name, "wb") as f:
            f.write(BytesIO(await img.read()).getbuffer())

    await session.close()


async def evolve():
    a = {}
    driver.get(EVOLVE)
    parse = BeautifulSoup(driver.page_source, "html5lib")
    await asyncio.sleep(3)
    soup = bs4.BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find("table", {"id": "evolution"})
    evolves = table.find_all("tr")
    for tag in evolves[1:]:
        pokes = tag.find_all("span", {"class": "infocard-cell-data"})
        lvl = tag.find("td", {"class": "cell-num"})
        if lvl is None:
            break
        names = []
        for pokemon in pokes:
            small = pokemon.find("small", {"class": "text-muted"})
            if small is None:
                small = pokemon.find("a")
            names.append(small.get_text())
        a[names[0]] = {"evolution": names[1], "level": lvl.get_text()}
    await write(a, "evolve")


async def write(lst, name):
    with open(f"pokecord/data/{name}.json", "w") as f:
        f.write(json.dumps(lst, indent=1))


def spawn_rate():
    with open(f"pokecord/data/pokedex.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        stats = []
        for pokemon in data:
            total = 0
            for stat in pokemon["stats"]:
                total += pokemon["stats"][stat]
            stats.append(800 - total)
            pokemon["spawnchance"] = (800 - total) / 800

    with open(f"pokecord/data/pokedex.json", "w") as f:
        f.write(json.dumps(data))


loop = asyncio.get_event_loop()
loop.run_until_complete(get_img())
