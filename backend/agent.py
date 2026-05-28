import json
import os
import re
from dotenv import load_dotenv
import anthropic
from catalog import listar_segmentos, listar_regioes, recomendar_produtos
from woocommerce_client import buscar_produtos_por_skus

load_dotenv(override=True)
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-haiku-4-5-20251001"

TOOLS = [
    {
        "name": "listar_segmentos",
        "description": "Retorna todos os segmentos de mercado disponíveis no catálogo.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "listar_regioes",
        "description": "Retorna as regiões geográficas disponíveis, opcionalmente filtradas por segmento.",
        "input_schema": {
            "type": "object",
            "properties": {
                "segmento": {
                    "type": "string",
                    "description": "Segmento de mercado para filtrar as regiões (opcional).",
                }
            },
            "required": [],
        },
    },
    {
        "name": "recomendar_produtos",
        "description": (
            "Recomenda os produtos mais vendidos para um segmento e região. "
            "Usa dados históricos de vendas para ranquear os produtos mais relevantes. "
            "Retorna SKU, nome do produto e volume de vendas. "
            "Segmentos disponíveis: BRINQUEDOS, BRINQUEDOS EDUCATIVOS, CONVENIÊNCIA, FARMÁCIA, PAPELARIA, SUPERMERCADOS. "
            "Regiões disponíveis: NORTE, NORDESTE, CENTRO-OESTE, SUDESTE, SUL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "segmento": {
                    "type": "string",
                    "description": "Segmento de mercado do lojista (ex: BRINQUEDOS, FARMÁCIA, PAPELARIA).",
                },
                "regiao": {
                    "type": "string",
                    "description": "Região geográfica (ex: SUDESTE, NORTE, SUL). Opcional.",
                },
                "limite": {
                    "type": "integer",
                    "description": "Quantidade máxima de produtos a retornar. Padrão: 20.",
                },
            },
            "required": ["segmento"],
        },
    },
    {
        "name": "buscar_produtos_woocommerce",
        "description": (
            "Busca informações em tempo real dos produtos no WooCommerce (preço, estoque, imagem, link). "
            "Retorna sempre Display ou Unidade."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "skus": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de SKUs para buscar no WooCommerce.",
                },
                "formato_preferido": {
                    "type": "string",
                    "enum": ["display", "unidade"],
                    "description": (
                        "Sempre use 'display'. Se o produto não tiver Display, "
                        "retorna Unidade automaticamente."
                    ),
                },
            },
            "required": ["skus"],
        },
    },
]

SYSTEM_PROMPT = """Você é um assistente de vendas da Polibrinq (brinquedos B2B).

══════════════════════════════════════════════════════════════
PROIBIDO — QUEBRAR QUALQUER REGRA ABAIXO É FALHA CRÍTICA:
══════════════════════════════════════════════════════════════
1. NUNCA use o caractere | (pipe). ZERO tabelas markdown.
2. NUNCA escreva a palavra "estoque" ou "disponível" ou "indisponível".
3. NUNCA liste ou mencione produtos removidos/sem estoque/excluídos.
4. NUNCA use ✅ ❌ ⚠️ como indicador de status.
5. NUNCA faça perguntas ("Posso ajustar?", "Deseja algo mais?").
6. NUNCA mostre contagem de unidades em estoque.
7. NUNCA mostre subtotais parciais.
8. NUNCA numere os produtos fora do JSON.
9. NUNCA use blocos ">" de citação markdown.
10. Sua resposta deve conter SOMENTE o que está no template abaixo.
11. NUNCA use travessão (—) nos textos. Use vírgula ou ponto.

══════════════════════════════════════════════════════════════
REGRAS DE NEGÓCIO:
══════════════════════════════════════════════════════════════
- Pedido mínimo OBRIGATÓRIO: R$ 1.500. O total DEVE ser ≥ R$ 1.500. NUNCA mostre produtos se o total for menor.
- Formato SEMPRE Display. Se o produto não tiver Display, use Unidade.
- A quantidade de cada produto deve respeitar a quantidade mínima da variação (ex: Display de 24 und = mínimo 24).
- Mínimo de 8 produtos na recomendação, sempre.
- Ajuste quantidades para atingir o mínimo de R$ 1.500. Diversifique o mix, aumente quantidades se necessário.

══════════════════════════════════════════════════════════════
TEMPLATE OBRIGATÓRIO (copie EXATAMENTE esta estrutura):
══════════════════════════════════════════════════════════════

Aqui está a lista perfeita de produtos para a sua loja! 🎯

```json
[{"nome":"Produto","formato":"Display","preco":"99.90","quantidade":2,"em_estoque":true,"imagem":"https://...","add_to_cart_url":"https://..."}]
```

💰 **Total estimado: R$ X.XXX,XX**

💡 **Dicas:**
- Uma dica curta
- Outra dica curta

══════════════════════════════════════════════════════════════
ISSO É TUDO. Nada antes, nada depois, nada além.
══════════════════════════════════════════════════════════════

MAPEAMENTO DE LOCALIZAÇÃO → REGIÃO:
- Norte: AM, PA, AC, RO, RR, AP, TO
- Nordeste: BA, PE, CE, MA, PB, RN, PI, AL, SE
- Centro-Oeste: GO, MT, MS, DF
- Sudeste: SP, RJ, MG, ES
- Sul: PR, SC, RS
Use o estado informado para determinar a região correta.

FLUXO:
1. recomendar_produtos(segmento, regiao) — regiao é NORTE, NORDESTE, CENTRO-OESTE, SUDESTE ou SUL
2. buscar_produtos_woocommerce(skus, formato_preferido)
3. DESCARTE silenciosamente produtos sem dados/fora de estoque
4. Monte o JSON apenas com produtos válidos
5. Calcule total (preço × quantidade de cada) para ≥ R$ 1.500
6. Responda APENAS com o template acima"""


