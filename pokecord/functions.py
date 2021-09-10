import discord
import tabulate
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box

_ = Translator("Pokecord", __file__)


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i : i + n]


async def poke_embed(cog, ctx, pokemon, *, file=False, menu=None):
    stats = pokemon["stats"]
    ivs = pokemon["ivs"]
    pokestats = tabulate.tabulate(
        [
            [_("HP"), stats["HP"], ivs["HP"]],
            [_("Attack"), stats["Attack"], ivs["Attack"]],
            [_("Defence"), stats["Defence"], ivs["Defence"]],
            [_("Sp. Atk"), stats["Sp. Atk"], ivs["Sp. Atk"]],
            [_("Sp. Def"), stats["Sp. Def"], ivs["Sp. Def"]],
            [_("Speed"), stats["Speed"], ivs["Speed"]],
        ],
        headers=[_("Stats"), _("Value"), _("IV")],
    )
    nick = pokemon.get("nickname")
    alias = _("**Nickname**: {nick}\n").format(nick=nick) if nick is not None else ""
    variant = (
        _("**Variant**: {variant}\n").format(variant=pokemon.get("variant"))
        if pokemon.get("variant")
        else ""
    )
    types = ", ".join(pokemon["type"])
    desc = _(
        "**ID**: {id}\n{alias}**Level**: {level}\n**Type**: {type}\n**Gender**: {gender}\n**XP**: {xp}/{totalxp}\n{variant}{stats}"
    ).format(
        id=f"#{pokemon.get('id')}" if pokemon.get("id") else "0",
        alias=alias,
        level=pokemon["level"],
        type=types,
        gender=pokemon.get("gender", "N/A"),
        variant=variant,
        xp=pokemon["xp"],
        totalxp=cog.calc_xp(pokemon["level"]),
        stats=box(pokestats, lang="prolog"),
    )
    embed = discord.Embed(
        title=cog.get_name(pokemon["name"], ctx.author)
        if not pokemon.get("alias", False)
        else pokemon.get("alias"),
        description=desc,
    )
    embed.set_footer(text=_("Pokémon ID: {number}").format(number=pokemon["sid"]))
    if file:
        _file = discord.File(
            cog.datapath
            + f'/pokemon/{pokemon["name"]["english"] if not pokemon.get("variant") else pokemon.get("alias") if pokemon.get("alias") else pokemon["name"]["english"]}.png'.replace(
                ":", ""
            ),
            filename="pokemonspawn.png",
        )
        embed.set_thumbnail(url="attachment://pokemonspawn.png")
        return embed, _file
    else:
        if pokemon.get("id"):
            embed.set_thumbnail(
                url=f"https://assets.pokemon.com/assets/cms2/img/pokedex/detail/{str(pokemon['id']).zfill(3)}.png"
                if not pokemon.get("url")
                else pokemon.get("url")
            )
        embed.set_footer(
            text=_("Pokémon ID: {number}/{amount}").format(
                number=pokemon["sid"], amount=menu.get_max_pages()
            )
        )
        return embed
