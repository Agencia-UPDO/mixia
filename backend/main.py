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
