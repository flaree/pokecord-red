import bs4
import aiohttp
import asyncio
from io import BytesIO

from selenium import webdriver
from bs4 import BeautifulSoup
import html5lib
import os

driver = webdriver.Chrome(executable_path=r"chromedriver.exe")
import json

URL = "https://pokemondb.net/pokedex/all"
CNDURL = "https://assets.pokemon.com/assets/cms2/img/pokedex/detail/{}.png"
EVOLVE = "https://pokemondb.net/evolution/level"


# DOESNT DO MEGAS ETC.


async def main():
    a = {"mega": [], "normal": []}
    driver.get(URL)
    parse = BeautifulSoup(driver.page_source, "html5lib")
    await asyncio.sleep(3)
    soup = bs4.BeautifulSoup(driver.page_source, "html.parser")
    da = soup.find_all("table", {"id": "pokedex"})[0]
    tags = da.find_all("tr")
    stat_headlines = ["HP", "Attack", "Defence", "Sp. Atk", "Sp. Def", "Speed"]
    for i, poke in enumerate(tags[1:]):
        name = poke.find("a")
        _id = poke.find("span", {"class": "infocard-cell-data"}).get_text()
        small = poke.find("small", {"class": "text-muted"})
        stats = poke.find_all("td", {"class": "cell-num"})
        stats_dict = {}
        for i, stat in enumerate(stats[1:]):
            stats_dict[stat_headlines[i]] = stat.get_text()
        icons = poke.find("td", {"class": "cell-icon"})
        types = []
        for icon in icons.find_all("a"):
            types.append(icon.get_text())
        name = name.get_text() if name is not None else f"Undefined-{i}"
        if small is not None:
            small = small.get_text()
        else:
            small = None
        if "Mega" in name:
            a["mega"].append(
                {
                    "name": name,
                    "alias": small,
                    "types": types,
                    "stats": stats_dict,
                    "id": _id,
                }
            )
            continue
        a["normal"].append(
            {
                "name": name,
                "alias": small,
                "types": types,
                "stats": stats_dict,
                "id": _id,
            }
        )
    await get_img(a)
    await write(a, "pokemon")
    
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
    print(a)
    await write(a, "evolve")


async def write(lst, name):
    with open(f"pokecord/data/{name}.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(lst))


async def get_img(lst):
    session = aiohttp.ClientSession()
    for pokemon in lst["normal"]:
        async with session.get(CNDURL.format(id)) as img:
            if os.path.exists(f'data/{pokemon["name"]}.png'):
                name = f"data/{pokemon['name']}-{pokemon['alias']}.png"
            else:
                name = f"data/{pokemon['name']}.png"
            with open(name, "wb") as f:
                f.write(BytesIO(await img.read()).getbuffer())
        print(pokemon["id"], name)

    await session.close()


loop = asyncio.get_event_loop()
loop.run_until_complete(evolve())
