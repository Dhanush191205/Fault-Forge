"""Run with python -m app.worker; PostgreSQL workers claim independently with expiring leases."""
import logging
import time
from .config import get_settings
from .db import SessionLocal
from .scenarios import claim_job, process_job


def run() -> None:
    """Process durable jobs until interrupted; transient infrastructure errors retry after a short pause."""
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            with SessionLocal() as db:
                claim = claim_job(db)
            if claim:
                process_job(SessionLocal, get_settings(), *claim)
            else:
                time.sleep(1)
        except KeyboardInterrupt:
            return
        except Exception:
            logging.error("worker_infrastructure_unavailable")
            time.sleep(3)


if __name__ == "__main__":
    run()
