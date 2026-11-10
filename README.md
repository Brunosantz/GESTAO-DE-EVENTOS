# GESTÃO DE EVENTOS — API

Projeto acadêmico em FastAPI para gerenciamento de usuários, eventos, categorias,
inscrições, vagas e certificados.

## Tecnologias

- FastAPI
- Swagger/OpenAPI
- Pydantic
- SQLAlchemy
- SQLite
- Alembic
- JWT
- bcrypt
- Uvicorn

## Estrutura

```text
GESTAO-DE-EVENTOS/
├── GESTAO DE EVENTOS.py
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_criacao_inicial.py
└── eventos.db
```

## Instalação

```bash
python -m pip install -r requirements.txt
```

## Banco de dados com Alembic

Primeiro, crie/atualize o banco usando a migration:

```bash
python -m alembic upgrade head
```

Para conferir o histórico:

```bash
python -m alembic current
python -m alembic history
```

Para criar uma nova migration depois de alterar os modelos:

```bash
python -m alembic revision --autogenerate -m "descricao_da_alteracao"
python -m alembic upgrade head
```

## Executar API

No PowerShell, se o terminal estiver na raiz `GESTAO-DE-EVENTOS-ALEMBIC` aberta no VS Code:

```powershell
Set-Location .\GESTAO-DE-EVENTOS
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Se o terminal já estiver na pasta `GESTAO-DE-EVENTOS`, execute:

```bash
python -m uvicorn main:app --reload
```

Depois que aparecer `Application startup complete`, abra `http://127.0.0.1:8000/docs`.

Se a porta 8000 estiver ocupada:

```bash
python -m uvicorn main:app --reload --port 8001
```

## Swagger

Abra:

```text
http://127.0.0.1:8000/docs
```

ou, usando 8001:

```text
http://127.0.0.1:8001/docs
```

As operações estão agrupadas no Swagger por assunto: Autenticação, Usuários,
Categorias, Eventos, Inscrições, Certificados e Sistema.

## Fluxo de teste

1. `POST /auth/register` para criar um organizador.
2. `POST /auth/login` usando `username = email` e a senha.
3. Autorize o Swagger com o token Bearer.
4. Crie uma categoria.
5. Crie um evento.
6. Crie outro usuário como participante.
7. Faça login com o participante.
8. Inscreva o participante no evento.
9. Volte ao organizador.
10. Emita o certificado pela inscrição.
11. Valide o certificado pelo código.

## Observação importante

O cadastro público não permite criar diretamente um usuário `admin`; uma tentativa
de registrar `admin` é convertida para `participante`. Para uma entrega acadêmica
que precise demonstrar rotas administrativas, recomenda-se criar um mecanismo de
bootstrap/seed de administrador separado e protegido, em vez de deixar uma senha
administrativa fixa na API.

A chave JWT está definida no arquivo apenas para facilitar o ambiente acadêmico.
Em produção ela deve ficar em variável de ambiente.
