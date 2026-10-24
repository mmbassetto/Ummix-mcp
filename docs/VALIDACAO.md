# Validação técnica — entrega AKCIT 2026

**DEMONSTRAÇÃO COM DADOS SIMULADOS · atualização de 24/10/2026**

A suíte atual contém **116 testes**, incluindo regras do motor, transporte MCP, aprovação, persistência, descoberta/conexão do agente e decisões verificáveis. O resumo da execução pré-publicação está em [evidencias/testes.json](evidencias/testes.json).

## Verificações realizadas

| Verificação | Resultado |
|---|---|
| Suíte completa pytest | 116 aprovados, zero falhas/erros/pulados |
| Dependências | `pip check` sem incompatibilidades |
| Modelo real | Codex CLI autenticado; resposta do modelo e ferramenta MCP verificadas |
| Catálogo e planejamento | Mercados, segmentos, inventário e simulação chamados pelo LLM |
| Aprovação | Zero aprovações e planos antes da confirmação; caixa desmarcada e botão bloqueado |
| Registro | Uma aprovação e um plano para a simulação gravada, após confirmação explícita de teste |
| Recuperação | `consultar_plano` e leitura independente do SQLite concordaram |
| Auditoria | SIMULACAO_CRIADA, APROVACAO_REGISTRADA, PLANO_CRIADO |
| Vídeo | 1920 × 1080, 25 fps, 192,01 s, H.264/AAC; 4.800 quadros decodificados, sem erros |

O ambiente validado foi Windows/Python 3.12.14, SDK MCP 1.28.0, Pydantic 2.14.1 e Codex CLI 0.163.0-alpha.11.1. Um aviso preexistente de depreciação HTTPX/Starlette aparece nos testes. Linux/macOS, Python 3.11, ChatGPT web/desktop, Claude e outros clientes não foram executados nesta entrega.

## Evidências públicas

- [Chamadas reais das sete ferramentas, entradas e respostas](evidencias/demo_mcp.json).
- [Vídeo contínuo](../video-demo/ummix-mcp-demo.mp4), [roteiro](../video-demo/roteiro.md) e [validação do MP4](../video-demo/validacao.md).
- [Captura da aprovação obrigatória](../video-demo/capturas/07-confirmacao-obrigatoria.png).
- [Captura do plano recuperado](../video-demo/capturas/video-sqlite.png).

Os IDs de plano/simulação são de uma execução com dados fictícios. O banco não é publicado; esses IDs não existirão no banco novo de quem clonar. Para gerar IDs recuperáveis no seu ambiente, execute o fluxo completo. A confirmação automatizada da gravação foi autorizada para o rascunho fictício do ensaio, sem aceite comercial de anunciante.

## Reproduzir os testes

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=var/pytest-local
& .\.venv\Scripts\python.exe -m pip check
```

Para o ensaio web real: iniciar a aplicação, autenticar o Codex e executar `scripts/check_web_connection.py --approve-test --challenge-approval`. A flag autoriza somente a confirmação de teste. Logs, bancos, credenciais e ambiente virtual permanecem locais e fora do GitHub.

## Limites

Inventário, preços, capacidade e impressões são fictícios. A heurística não garante ótimo global. Alcance único e frequência não estão disponíveis, sem deduplicação. Público é afinidade editorial hipotética e objetivo é contexto textual. Não há dados reais de audiência, validação comercial ou integração de produção. O MCP original confia na declaração do cliente; a UI adiciona a permissão para este fluxo local. Auditoria/checksum não são invioláveis contra quem controla o banco.

Nenhuma compra, cobrança, reserva, contratação ou publicação de mídia foi implementada. A entrega do código no GitHub não expõe o serviço web: a aplicação continua local e escuta loopback.
