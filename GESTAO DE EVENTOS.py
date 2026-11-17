import os
import secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta
from enum import Enum

from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    create_engine, select
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, Session, mapped_column,
    sessionmaker
)

from jose import JWTError, jwt
from passlib.context import CryptContext


# =========================================================
# CONFIGURAÇÕES
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + (BASE_DIR / "eventos.db").as_posix()
)

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "A variável JWT_SECRET_KEY não foi configurada no arquivo .env"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


# =========================================================
# MODELOS DO BANCO DE DADOS
# =========================================================

class Base(DeclarativeBase):
    pass


class Perfil(str, Enum):
    admin = "admin"
    organizador = "organizador"
    participante = "participante"


class StatusEvento(str, Enum):
    planejado = "planejado"
    aberto = "aberto"
    lotado = "lotado"
    encerrado = "encerrado"
    cancelado = "cancelado"


class StatusInscricao(str, Enum):
    confirmada = "confirmada"
    cancelada = "cancelada"


class StatusCertificado(str, Enum):
    emitido = "emitido"
    cancelado = "cancelado"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    perfil: Mapped[str] = mapped_column(
        String(30),
        default=Perfil.participante.value,
        nullable=False
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)


class Evento(Base):
    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_fim: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    capacidade: Mapped[int] = mapped_column(Integer, nullable=False)
    preco: Mapped[float] = mapped_column(
        Float, default=0, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default=StatusEvento.planejado.value,
        nullable=False
    )
    organizador_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False
    )
    categoria_id: Mapped[int | None] = mapped_column(
        ForeignKey("categorias.id"), nullable=True
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Inscricao(Base):
    __tablename__ = "inscricoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evento_id: Mapped[int] = mapped_column(
        ForeignKey("eventos.id"), nullable=False
    )
    participante_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False
    )
    data_inscricao: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default=StatusInscricao.confirmada.value,
        nullable=False
    )


class Certificado(Base):
    __tablename__ = "certificados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    titulo: Mapped[str] = mapped_column(String(180), nullable=False)
    carga_horaria: Mapped[int] = mapped_column(Integer, nullable=False)
    data_emissao: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default=StatusCertificado.emitido.value,
        nullable=False
    )
    inscricao_id: Mapped[int] = mapped_column(
        ForeignKey("inscricoes.id"),
        unique=True,
        nullable=False
    )


# Base.metadata.create_all(bind=engine)


# =========================================================
# AUTENTICAÇÃO E CONFIGURAÇÃO DOS SCHEMAS
# =========================================================

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=6, max_length=100)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    perfil: str
    ativo: bool


class CategoriaCreate(BaseModel):
    nome: str
    descricao: str | None = None


