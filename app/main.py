"""Node entrypoint: the composition root that wires everything together."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from dishka.integrations.fastapi import setup_dishka

from .application import Node
from .infrastructure.api import create_app
from .infrastructure.config_loader import build_arg_parser, load_config
from .infrastructure.container import build_container
from .infrastructure.logger import setup_logging


def main() -> None:
    args = build_arg_parser().parse_args()
    config = load_config(args.config, cli_args=args)
    setup_logging(config.self_id, log_dir=config.limits.log_dir)

    container = build_container(config)

    @asynccontextmanager
    async def lifespan(app):
        node = await container.get(Node)
        await node.start()
        yield
        await node.stop()
        await container.close()

    app = create_app()

    setup_dishka(container, app)
    app.router.lifespan_context = lifespan

    host, port = config.self_node.host, config.self_node.port
    uvicorn.run(app, host=host, port=port, log_config=None)


if __name__ == "__main__":
    main()