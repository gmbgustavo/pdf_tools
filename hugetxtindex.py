#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from pathlib import Path


def fts5_quote_literal(text: str) -> str:
    # Quote as a single literal phrase for FTS5.
    # Doubles embedded double-quotes per SQL/FTS quoting rules.
    return '"' + text.replace('"', '""') + '"'


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pesquisar substrings em um arquivo indexado com SQLite FTS5 trigram."
    )
    parser.add_argument("query", help="Substring literal a pesquisar")
    parser.add_argument(
        "db",
        nargs="?",
        default="breach.db",
        help="Caminho do banco SQLite (default: breach.db)",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=50,
        help="Número máximo de resultados exibidos (default: 50)",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="Apenas contar resultados, sem imprimir linhas",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[erro] Banco não encontrado: {db_path}", file=sys.stderr)
        return 2

    q = args.query

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Trigram FTS5 is ideal for substring search, but queries shorter than 3 chars
    # are not a good fit. For those, fall back to a full scan.
    if len(q) >= 3:
        match_expr = fts5_quote_literal(q)
        sql_count = "SELECT count(*) AS c FROM breach WHERE breach MATCH ?"
        sql_rows = "SELECT rowid, line FROM breach WHERE breach MATCH ? LIMIT ?"
        params_count = (match_expr,)
        params_rows = (match_expr, args.limit if args.limit > 0 else -1)
    else:
        print(
            "[aviso] Query com menos de 3 caracteres: fallback para varredura completa (mais lento).",
            file=sys.stderr,
        )
        sql_count = "SELECT count(*) AS c FROM breach WHERE instr(line, ?) > 0"
        sql_rows = "SELECT rowid, line FROM breach WHERE instr(line, ?) > 0 LIMIT ?"
        params_count = (q,)
        params_rows = (q, args.limit if args.limit > 0 else -1)

    if args.count:
        row = cur.execute(sql_count, params_count).fetchone()
        print(row["c"] if row else 0)
        return 0

    found = 0
    for row in cur.execute(sql_rows, params_rows):
        print(f"{row['rowid']}:{row['line']}", end="" if row['line'].endswith("\n") else "\n")
        found += 1

    if found == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