class CategoriaOut(CategoriaCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class EventoCreate(BaseModel):
    titulo: str
    descricao: str | None = None
    data_inicio: datetime
    data_fim: datetime
    capacidade: int = Field(gt=0)
    preco: float = Field(default=0, ge=0)
    categoria_id: int | None = None
    observacoes: str | None = None


class EventoOut(EventoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    organizador_id: int


class InscricaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evento_id: int
    participante_id: int
    data_inscricao: datetime
    status: str


class CertificadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    titulo: str
    carga_horaria: int
    data_emissao: datetime
    status: str
    inscricao_id: int


# =========================================================
# APLICAÇÃO FASTAPI
# =========================================================

app = FastAPI(
    title="Gestão de Eventos API",
    description=(
        "API acadêmica para gerenciamento de eventos, usuários, "
        "inscrições, vagas e certificados."
    ),
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Autenticação",
            "description": "Cadastro, login e consulta do usuário autenticado."
        },
        {
            "name": "Usuários",
            "description": "Consulta e gerenciamento de usuários."
        },
        {
            "name": "Categorias",
            "description": "Organização das categorias de eventos."
        },
        {
            "name": "Eventos",
            "description": "Criação, consulta e gerenciamento de eventos e vagas."
        },
        {
            "name": "Inscrições",
            "description": "Inscrição e consulta de participantes nos eventos."
        },
        {
            "name": "Certificados",
            "description": "Emissão, consulta, validação e cancelamento de certificados."
        },
        {
            "name": "Sistema",
            "description": "Informações gerais e verificação de disponibilidade da API."
        },
    ],
)


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def criar_token(usuario: Usuario):
    agora = datetime.now(timezone.utc)

    expiracao = agora + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(usuario.id),
        "perfil": usuario.perfil,
        "iat": agora,
        "exp": expiracao
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def usuario_atual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    cred = HTTPException(
        status_code=401,
        detail="Token inválido ou expirado"
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        uid = payload.get("sub")

        if not uid:
            raise cred

        usuario_id = int(uid)

    except (JWTError, ValueError, TypeError):
        raise cred

    usuario = db.get(Usuario, usuario_id)

    if not usuario or not usuario.ativo:
        raise cred

    return usuario


def exigir(*perfis):
    def dep(usuario: Usuario = Depends(usuario_atual)):
        if usuario.perfil not in [
            p.value if isinstance(p, Enum) else p
            for p in perfis
        ]:
            raise HTTPException(
                status_code=403,
                detail="Permissão insuficiente"
            )

        return usuario

    return dep


def vagas_disponiveis(evento_id: int, db: Session):
    evento = db.get(Evento, evento_id)

    if not evento:
        raise HTTPException(404, "Evento não encontrado")

    total = len(
        db.scalars(
            select(Inscricao).where(
                Inscricao.evento_id == evento_id,
                Inscricao.status == StatusInscricao.confirmada.value
            )
        ).all()
    )

    return max(evento.capacidade - total, 0)


# =========================================================
# ROTAS DO SISTEMA
# =========================================================

@app.get(
    "/",
    tags=["Sistema"],
    summary="Página inicial da API",
    description="Retorna informações básicas sobre o sistema e o endereço da documentação."
)
def raiz():
    return {
        "sistema": "Gestão de Eventos",
        "status": "online",
        "docs": "/docs"
    }


@app.get(
    "/health",
    tags=["Sistema"],
    summary="Verificar disponibilidade da API",
    description="Verifica se a API está funcionando."
)
def health():
    return {"status": "ok"}


# =========================================================
# ROTAS DE AUTENTICAÇÃO
# =========================================================

@app.post(
    "/auth/register",
    response_model=UsuarioOut,
    status_code=201,
    tags=["Autenticação"],
    summary="Cadastrar usuário",
    description=(
        "Cadastra um novo usuário no sistema. "
        "O usuário é criado com o perfil participante por padrão. "
        "O e-mail deve ser único e a senha precisa atender aos critérios mínimos."
    ),
    responses={
        409: {"description": "E-mail já cadastrado."},
        422: {"description": "Dados de cadastro inválidos."},
    },
)
def registrar(dados: UsuarioCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Usuario).where(Usuario.email == dados.email)):
        raise HTTPException(409, "E-mail já cadastrado")

    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=pwd_context.hash(dados.senha),
        perfil=Perfil.participante.value
    )

    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    return usuario


@app.post(
    "/auth/login",
    tags=["Autenticação"],
    summary="Autenticar usuário",
    description=(
        "Autentica um usuário utilizando e-mail e senha. "
        "O campo username deve receber o e-mail cadastrado. "
        "O usuário precisa estar ativo. Em caso de sucesso, "
        "retorna um token JWT do tipo Bearer para acessar as rotas protegidas."
    ),
    responses={
        401: {"description": "E-mail ou senha inválidos, ou usuário inativo."},
        422: {"description": "Dados de autenticação inválidos."},
    },
)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    usuario = db.scalar(
        select(Usuario).where(Usuario.email == form.username)
    )

    if (
        not usuario
        or not usuario.ativo
        or not pwd_context.verify(form.password, usuario.senha_hash)
    ):
        raise HTTPException(401, "E-mail ou senha inválidos")

    return {
        "access_token": criar_token(usuario),
        "token_type": "bearer"
    }


