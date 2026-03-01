# Tutorial Operacional (PT-BR) - Media-Maker Convexe

Este tutorial cobre o fluxo completo que voce roda no dia a dia: setup, criacao de lote, geracao de imagens, revisao no Airtable e preparacao para video.

## 1. Preparacao inicial
1. Criar e ativar ambiente virtual:
```powershell
python -m venv .venv
.venv\Scripts\activate
```
2. Instalar dependencias:
```powershell
pip install -r requirements.txt
```
3. Criar `.claude/.env` a partir do exemplo:
```powershell
copy .claude\.env.example .claude\.env
```
4. Preencher `.claude/.env` com:
- `GOOGLE_API_KEY`
- `KIE_API_KEY`
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`
- `AIRTABLE_TABLE_ID`

## 2. Verificacao de ambiente
1. Validar configuracao:
```powershell
python -m tools.cli validate-config
```
2. Criar/validar schema Airtable:
```powershell
python -m tools.cli airtable setup
```
3. Atualizar catalogo de assets Convexe:
```powershell
python -m tools.cli catalog build
```

## 3. Fluxo rapido (recomendado): `ingest run`
Use quando voce quer gerar no mesmo passo:
- criar registros no Airtable
- gerar imagens
- anexar resultado e custo

Exemplo:
```powershell
python -m tools.cli ingest run ^
  --frame-number 189 ^
  --frame-name "Quadro 189 performance" ^
  --mockup-path "G:\...\#189 - Front png.png" ^
  --style "ultra realistic premium social ad, synthetic adult persona, both hands touching frame edges" ^
  --variations 3 ^
  --mode img2img ^
  --confirm-cost
```

### O que acontece internamente
1. Resolve contexto Convexe (repo irmao, quando disponivel).
2. Sobe mockups para URL publica.
3. Define `img2img` quando ha referencia.
4. Le a proporcao do mockup e aplica lock da proporcao da arte no prompt.
5. Cria linhas `Pending` no Airtable.
6. Estima custo e bloqueia se passar teto sem override.
7. Gera imagem (`kie -> google`) e atualiza `Generated`.
8. Grava auditoria em `output/runs`.

## 4. Fluxo em duas etapas (campanha + execucao)
Quando voce quer separar cadastro do lote e geracao:

1. Criar batch:
```powershell
python -m tools.cli campaign create ^
  --product "Quadro Atlas" ^
  --style "premium documentary realism" ^
  --variations 5 ^
  --mode txt2img
```
2. Gerar imagens do batch:
```powershell
python -m tools.cli image generate --batch-id <BATCH_ID> --confirm-cost
```

## 5. Revisao no Airtable
Na tabela `Content`:
- revisar `Generated Image`
- marcar `Image Status` como `Approved` ou `Rejected`
- observar `Provider Used`, `Estimated Cost`, `Actual Cost`, `Generation Error`

## 6. Video (fase 2)
Depois que houver imagens aprovadas:
```powershell
python -m tools.cli video generate --from-approved --confirm-cost
```

## 7. Guardrails de qualidade (ja implementados)
- Personas sinteticas (sem likeness real).
- Moldura preta fosca limpa (sem tag/placa metalica).
- Sem vidro/acrilico/reflexo de poster.
- Sem split/collage/two-in-one.
- Fisica de contato valida (mao encostando no quadro).
- Sem olhar para cima artificial quando cena pede instalacao natural.
- Proporcao do quadro preservada conforme referencia.

## 8. Como pedir variacoes com melhor resultado
No `--style`, seja especifico:
- contexto do ambiente (apartamento premium, home office moderno)
- faixa etaria adulta (ex.: 25-35)
- postura (duas maos em contato com bordas da moldura)
- mood (aspiracional, motivacional, brand-safe)
- camera/lente/luz quando necessario

Exemplo:
```text
ultra realistic premium ad photo, single attractive adult woman age 25-32,
subtle sensual confidence, both hands firmly touching opposite frame edges,
matte floating black frame, no glass reflection, modern luxury interior,
single image only, no split, social conversion framing
```

## 9. Troubleshooting
- Google 429 quota: manter Kie como primario.
- Falha de rede Kie: retries com backoff estao ativos; rerodar lote se preciso.
- Airtable sem anexos: validar token/scopes e table id.
- Resultado distorcido: reforcar estilo + referencias e rodar nova variacao.

## 10. Auditoria e rastreabilidade
- Batches: `output/batches/*.json`
- Runs: `output/runs/*.json`
- Imagens: `output/images/<campanha>/<timestamp>/`
- Espelho nuvem (opcional): pasta configurada em `cloud_sync.root`

