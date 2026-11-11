from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from parley.db.session import make_engine, to_driver_url
from parley.settings import PROJECT_ROOT, get_settings

EVAL_SUFFIX = "_eval"


def eval_database_url() -> str:
    url = make_url(str(get_settings().database_url))
    return url.set(database=f"{url.database}{EVAL_SUFFIX}").render_as_string(hide_password=False)


def recreate_eval_database(url: str | None = None) -> Engine:
    """Drop and rebuild the throwaway eval database, so runs never touch the dev data."""
    target = url or eval_database_url()
    name = make_url(target).database or ""
    if not name.endswith(EVAL_SUFFIX):
        raise ValueError(f"refusing to recreate a database not named *{EVAL_SUFFIX}: {name}")
    admin_url = make_url(target).set(database="postgres").render_as_string(hide_password=False)
    admin = create_engine(to_driver_url(admin_url), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.attributes["url"] = target
    command.upgrade(config, "head")
    return make_engine(target)