@app.get(
    "/auth/me",
    response_model=UsuarioOut,
    tags=["Autenticação"],
    summary="Consultar usuário autenticado",
    description="Retorna os dados do usuário identificado pelo token JWT.",
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
    },
)
def me(usuario: Usuario = Depends(usuario_atual)):
    return usuario


# =========================================================
# ROTAS DE USUÁRIOS
# =========================================================

@app.get(
    "/usuarios",
    response_model=list[UsuarioOut],
    tags=["Usuários"],
    summary="Listar usuários",
    description="Lista todos os usuários cadastrados. A operação é exclusiva para administradores.",
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão de administrador."},
    },
)
def listar_usuarios(
    _: Usuario = Depends(exigir(Perfil.admin)),
    db: Session = Depends(get_db)
):
    return db.scalars(select(Usuario)).all()


@app.get(
    "/usuarios/{usuario_id}",
    response_model=UsuarioOut,
    tags=["Usuários"],
    summary="Consultar usuário",
    description=(
        "Consulta os dados de um usuário pelo identificador. "
        "Administradores podem consultar qualquer usuário; "
        "os demais usuários podem consultar apenas seus próprios dados."
    ),
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão para consultar este cadastro."},
        404: {"description": "Usuário não encontrado."},
        422: {"description": "Identificador inválido."},
    },
)
def buscar_usuario(
    usuario_id: int,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db)
):
    if usuario.perfil != Perfil.admin.value and usuario.id != usuario_id:
        raise HTTPException(403, "Sem permissão")

    obj = db.get(Usuario, usuario_id)

    if not obj:
        raise HTTPException(404, "Usuário não encontrado")

    return obj


@app.delete(
    "/usuarios/{usuario_id}",
    tags=["Usuários"],
    summary="Desativar usuário",
    description="Desativa um usuário cadastrado. A operação é exclusiva para administradores.",
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão de administrador."},
        404: {"description": "Usuário não encontrado."},
        409: {"description": "Usuário já está desativado."},
        422: {"description": "Identificador inválido."},
    },
)
def desativar_usuario(
    usuario_id: int,
    _: Usuario = Depends(exigir(Perfil.admin)),
    db: Session = Depends(get_db)
):
    obj = db.get(Usuario, usuario_id)

    if not obj:
        raise HTTPException(404, "Usuário não encontrado")

    if not obj.ativo:
        raise HTTPException(409, "Usuário já está desativado")

    obj.ativo = False
    db.commit()

    return {"mensagem": "Usuário desativado"}


# =========================================================
# ROTAS DE CATEGORIAS
# =========================================================

@app.post(
    "/categorias",
    response_model=CategoriaOut,
    status_code=201,
    tags=["Categorias"],
    summary="Criar categoria",
    description="Cria uma categoria de eventos. A operação é permitida para administradores e organizadores.",
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão para criar categorias."},
        409: {"description": "Categoria já existe."},
        422: {"description": "Dados da categoria inválidos."},
    },
)
def criar_categoria(
    dados: CategoriaCreate,
    _: Usuario = Depends(exigir(Perfil.admin, Perfil.organizador)),
    db: Session = Depends(get_db)
):
    if db.scalar(select(Categoria).where(Categoria.nome == dados.nome)):
        raise HTTPException(409, "Categoria já existe")

    obj = Categoria(**dados.model_dump())

    db.add(obj)
    db.commit()
    db.refresh(obj)

    return obj


@app.get(
    "/categorias",
    response_model=list[CategoriaOut],
    tags=["Categorias"],
    summary="Listar categorias",
    description="Retorna todas as categorias cadastradas no sistema."
)
def listar_categorias(db: Session = Depends(get_db)):
    return db.scalars(select(Categoria)).all()


