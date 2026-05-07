from contextlib import asynccontextmanager
from pathlib import Path
import os

from dotenv import load_dotenv, set_key
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv(override=True)

from agent import chat
from catalog import DB_PATH, build_catalog, listar_segmentos
import recomendacoes

ENV_PATH = Path(__file__).parent / ".env"
bearer = HTTPBearer()


def verify_admin_token(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected or credentials.credentials != expected:
        raise HTTPException(status_code=401, detail="Token inválido")
    return credentials.credentials


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DB_PATH.exists():
        print("Construindo catálogo SQLite...")
        build_catalog()
    recomendacoes.init_db()
    yield


app = FastAPI(title="Mixia — Robô de Recomendação", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessoes: dict[str, list[dict]] = {}


class MensagemRequest(BaseModel):
    session_id: str
    mensagem: str
    segmento: str | None = None
    regiao: str | None = None
    uf: str | None = None
    porte: str | None = None


class MensagemResponse(BaseModel):
    resposta: str
    produtos: list[dict] = []
    total: float = 0.0
    session_id: str


class UpdateConfigRequest(BaseModel):
    anthropic_api_key: str | None = None
    woocommerce_key: str | None = None
    woocommerce_secret: str | None = None


@app.post("/chat", response_model=MensagemResponse)
async def endpoint_chat(body: MensagemRequest):
    historico = sessoes.get(body.session_id, [])
    try:
        resposta, historico_atualizado, produtos, total = chat(historico, body.mensagem)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    sessoes[body.session_id] = historico_atualizado

    # Salvar recomendacao se houver produtos
    if produtos:
        try:
            recomendacoes.salvar(
                session_id=body.session_id,
                segmento=body.segmento or "",
                regiao=body.regiao or "",
                uf=body.uf or "",
                porte=body.porte or "",
                produtos=produtos,
                total=total,
            )
        except Exception as e:
            print(f"[WARN] Erro ao salvar recomendacao: {e}", flush=True)

    return MensagemResponse(resposta=resposta, produtos=produtos, total=total, session_id=body.session_id)


@app.delete("/chat/{session_id}")
async def limpar_sessao(session_id: str):
    sessoes.pop(session_id, None)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok", "catalog": DB_PATH.exists()}


@app.post("/admin/update-config")
async def update_config(body: UpdateConfigRequest, _token: str = Security(verify_admin_token)):
    """Atualiza chaves de API no .env e recarrega as variáveis de ambiente."""
    updated = []

    if body.anthropic_api_key:
        set_key(ENV_PATH, "ANTHROPIC_API_KEY", body.anthropic_api_key)
        os.environ["ANTHROPIC_API_KEY"] = body.anthropic_api_key
        updated.append("ANTHROPIC_API_KEY")

    if body.woocommerce_key:
        set_key(ENV_PATH, "WOOCOMMERCE_KEY", body.woocommerce_key)
        os.environ["WOOCOMMERCE_KEY"] = body.woocommerce_key
        updated.append("WOOCOMMERCE_KEY")

    if body.woocommerce_secret:
        set_key(ENV_PATH, "WOOCOMMERCE_SECRET", body.woocommerce_secret)
        os.environ["WOOCOMMERCE_SECRET"] = body.woocommerce_secret
        updated.append("WOOCOMMERCE_SECRET")

    return {"ok": True, "updated": updated}


@app.get("/segments")
async def get_segments():
    return {"segments": listar_segmentos()}


@app.post("/admin/rebuild-catalog")
async def rebuild_catalog(_token: str = Security(verify_admin_token)):
    build_catalog()
    return {"ok": True, "message": "Catálogo reconstruído com sucesso"}


# ── Recomendações / Relatórios ──

@app.get("/admin/recomendacoes")
async def listar_recomendacoes(
    limit: int = 100,
    offset: int = 0,
    _token: str = Security(verify_admin_token),
):
    return {"recomendacoes": recomendacoes.listar(limit, offset)}


@app.get("/admin/recomendacoes/{rec_id}")
async def obter_recomendacao(rec_id: int, _token: str = Security(verify_admin_token)):
    rec = recomendacoes.obter(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recomendacao nao encontrada")
    return rec


@app.get("/admin/recomendacoes/{rec_id}/export")
async def exportar_recomendacao(rec_id: int, _token: str = Security(verify_admin_token)):
    from fastapi.responses import StreamingResponse
    buf = recomendacoes.exportar_excel(rec_id)
    if not buf:
        raise HTTPException(status_code=404, detail="Recomendacao nao encontrada")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=recomendacao_{rec_id}.xlsx"},
    )


@app.get("/admin/recomendacoes-export")
async def exportar_todas_recomendacoes(limit: int = 500, _token: str = Security(verify_admin_token)):
    from fastapi.responses import StreamingResponse
    buf = recomendacoes.exportar_excel_todos(limit)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=recomendacoes_todas.xlsx"},
    )
