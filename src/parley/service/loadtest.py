import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select

from parley.db.models import Customer
from parley.db.session import make_engine, session_scope

DONE = {"resolved", "failed", "awaiting_approval"}


@dataclass
class Sample:
    accepted_ms: float = 0.0
    total_s: float = 0.0
    status: str = "error"


@dataclass
class Report:
    samples: list[Sample] = field(default_factory=list)
    wall_s: float = 0.0

    def render(self) -> str:
        ok = [s for s in self.samples if s.status in DONE and s.status != "failed"]
        totals = sorted(s.total_s for s in ok) or [0.0]
        accepted = sorted(s.accepted_ms for s in self.samples) or [0.0]
        bad = len(self.samples) - len(ok)
        return "\n".join(
            [
                "| Metric | Value |",
                "| --- | --- |",
                f"| Tickets | {len(self.samples)} |",
                f"| Failed or timed out | {bad} |",
                f"| Wall time | {self.wall_s:.1f}s |",
                f"| Throughput | {len(ok) / max(self.wall_s, 1e-9):.1f} tickets/s |",
                f"| Accept latency p50 / p95 | {_pct(accepted, 0.5):.0f} ms / "
                f"{_pct(accepted, 0.95):.0f} ms |",
                f"| Time to reply p50 / p95 / max | {_pct(totals, 0.5):.1f}s / "
                f"{_pct(totals, 0.95):.1f}s / {totals[-1]:.1f}s |",
                f"| Time to reply mean | {statistics.fmean(totals):.1f}s |",
            ]
        )


def _pct(values: list[float], q: float) -> float:
    return values[min(len(values) - 1, round(q * (len(values) - 1)))]


async def one(client: httpx.AsyncClient, email: str, timeout_s: float) -> Sample:
    sample = Sample()
    started = time.perf_counter()
    body = {"sender_email": email, "subject": "Load test", "body": "Where is my parcel?"}
    response = await client.post("/tickets", json=body)
    sample.accepted_ms = (time.perf_counter() - started) * 1000
    if response.status_code != 202:
        return sample
    ticket_id = response.json()["id"]
    while time.perf_counter() - started < timeout_s:
        found = await client.get(f"/tickets/{ticket_id}")
        status = found.json()["status"] if found.status_code == 200 else "error"
        if status in DONE:
            sample.status = status
            sample.total_s = time.perf_counter() - started
            return sample
        await asyncio.sleep(0.25)
    sample.status = "timeout"
    return sample


async def run(url: str, key: str, emails: list[str], tickets: int, concurrency: int) -> Report:
    gate = asyncio.Semaphore(concurrency)
    report = Report()
    headers = {"X-API-Key": key} if key else {}
    async with httpx.AsyncClient(base_url=url, headers=headers, timeout=30) as client:

        async def job(n: int) -> None:
            async with gate:
                report.samples.append(await one(client, emails[n % len(emails)], 120.0))

        started = time.perf_counter()
        await asyncio.gather(*(job(n) for n in range(tickets)))
        report.wall_s = time.perf_counter() - started
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Drive the ticket service with many tickets.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--key", default="")
    parser.add_argument("--tickets", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()
    with session_scope(make_engine()) as session:
        emails = list(session.scalars(select(Customer.email).limit(args.tickets)))
    if not emails:
        raise SystemExit("no customers in the database; run `make seed`")
    print(asyncio.run(run(args.url, args.key, emails, args.tickets, args.concurrency)).render())


if __name__ == "__main__":
    main()