@app.delete(
    "/categorias/{categoria_id}",
    tags=["Categorias"],
    summary="Excluir categoria",
    description="Exclui uma categoria. A operação é exclusiva para administradores e não permite excluir categorias vinculadas a eventos.",
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão de administrador."},
        404: {"description": "Categoria não encontrada."},
        409: {"description": "Categoria vinculada a um ou mais eventos."},
        422: {"description": "Identificador inválido."},
    },
)
def excluir_categoria(
    categoria_id: int,
    _: Usuario = Depends(exigir(Perfil.admin)),
    db: Session = Depends(get_db)
):
    obj = db.get(Categoria, categoria_id)

    if not obj:
        raise HTTPException(404, "Categoria não encontrada")

    evento_vinculado = db.scalar(
        select(Evento.id).where(
            Evento.categoria_id == categoria_id
        ).limit(1)
    )

    if evento_vinculado:
        raise HTTPException(
            409,
            "Categoria vinculada a um ou mais eventos"
        )

    db.delete(obj)
    db.commit()

    return {"mensagem": "Categoria excluída"}


# =========================================================
# ROTAS DE EVENTOS
# =========================================================

@app.post(
    "/eventos",
    response_model=EventoOut,
    status_code=201,
    tags=["Eventos"],
    summary="Criar evento",
    description=(
        "Cria um novo evento. A operação é permitida para administradores "
        "e organizadores autenticados. A data de fim deve ser posterior "
        "à data de início. Caso uma categoria seja informada, ela deve existir."
    ),
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão para criar eventos."},
        404: {"description": "Categoria não encontrada."},
        422: {"description": "Data inválida ou dados da requisição inválidos."},
    },
)
def criar_evento(
    dados: EventoCreate,
    usuario: Usuario = Depends(exigir(Perfil.admin, Perfil.organizador)),
    db: Session = Depends(get_db)
):
    if dados.data_fim <= dados.data_inicio:
        raise HTTPException(
            422,
            "A data de fim deve ser posterior à data de início"
        )

    if dados.categoria_id and not db.get(Categoria, dados.categoria_id):
        raise HTTPException(404, "Categoria não encontrada")

    obj = Evento(
        **dados.model_dump(),
        organizador_id=usuario.id,
        status=StatusEvento.planejado.value
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)

    return obj


@app.get(
    "/eventos",
    response_model=list[EventoOut],
    tags=["Eventos"],
    summary="Listar eventos",
    description="Retorna todos os eventos cadastrados no sistema."
)
def listar_eventos(db: Session = Depends(get_db)):
    return db.scalars(select(Evento)).all()


@app.get(
    "/eventos/{evento_id}",
    response_model=EventoOut,
    tags=["Eventos"],
    summary="Consultar evento",
    description="Retorna os dados de um evento específico pelo identificador.",
    responses={
        404: {"description": "Evento não encontrado."},
        422: {"description": "Identificador inválido."},
    },
)
def buscar_evento(evento_id: int, db: Session = Depends(get_db)):
    obj = db.get(Evento, evento_id)

    if not obj:
        raise HTTPException(404, "Evento não encontrado")

    return obj


@app.put(
    "/eventos/{evento_id}",
    response_model=EventoOut,
    tags=["Eventos"],
    summary="Atualizar evento",
    description=(
        "Atualiza os dados de um evento. Administradores podem atualizar "
        "qualquer evento; organizadores podem atualizar somente os eventos "
        "que organizaram. A data de fim deve ser posterior à data de início."
    ),
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão para atualizar este evento."},
        404: {"description": "Evento não encontrado."},
        422: {"description": "Dados inválidos ou período do evento incorreto."},
    },
)
def atualizar_evento(
    evento_id: int,
    dados: EventoCreate,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db)
):
    obj = db.get(Evento, evento_id)

    if not obj:
        raise HTTPException(404, "Evento não encontrado")

    if usuario.perfil != Perfil.admin.value:
        if usuario.perfil != Perfil.organizador.value:
            raise HTTPException(403, "Sem permissão")

        if obj.organizador_id != usuario.id:
            raise HTTPException(403, "Sem permissão")

    if dados.data_fim <= dados.data_inicio:
        raise HTTPException(
            422,
            "A data de fim deve ser posterior à data de início"
        )

    for k, v in dados.model_dump().items():
        setattr(obj, k, v)

    db.commit()
    db.refresh(obj)

    return obj


