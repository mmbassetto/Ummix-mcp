# Validação do vídeo — Ummix MCP / AKCIT 2026

**DEMONSTRAÇÃO COM DADOS SIMULADOS. IA externa real; inventário fictício.**

## Arquivo final

- [MP4 público](https://raw.githubusercontent.com/mmbassetto/Ummix-mcp/main/video-demo/ummix-mcp-demo.mp4), também versionado em `video-demo/ummix-mcp-demo.mp4`.
- Duração: **192,01 segundos (3min12s)**; 1920 × 1080; 25 fps.
- H.264/yuv420p, AAC estéreo/48 kHz, MP4 com fast start.
- Tamanho: **17866768 bytes**.
- SHA-256: `c6c635ef2a513db3410d5edd0e345e085aeb051776d4a9cdceaf8ccd7ad02833`.
- Decodificação integral: **4.800 quadros, zero erros**; áudio verificado, volume médio -19,2 dB e pico -0,9 dB.
- Ferramentas: Playwright 1.62.1, Chromium 151.0.7922.34, FFmpeg 7.1, imageio-ffmpeg 0.6.0. Narração editorial: Microsoft Maria/Windows SAPI, português do Brasil.

## Execução observada

As sete ferramentas foram chamadas pelo LLM: `listar_mercados`, `listar_segmentos`, `consultar_inventario`, `simular_plano`, `registrar_aprovacao`, `criar_plano` e `consultar_plano`. Não houve mocks, interceptação de rede ou alteração das respostas MCP. [Entradas e respostas reais](../docs/evidencias/demo_mcp.json).

Eficiência: R$ 5.000, cinco veículos e 16 inserções. Diversificação: R$ 4.990, seis veículos e 17 inserções. O agente escolheu Diversificação com o critério de mais combinações cidade/canal, seis contra cinco. A opção Eficiência deixa Rio Verde sem TV. Alcance único e frequência permaneceram indisponíveis.

O modal iniciou com caixa desmarcada e botão bloqueado. Antes da confirmação havia zero aprovações e zero planos para a simulação; depois, uma aprovação e um plano. As escritas MCP ocorreram após o evento de confirmação. Essa confirmação automatizada foi feita somente para o rascunho fictício do ensaio autorizado.

- Simulação: `0078d99c-a3b6-41c1-93fa-1013f3ecef0d`.
- Plano: **`a20f00ef-b382-4fd0-a2e7-54beb5714028`**, `RASCUNHO_APROVADO`.
- Recuperação MCP por `consultar_plano` e conferência independente do corpo do plano no SQLite: aprovadas.
- Auditoria: SIMULACAO_CRIADA → APROVACAO_REGISTRADA → PLANO_CRIADO.

Os IDs são da execução gravada, não de um banco distribuído no repositório. Nenhuma compra, pagamento, reserva ou publicação de mídia ocorreu.

## Testes e ocorrências

A suíte de 116 testes passou antes da gravação e foi repetida para a publicação. Nenhum arquivo de produção foi alterado para gravar. Credenciais, logs brutos, SQLite e diretórios pessoais foram excluídos da publicação.

Nenhuma falha da aplicação ou ferramenta MCP foi observada na gravação. Na preparação, uma sondagem foi bloqueada pela restrição de sockets do ambiente e repetida com acesso local autorizado. Na montagem, o texto da narração foi encurtado para caber nas etapas, e a posição da segunda linha das legendas foi corrigida após revisão visual. O vídeo contínuo original permaneceu intacto. As ocorrências foram de preparação/montagem, não resultados da IA ou do protótipo.