def processar_tool(nome: str, inputs: dict) -> str:
    if nome == "listar_segmentos":
        resultado = listar_segmentos()
        return json.dumps(resultado, ensure_ascii=False)

    if nome == "listar_regioes":
        resultado = listar_regioes(inputs.get("segmento"))
        return json.dumps(resultado, ensure_ascii=False)

    if nome == "recomendar_produtos":
        resultado = recomendar_produtos(
            segmento=inputs["segmento"],
            regiao=inputs.get("regiao"),
            limite=inputs.get("limite", 20),
        )
        return json.dumps(resultado, ensure_ascii=False)

    if nome == "buscar_produtos_woocommerce":
        resultado = buscar_produtos_por_skus(
            inputs["skus"],
            formato_preferido=inputs.get("formato_preferido", "display"),
        )
        return json.dumps(resultado, ensure_ascii=False)

    return json.dumps({"erro": f"Tool desconhecida: {nome}"})


def chat(historico: list[dict], mensagem_usuario: str) -> tuple[str, list[dict], list[dict], float]:
    """
    Retorna (resposta_texto, historico_atualizado, produtos, total).
    produtos é a lista de produtos extraída para o frontend usar diretamente.
    """
    historico = historico + [{"role": "user", "content": mensagem_usuario}]
    # Captura resultados das chamadas ao WooCommerce ao longo do loop
    woo_results: list[dict] = []

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=historico,
        )

        # Adiciona resposta do assistente ao histórico
        historico = historico + [{"role": "assistant", "content": response.content}]

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    resultado = processar_tool(block.name, block.input)
                    if block.name == "buscar_produtos_woocommerce":
                        try:
                            data = json.loads(resultado)
                            if isinstance(data, list):
                                woo_results.extend(data)
                        except Exception:
                            pass
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": resultado,
                    })

            historico = historico + [{"role": "user", "content": tool_results}]
            continue

        # stop_reason == "end_turn" — extrai texto final
        texto = next(
            (b.text for b in response.content if hasattr(b, "text")), ""
        )
        texto_limpo, produtos, total = sanitizar_resposta(texto, woo_results)
        print(f"[SANITIZE] woo_results={len(woo_results)} produtos={len(produtos)} total=R${total:.2f}", flush=True)
        return texto_limpo, historico, produtos, total


def _contar_produtos(texto: str) -> int:
    m = re.search(r"```json\s*([\s\S]*?)```", texto)
    if not m:
        return 0
    try:
        return len(json.loads(m.group(1)))
    except Exception:
        return -1


def sanitizar_resposta(texto: str, woo_results: list[dict] | None = None) -> tuple[str, list[dict], float]:
    """
    Retorna (texto_limpo, produtos, total).
    texto_limpo: mensagem sem o bloco JSON (para exibição no chat).
    produtos: lista de produtos para o frontend renderizar diretamente.
    total: soma dos preços × quantidades.
    """
    produtos = _extrair_produtos_do_texto(texto)

    if not produtos and woo_results:
        produtos = _produtos_de_woo(woo_results)

    if not produtos:
        return _strip_tabelas(texto), [], 0.0

    # Enriquece produtos com ID e min_qty do WooCommerce
    if woo_results:
        woo_by_url = {p.get("add_to_cart_url", ""): p for p in woo_results if isinstance(p, dict)}
        woo_by_nome = {p.get("nome", "").lower(): p for p in woo_results if isinstance(p, dict)}
        for p in produtos:
            woo = woo_by_url.get(p.get("add_to_cart_url", ""))
            if not woo:
                woo = woo_by_nome.get(p.get("nome", "").lower())
            if woo:
                if not p.get("product_id") and woo.get("id"):
                    p["product_id"] = woo["id"]
                if not p.get("variation_id") and woo.get("variation_id"):
                    p["variation_id"] = woo["variation_id"]
                # Aplica quantidade mínima do Display/variação
                min_qty = woo.get("min_qty")
                if min_qty and int(p.get("quantidade", 1)) < min_qty:
                    p["quantidade"] = min_qty

    total = 0.0
    for p in produtos:
        try:
            total += float(p.get("preco", 0)) * int(p.get("quantidade", 1))
        except Exception:
            pass

    # ── Garante mínimo R$ 1.500 — ajusta quantidades respeitando estoque ──
    if produtos and total < 1500:
        produtos.sort(key=lambda c: float(c.get("preco", 0)))
        i = 0
        safeguard = 0
        while total < 1500 and safeguard < 500:
            try:
                preco = float(produtos[i].get("preco", 0))
            except Exception:
                preco = 0
            if preco > 0:
                estoque = produtos[i].get("estoque")
                qty_atual = int(produtos[i].get("quantidade", 1))
                # Só aumenta se estoque for desconhecido (None) ou tiver espaço
                if estoque is None or qty_atual < int(estoque):
                    produtos[i]["quantidade"] = qty_atual + 1
                    total += preco
            i = (i + 1) % len(produtos)
            safeguard += 1

    # Se mesmo após ajuste não atingiu R$ 1.500, não exibe produtos
    if produtos and total < 1500:
        return (
            "⚠️ Não foi possível montar um pedido que atinja o valor mínimo de **R$ 1.500,00**. "
            "Tente novamente com mais produtos ou um segmento diferente.",
            [],
            0.0,
        )

    total_str = f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    dicas = _extrair_dicas(texto)

    # Texto limpo — sem bloco JSON, só mensagem + total + dicas
    saida = f"💰 **Total estimado: R$ {total_str}**"
    if dicas:
        saida += "\n\n💡 **Dicas:**\n"
        for d in dicas[:3]:
            saida += f"- {d}\n"

    return saida.strip(), produtos, total


