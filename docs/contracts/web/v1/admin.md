# Administração de equivalências — API v1

A interface `/admin` atende um único responsável. Configure `ADMIN_USERNAME` e
`ADMIN_PASSWORD_HASH` (PHC Argon2id v19) no core. Sem as duas credenciais, as rotas
não são registradas; configuração parcial ou hash inválido impede a inicialização.
As credenciais dos coletores não concedem acesso administrativo.

Todas as respostas usam `Cache-Control: no-store`. Use HTTPS na mesma origem da
interface. Requisições de escrita exigem `Origin: https://<host>`; após o login,
exigem também `X-CSRF-Token` com o token devolvido pela sessão. Não há CORS,
registro, recuperação de senha ou autorização por token de scraper.

## Sessões

| Método e caminho (`/api/v1/admin`) | Corpo / resposta |
| --- | --- |
| `POST /session` | JSON `{"username":"responsavel","password":"..."}`; devolve `{"username":"responsavel","csrf":"..."}`. |
| `GET /session` | Mesma resposta, exige cookie válido. |
| `DELETE /session` | Exige CSRF; revoga a sessão no servidor e remove o cookie; `204`. |

O cookie `__Host-nossa-admin` é opaco, `Secure`, `HttpOnly`, `SameSite=Strict`,
com caminho `/` e validade absoluta de oito horas. O banco guarda apenas SHA-256
do identificador aleatório de 256 bits, CSRF e expiração. Sessões expiradas são
ignoradas e removidas em novos logins. O limite compartilhado entre processos é
10 tentativas por responsável em 15 minutos, incluindo tentativas bem-sucedidas;
a 11ª retorna `429` com `Retry-After: 900`, antes de calcular Argon2.

## Consulta e prévia

| Método e caminho | Resposta |
| --- | --- |
| `GET /candidates` | Instantâneo consistente do catálogo descrito abaixo. |
| `GET /products?q=texto` | Lista de produtos originais; busca por nome normalizado ou ID. Sem `q`, lista todos. |
| `GET /products/:id` | Produto original e representante atual. |
| `GET /groups` | Mesmo instantâneo, permitindo inspecionar grupos, prévia e auditoria. |
| `GET /groups/:id` | `revision`, `representative`, `members`, `audit`; ID do representante atual. |

O instantâneo contém `revision`, `genericEnabled`, `products`, `candidates`,
`generic` e `audit`. `generic` é a prévia de pares elegíveis ainda não agrupados;
não é ativada pela consulta. Produtos informam ID, nome, marca, código,
`package` nulo ou `{Quantity, Unit, Count}`, bases observadas, anúncios
(`name`, `brand`, `barcode`, `url`, `shop`), quantidade de observações,
`firstObserved`, `lastObserved` (UTC) e `representative`.

Cada candidato informa `first`, `second`, `kind` (`exact`, `fuzzy`, `generic`),
`score` (0–1), `differences`, `reason` e `verificationRequired`. A pontuação mede
similaridade de palavras, **não probabilidade de identidade**. Exatos vêm primeiro;
os aproximados são ordenados por pontuação. Marcas e embalagens completas,
incluindo contagens, devem ser equivalentes. Diferenças explícitas de variante
excluem sugestões comuns. Informação omitida, incluindo “Vácuo” no exemplo
Pilão 133/3103, permanece visível e exige conferência das fontes para aprovação.
Busca e seleção manual atendem pares fora da descoberta automática.

## Decisões e reversão

`POST /reviews` e `POST /groups` recebem o mesmo objeto:

```json
{
  "revision": 42,
  "action": "approve",
  "first": 133,
  "second": 3103,
  "reason": "Explicação baseada na conferência das fontes",
  "sourceVerified": true
}
```

Este exemplo descreve apenas a forma do pedido, **não aprova os produtos citados**.

| Ação | Campos adicionais e comportamento |
| --- | --- |
| `approve` | `first`, `second`; combina os grupos existentes, exige comparabilidade. Diferenças de palavras exigem `sourceVerified`. Conflitos explícitos entre quaisquer membros ou exclusões impedem a união. |
| `reject` | `first`, `second`; registra exclusão persistente, inclusive contra união transitiva. |
| `remove` | `first`; retira o membro e exclui sua reunião com os antigos pares. Recalcula o representante se necessário. |
| `dissolve` | `first` (qualquer membro); dissolve o grupo e exclui todos os pares anteriores. |
| `representative` | `first` (qualquer membro), `representative` (membro do mesmo grupo). |
| `activate` | Ativa as regras genéricas e aplica a prévia ao catálogo existente, atomicamente. |
| `deactivate` | Interrompe novas decisões automáticas; grupos existentes continuam reversíveis. |

