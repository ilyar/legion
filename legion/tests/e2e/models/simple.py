import argparse
import typing

from legion.toolchain import model
from legion.toolchain.model import init, export, save
from pandas import DataFrame


def default(df: DataFrame) -> typing.Dict[str, int]:
    return {'result': 42}


def feedback(df: DataFrame) -> typing.Dict[str, str]:
    return {'result': df['str'] * df['copies']}


def build_model(id: str, version: str) -> None:
    """
    Build mock model for robot tests

    :param id: model id
    :param version: model version
    """
    init(id, version)

    export(apply_func=default, column_types={"a": model.string, "b": model.string})
    export(apply_func=feedback, column_types={"str": model.string,  "copies": model.int64}, endpoint='feedback')

    save('robot.model')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', help='model id', required=True)
    parser.add_argument('--version', help='model version', required=True)
    args = parser.parse_args()

    build_model(args.id, args.version)