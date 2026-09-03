# Focuslyra — Análise técnica e de produto

Data: 2026-09-03 (todas as correções abaixo já aplicadas e testadas)

## Status: os 8 itens da tabela de prioridades foram resolvidos

Cada mudança foi testada de verdade antes de ir para o seu projeto: compilação Python de todos os módulos, importação real do FastAPI app, `TestClient` cobrindo os endpoints novos e antigos, e por fim o servidor rodando de verdade (`uvicorn`) respondendo a requisições HTTP reais — não só leitura de código.

### 1. `app/runtime.py` — já estava resolvido no seu pull anterior
`RuntimeConfig`, `current_user_id()`, `user_private_dir()`, `user_media_dir()` continuam como estavam. Adicionei duas funções de apoio (`to_storable_path` / `from_storable_path`) para os outros módulos conseguirem gravar caminhos de forma segura mesmo com `FOCUSLYRA_MEDIA_ROOT` customizado, e `legacy_media_root()` para achar arquivos antigos.

### 2. Áudio/TTS/pronúncia agora usam `user_media_dir()`
`audio_service.py`, `pronunciation_service.py` e `tts_service.py` gravam gravações e áudio gerado em `media/users/<id>/...` em vez do caminho fixo `media/...`. Gravações **antigas** (salvas antes dessa mudança) continuam sendo encontradas — testei isso explicitamente: criei uma gravação no layout antigo e confirmei que `_find_recording` ainda a localiza via fallback.

### 3. `/api/profile` agora é `GET`/`PUT` de verdade
Antes lia `data/profile.json` bruto e não tinha `PUT`. Agora usa `profile_service.py` (que já existia mas não estava exposto): grava por usuário, com fallback pro JSON global enquanto o usuário não salvou o próprio. Testado: `PUT` altera nome/duração/foco, `GET` seguinte reflete a mudança.

### 4. Sidebar consolidada — de 9 itens para 5 + Settings
Removi Concepts/Calendar/AI como itens de topo. Sidebar agora: Dashboard, Study, Review, Memory, Progress, e **Settings** isolado visualmente (linha divisória) com 5 abas internas: Profile, Languages, Voices, AI providers, Calendar. Memory ganhou abas internas (Sources/Concepts) em vez de Concepts ser uma tela própria. Voices deixou de se injetar como item de menu à parte (era um acoplamento frágil entre `voice-settings.js` e `app.js` via busca de botão no DOM) e agora vive dentro do painel de Settings.

### 5. `app.js` sem handlers duplicados
Removi as versões "simples" de `saveWriting`/`saveRecording` que só existiam para serem canceladas pelo `stopImmediatePropagation()` do `learning.js`. `learning.js` também foi simplificado (não precisa mais de `{capture: true}` nem de cancelar propagação, já que não há mais um segundo handler para brigar).

### 6. Upload de gravação com limite
`POST /api/recordings` agora rejeita (HTTP 413) uploads acima de 25MB (configurável via `FOCUSLYRA_MAX_RECORDING_MB`). Testado com um upload de 26MB — retorna erro claro em vez de deixar crescer o disco silenciosamente.

### 7. "Start"/"10-minute mode" agora escolhem um idioma real
Novo endpoint `GET /api/study/today`: escolhe o idioma **ativo** de maior prioridade em `languages.json` (mesmo dado que já alimentava o dashboard) e devolve a duração normal/mínima do `profile.json`. "Start today's session" e "10-minute mode" chamam esse endpoint, atualizam o subtítulo da página com o idioma real e passam a marcar gravações/textos salvos com o `language_code` correto — antes tudo ia sempre com `'es-ES'` fixo, então uma sessão em japonês, por exemplo, era silenciosamente registrada como espanhol. O conteúdo de exemplo (roleplay do hotel etc.) continua estático — isso é o gerador de exercícios dinâmico do roadmap, não um bug — mas agora há uma nota visível no painel deixando isso explícito, e os dados salvos não mentem mais sobre o idioma.

### 8. Editor de perfil e idiomas dentro de Settings
- **Settings → Profile**: formulário editando nome, idioma nativo, duração normal/mínima de sessão, importância de acento e foco de aprendizado (fala/escuta/leitura/escrita) — grava via `PUT /api/profile`.
- **Settings → Languages**: lista todos os idiomas com prioridade (número) e status (active/maintenance/parked) editáveis — grava via novo `PUT /api/languages` (novo `app/language_service.py`), que só altera esses dois campos e nunca adiciona/remove idioma (isso continua sendo uma mudança de dados/config, como o `ARCHITECTURE.md` pede). O dashboard e o "Start" já refletem a mudança assim que salva.

## O que ficou de fora (fora do escopo de "corrigir erros")

- Conteúdo de exercício por idioma ainda é estático/demo — é o "dynamic exercise generation" do roadmap, uma funcionalidade nova, não um bug.
- `source_manager.py` (fontes Git externas) continua com caminho global, não por usuário — isso é intencional, já que fontes de interesse são dados compartilhados de referência, não dados privados de aprendizado.
- Review scheduling / daily session planner continuam estáticos — também é funcionalidade nova, não bug.

## Como validar no seu PC

1. `run.bat` (Windows) — agora imprime a URL lendo `FOCUSLYRA_HOST`/`FOCUSLYRA_PORT` do seu `.env`.
2. Abra a Sidebar: deve aparecer só Dashboard/Study/Review/Memory/Progress + Settings.
3. Em Settings → Profile e Settings → Languages, edite algo e salve — confirme que persiste ao recarregar a página.
4. Clique "Start today's session" no Dashboard — o subtítulo deve mostrar o idioma de maior prioridade ativo (hoje: 🇬🇧 English, prioridade 1).
