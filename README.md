# Media-Maker Convexe
Engine de criativos da Convexe para gerar imagens (fase 1) e videos (fase 2) com governanca de custo, qualidade e revisao em nuvem.

## O que este projeto entrega hoje
- Gera prompts estruturados (schema canonico) para cenarios ultra-realistas.
- Gera imagens com fallback de provider (`kie -> google`).
- Publica assets e atualiza Airtable (`Content`) como hub de revisao.
- Faz ingestao manual por codigo/nome/mockup de quadro em um unico comando.
- Aplica guardrails de qualidade para Convexe:
  - moldura preta fosca limpa (sem tags/etiquetas)
  - imagem unica (sem split/diptych/collage)
  - fisica de instalacao coerente (maos em contato real com a moldura)
  - superficie de arte em canvas fosco (sem vidro/acrilico/reflexo espelhado)
  - bloqueio de poses ruins (ex.: olhar para cima sem sentido)
  - lock de proporcao real do quadro de referencia (sem distorcer arte)

## Arquitetura (resumo)
```text
Voce (direcao criativa)
  -> tools/cli.py (orquestrador)
    -> tools/prompt_engine.py (schema + variacoes)
    -> tools/image_gen.py (Kie/Google + fallback + cloud sync)
    -> tools/airtable.py (CRUD + setup schema)
    -> tools/upload.py (hosting para URLs publicas)
    -> tools/intel_ingest.py (contexto Convexe do repo irmao)
  -> Airtable (revisao e status)
  -> output/ (auditoria local)
```

## Estrutura de pastas
```text
media-maker/
|-- .claude/.env.example
|-- .github/workflows/ci.yml
|-- config/
|   |-- settings.yml
|   |-- pricing.yml
|-- tools/
|-- tests/
|-- references/inputs/
|-- output/
|-- docs/TUTORIAL_PTBR.md
|-- GEMINI.md
|-- CLAUDE.md
```

## Requisitos
- Python 3.10+ (recomendado)
- Credenciais:
  - `GOOGLE_API_KEY`
  - `KIE_API_KEY`
  - `AIRTABLE_API_KEY`
  - `AIRTABLE_BASE_ID`
  - `AIRTABLE_TABLE_ID` (recomendado quando ja existe tabela)

## Instalacao
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .claude\.env.example .claude\.env
```

Preencha `.claude/.env` com as chaves e IDs reais.

## Configuracao importante
Arquivo: `config/settings.yml`

- `generation.default_provider_order`: ordem de fallback
- `generation.max_batch_cost_usd`: teto de custo por lote
- `generation.require_explicit_cost_confirmation`: exige `--confirm-cost`
- `providers.kie.request_retries`: retries de rede da Kie
- `providers.kie.retry_backoff_seconds`: backoff de retry
- `providers.kie.poll_interval_seconds`: polling de task Kie
- `cloud_sync.enabled/root`: espelho em nuvem (Google Drive local)
- `local_gallery.enabled/root`: pasta unica local com copia de toda imagem gerada

Arquivo: `config/pricing.yml`
- tabela de custo por provider/resolucao para estimativa e guardrail

## Comandos principais (CLI)
```powershell
python -m tools.cli init
python -m tools.cli validate-config
python -m tools.cli airtable setup
python -m tools.cli catalog build
python -m tools.cli catalog lookup --frame-code 189
python -m tools.cli campaign create --product "Quadro Atlas" --variations 5 --style "premium documentary"
python -m tools.cli image generate --batch-id <id> --confirm-cost
python -m tools.cli ingest run --frame-number 189 --variations 3 --confirm-cost
python -m tools.cli status
python -m tools.cli video generate --from-approved --confirm-cost
```

## Fluxo recomendado (producao)
1. `python -m tools.cli validate-config`
2. `python -m tools.cli airtable setup` (uma vez, ou quando schema mudar)
3. `python -m tools.cli catalog build` (atualiza catalogo de assets Convexe)
4. Criar e gerar lote:
   - via campanha: `campaign create` + `image generate`
   - ou via atalho: `ingest run` (create+generate em um comando)
5. Revisar no Airtable (`Image Status` Approved/Rejected)
6. Para fase 2, rodar `video generate --from-approved --confirm-cost`

## Ingestao manual (atalho mais usado)
Use quando voce ja tem o quadro alvo e mockup:

```powershell
python -m tools.cli ingest run ^
  --frame-number 189 ^
  --frame-name "Quadro 189 premium" ^
  --mockup-path "G:\...\#189 - Front png.png" ^
  --no-auto-from-catalog ^
  --style "ultra realistic premium social ad, synthetic adult persona, both hands touching frame edges" ^
  --variations 3 ^
  --mode img2img ^
  --confirm-cost
```

O que o comando faz:
- resolve contexto Convexe
- sobe referencias para URL publica
- infere `img2img`
- infere proporcao do quadro de referencia e aplica lock estrutural no prompt
- cria registros `Pending` no Airtable
- estima custo, valida teto, gera imagem, anexa URL
- grava auditoria em `output/runs/*.json`

## Regras de qualidade aplicadas no prompt
- sem celebridades/likeness real
- sem filtros de embelezamento
- sem moldura com etiqueta/tag metalica
- sem vidro/acrilico/reflexo espelhado sobre a arte
- sem split image / before-after / collage
- sem pose fisicamente impossivel (mao “no ar”)
- foco em textura realista e fotografia documental premium

## Airtable (tabela `Content`)
Campos operacionais esperados:
- `Ad Name`, `Product`, `Reference Images`, `Image Prompt`, `Image Model`, `Image Status`, `Generated Image`
- `Video Prompt`, `Video Model`, `Video Status`, `Generated Video`
- `Prompt JSON`, `Prompt Schema`, `Provider Used`, `Estimated Cost`, `Actual Cost`, `Batch ID`, `Generation Error`, `Convexe Insight Source`, `Cloud Asset Path`

## Troubleshooting rapido
- `429 RESOURCE_EXHAUSTED` no Google: cota da API esgotada; manter `kie` como primario.
- `Connection reset` na Kie: retries ja estao ativos em `tools/image_gen.py`; repetir lote se necessario.
- Airtable sem anexos: conferir token/scopes e `AIRTABLE_BASE_ID`/`AIRTABLE_TABLE_ID`.
- Resultado com visual indesejado: ajustar `--style` e rerodar variação (pipeline preserva auditoria por batch).

## Galeria Local Consolidada
- Toda imagem gerada recebe copia automatica em `output/all-images` (configuravel em `local_gallery.root`).
- O nome inclui `batch_id` + nome original do arquivo para facilitar busca/triagem.

## Testes e CI
Local:
```powershell
python -m pytest -q
python -m tools.cli validate-config
```

CI (`.github/workflows/ci.yml`):
- instala dependencias
- roda testes
- valida config

## Documentacao complementar
- Tutorial completo: `docs/TUTORIAL_PTBR.md`
- Orquestracao por agente:
  - `GEMINI.md`
  - `CLAUDE.md`