`reason` é obrigatório em todas as ações (até 2000 caracteres). Deixar pendente é
uma ação local: não envia decisão. Toda escrita bem-sucedida retorna `204`.
Alterações e ingestão usam o mesmo bloqueio de catálogo; revisão desatualizada
retorna `409 stale_review`. Atualize e confira novamente, sem repetir a aprovação
silenciosamente. `422 invalid_decision` indica incompatibilidade, exclusão,
campos inválidos ou ausência de conferência. `400` indica JSON/ID inválido,
`401` sessão ausente/expirada ou credenciais inválidas, `403` origem/CSRF inválido,
`404` recurso ausente/admin desativado e `500`/`503` indisponibilidade interna.

A auditoria inclui ator, horário, ação, motivo, revisão, versão da regra automática,
pedido e composição anterior/posterior. Os últimos 100 registros são apresentados;
a tabela conserva todos. A exclusão manual prevalece sobre regras automáticas.

## Regras genéricas `commodities_v2`

A migração 00018 ativa as regras em instalações novas e existentes. A inicialização
aplica as regras ao catálogo existente antes de iniciar a ingestão; as ingestões
seguintes continuam agrupando os elegíveis. A desativação explícita posterior continua disponível e
exclusões manuais sempre prevalecem.

São aceitas ofertas por kg e pacotes com peso em g/kg, incluindo a contagem de
componentes. Marcas de hortifruti, como `GERAL`, `Direto do Produtor` e `Hortifruti`,
não determinam identidade. No título, marcas informadas e os rótulos conhecidos
Santome, Taeq, RDU e Qualyban são ignorados. A regra consome todas as palavras;
termos desconhecidos continuam exigindo revisão. Nas carnes, marcas ausentes e
rótulos genéricos (`Açougue`, `Bovino in Natura`,
`GERAL`, `Bandeiras`, `Direto do Produtor`) não mudam a identidade. Marcas comerciais
continuam separadas; pacotes de pesos diferentes da mesma marca podem ser unidos.
Códigos divergentes são preservados.

Variedades suportadas: banana maçã, prata, terra e nanica/caturra (incluindo
“Caturra/Nanica”); batata sem variedade e inglesa separadamente; tomate sem
variedade, italiano e cereja separadamente; cebola sem variedade e roxa
separadamente; cenoura. Cortes: acém, miolo de acém, picanha bovina e suína
(separadas), músculo, patinho,
coxão mole/chã de dentro e coxão duro/chã de fora. Carne moída sem corte informado
fica separada de acém ou patinho moídos; carne moída bovina explícita também fica
separada de carne moída sem espécie declarada. Preparações não informada, inteira,
pedaço/peça, bife, tiras, cubos e moída são distintas. Com osso, sem osso e osso
não informado ficam separados. Orgânico, Angus, fresco, resfriado e congelado são
atributos distintos; conservação incompatível ou “com osso” junto com “sem osso”
invalidam o reconhecimento. Temperos, pratos prontos, linguiças e sabores de
picanha não estabelecem identidade com o corte.

Não se infere variedade, preparação ou estado de conservação. Orgânico (incluindo
`Org`), Baby e Turma da Mônica permanecem em grupos próprios. Bandeja (`Bdj`), granel,
“fruta”, pesos no título e estimativas de contagem entre parênteses não criam uma
variante. Processados, temperos, maços, preços por unidade e termos desconhecidos
ficam fora da união automática. Alface ambígua e produtos Nescafé não são
pré-aprovados. Marcas não mudam a identidade de uma fruta reconhecida.

Os históricos e a visão global resolvem a composição atual antes dos cálculos.
Não reescrevem nomes originais de `products`, códigos, `shop_products`, preços,
pesos observados nem a atribuição histórica das observações. A associação guarda
um nome genérico (sem marca no hortifruti) e a base `kg`. Pacotes são convertidos
por `preço × 1000 / (gramas × contagem)`, com aritmética decimal e arredondamento
apenas na saída. Uma massa única, explícita e no fim do título original, como
`1,1kg` ou `1k`, pode suprir um peso ausente quando o produto original não tem
embalagem estruturada. Estimativas, pesos por unidade e títulos com múltiplas
quantidades não suprem esse peso. Peso desconhecido não vira zero.

Uma união muda a unidade de agregação da visão global para o grupo; anúncios,
localidades e condições conservam seus próprios fluxos. A busca consulta todos os
membros e retorna uma linha por representante, com nome neutro para grupos
genéricos. O histórico usa preços por kg e mantém a exigência de condições
comparáveis e cobertura. A mesma conversão é aplicada aos dados brutos e aos
resumos diários; a versão de metodologia invalida resultados antigos em cache.

## Coletores

A mesma sessão permite revisar [relatórios e diagnósticos dos coletores](../../scraper-reports/v1/README.md).