@app.delete(
    "/eventos/{evento_id}",
    tags=["Eventos"],
    summary="Cancelar evento",
    description=(
        "Cancela um evento. Administradores podem cancelar qualquer evento; "
        "organizadores podem cancelar somente os eventos que organizaram."
    ),
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão para cancelar este evento."},
        404: {"description": "Evento não encontrado."},
        422: {"description": "Identificador inválido."},
    },
)
def cancelar_evento(
    evento_id: int,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db)
):
    obj = db.get(Evento, evento_id)

    if not obj:
        raise HTTPException(404, "Evento não encontrado")

    if usuario.perfil != Perfil.admin.value:
        if usuario.perfil != Perfil.organizador.value:
            raise HTTPException(403, "Sem permissão")

        if obj.organizador_id != usuario.id:
            raise HTTPException(403, "Sem permissão")

    obj.status = StatusEvento.cancelado.value

    db.commit()

    return {"mensagem": "Evento cancelado"}


@app.get(
    "/eventos/{evento_id}/vagas",
    tags=["Eventos"],
    summary="Consultar vagas disponíveis",
    description="Consulta a capacidade total e a quantidade de vagas disponíveis para um evento.",
    responses={
        404: {"description": "Evento não encontrado."},
        422: {"description": "Identificador inválido."},
    },
)
def consultar_vagas(evento_id: int, db: Session = Depends(get_db)):
    evento = db.get(Evento, evento_id)

    if not evento:
        raise HTTPException(404, "Evento não encontrado")

    disponiveis = vagas_disponiveis(evento_id, db)

    return {
        "evento_id": evento_id,
        "capacidade": evento.capacidade,
        "vagas_disponiveis": disponiveis
    }


# =========================================================
# ROTAS DE INSCRIÇÕES
# =========================================================

@app.post(
    "/eventos/{evento_id}/inscricoes",
    response_model=InscricaoOut,
    status_code=201,
    tags=["Inscrições"],
    summary="Inscrever usuário em evento",
    description=(
        "Realiza a inscrição de um usuário autenticado em um evento. "
        "A operação é permitida para administradores e participantes. "
        "Não permite inscrição em eventos cancelados, eventos lotados "
        "ou inscrições duplicadas. Ao preencher a última vaga, o evento "
        "passa automaticamente para o status lotado."
    ),
    responses={
        400: {"description": "O evento está cancelado."},
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão para realizar a inscrição."},
        404: {"description": "Evento não encontrado."},
        409: {"description": "Evento lotado ou usuário já inscrito."},
        422: {"description": "Dados da requisição inválidos."},
    },
)
def inscrever(
    evento_id: int,
    usuario: Usuario = Depends(
        exigir(Perfil.admin, Perfil.participante)
    ),
    db: Session = Depends(get_db)
):
    evento = db.get(Evento, evento_id)

    if not evento:
        raise HTTPException(404, "Evento não encontrado")

    if evento.status == StatusEvento.cancelado.value:
        raise HTTPException(400, "Evento cancelado")

    if vagas_disponiveis(evento_id, db) <= 0:
        raise HTTPException(409, "Evento lotado")

    existente = db.scalar(
        select(Inscricao).where(
            Inscricao.evento_id == evento_id,
            Inscricao.participante_id == usuario.id,
            Inscricao.status == StatusInscricao.confirmada.value
        )
    )

    if existente:
        raise HTTPException(409, "Usuário já está inscrito")

    obj = Inscricao(
        evento_id=evento_id,
        participante_id=usuario.id,
        status=StatusInscricao.confirmada.value
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)

    if vagas_disponiveis(evento_id, db) == 0:
        evento.status = StatusEvento.lotado.value
        db.commit()

    return obj


