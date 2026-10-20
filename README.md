# Raft

Распределённый консенсус по статье Raft (Ongaro & Ousterhout).
Этап 1: скелет + выборы лидера + REST API статуса.

## Окружение

- Python 3.12+
- Управление зависимостями — [uv](https://docs.astral.sh/uv/)
- FastAPI + uvicorn (asyncio), structlog, pydantic, pyyaml, httpx, dishka (DI)

## Установка

Перейти в директорию проекта:

```bash
cd ~/PycharmProjects/raft
```

Синхронизировать виртуальное окружение:

```bash
uv sync
```

Активировать виртуальное окружение:

```bash
source .venv/bin/activate
```

`uv sync` сам создаёт `.venv` и ставит зависимости из `pyproject.toml`.

## Запуск кластера

Без флага `--stdout` логи пишутся в logs/node-\<id\>.log, с флагом $-$ в терминал
```bash
uv run python launcher.py --config configs/cluster.yaml
```

## Запуск узла вручную

```bash
uv run python -m app.main --config configs/cluster.yaml --self-id node-1
uv run python -m app.main --config configs/cluster.yaml --self-id node-2
uv run python -m app.main --config configs/cluster.yaml --self-id node-3
```

## REST API

| Метод | Путь | Что делает |
|-------|------|------------|
| GET  | `/status` | роль, term, лидер, голос, статистика |
| GET  | `/leader` | текущий лидер |
| GET  | `/vote`   | кому отдан голос в текущем терме |
| POST | `/role`   | принудительно сменить роль (`follower`/`leader`) |
| POST | `/raft/request_vote`   | внутренний RPC |
| POST | `/raft/append_entries` | внутренний RPC |

Примеры:

```bash
curl -s localhost:8101/status
curl -s localhost:8101/leader
curl -s -X POST localhost:8101/role -H 'Content-Type: application/json' -d '{"role":"follower"}'
```

## Структура (чистая архитектура)

```
app/
  domain/          # чистые модели и правила консенсуса (без IO)
    config.py      #   pydantic-модели конфига
    state.py       #   роли, persistent/volatile state
    messages.py    #   DTO RPC-сообщений
    election.py    #   правила выборов (из статьи)
    types.py
  application/     # оркестрация; зависит только от domain
    node.py        #   Node (asyncio-машина состояний)
    ports.py       #   интерфейсы Transport, Logger
  infrastructure/  # доставка и технические детали
    api.py         #   FastAPI (REST + RPC)
    network.py     #   RpcClient (HTTP-реализация Transport)
    config_loader.py  # YAML/CLI → ClusterConfig
    container.py   #   Dishka-провайдер (composition root)
    logger.py      #   structlog
  main.py          # входная точка: собирает всё через Dishka
```

**DI (Dishka):** `infrastructure/container.py` (провайдер) связывает application-порты
(`Transport`, `Logger`) с конкретными реализациями. `main.py` — единственное место,
где собирается контейнер; FastAPI-эндпоинты получают `Node` через `FromDishka[Node]`
(роутер с `route_class=DishkaRoute`).

## Конфиг

`configs/cluster.yaml` — список узлов, тайминги, кворум (`len(nodes)//2 + 1`).
Число узлов любое (3, 5, 15, ...). Текущий узел задаётся `--self-id`.

## Как проверять

1. Запустить 3 узла → должно появиться ровно одно `{role: leader}`.
2. `GET /status` и `GET /leader` на всех узлах указывают на одного лидера.
3. Деградировать лидера (`POST /role` → follower) → перевыборы → новый лидер.
4. Убить лидера (Ctrl+C) → кластер переизбирает лидера.
5. Swagger UI доступен на `/docs` (проверка/отправка сигналов вручную).

## Следующие этапы

- Этап 2: репликация лога (`AppendEntries` с записями, `commit_index`).