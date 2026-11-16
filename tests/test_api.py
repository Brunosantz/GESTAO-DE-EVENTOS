
import pytest
import main

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

api = main.module

Base = api.Base
Usuario = api.Usuario

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


# ============================================================
# FIXTURES E FUNÇÕES AUXILIARES
# ============================================================

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

    try:
        with TestClient(api.app) as cliente:
            yield cliente
    finally:
        api.app.dependency_overrides.clear()
        api.Base.metadata.drop_all(bind=engine_teste)


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


def obter_token(client, email):
    resposta = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "Senha123456"
        }
    )

    assert resposta.status_code == 200, resposta.text
    return resposta.json()["access_token"]


def criar_evento(client, token, titulo="Evento de Teste", capacidade=10):
    return client.post(
        "/eventos",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "titulo": titulo,
            "descricao": "Descrição do evento",
            "data_inicio": "2027-05-10T09:00:00",
            "data_fim": "2027-05-10T18:00:00",
            "capacidade": capacidade,
            "preco": 50.0
        }
    )


# ============================================================
# TESTES DE AUTENTICAÇÃO E USUÁRIOS
# ============================================================

def test_pagina_inicial(client):
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "online"


def test_health(client):
    resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_cadastrar_usuario(client):
    resposta = cadastrar_usuario(
        client,
        "participante_teste@email.com"
    )

    assert resposta.status_code == 201
    assert resposta.json()["perfil"] == "participante"


def test_email_duplicado(client):
    email = "duplicado@email.com"

    primeira = cadastrar_usuario(client, email)
    segunda = cadastrar_usuario(client, email)

    assert primeira.status_code == 201
    assert segunda.status_code == 409


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


def test_acesso_sem_token(client):
    resposta = client.get("/auth/me")
    assert resposta.status_code == 401


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


def test_organizador_com_permissao(client):
    email = "organizador_teste@email.com"
    cadastrar_usuario(client, email, perfil="organizador")
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