@app.get(
    "/inscricoes",
    response_model=list[InscricaoOut],
    tags=["Inscrições"],
    summary="Listar inscrições",
    description=(
        "Lista as inscrições conforme o perfil do usuário autenticado. "
        "Administradores podem consultar todas as inscrições. "
        "Organizadores podem consultar as inscrições dos eventos que organizam. "
        "Participantes podem consultar somente suas próprias inscrições."
    ),
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
    },
)
def listar_inscricoes(
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db)
):
    if usuario.perfil == Perfil.admin.value:
        return db.scalars(select(Inscricao)).all()

    if usuario.perfil == Perfil.organizador.value:
        eventos = db.scalars(
            select(Evento.id).where(
                Evento.organizador_id == usuario.id
            )
        ).all()

        if not eventos:
            return []

        return db.scalars(
            select(Inscricao).where(
                Inscricao.evento_id.in_(eventos)
            )
        ).all()

    return db.scalars(
        select(Inscricao).where(
            Inscricao.participante_id == usuario.id
        )
    ).all()


@app.delete(
    "/inscricoes/{inscricao_id}",
    tags=["Inscrições"],
    summary="Cancelar inscrição",
    description=(
        "Cancela uma inscrição existente. A operação é permitida "
        "para administradores ou para o próprio participante "
        "responsável pela inscrição. A inscrição passa a ter "
        "o status cancelada."
    ),
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão para cancelar esta inscrição."},
        404: {"description": "Inscrição não encontrada."},
        422: {"description": "Identificador da inscrição inválido."},
    },
)
def cancelar_inscricao(
    inscricao_id: int,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db)
):
    obj = db.get(Inscricao, inscricao_id)

    if not obj:
        raise HTTPException(404, "Inscrição não encontrada")

    if (
        usuario.perfil != Perfil.admin.value
        and obj.participante_id != usuario.id
    ):
        raise HTTPException(403, "Sem permissão")

    obj.status = StatusInscricao.cancelada.value
    db.commit()

    return {"mensagem": "Inscrição cancelada"}


# =========================================================
# ROTAS DE CERTIFICADOS
# =========================================================

@app.post(
    "/certificados/emitir/{inscricao_id}",
    response_model=CertificadoOut,
    status_code=201,
    tags=["Certificados"],
    summary="Emitir certificado",
    description=(
        "Emite um certificado para uma inscrição confirmada. "
        "A operação é permitida para administradores e para o organizador "
        "responsável pelo evento. Não permite emitir mais de um certificado "
        "para a mesma inscrição."
    ),
    responses={
        400: {"description": "A inscrição não está confirmada."},
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão para emitir este certificado."},
        404: {"description": "Inscrição não encontrada."},
        409: {"description": "Certificado já emitido para esta inscrição."},
        422: {"description": "Identificador ou carga horária inválidos."},
    },
)
def emitir_certificado(
    inscricao_id: int,
    carga_horaria: int = 4,
    usuario: Usuario = Depends(
        exigir(Perfil.admin, Perfil.organizador)
    ),
    db: Session = Depends(get_db)
):
    inscricao = db.get(Inscricao, inscricao_id)

    if not inscricao:
        raise HTTPException(404, "Inscrição não encontrada")

    evento = db.get(Evento, inscricao.evento_id)

    if (
        usuario.perfil != Perfil.admin.value
        and evento.organizador_id != usuario.id
    ):
        raise HTTPException(403, "Sem permissão")

    if inscricao.status != StatusInscricao.confirmada.value:
        raise HTTPException(400, "A inscrição não está confirmada")

    if db.scalar(
        select(Certificado).where(
            Certificado.inscricao_id == inscricao_id
        )
    ):
        raise HTTPException(409, "Certificado já emitido")

    obj = Certificado(
        codigo="CERT-" + secrets.token_hex(6).upper(),
        titulo=evento.titulo,
        carga_horaria=carga_horaria,
        inscricao_id=inscricao_id
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)

    return obj


