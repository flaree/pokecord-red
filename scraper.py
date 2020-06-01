import bs4
import aiohttp
import asyncio
from io import BytesIO

from selenium import webdriver
from bs4 import BeautifulSoup
import html5lib
driver = webdriver.Chrome(executable_path=r'chromedriver.exe')
import json
URL = "https://pokemondb.net/pokedex/all"
CNDURL = "https://assets.pokemon.com/assets/cms2/img/pokedex/detail/{}.png"


# DOESNT DO MEGAS ETC.

async def main():
    a = {"mega": [], "normal": []}
    driver.get(URL)
    parse = BeautifulSoup(driver.page_source, 'html5lib')
    await asyncio.sleep(3)
    soup = bs4.BeautifulSoup(driver.page_source,'html.parser')
    da = soup.find_all("table", {"id": "pokedex"})[0]
    tags = da.find_all("tr")
    stat_headlines = ["HP", "Attack", "Defence", "Sp. Atk", "Sp. Def", "Speed"]
    for i, poke in enumerate(tags[1:]):
        name = poke.find("a")
        _id = poke.find("span", {"class": "infocard-cell-data"})
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
            a["mega"].append({"name": name, "alias": small, "types": types, "stats": stats_dict})
            continue
        a["normal"].append({"name": name,"alias": small, "types": types, "stats": stats_dict})
    #await get_img(A)
    await write(a)

async def write(lst):
    with open("pokecord/data/pokemon.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(lst))

async def get_img(lst):
    session = aiohttp.ClientSession()
    for name, id in lst:
        print(id, "getting img")
        async with session.get(CNDURL.format(id)) as img:
            with open(f"data/{name}.png", "wb") as f:
                f.write(BytesIO(await img.read()).getbuffer())

    await session.close()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())

