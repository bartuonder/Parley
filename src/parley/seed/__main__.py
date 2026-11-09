import argparse

from parley.db.session import make_engine, session_scope
from parley.seed.config import SeedConfig
from parley.seed.runner import fingerprint, seed_database, summarize
from parley.seed.static_data import check_static_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the synthetic world from scratch.")
    parser.add_argument("--seed", type=int, default=SeedConfig.seed)
    args = parser.parse_args()

    static = check_static_data()
    engine = make_engine()
    with session_scope(engine) as session:
        world = seed_database(session, SeedConfig(seed=args.seed))
        session.flush()
        digest = fingerprint(session)
    for name, count in summarize(world).items():
        print(f"{name:<14}{count}")
    for name, count in static.items():
        print(f"{name:<14}{count}")
    print(f"fingerprint   {digest[:16]}")


if __name__ == "__main__":
    main()