@app.get(
    "/certificados",
    response_model=list[CertificadoOut],
    tags=["Certificados"],
    summary="Listar certificados",
    description=(
        "Lista os certificados de acordo com o perfil do usuário autenticado. "
        "Administradores consultam todos; organizadores consultam os certificados "
        "dos eventos que organizam; participantes consultam os próprios certificados."
    ),
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
    },
)
def listar_certificados(
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db)
):
    if usuario.perfil == Perfil.admin.value:
        return db.scalars(select(Certificado)).all()

    if usuario.perfil == Perfil.organizador.value:
        return db.scalars(
            select(Certificado)
            .join(
                Inscricao,
                Certificado.inscricao_id == Inscricao.id
            )
            .join(
                Evento,
                Inscricao.evento_id == Evento.id
            )
            .where(Evento.organizador_id == usuario.id)
        ).all()

    inscricoes = db.scalars(
        select(Inscricao).where(
            Inscricao.participante_id == usuario.id
        )
    ).all()

    ids = [inscricao.id for inscricao in inscricoes]

    if not ids:
        return []

    return db.scalars(
        select(Certificado).where(
            Certificado.inscricao_id.in_(ids)
        )
    ).all()


@app.get(
    "/certificados/{certificado_id}",
    response_model=CertificadoOut,
    tags=["Certificados"],
    summary="Consultar certificado",
    description=(
        "Consulta um certificado pelo identificador. "
        "Administradores podem consultar qualquer certificado; "
        "organizadores podem consultar certificados de seus eventos; "
        "participantes podem consultar somente seus próprios certificados."
    ),
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão para consultar este certificado."},
        404: {"description": "Certificado não encontrado."},
        422: {"description": "Identificador inválido."},
    },
)
def buscar_certificado(
    certificado_id: int,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db)
):
    obj = db.get(Certificado, certificado_id)

    if not obj:
        raise HTTPException(404, "Certificado não encontrado")

    inscricao = db.get(Inscricao, obj.inscricao_id)
    evento = db.get(Evento, inscricao.evento_id)

    if usuario.perfil == Perfil.admin.value:
        return obj

    if usuario.perfil == Perfil.organizador.value:
        if evento.organizador_id != usuario.id:
            raise HTTPException(403, "Sem permissão")

        return obj

    if inscricao.participante_id != usuario.id:
        raise HTTPException(403, "Sem permissão")

    return obj


@app.get(
    "/certificados/validar/{codigo}",
    tags=["Certificados"],
    summary="Validar certificado",
    description=(
        "Verifica a autenticidade de um certificado por meio do código. "
        "Retorna se o certificado está válido e os dados correspondentes."
    ),
    responses={
        404: {"description": "Certificado não encontrado."},
        422: {"description": "Código inválido."},
    },
)
def validar_certificado(codigo: str, db: Session = Depends(get_db)):
    obj = db.scalar(
        select(Certificado).where(
            Certificado.codigo == codigo
        )
    )

    if not obj:
        raise HTTPException(404, "Certificado não encontrado")

    return {
        "valido": obj.status == StatusCertificado.emitido.value,
        "certificado": obj
    }


@app.delete(
    "/certificados/{certificado_id}",
    tags=["Certificados"],
    summary="Cancelar certificado",
    description=(
        "Cancela um certificado existente. A operação é exclusiva "
        "para administradores. O certificado permanece cadastrado, "
        "mas passa a ter o status cancelado."
    ),
    responses={
        401: {"description": "Usuário não autenticado ou token inválido."},
        403: {"description": "Usuário sem permissão de administrador."},
        404: {"description": "Certificado não encontrado."},
        422: {"description": "Identificador inválido."},
    },
)
def cancelar_certificado(
    certificado_id: int,
    _: Usuario = Depends(exigir(Perfil.admin)),
    db: Session = Depends(get_db)
):
    obj = db.get(Certificado, certificado_id)

    if not obj:
        raise HTTPException(404, "Certificado não encontrado")

    obj.status = StatusCertificado.cancelado.value
    db.commit()

    return {"mensagem": "Certificado cancelado"}