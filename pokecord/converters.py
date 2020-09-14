import argparse

from redbot.core.commands import BadArgument, Converter


class NoExitParser(argparse.ArgumentParser):
    def error(self, message):
        raise BadArgument()


class Args(Converter):
    async def convert(self, ctx, argument):
        argument = argument.replace("—", "--")
        parser = NoExitParser(description="Pokecord Search", add_help=False)

        pokemon = parser.add_mutually_exclusive_group()
        pokemon.add_argument("--name", "--n", nargs="*", dest="names", default=[])
        pokemon.add_argument("--level", "--l", nargs="*", dest="level", type=int, default=0)
        pokemon.add_argument("--id", "--i", nargs="*", dest="id", type=int, default=0)
        pokemon.add_argument("--variant", "--v", nargs="*", dest="variant", default=[])
        pokemon.add_argument("--gender", "--g", nargs="*", dest="gender", default=[])
        pokemon.add_argument("--iv", nargs="*", dest="iv", type=int, default=0)
        pokemon.add_argument("--type", "--t", nargs="*", dest="type", default=[])

        try:
            vals = vars(parser.parse_args(argument.split(" ")))
        except Exception as error:
            raise BadArgument() from error

        if not any(
            [
                vals["names"],
                vals["level"],
                vals["id"],
                vals["variant"],
                vals["gender"],
                vals["iv"],
                vals["type"],
            ]
        ):
            raise BadArgument(
                "You must provide one of `--name`, `--level`, `--id`, `--variant`, `--iv`, `--gender` or `--type``"
            )

        vals["names"] = " ".join(vals["names"])
        vals["variant"] = " ".join(vals["variant"])
        vals["gender"] = " ".join(vals["gender"])
        vals["type"] = " ".join(vals["type"])
        return vals
