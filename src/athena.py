import io
import time

import boto3
import pandas as pd

from config import (
    ATHENA_DATABASE,
    ATHENA_RESULTS_PREFIX,
    ATHENA_WORKGROUP,
    BUCKET,
)

POLL_SECONDS = 1.0
TIMEOUT_SECONDS = 120

_athena = None
_s3 = None


class AthenaQueryError(RuntimeError):
    pass


def _clients():
    global _athena, _s3
    if _athena is None:
        _athena = boto3.client("athena")
        _s3 = boto3.client("s3")
    return _athena, _s3


def run_query(sql):
    athena, s3 = _clients()
    query_id = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        WorkGroup=ATHENA_WORKGROUP,
    )["QueryExecutionId"]

    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)
        state = status["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = status["QueryExecution"]["Status"].get("StateChangeReason", "")
            raise AthenaQueryError(f"{state}: {reason}")
        if time.monotonic() > deadline:
            raise AthenaQueryError(f"timeout after {TIMEOUT_SECONDS}s on {query_id}")
        time.sleep(POLL_SECONDS)

    body = s3.get_object(
        Bucket=BUCKET, Key=f"{ATHENA_RESULTS_PREFIX}/{query_id}.csv"
    )["Body"].read()
    return pd.read_csv(io.BytesIO(body))