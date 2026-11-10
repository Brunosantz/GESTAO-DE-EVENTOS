import pytest
import main

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

api = main.module

Base = api.Base
Usuario = api.Usuario
pwd_context = api.pwd_context
get_db = api.get_db

# Banco de dados exclusivo para testes
engine_teste = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

SessionTeste = sessionmaker(
    bind=engine_teste,
    autoflush=False,
    autocommit=False
)


# Fixture: prepara e encerra o ambiente de testes
@pytest.fixture
def client():
    api.Base.metadata.create_all(bind=engine_teste)

    def override_get_db():
        db = SessionTeste()
        try:
            yield db
        finally:
            db.close()

    api.app.dependency_overrides[api.get_db] = override_get_db

    with TestClient(api.app) as cliente:
        yield cliente

    api.app.dependency_overrides.clear()
    api.Base.metadata.drop_all(bind=engine_teste)


# Cadastra participantes pela API e cria outros perfis
# diretamente no banco exclusivo dos testes.
def cadastrar_usuario(client, email, perfil="participante"):

    if perfil == "participante":
        return client.post(
            "/auth/register",
            json={
                "nome": "Usuario Teste",
                "email": email,
                "senha": "Senha123456"
            }
        )

    db = SessionTeste()

    try:
        usuario = api.Usuario(
            nome="Usuario Teste",
            email=email,
            senha_hash=api.pwd_context.hash("Senha123456"),
            perfil=perfil,
            ativo=True
        )

        db.add(usuario)
        db.commit()
        db.refresh(usuario)

        return usuario

    finally:
        db.close()


# Obtém token de autenticação
def obter_token(client, email):
    resposta = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "Senha123456"
        }
    )

    assert resposta.status_code == 200
    return resposta.json()["access_token"]


# TESTE 1 - Página inicial
def test_pagina_inicial(client):
    resposta = client.get("/")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "online"


# TESTE 2 - Saúde da API
def test_health(client):
    resposta = client.get("/health")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


# TESTE 3 - Cadastro de participante
def test_cadastrar_usuario(client):
    resposta = cadastrar_usuario(
        client,
        "participante_teste@email.com"
    )

    assert resposta.status_code == 201
    assert resposta.json()["perfil"] == "participante"


# TESTE 4 - Impedir e-mail duplicado
def test_email_duplicado(client):
    email = "duplicado@email.com"

    primeira = cadastrar_usuario(client, email)
    segunda = cadastrar_usuario(client, email)

    assert primeira.status_code == 201
    assert segunda.status_code == 409


# TESTE 5 - Login
def test_login(client):
    email = "login@email.com"

    cadastrar_usuario(client, email)

    resposta = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "Senha123456"
        }
    )

    assert resposta.status_code == 200
    assert "access_token" in resposta.json()
    assert resposta.json()["token_type"] == "bearer"


# TESTE 6 - Consultar usuário autenticado
def test_usuario_autenticado(client):
    email = "autenticado@email.com"

    cadastrar_usuario(client, email)
    token = obter_token(client, email)

    resposta = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 200
    assert resposta.json()["email"] == email


# TESTE 7 - Impedir acesso sem token
def test_acesso_sem_token(client):
    resposta = client.get("/auth/me")

    assert resposta.status_code == 401


# TESTE 8 - Participante não pode criar categoria
def test_participante_sem_permissao(client):
    email = "participante_bloqueado@email.com"

    cadastrar_usuario(client, email)
    token = obter_token(client, email)

    resposta = client.post(
        "/categorias",
        json={
            "nome": "Categoria Teste",
            "descricao": "Teste de autorização"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 403


# TESTE 9 - Organizador pode criar categoria
def test_organizador_com_permissao(client):
    email = "organizador_teste@email.com"

    cadastrar_usuario(
        client,
        email,
        perfil="organizador"
    )

    token = obter_token(client, email)

    resposta = client.post(
        "/categorias",
        json={
            "nome": "Categoria do Organizador",
            "descricao": "Categoria criada durante o teste"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 201
    assert resposta.json()["nome"] == "Categoria do Organizador"
