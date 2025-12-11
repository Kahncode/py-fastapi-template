import re
import uuid
from collections.abc import Awaitable, Callable, Sequence
from contextvars import ContextVar
from types import TracebackType
from typing import Any

from sqlalchemy import ClauseElement, text
from sqlalchemy.engine import Result, Row
from sqlalchemy.exc import ArgumentError, DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from shared.core.logging import get_logger
from shared.services.base_service import BaseService


# Declarative syntax for ORM models
# See: https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html#declarative-mapping
class Base(DeclarativeBase):
    pass


_DB_PROTOCOL_REGEX = r"^(?P<proto>[a-zA-Z0-9_+\-]+)://"

# Handling pgbouncer Prepared Statement Issues in SQLAlchemy Async Engine
# --------------------------------------------------------------

# Problem:
# ----------
# - When using pgbouncer (or supabase/supavisor) in transaction pooling mode with SQLAlchemy's asyncpg driver,
#   prepared statements can lead to errors such as DuplicatePreparedStatementError or InvalidSQLStatementNameError.
# - This is due to pgbouncer dropping prepared statements when connections are returned to the pool,
#   causing subsequent executions of those statements to fail.

# Solutions/Workarounds Implemented:
# ----------------------------------
#   - Unique Prepared Statement Names: The code sets 'prepared_statement_name_func' in connect_args to generate a unique name for each statement using UUIDs.
#   - Prepared statement cache sizes are set to 0 to disable caching, forcing new statements to be prepared each time.
#   - Retry on prepared statement error. This works as long as the statement is not reused by the ORM, which is not always the case.

# Solutions/Workarounds NOT Implemented:
# ----------------------------------
# - NullPool Usage:
#   - The SQLAlchemy engine can be configured to use NullPool, which disables SQLAlchemy's connection pooling.
#   - This helps avoid issues with pgbouncer's own pooling, but adds 200+ms to each session, and increases the amount of connections.
#   - This was deemed to not be an acceptable solution both in latency and scalability.

# - Connecting directly and bypassing pgbouncer/supavisor:
#   - This is undesireable from a scalability point of view, and should only be used as a last resort.

# - autoflush=True: Flushes pending changes to the database as early as possible, reducing the chance of conflicts with prepared statements.
#   - Disabled for now as it may affect performance, to be reevaluated if the issue persists.

# Limitations:
# ------------
# - These workarounds reduce the frequency of errors but do not fully resolve all issues with pgbouncer.
# - Some errors may still occur due to the fundamental limitations of pgbouncer's pooling and statement management.

# References:
# -----------
# - https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#prepared-statement-name-with-pgbouncer
# - https://github.com/supabase/supavisor/issues/287


def _should_retry_on_exception(exception: BaseException) -> bool:
    """Determine if we should retry based on the exception type."""
    if isinstance(exception, (OperationalError, OSError)):
        return True
    if isinstance(exception, DBAPIError):
        # Retry on prepared statement errors due to spurious errors with pgbouncer, even with unique names
        # However in many cases the retry will fail because it's reusing the same prepared statement name
        msg = str(exception)
        if "DuplicatePreparedStatementError" in msg or "InvalidSQLStatementNameError" in msg:
            get_logger().warning("Retrying due to prepared statement error with pgbouncer", error=msg)
            return True

    return False


retry_on_db_errors = retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_should_retry_on_exception),
)


def _get_prepared_stmt_name() -> str:
    return f"_asyncpg_stmt_{uuid.uuid4()}_"