def _extrair_produtos_do_texto(texto: str) -> list[dict]:
    """Extrai produtos válidos do bloco ```json``` da resposta do Claude."""
    match = re.search(r"```json\s*([\s\S]*?)```", texto)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [
        p for p in data
        if isinstance(p, dict)
        and p.get("add_to_cart_url")
        and p.get("em_estoque", True) is not False
    ]


def _produtos_de_woo(woo_results: list[dict]) -> list[dict]:
    """
    Constrói a lista de produtos para o cliente a partir dos resultados
    crus do WooCommerce. Filtra apenas em estoque, deduplica e calcula
    quantidades para atingir R$ 1.500.
    """
    vistos = set()
    candidatos: list[dict] = []
    for p in woo_results:
        if not isinstance(p, dict):
            continue
        if p.get("em_estoque") is False:
            continue
        url = p.get("add_to_cart_url") or ""
        if not url or url in vistos:
            continue
        vistos.add(url)
        try:
            preco = float(p.get("preco") or 0)
        except Exception:
            preco = 0
        if preco <= 0:
            continue
        min_qty = p.get("min_qty") or 1
        estoque = p.get("estoque")
        candidatos.append({
            "product_id": p.get("id"),
            "nome": p.get("nome") or "",
            "formato": p.get("formato") or "Display",
            "preco": f"{preco:.2f}",
            "quantidade": max(1, min_qty),
            "estoque": estoque,
            "em_estoque": True,
            "imagem": p.get("imagem") or "",
            "add_to_cart_url": url,
            "variation_id": p.get("variation_id") or 0,
        })

    if not candidatos:
        return []

    # Garante mínimo de R$ 1.500 — aumenta quantidade respeitando estoque
    def total_atual():
        return sum(float(c["preco"]) * c["quantidade"] for c in candidatos)

    candidatos.sort(key=lambda c: float(c["preco"]))
    i = 0
    safeguard = 0
    while total_atual() < 1500 and safeguard < 200:
        estoque = candidatos[i].get("estoque")
        qty_atual = candidatos[i]["quantidade"]
        if estoque is None or qty_atual < int(estoque):
            candidatos[i]["quantidade"] += 1
        i = (i + 1) % len(candidatos)
        safeguard += 1

    return candidatos


def _strip_tabelas(texto: str) -> str:
    """Remove linhas de tabela markdown e blocos de citação."""
    linhas = []
    for ln in texto.splitlines():
        s = ln.strip()
        if "|" in s and s.count("|") >= 2:
            continue
        if s.startswith(">"):
            continue
        linhas.append(ln)
    return "\n".join(linhas).strip()


def _extrair_dicas(texto: str) -> list[str]:
    """Extrai dicas curtas (linhas começando com - ou • ou emoji)."""
    dicas = []
    capturando = False
    for ln in texto.splitlines():
        s = ln.strip()
        if not s:
            continue
        if "dica" in s.lower() and (":" in s or "💡" in s):
            capturando = True
            continue
        if capturando and (s.startswith("-") or s.startswith("•") or s.startswith("*")):
            dica = re.sub(r"^[\-•*]\s*", "", s)
            dica = re.sub(r"\*\*", "", dica)
            if len(dica) > 3:
                dicas.append(dica)
        elif capturando and not (s.startswith("-") or s.startswith("•") or s.startswith("*") or s.startswith("🖊") or s.startswith("🦕")):
            # Acabou a seção de dicas
            if dicas:
                break
    return dicas
