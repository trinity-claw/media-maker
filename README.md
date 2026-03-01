# Media-Maker Convexe

Engine de prompts ultrarealistas para Convexe com foco em:

- Fase 1: prompt estruturado + geracao de imagem + revisao no Airtable
- Fase 2: geracao de video a partir de imagens aprovadas

## Principios

- Prompt tecnico em ingles, copy final em PT-BR.
- Personas sinteticas apenas (sem likeness de pessoas reais).
- Controle de custo obrigatorio antes de chamar API de geracao.
- Fallback de provider: `kie -> google`.

## Estrutura

```text
media-maker/
|-- .claude/.env.example
|-- config/settings.yml
|-- config/pricing.yml
|-- tools/
|-- tests/
|-- references/inputs/
|-- output/
|-- GEMINI.md
|-- CLAUDE.md
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .claude\.env.example .claude\.env
```

Preencha `.claude/.env` com:

- `GOOGLE_API_KEY`
- `KIE_API_KEY`
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`

## Comandos CLI

```bash
python -m tools.cli init
python -m tools.cli validate-config
python -m tools.cli airtable setup
python -m tools.cli campaign create --product "Quadro Atlas" --variations 5 --style "premium documentary"
python -m tools.cli image generate --batch-id <id> --confirm-cost
python -m tools.cli status
python -m tools.cli video generate --from-approved --confirm-cost
```

## Dry Run

`config/settings.yml` vem com `generation.dry_run: true` para testes sem custo.
Para geracao real, mude para `false`.

## CI

Pipeline minimo em `.github/workflows/ci.yml`:

- Instala dependencias
- `pytest -q`
- `python -m tools.cli validate-config`