class SQLDatabaseService(BaseService):
    """
    Async SQLAlchemy database service.

    - Heavily focused on postgresql with asyncpg driver.
    - Use connect_args for driver-specific options (SSL, credentials, etc.).
    - engine_args can be used for SQLAlchemy engine configuration (pooling, etc.).

    Configuration examples (YAML):

    # Example 1: Full connection URL
    url: "postgresql://user:password@10.20.30.40:5432/db_name?sslmode=require"

    # Example 2: Minimal URL with connect_args
    url: "postgresql://"
    connect_args:
      sslmode: "require"
      user: "user"
      password: "password"
      host: "10.20.30.40"
      port: 5432
      database: "db_name"

    """

    # Configuration fields
    url: str = ""
    engine_args: dict
    connect_args: dict

    # Runtime fields
    engine: AsyncEngine
    session_maker: sessionmaker
    # Only one session per request, stored in context var
    _session_ctx: ContextVar[AsyncSession | None] = ContextVar("db_session", default=None)

    def __init__(self, **config: object) -> None:
        self.url = str(config.get("url", ""))
        self.engine = None
        self.session_maker = None

        self.engine_args = config.get("engine_args", {})
        if "pool_size" not in self.engine_args:
            self.engine_args["pool_size"] = 5  # default pool size
        if "max_overflow" not in self.engine_args:
            self.engine_args["max_overflow"] = 0  # Do not allow overflow connections beyond pool_size
        if "pool_pre_ping" not in self.engine_args:
            self.engine_args["pool_pre_ping"] = True
        if "pool_recycle" not in self.engine_args:
            self.engine_args["pool_recycle"] = 900  # recycle connections every 15 minutes

        self.connect_args = config.get("connect_args", {})

        # Fix pgbouncer error: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#prepared-statement-name-with-pgbouncer
        # Note that this mostly works but we still have the error, not because of UUID collision but probably because pgbouncer
        # spuriously drops the statements before we can execute them, or that we end up using some different connection than the one
        # where the prepared statement was created, due to pgbouncer pooling.
        self.connect_args["prepared_statement_name_func"] = _get_prepared_stmt_name
        self.connect_args["statement_cache_size"] = 0
        self.connect_args["prepared_statement_cache_size"] = 0

        logger = get_logger()

        if not self.url:
            msg = "Database URL is required for SQLAlchemyAsyncDatabaseService"
            raise ValueError(msg)

        # Fix protocol for PostgreSQL to ensure async
        match = re.match(_DB_PROTOCOL_REGEX, self.url)
        if match:
            proto = match.group("proto")
            if "postgre" in proto:
                self.url = re.sub(_DB_PROTOCOL_REGEX, "postgresql+asyncpg://", self.url, count=1)
            else:
                logger.warning("Unsupported DB protocol for SQLAlchemy async engine", protocol=proto)
        else:
            msg = "Invalid database URL format. Must contain at least a protocol (e.g., postgresql://)"
            raise ValueError(msg)

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        """
        Disconnect context session to avoid session leaks.
        """
        await self.disconnect_session()

    async def connect(self) -> None:
        if self.get_session() is not None:
            return  # already connected

        logger = get_logger()
        if self.engine is None or self.session_maker is None:
            try:
                async_creator = self._get_async_creator_func()
                if async_creator is not None:
                    self.engine_args["async_creator"] = async_creator  # Only feed async_creator if it is valid

                self.engine = create_async_engine(
                    self.url,
                    connect_args=self.connect_args,
                    **self.engine_args,
                )

                self.session_maker = sessionmaker(class_=AsyncSession, expire_on_commit=False)
            except (ArgumentError, OperationalError, DBAPIError):
                logger.exception("Failed to create SQLAlchemy async engine")
                raise
        try:
            session = self.session_maker(bind=self.engine)
            self._session_ctx.set(session)

        except Exception:
            logger.exception("Failed to create SQLAlchemy async session", pool_status=self.engine.pool.status())
            raise

    def _get_async_creator_func(self) -> Callable[[], Awaitable[Any]] | None:
        """
        Return an async creator function for the engine.

        This is needed for some async drivers that require a coroutine to create connections.
        """
        # For most drivers, we can just return None
        return None

    async def is_connected(self) -> bool:
        """
        Check if the session is valid and the connection is alive.

        Returns True if connected, False otherwise.
        """
        return self.get_session() is not None

    async def disconnect_session(self) -> None:
        """
        Disconnect the current session.
        """
        session = self._session_ctx.get()
        if session:
            await session.close()
            self._session_ctx.set(None)

    async def disconnect(self) -> None:
        """
        Disconnect fully and dispose of the engine, only do upon application shutdown.
        """
        await self.disconnect_session()

        self.session_maker = None
        if self.engine:
            await self.engine.dispose()
            self.engine = None

    def get_session(self) -> AsyncSession:
        """
        Return the current request's session, or create one if not set.
        """
        return self._session_ctx.get()

    async def test_connection(self) -> bool:
        """
        Test connectivity to the database by executing a simple query.
        """
        await self.connect()
        result = await self.execute(text("SELECT 1"))
        success: bool = result.scalar() == 1
        logger = get_logger()
        logger.debug("Database connectivity test result", success=success)
        return success

    def log_pool_status(self) -> None:
        """
        Print connection pool status for debugging.
        """
        logger = get_logger()
        if self.engine and self.engine.pool:
            logger.debug(self.engine.pool.status())
        else:
            logger.debug("Engine or pool not are None, cannot log pool status")

    @retry_on_db_errors
    async def execute(
        self, query: ClauseElement | str, params: dict | None = None, *, auto_commit: bool = True
    ) -> Result:
        """
        Execute a query, which can be a raw SQL string or a SQLAlchemy ClauseElement.

        Handles connection errors and attempts to reconnect once.
        """
        await self.connect()

        if isinstance(query, str):
            result = await self.get_session().execute(text(query), params or {})
        elif isinstance(query, ClauseElement):
            result = await self.get_session().execute(query, params or {})
        else:
            msg = "Query must be a SQL string or SQLAlchemy ClauseElement"
            raise TypeError(msg)
        if auto_commit:
            await self.get_session().commit()  # for now, commit after every execute. We will handle transactions later
        return result

    async def fetchone(self, query: ClauseElement | str, params: dict | None = None) -> Row[Any] | None:
        result = await self.execute(query, params)
        return result.fetchone()

    async def fetchall(self, query: ClauseElement | str, params: dict | None = None) -> Sequence[Row[Any]] | None:
        result = await self.execute(query, params)
        return result.fetchall()

    @retry_on_db_errors
    async def add(self, obj: object) -> None:
        await self.connect()
        self.get_session().add(obj)

    @retry_on_db_errors
    async def add_all(self, objs: list[object]) -> None:
        await self.connect()
        self.get_session().add_all(objs)

    @retry_on_db_errors
    async def delete(self, obj: object) -> None:
        await self.connect()
        await self.get_session().delete(obj)

    @retry_on_db_errors
    async def commit(self) -> None:
        await self.connect()
        await self.get_session().commit()

    @retry_on_db_errors
    async def rollback(self) -> None:
        await self.connect()
        await self.get_session().rollback()

    @retry_on_db_errors
    async def refresh(self, obj: object) -> None:
        await self.connect()
        await self.get_session().refresh(obj)