def test_admin_desativa_usuario(client):
    cadastrar_usuario(client, "usuario_para_desativar@email.com")
    admin = cadastrar_usuario(
        client, "admin_desativar@email.com", perfil="admin"
    )
    token = obter_token(client, admin.email)

    db = SessionTeste()
    try:
        usuario = db.query(Usuario).filter_by(
            email="usuario_para_desativar@email.com"
        ).one()
        usuario_id = usuario.id
    finally:
        db.close()

    resposta = client.delete(
        f"/usuarios/{usuario_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 200
    assert resposta.json()["mensagem"] == "Usuário desativado"

    login = client.post(
        "/auth/login",
        data={
            "username": "usuario_para_desativar@email.com",
            "password": "Senha123456"
        }
    )
    assert login.status_code == 401


def test_participante_nao_pode_desativar_usuario(client):
    cadastrar_usuario(client, "outro_usuario@email.com")
    cadastrar_usuario(client, "participante_exclusao@email.com")
    token = obter_token(client, "participante_exclusao@email.com")

    db = SessionTeste()
    try:
        usuario = db.query(Usuario).filter_by(
            email="outro_usuario@email.com"
        ).one()
        usuario_id = usuario.id
    finally:
        db.close()

    resposta = client.delete(
        f"/usuarios/{usuario_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 403


# ============================================================
# TESTES DE CATEGORIAS
# ============================================================

def test_admin_exclui_categoria_sem_eventos(client):
    admin = cadastrar_usuario(
        client, "admin_categoria@email.com", perfil="admin"
    )
    token = obter_token(client, admin.email)

    categoria_resposta = client.post(
        "/categorias",
        json={"nome": "Categoria para excluir"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert categoria_resposta.status_code == 201

    categoria = categoria_resposta.json()

    resposta = client.delete(
        f"/categorias/{categoria['id']}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 200
    assert resposta.json()["mensagem"] == "Categoria excluída"


def test_categoria_vinculada_nao_pode_ser_excluida(client):
    admin = cadastrar_usuario(
        client, "admin_categoria_vinculada@email.com", perfil="admin"
    )
    token = obter_token(client, admin.email)
    headers = {"Authorization": f"Bearer {token}"}

    categoria_resposta = client.post(
        "/categorias",
        json={"nome": "Categoria vinculada"},
        headers=headers
    )
    assert categoria_resposta.status_code == 201
    categoria = categoria_resposta.json()

    evento = client.post(
        "/eventos",
        json={
            "titulo": "Evento com categoria",
            "data_inicio": "2030-01-01T10:00:00",
            "data_fim": "2030-01-01T11:00:00",
            "capacidade": 10,
            "categoria_id": categoria["id"]
        },
        headers=headers
    )
    assert evento.status_code == 201

    resposta = client.delete(
        f"/categorias/{categoria['id']}",
        headers=headers
    )

    assert resposta.status_code == 409


# ============================================================
# TESTES DE EVENTOS
# ============================================================

def test_organizador_cria_evento(client):
    cadastrar_usuario(
        client, "organizador_evento@email.com", "organizador"
    )
    token = obter_token(client, "organizador_evento@email.com")

    resposta = criar_evento(client, token)

    assert resposta.status_code == 201
    assert resposta.json()["titulo"] == "Evento de Teste"
    assert resposta.json()["status"] == "planejado"


def test_participante_nao_pode_criar_evento(client):
    cadastrar_usuario(client, "participante_evento@email.com")
    token = obter_token(client, "participante_evento@email.com")

    resposta = criar_evento(client, token)

    assert resposta.status_code == 403


def test_evento_com_data_invalida(client):
    cadastrar_usuario(client, "organizador_data@email.com", "organizador")
    token = obter_token(client, "organizador_data@email.com")

    resposta = client.post(
        "/eventos",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "titulo": "Evento com data inválida",
            "data_inicio": "2027-05-10T18:00:00",
            "data_fim": "2027-05-10T09:00:00",
            "capacidade": 10,
            "preco": 0
        }
    )

    assert resposta.status_code == 422


def test_evento_com_capacidade_zero(client):
    cadastrar_usuario(
        client, "organizador_capacidade@email.com", "organizador"
    )
    token = obter_token(client, "organizador_capacidade@email.com")

    resposta = client.post(
        "/eventos",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "titulo": "Evento sem capacidade",
            "data_inicio": "2027-05-10T09:00:00",
            "data_fim": "2027-05-10T18:00:00",
            "capacidade": 0,
            "preco": 0
        }
    )

    assert resposta.status_code == 422


def test_listar_eventos_publicamente(client):
    resposta = client.get("/eventos")
    assert resposta.status_code == 200
    assert isinstance(resposta.json(), list)


def test_consultar_evento_inexistente(client):
    resposta = client.get("/eventos/9999")
    assert resposta.status_code == 404


def test_organizador_nao_edita_evento_de_outro(client):
    cadastrar_usuario(client, "organizador_a@email.com", "organizador")
    cadastrar_usuario(client, "organizador_b@email.com", "organizador")

    token_a = obter_token(client, "organizador_a@email.com")
    token_b = obter_token(client, "organizador_b@email.com")

    evento = criar_evento(client, token_a)
    assert evento.status_code == 201
    evento_id = evento.json()["id"]

    resposta = client.put(
        f"/eventos/{evento_id}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={
            "titulo": "Tentativa de alteração",
            "data_inicio": "2027-05-10T09:00:00",
            "data_fim": "2027-05-10T18:00:00",
            "capacidade": 10,
            "preco": 50
        }
    )

    assert resposta.status_code == 403


def test_organizador_cancela_evento_proprio(client):
    cadastrar_usuario(
        client, "organizador_cancelar@email.com", "organizador"
    )
    token = obter_token(client, "organizador_cancelar@email.com")

    evento = criar_evento(client, token)
    assert evento.status_code == 201
    evento_id = evento.json()["id"]

    resposta = client.delete(
        f"/eventos/{evento_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 200
    assert resposta.json()["mensagem"] == "Evento cancelado"

    consulta = client.get(f"/eventos/{evento_id}")
    assert consulta.json()["status"] == "cancelado"


# ============================================================
# TESTES DE INSCRIÇÕES
# ============================================================

def test_participante_inscreve_evento(client):
    cadastrar_usuario(client, "organizador_inscricao@email.com", "organizador")
    cadastrar_usuario(client, "participante_inscricao@email.com")

    token_org = obter_token(client, "organizador_inscricao@email.com")
    token_part = obter_token(client, "participante_inscricao@email.com")

    evento = criar_evento(client, token_org)
    assert evento.status_code == 201
    evento_id = evento.json()["id"]

    resposta = client.post(
        f"/eventos/{evento_id}/inscricoes",
        headers={"Authorization": f"Bearer {token_part}"}
    )

    assert resposta.status_code == 201
    assert resposta.json()["evento_id"] == evento_id
    assert resposta.json()["status"] == "confirmada"


def test_usuario_nao_pode_inscrever_duas_vezes(client):
    cadastrar_usuario(client, "organizador_duplo@email.com", "organizador")
    cadastrar_usuario(client, "participante_duplo@email.com")

    token_org = obter_token(client, "organizador_duplo@email.com")
    token_part = obter_token(client, "participante_duplo@email.com")

    evento = criar_evento(client, token_org)
    assert evento.status_code == 201
    evento_id = evento.json()["id"]

    headers = {"Authorization": f"Bearer {token_part}"}

    primeira = client.post(
        f"/eventos/{evento_id}/inscricoes",
        headers=headers
    )
    segunda = client.post(
        f"/eventos/{evento_id}/inscricoes",
        headers=headers
    )

    assert primeira.status_code == 201
    assert segunda.status_code == 409


def test_evento_lotado_nao_aceita_inscricao(client):
    cadastrar_usuario(client, "organizador_lotado@email.com", "organizador")
    cadastrar_usuario(client, "participante_lotado_a@email.com")
    cadastrar_usuario(client, "participante_lotado_b@email.com")

    token_org = obter_token(client, "organizador_lotado@email.com")
    token_a = obter_token(client, "participante_lotado_a@email.com")
    token_b = obter_token(client, "participante_lotado_b@email.com")

    evento = criar_evento(client, token_org, capacidade=1)
    assert evento.status_code == 201
    evento_id = evento.json()["id"]

    primeira = client.post(
        f"/eventos/{evento_id}/inscricoes",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    segunda = client.post(
        f"/eventos/{evento_id}/inscricoes",
        headers={"Authorization": f"Bearer {token_b}"}
    )

    assert primeira.status_code == 201
    assert segunda.status_code == 409


def test_evento_cancelado_nao_aceita_inscricao(client):
    cadastrar_usuario(client, "organizador_cancelado@email.com", "organizador")
    cadastrar_usuario(client, "participante_cancelado@email.com")

    token_org = obter_token(client, "organizador_cancelado@email.com")
    token_part = obter_token(client, "participante_cancelado@email.com")

    evento = criar_evento(client, token_org)
    assert evento.status_code == 201
    evento_id = evento.json()["id"]

    cancelamento = client.delete(
        f"/eventos/{evento_id}",
        headers={"Authorization": f"Bearer {token_org}"}
    )
    assert cancelamento.status_code == 200

    resposta = client.post(
        f"/eventos/{evento_id}/inscricoes",
        headers={"Authorization": f"Bearer {token_part}"}
    )

    assert resposta.status_code == 400


def test_participante_cancela_propria_inscricao(client):
    cadastrar_usuario(
        client, "organizador_cancela_inscricao@email.com", "organizador"
    )
    cadastrar_usuario(client, "participante_cancela@email.com")

    token_org = obter_token(client, "organizador_cancela_inscricao@email.com")
    token_part = obter_token(client, "participante_cancela@email.com")

    evento = criar_evento(client, token_org)
    assert evento.status_code == 201
    evento_id = evento.json()["id"]

    inscricao = client.post(
        f"/eventos/{evento_id}/inscricoes",
        headers={"Authorization": f"Bearer {token_part}"}
    )
    assert inscricao.status_code == 201

    resposta = client.delete(
        f"/inscricoes/{inscricao.json()['id']}",
        headers={"Authorization": f"Bearer {token_part}"}
    )

    assert resposta.status_code == 200
    assert resposta.json()["mensagem"] == "Inscrição cancelada"


def test_participante_nao_cancela_inscricao_de_outro(client):
    cadastrar_usuario(client, "organizador_protecao@email.com", "organizador")
    cadastrar_usuario(client, "participante_dono@email.com")
    cadastrar_usuario(client, "participante_outro@email.com")

    token_org = obter_token(client, "organizador_protecao@email.com")
    token_dono = obter_token(client, "participante_dono@email.com")
    token_outro = obter_token(client, "participante_outro@email.com")

    evento = criar_evento(client, token_org)
    assert evento.status_code == 201
    evento_id = evento.json()["id"]

    inscricao = client.post(
        f"/eventos/{evento_id}/inscricoes",
        headers={"Authorization": f"Bearer {token_dono}"}
    )
    assert inscricao.status_code == 201

    resposta = client.delete(
        f"/inscricoes/{inscricao.json()['id']}",
        headers={"Authorization": f"Bearer {token_outro}"}
    )

    assert resposta.status_code == 403


# ============================================================
# TESTES DE CERTIFICADOS
# ============================================================

def preparar_inscricao_para_certificado(client, email):
    # Cria o organizador
    cadastrar_usuario(client, email, perfil="organizador")
    token_org = obter_token(client, email)

    # Organizador cria o evento
    evento = criar_evento(client, token_org)
    assert evento.status_code == 201, evento.text
    evento_id = evento.json()["id"]

    # Cria um participante separado
    email_participante = f"participante_{email}"
    cadastro = cadastrar_usuario(client, email_participante)
    assert cadastro.status_code == 201, cadastro.text

    token_part = obter_token(client, email_participante)

    # Participante faz a inscrição
    inscricao = client.post(
        f"/eventos/{evento_id}/inscricoes",
        headers={"Authorization": f"Bearer {token_part}"}
    )
    assert inscricao.status_code == 201, inscricao.text

    return token_org, token_part, inscricao.json()


def test_organizador_emite_certificado(client):
    token_org, _, inscricao = preparar_inscricao_para_certificado(
        client, "organizador_certificado@email.com"
    )

    resposta = client.post(
        f"/certificados/emitir/{inscricao['id']}",
        headers={"Authorization": f"Bearer {token_org}"}
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["titulo"] == "Evento de Teste"
    assert resposta.json()["carga_horaria"] == 4
    assert resposta.json()["status"] == "emitido"


def test_nao_emite_certificado_com_inscricao_cancelada(client):
    token_org, token_part, inscricao = preparar_inscricao_para_certificado(
        client, "organizador_cancelado@email.com"
    )

    cancelamento = client.delete(
        f"/inscricoes/{inscricao['id']}",
        headers={"Authorization": f"Bearer {token_part}"}
    )
    assert cancelamento.status_code == 200

    resposta = client.post(
        f"/certificados/emitir/{inscricao['id']}",
        headers={"Authorization": f"Bearer {token_org}"}
    )

    assert resposta.status_code == 400


def test_nao_emite_certificado_duplicado(client):
    token_org, _, inscricao = preparar_inscricao_para_certificado(
        client, "organizador_duplicado@email.com"
    )

    url = f"/certificados/emitir/{inscricao['id']}"
    headers = {"Authorization": f"Bearer {token_org}"}

    primeira = client.post(url, headers=headers)
    segunda = client.post(url, headers=headers)

    assert primeira.status_code == 201, primeira.text
    assert segunda.status_code == 409


def test_participante_nao_emite_certificado(client):
    _, token_part, inscricao = preparar_inscricao_para_certificado(
        client, "organizador_permissao_cert@email.com"
    )

    resposta = client.post(
        f"/certificados/emitir/{inscricao['id']}",
        headers={"Authorization": f"Bearer {token_part}"}
    )

    assert resposta.status_code == 403


def test_participante_consulta_proprio_certificado(client):
    token_org, token_part, inscricao = preparar_inscricao_para_certificado(
        client, "organizador_consulta_cert@email.com"
    )

    emissao = client.post(
        f"/certificados/emitir/{inscricao['id']}",
        headers={"Authorization": f"Bearer {token_org}"}
    )
    assert emissao.status_code == 201, emissao.text

    resposta = client.get(
        f"/certificados/{emissao.json()['id']}",
        headers={"Authorization": f"Bearer {token_part}"}
    )

    assert resposta.status_code == 200


def test_validar_certificado(client):
    token_org, _, inscricao = preparar_inscricao_para_certificado(
        client, "organizador_validar_cert@email.com"
    )

    emissao = client.post(
        f"/certificados/emitir/{inscricao['id']}",
        headers={"Authorization": f"Bearer {token_org}"}
    )
    assert emissao.status_code == 201, emissao.text

    codigo = emissao.json()["codigo"]
    resposta = client.get(f"/certificados/validar/{codigo}")

    assert resposta.status_code == 200
    assert resposta.json()["valido"] is True


def test_certificado_inexistente(client):
    cadastrar_usuario(client, "participante_inexistente@email.com")
    token = obter_token(client, "participante_inexistente@email.com")

    resposta = client.get(
        "/certificados/9999",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 404


def test_administrador_cancela_certificado(client):
    token_org, _, inscricao = preparar_inscricao_para_certificado(
        client, "organizador_cancelar_cert@email.com"
    )

    emissao = client.post(
        f"/certificados/emitir/{inscricao['id']}",
        headers={"Authorization": f"Bearer {token_org}"}
    )
    assert emissao.status_code == 201, emissao.text

    admin = cadastrar_usuario(
        client, "admin_certificado@email.com", "admin"
    )
    token_admin = obter_token(client, admin.email)

    certificado_id = emissao.json()["id"]

    resposta = client.delete(
        f"/certificados/{certificado_id}",
        headers={"Authorization": f"Bearer {token_admin}"}
    )

    assert resposta.status_code == 200
    assert resposta.json()["mensagem"] == "Certificado cancelado"

    validacao = client.get(
        f"/certificados/validar/{emissao.json()['codigo']}"
    )

    assert validacao.status_code == 200
    assert validacao.json()["valido"] is False
