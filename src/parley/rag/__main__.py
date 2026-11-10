from parley.db.session import make_engine, session_scope
from parley.rag.service import DEFAULT_EMBEDDING, DEFAULT_STRATEGY, build_default_index


def main() -> None:
    with session_scope(make_engine()) as session:
        count = build_default_index(session)
    print(f"indexed {count} {DEFAULT_STRATEGY.value} chunks with {DEFAULT_EMBEDDING}")


if __name__ == "__main__":
    main()
