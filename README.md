# GESTÃO DE EVENTOS — API

Projeto acadêmico desenvolvido em FastAPI para gerenciamento de usuários, eventos, categorias, inscrições, vagas e certificados.

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
- Pytest

## Estrutura do projeto

```text
GESTAO-DE-EVENTOS/
├── main.py
├── GESTAO DE EVENTOS.py
├── requirements.txt
├── alembic.ini
├── .env.example
├── .gitignore
├── README.md
├── MATRIZ_PERMISSOES.md
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 0001_criacao_inicial.py
│       ├── 76d7635e77bd_descricao_da_alteracao.py
│       ├── 628022ca30a4_descricao_da_alteracao.py
│       └── 8e12ef9a37a6_teste_controle_migracoes.py
└── tests/
    └── test_api.py
```

## Instalação

Instale as dependências do projeto:

```bash
python -m pip install -r requirements.txt
```

## Banco de dados e migrations

Para criar ou atualizar a estrutura do banco de dados, execute:

```bash
python -m alembic upgrade head
```

Para verificar a migration atual:

```bash
python -m alembic current
```

Para consultar o histórico de migrations:

```bash
python -m alembic history
```

Para criar uma nova migration depois de alterar os modelos:

```bash
python -m alembic revision --autogenerate -m "descricao_da_alteracao"
```

Depois, aplique a migration:

```bash
python -m alembic upgrade head
```

## Executar a API

No PowerShell, se o terminal estiver na pasta raiz `GESTAO-DE-EVENTOS-ALEMBIC`, execute:

```powershell
Set-Location .\GESTAO-DE-EVENTOS
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Se o terminal já estiver dentro da pasta `GESTAO-DE-EVENTOS`, execute:

```powershell
python -m uvicorn main:app --reload
```

Quando aparecer a mensagem `Application startup complete`, a API estará iniciada.

## Swagger / Documentação

Acesse a documentação interativa:

http://127.0.0.1:8000/docs

Se estiver utilizando a porta 8001:

http://127.0.0.1:8001/docs

As operações estão organizadas por assunto:

- Autenticação
- Usuários
- Categorias
- Eventos
- Inscrições
- Certificados
- Sistema

## Fluxo de teste da API

1. Utilize `POST /auth/register` para cadastrar um organizador.
2. Utilize `POST /auth/login` para realizar o login, usando o e-mail como username e a senha cadastrada.
3. Autorize o Swagger com o token Bearer.
4. Crie uma categoria.
5. Crie um evento.
6. Cadastre outro usuário como participante.
7. Faça login com o participante.
8. Inscreva o participante no evento.
9. Retorne à conta do organizador.
10. Emita o certificado referente à inscrição.
11. Valide o certificado utilizando seu código.

## Testes automatizados

Para executar os testes automatizados do projeto:

```bash
python -m pytest -v
```

Para verificar se existem alterações nos modelos que precisam de migrations:

```bash
python -m alembic check
```

## Observações importantes

O cadastro público não permite criar diretamente um usuário com perfil `admin`. Uma tentativa de registrar esse perfil é convertida para `participante`.

Para demonstrar rotas administrativas em uma entrega acadêmica, recomenda-se utilizar um mecanismo de bootstrap ou seed de administrador separado e protegido.

A chave JWT está definida no arquivo para facilitar o ambiente acadêmico. Em produção, ela deve ser armazenada em uma variável de ambiente.

Arquivos locais de banco de dados e variáveis de ambiente não devem ser enviados ao repositório.