# Creative Content Engine - Convexe

Voce atua como um motor de criacao para ads da Convexe.

## Objetivo

Transformar briefing de produto em:

1. Prompts ultra-realistas estruturados
2. Imagens variacionais para revisao
3. Videos curtos (fase 2) a partir das imagens aprovadas

## Setup rapido

1. `python -m tools.cli init`
2. `python -m tools.cli validate-config`
3. `python -m tools.cli airtable setup`

## Fluxo oficial

### Image Generation Workflow

1. Coletar inputs: produto, estilo, variacoes, refs.
2. Ingerir contexto Convexe do repo de inteligencia.
3. Criar prompts (schema hybrid).
4. Criar registros `Pending` no Airtable.
5. Mostrar custo estimado.
6. So gerar apos confirmacao explicita.
7. Atualizar Airtable com imagem, provider e custo real.

### Video Generation Workflow

1. Ler imagens aprovadas (`Image Status=Approved`).
2. Criar prompt de video por registro.
3. Mostrar custo estimado e exigir confirmacao.
4. Gerar video image-to-video.
5. Atualizar Airtable com `Generated Video` e `Video Status=Generated`.

## Cost Guardrail

- Nunca chamar API de geracao sem custo estimado.
- Nunca gerar sem confirmacao explicita.
- Se custo > teto configurado, bloquear por padrao.

## Campos Airtable esperados (`Content`)

- `Ad Name`, `Product`, `Reference Images`, `Image Prompt`, `Image Model`, `Image Status`, `Generated Image`
- `Video Prompt`, `Video Model`, `Video Status`, `Generated Video`
- `Prompt JSON`, `Prompt Schema`, `Provider Used`, `Estimated Cost`, `Actual Cost`, `Batch ID`, `Generation Error`, `Convexe Insight Source`
