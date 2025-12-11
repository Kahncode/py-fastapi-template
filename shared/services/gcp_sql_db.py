from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
from google.cloud.sql.connector import Connector, IPTypes

from shared.services.sql_db import SQLDatabaseService

# Research links:
# https://github.com/GoogleCloudPlatform/cloud-sql-python-connector
# Official docs to connect from Cloud RUn: https://cloud.google.com/sql/docs/mysql/connect-run#python_1
# Interesting issue implementing what we want: https://github.com/sqlalchemy/sqlalchemy/issues/8215


class GCPCloudSQLDatabaseService(SQLDatabaseService):
    """
    SQL Database Service for GCP Cloud SQL using Python Connector.

    IMPORTANT NOTE: Only supports asyncpg driver for PostgreSQL.

    Example configuration (YAML):

    cloud_sql_name: "project:region:instance"
    url: "postgresql://" #Protocol only
    connect_args:
      user: "service-account@project.iam" # IAM user or Service account without .gserviceaccount.com
      db: "postgres" # Note that the expected parameter is "db" not "database" like asyncpg expects

    """

    cloud_sql_name: str  # Cloud SQL name in the form "project:region:instance"

    # Runtime vars
    connector: Connector | None = None

    def __init__(self, **config: object) -> None:
        self.cloud_sql_name = str(config.pop("cloud_sql_name", None))
        super().__init__(**config)

    def _get_async_creator_func(self) -> Callable[[], Awaitable[Any]] | None:
        return self._get_async_creator

    async def _get_async_creator(self) -> asyncpg.Connection:
        if not self.connector:
            # lazy refresh strategy as recommended in the docs for cloud run
            self.connector = Connector(ip_type=IPTypes.PUBLIC, refresh_strategy="lazy", enable_iam_auth=True)

        return await self.connector.connect_async(self.cloud_sql_name, "asyncpg", **self.connect_args)
