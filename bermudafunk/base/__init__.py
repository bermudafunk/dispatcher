import asyncio
import logging
import typing

import config

logging.basicConfig(
    format="%(asctime)s : %(levelname)8s : %(name)30s : %(funcName)-20s : %(lineno)4d : %(message)s",
    level=logging.INFO,
)

logging.getLogger("transitions").setLevel(logging.INFO)

if config.DEBUG:
    logging.getLogger("bermudafunk").setLevel(logging.DEBUG)
    # logging.getLogger("symnet_cp").setLevel(logging.DEBUG)
    logging.getLogger("transitions").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

cleanup_tasks: typing.List[asyncio.Task] = []
