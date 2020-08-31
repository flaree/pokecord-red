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
        pokemon.add_argument(
            "--level", "--l", nargs="*", dest="level", type=int, default=0
        )
        pokemon.add_argument("--id", "--i", nargs="*", dest="id", type=int, default=0)
        pokemon.add_argument("--variant", "--v", nargs="*", dest="variant", default=[])

        try:
            vals = vars(parser.parse_args(argument.split(" ")))
        except Exception as error:
            raise BadArgument() from error

        if not any([vals["names"], vals["level"], vals["id"], vals["variant"]]):
            raise BadArgument(
                "You must provide one of `--name`, `--level`, `--id` or `--variant`"
            )

        vals["names"] = " ".join(vals["names"])
        vals["variant"] = " ".join(vals["variant"])
        return vals
