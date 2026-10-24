# Roteiro da demonstração — Ummix MCP / AKCIT 2026

**DEMONSTRAÇÃO COM DADOS SIMULADOS.** Gravação real de **3min12s**, 1920 × 1080, 25 fps. O vídeo é complementar ao [pitch de três minutos](../docs/PITCH_3_MIN.md).

[Assistir/baixar o MP4 público](https://raw.githubusercontent.com/mmbassetto/Ummix-mcp/main/video-demo/ummix-mcp-demo.mp4) · [arquivo no repositório](ummix-mcp-demo.mp4).

| Tempo | Sequência demonstrada |
|---|---|
| 00:00–00:14 | Ummix MCP • Hackathon AKCIT 2026 |
| 00:14–00:26 | Briefing do anunciante |
| 00:26–00:55 | Agente e ferramentas em execução |
| 00:55–01:17 | Duas alternativas retornadas pelo MCP |
| 01:17–01:35 | Decisão do agente, conferida nas ferramentas |
| 01:35–01:55 | Filtros atendidos e limites dos dados |
| 01:55–02:15 | Aprovação exige confirmação explícita |
| 02:15–02:41 | Registro pelo agente, através do MCP |
| 02:41–02:58 | Plano registrado e recuperado do SQLite |
| 02:58–03:12 | Decisões verificáveis, aprovação humana |

A sequência foi controlada com Playwright e gravada por `recordVideo`, em tempo real. A IA e as ferramentas MCP não foram simuladas. Não houve cortes no fluxo ou aceleração da gravação. As faixas de identificação e as legendas são editoriais; o aviso de dados simulados permanece visível durante as rolagens.

A voz Microsoft Maria, em português do Brasil, é narração editorial gerada localmente pelo Windows. Não representa a voz nem o raciocínio interno do agente. Valores e justificativa foram obtidos da execução real. As respostas do agente aparecem no chat.

O briefing usa um produto fictício, adultos em Goiânia/Anápolis/Rio Verde, orçamento de R$ 5.000, sete dias e rádio/TV. A gravação compara alternativas, mostra a recomendação verificada, os limites, a confirmação inicialmente bloqueada e o plano recuperado do SQLite.

Os scripts de gravação/montagem estão em `scripts/record_video_demo.cjs`, `scripts/narrate_video_demo.ps1` e `scripts/render_video_demo.py`. São auxiliares de vídeo para Windows, requerem Node/Playwright, Chromium/gravador FFmpeg, pacote imageio-ffmpeg em `var/video-tools`, voz local em português e Codex autenticado. Essas ferramentas não são necessárias para executar o protótipo nem reproduzir o MP4.

Os arquivos intermediários e o original contínuo são mantidos localmente e excluídos do GitHub; a publicação contém o MP4 final, capturas selecionadas e [evidências públicas](../docs/evidencias/demo_mcp.json).
