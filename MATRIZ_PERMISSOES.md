# Matriz de Permissões — Gestão de Eventos

Esta matriz apresenta as permissões de acesso dos perfis do sistema.

| Endpoint | Administrador | Organizador | Participante |
|---|---|---|---|
| POST /categorias | Permitido | Permitido | Negado (403) |
| POST /eventos | Permitido | Permitido | Negado (403) |
| POST /certificados/emitir/{inscricao_id} | Permitido | Apenas eventos próprios | Negado (403) |
| DELETE /certificados/{certificado_id} | Permitido | Negado (403) | Negado (403) |
| GET /inscricoes | Todas as inscrições | Inscrições de eventos próprios | Apenas suas inscrições |

## Regras de autenticação e autorização

- **401 Unauthorized:** ocorre quando a requisição é feita sem autenticação válida.
- **403 Forbidden:** ocorre quando o usuário está autenticado, mas não possui permissão para realizar a operação.
- O administrador possui acesso às operações administrativas.
- O organizador pode gerenciar eventos e categorias, respeitando as restrições de propriedade dos recursos.
- O participante possui acesso às operações permitidas ao seu próprio perfil e às suas inscrições.

**Observação:** a matriz deve corresponder às regras de permissão definidas na Primeira Unidade e implementadas no projeto.