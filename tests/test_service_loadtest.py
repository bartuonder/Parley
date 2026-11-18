import asyncio

import httpx

from parley.service.loadtest import DONE, Report, Sample, one, run


def test_the_report_summarizes_latency_and_counts_failures() -> None:
    report = Report(
        samples=[Sample(10, t, "resolved") for t in (1.0, 2.0, 3.0, 4.0)]
        + [Sample(5, 9, "timeout")],
        wall_s=4.0,
    )
    text = report.render()
    assert "| Tickets | 5 |" in text and "| Failed or timed out | 1 |" in text
    assert "| Throughput | 1.0 tickets/s |" in text
    assert "Time to reply p50 / p95 / max | 3.0s / 4.0s / 4.0s" in text


def test_a_ticket_is_followed_until_it_is_done() -> None:
    polls = iter(["queued", "running", "resolved"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"id": "T-1"})
        return httpx.Response(200, json={"status": next(polls)})

    async def go() -> Sample:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            return await one(client, "a@example.com", 5.0)

    sample = asyncio.run(go())
    assert sample.status == "resolved" and sample.status in DONE and sample.total_s > 0.4


def test_a_refused_ticket_is_reported_as_an_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={})

    async def go() -> Sample:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://t"
        ) as client:
            return await one(client, "a@example.com", 5.0)

    assert asyncio.run(go()).status == "error"


def test_the_runner_spreads_tickets_over_the_given_emails(monkeypatch: object) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            seen.append(request.content.decode())
            return httpx.Response(202, json={"id": f"T-{len(seen)}"})
        return httpx.Response(200, json={"status": "resolved"})

    real = httpx.AsyncClient

    def fake_client(**kwargs: object) -> httpx.AsyncClient:
        return real(transport=httpx.MockTransport(handler), **kwargs)  # type: ignore[arg-type]

    import parley.service.loadtest as module

    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client)  # type: ignore[attr-defined]
    report = asyncio.run(run("http://t", "", ["a@example.com", "b@example.com"], 4, 2))
    assert len(report.samples) == 4 and all(s.status == "resolved" for s in report.samples)
    assert sum("a@example.com" in body for body in seen) == 2
