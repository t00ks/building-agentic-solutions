"""
This module implements the TTL feature on short-term memory, removing chat history from
the Postgres checkpointer where no activity is seen over the preceding 24 hours (default).
"""

from datetime import datetime, timedelta

import psycopg
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from structlog import BoundLogger

from core.config import get_config
from core.logging_config import get_logger


class CheckpointsTTLService:

    def __init__(self):
        self.logger: BoundLogger = get_logger(__name__)

    def setup(self):
        self.config = get_config()
        conn_string = self.config.database.postgres_uri
        if not conn_string:
            self.logger.error("POSTGRES_URI connection string not set")
            return False
        self.conn = psycopg.connect(conn_string)
        self.ttl_hours = int(self.config.database.checkpoint_ttl_hours)
        self.ttl_interval = int(self.config.database.checkpoint_ttl_interval)

    def cleanup(self):
        self.conn.close()

    def scrub_old_checkpoints(self):
        expired_threads_sql = """
        SELECT q.thread_id
        FROM (
            SELECT thread_id, max(CAST(checkpoint->>'ts' as timestamptz)) as latest
            FROM checkpoints
            GROUP BY thread_id
            HAVING thread_id NOT IN ('string', 'default')) AS q
        WHERE q.latest < (now() - '%s hours'::interval)
        """

        purge_sql = """
            WITH expired AS (""" + expired_threads_sql + """),
            cp_blobs AS (
                DELETE FROM checkpoint_blobs 
                WHERE thread_id IN (SELECT thread_id FROM expired)
                RETURNING *
            ),
            cp_writes AS (
                DELETE FROM checkpoint_writes 
                WHERE thread_id IN (SELECT thread_id FROM expired)
                RETURNING *
            ),
            cps AS (
                DELETE FROM checkpoints 
                WHERE thread_id IN (SELECT thread_id FROM expired)
                RETURNING *
            )
            SELECT SUM(count) as count, '' as message
            FROM (
                SELECT count(*) as count FROM cp_blobs
                UNION
                SELECT count(*) as count FROM cp_writes
                UNION
                SELECT count(*) as count FROM cps
            ) sq;
        """

        if self.ttl_hours is None or self.ttl_hours <= 0:
            return

        num_threads: int = 0
        num_records: int = 0
        error_message: str = ""

        self.logger.info(f"Scrubbing expired checkpoints older than {self.ttl_hours} hours")
        with self.conn.cursor() as cursor:
            from psycopg.sql import SQL

            sql_count_query = SQL(expired_threads_sql)
            cursor.execute(sql_count_query, (self.ttl_hours,))
            thread_ids = cursor.fetchall()
            self.conn.commit()
        
            num_threads = len(thread_ids)

            sql_purge_query = SQL(purge_sql)
            cursor.execute(sql_purge_query, (self.ttl_hours,))
            sums = cursor.fetchall()

            if sums is None or len(sums) != 1:
                num_records = 0
                error_message = 'An error occurred scrubbing expired checkpoints'
                self.conn.rollback()
            else:
                num_records = int(sums[0][0])
                error_message = sums[0][1]
                self.conn.commit()

        if error_message:
            self.logger.error(error_message)
        else:
            self.logger.info(f"Expired checkpoints scrubbed. Deleted {num_threads} threads and a total of {num_records} records.")


def schedule_checkpoints_ttl(app: FastAPI) -> None:
    # Attach scheduler and service to the app, to run in the background at the specified interval.
    app._scheduler = BackgroundScheduler()
    app._ttlService = CheckpointsTTLService()
    app._ttlService.setup()
    # How often to scrub old checkpoints - default 1 hour if no sensible value given.
    trigger_interval = app._ttlService.ttl_interval
    if trigger_interval is None or trigger_interval <= 0:
        trigger_interval = 1
    # Schedule to run 30 seconds from now, then on the specified interval.
    app._scheduler.add_job(
        app._ttlService.scrub_old_checkpoints,
        trigger="interval",
        hours=trigger_interval,
        next_run_time=datetime.now() + timedelta(seconds=30),
    )
    app._scheduler.start()

def shutdown_checkpoints_ttl(app: FastAPI) -> None:
    app._scheduler.shutdown()
    app._ttlService.cleanup()
    
