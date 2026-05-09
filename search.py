import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Union

DB_PATH = Path("products.db")


def _compile_ts_regex(regex_literal: str) -> re.Pattern:
    # Strictly require /pattern/flags syntax.
    if not regex_literal.startswith("/") or regex_literal.count("/") < 2:
        raise ValueError("Expected TypeScript regex literal format: /pattern/flags")

    last_slash = regex_literal.rfind("/")
    if last_slash <= 0:
        raise ValueError("Expected TypeScript regex literal format: /pattern/flags")

    pattern = regex_literal[1:last_slash]
    flags_str = regex_literal[last_slash + 1 :]

    flags = 0
    for ch in flags_str:
        if ch == "i":
            flags |= re.IGNORECASE
        elif ch == "m":
            flags |= re.MULTILINE
        elif ch == "s":
            flags |= re.DOTALL
        elif ch == "":
            continue
        else:
            raise ValueError(f"Unsupported regex flag: {ch}")

    return re.compile(pattern, flags)


def get_connection(db_path: Union[Path, str] = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            absolute_site_link TEXT,
            price REAL,
            created_date TEXT,
            updated_date TEXT
        )
        """
    )

    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
            id UNINDEXED,
            name,
            description
        )
        """
    )
    conn.commit()


def rebuild_index(
    products: Iterable[Mapping[str, Any]], db_path: Union[Path, str] = DB_PATH
) -> int:
    conn = get_connection(db_path)
    try:
        init_db(conn)
        conn.execute("DELETE FROM products")
        conn.execute("DELETE FROM products_fts")

        rows = [
            (
                str(p.get("id") or ""),
                p.get("name") or "",
                p.get("description") or "",
                p.get("absolute_site_link") or "",
                p.get("price"),
                p.get("created_date") or "",
                p.get("updated_date") or "",
            )
            for p in products
            if p.get("id") is not None
        ]

        conn.executemany(
            """
            INSERT INTO products (
                id, name, description, absolute_site_link, price, created_date, updated_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.executemany(
            """
            INSERT INTO products_fts (id, name, description)
            VALUES (?, ?, ?)
            """,
            [(r[0], r[1], r[2]) for r in rows],
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def search_regex(
    regex_pattern: str,
    limit: int = 20,
    order_by: str = "date",
    sort: str = "desc",
    created_since: str = "",
    updated_since: str = "",
    db_path: Union[Path, str] = DB_PATH,
) -> List[sqlite3.Row]:
    sort_columns = {
        "name": "p.name COLLATE NOCASE",
        "price": "p.price",
        "date": "p.updated_date",
    }
    order_sql = "ASC" if sort.lower() == "asc" else "DESC"
    sort_expr = sort_columns.get(order_by, sort_columns["date"])

    where_clauses: List[str] = []
    params: List[Any] = []
    if created_since:
        where_clauses.append("p.created_date >= ?")
        params.append(created_since)
    if updated_since:
        where_clauses.append("p.updated_date >= ?")
        params.append(updated_since)

    conn = get_connection(db_path)
    try:
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        sql = f"""
            SELECT
                p.id,
                p.name,
                p.description,
                p.absolute_site_link,
                p.price,
                p.updated_date
            FROM products p
            WHERE {where_sql}
            ORDER BY {sort_expr} {order_sql}
            LIMIT ?
        """
        params.append(int(max(limit * 5, limit)))
        cur = conn.execute(sql, tuple(params))
        rows = cur.fetchall()

        compiled = _compile_ts_regex(regex_pattern)
        filtered = []
        for row in rows:
            haystack = f"{row['name'] or ''}\n{row['description'] or ''}"
            if compiled.search(haystack):
                filtered.append(row)
                if len(filtered) >= limit:
                    break
        return filtered
    finally:
        conn.close()


def _snippet(text: str, max_len: int = 140) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def main() -> None:
    parser = argparse.ArgumentParser(description="Keyword search products index")
    parser.add_argument("--limit", type=int, default=100, help="Max results")
    parser.add_argument(
        "--order-by",
        choices=["name", "price", "date"],
        default="date",
        help="Order-by column",
    )
    parser.add_argument(
        "--sort", choices=["asc", "desc"], default="desc", help="Sort direction"
    )
    parser.add_argument(
        "--created-since",
        dest="created_since",
        default="",
        help="Include only rows with created_date >= this value",
    )
    parser.add_argument(
        "--updated-since",
        dest="updated_since",
        default="",
        help="Include only rows with updated_date >= this value",
    )
    parser.add_argument(
        "--regex",
        required=True,
        help="Regex in TS-style /pattern/flags (supports i,m,s)",
    )
    args = parser.parse_args()

    try:
        rows = search_regex(
            args.regex,
            limit=args.limit,
            order_by=args.order_by,
            sort=args.sort,
            created_since=args.created_since,
            updated_since=args.updated_since,
        )
    except ValueError as exc:
        raise SystemExit(f"Invalid --regex: {exc}")
    except re.error as exc:
        raise SystemExit(f"Invalid --regex pattern: {exc}")
    if not rows:
        return

    for row in rows:
        payload = {
            "name": row["name"],
            "price": row["price"],
            "absolute_site_link": row["absolute_site_link"],
            "updated_date": row["updated_date"],
        }
        print(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    main()
