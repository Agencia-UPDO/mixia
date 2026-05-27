import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from woocommerce import API

load_dotenv(override=True)

WOOCOMMERCE_URL = os.environ["WOOCOMMERCE_URL"]


def get_client():
    return API(
        url=WOOCOMMERCE_URL,
        consumer_key=os.environ["WOOCOMMERCE_KEY"],
        consumer_secret=os.environ["WOOCOMMERCE_SECRET"],
        version="wc/v3",
        timeout=15,
    )


def _extrair_min_qty(variacao: dict | None) -> int | None:
    """
    Tenta extrair a quantidade mínima de compra da variação.
    Busca em meta_data por chaves comuns de plugins de min/max qty.
    """
    if not variacao:
        return None
    for meta in variacao.get("meta_data", []):
        key = meta.get("key", "")
        if key in ("minimum_allowed_quantity", "min_quantity", "_wc_min_qty",
                    "variation_minimum_allowed_quantity", "group_of_quantity"):
            try:
                val = int(meta["value"])
                if val > 0:
                    return val
            except (ValueError, TypeError):
                pass
    return None


def _formatar_produto(p: dict, variacao: dict | None = None) -> dict:
    """Monta dict de produto priorizando Display ou Unidade."""
    base_id = p["id"]
    url_base = f"{WOOCOMMERCE_URL}/?add-to-cart={base_id}"

    if variacao:
        preco = variacao.get("price", "")
        estoque = variacao.get("stock_quantity")
        em_estoque = variacao.get("in_stock", estoque is None or estoque > 0)
        # descobre qual formato foi selecionado
        formato = next(
            (a.get("option", "Display") for a in variacao.get("attributes", [])
             if "formato" in a.get("slug", "").lower()),
            "Display"
        )
        slug_formato = formato.lower().replace(" ", "-")
        add_to_cart = f"{url_base}&variation_id={variacao['id']}&attribute_pa_formato-de-compra={slug_formato}"
    else:
        preco = p.get("price", "")
        estoque = p.get("stock_quantity")
        em_estoque = p.get("in_stock", False)
        add_to_cart = url_base
        formato = "Unidade"

    min_qty = _extrair_min_qty(variacao)

    result = {
        "id": base_id,
        "sku": p["sku"],
        "nome": p["name"],
        "formato": formato,
        "preco": preco,
        "estoque": estoque,
        "em_estoque": em_estoque,
        "imagem": p["images"][0]["src"] if p.get("images") else None,
        "url": p.get("permalink", ""),
        "add_to_cart_url": add_to_cart,
    }
    if min_qty:
        result["min_qty"] = min_qty
    return result


FORMATOS_PREFERIDOS = ["display", "unidade"]


def _buscar_variacao_display(produto_id: int) -> dict | None:
    """
    Busca a variação Display de um produto variável.
    Prioridade: Display > Unidade.
    """
    wcapi = get_client()
    r = wcapi.get(f"products/{produto_id}/variations", params={"per_page": 20})
    if r.status_code != 200:
        return None

    por_formato: dict[str, dict] = {}
    for v in r.json():
        for attr in v.get("attributes", []):
            if "formato" in attr.get("slug", "").lower():
                por_formato[attr.get("option", "").lower()] = v

    # Ordem: Display primeiro, depois Unidade.
    for formato in FORMATOS_PREFERIDOS:
        if formato in por_formato:
            return por_formato[formato]
    return None


def buscar_produtos_por_skus(skus: list[str], formato_preferido: str = "display") -> list[dict]:
    """
    Busca produtos no WooCommerce pelos SKUs.
    Para produtos variáveis, busca variações em paralelo (até 8 simultâneas).
    """
    wcapi = get_client()
    produtos_brutos = []

    for i in range(0, len(skus), 50):
        batch = [s.strip() for s in skus[i:i + 50]]
        r = wcapi.get("products", params={"sku": ",".join(batch), "per_page": 50})
        if r.status_code != 200:
            continue
        produtos_brutos.extend(r.json())

    # Separa variáveis de simples
    variaveis = [p for p in produtos_brutos if p.get("type") == "variable" and p.get("variations")]
    simples   = [p for p in produtos_brutos if p not in variaveis]

    resultado = [_formatar_produto(p, None) for p in simples]

    # Busca variações em paralelo
    def buscar(p):
        variacao = _buscar_variacao_display(p["id"])
        return _formatar_produto(p, variacao)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(buscar, p): p for p in variaveis}
        for future in as_completed(futures):
            try:
                resultado.append(future.result())
            except Exception:
                pass

    return resultado
