import sqlite3
import openpyxl
from pathlib import Path

EXCEL_PATH = Path(__file__).parent / "Produtos Segmento e Regiao.xlsx"
DB_PATH = Path("/app/data/catalog.db") if Path("/app/data").exists() else Path(__file__).parent / "catalog.db"


ABAS_EXCLUIDAS = {"Base Consolidada", "CAUDA (<R$100k)"}


def build_catalog():
    """Lê a aba Base Consolidada do Excel e grava em SQLite."""
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)

    # Salva nomes das abas (segmentos curados) antes de abrir Base Consolidada
    abas = [s for s in wb.sheetnames if s not in ABAS_EXCLUIDAS]

    ws = wb["Base Consolidada"]

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS produtos")
    conn.execute("DROP TABLE IF EXISTS segmentos_abas")
    conn.execute("CREATE TABLE segmentos_abas (nome TEXT)")
    conn.executemany("INSERT INTO segmentos_abas VALUES (?)", [(a,) for a in abas])
    conn.execute("""
        CREATE TABLE produtos (
            segmento TEXT,
            grupo_produto TEXT,
            sku TEXT,
            produto TEXT,
            uf TEXT,
            cidade TEXT,
            regiao TEXT,
            clientes INTEGER,
            qtd_2025 INTEGER,
            qtd_2026 INTEGER,
            qtd_total INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_seg ON produtos(segmento)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_uf ON produtos(uf)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_regiao ON produtos(regiao)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sku ON produtos(sku)")

    rows = []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
        if i == 0:
            continue  # pula cabeçalho interno das abas (linha 3 do excel = row index 1)
        if not row[0]:
            continue
        # trim espaços dos SKUs
        row = list(row[:11])
        if row[2]:
            row[2] = str(row[2]).strip()
        rows.append(row)
        if len(rows) >= 1000:
            conn.executemany("INSERT INTO produtos VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
            rows = []

    if rows:
        conn.executemany("INSERT INTO produtos VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)

    conn.commit()
    conn.close()
    wb.close()
    print(f"Catálogo construído: {DB_PATH}")


def get_connection():
    return sqlite3.connect(DB_PATH)


def listar_segmentos() -> list[str]:
    """Retorna os segmentos em ordem alfabética."""
    conn = get_connection()
    rows = conn.execute("SELECT nome FROM segmentos_abas ORDER BY nome").fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def listar_regioes(segmento: str | None = None) -> list[str]:
    conn = get_connection()
    if segmento:
        rows = conn.execute(
            "SELECT DISTINCT regiao FROM produtos WHERE segmento = ? ORDER BY regiao",
            (segmento,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT regiao FROM produtos ORDER BY regiao"
        ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def recomendar_produtos(
    segmento: str,
    regiao: str | None = None,
    uf: str | None = None,
    limite: int = 20,
) -> list[dict]:
    """Retorna os produtos mais vendidos para o segmento/região, ordenados por qtd_total."""
    conn = get_connection()
    query = """
        SELECT sku, produto, grupo_produto, regiao, uf,
               SUM(clientes) as total_clientes,
               SUM(qtd_total) as total_vendas
        FROM produtos
        WHERE segmento = ?
    """
    params: list = [segmento]

    if regiao:
        query += " AND regiao = ?"
        params.append(regiao)
    if uf:
        query += " AND uf = ?"
        params.append(uf)

    query += """
        GROUP BY sku, produto, grupo_produto
        ORDER BY total_vendas DESC
        LIMIT ?
    """
    params.append(limite)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [
        {
            "sku": r[0],
            "produto": r[1],
            "grupo_produto": r[2],
            "regiao": r[3],
            "uf": r[4],
            "total_clientes": r[5],
            "total_vendas": r[6],
        }
        for r in rows
    ]


if __name__ == "__main__":
    build_catalog()
