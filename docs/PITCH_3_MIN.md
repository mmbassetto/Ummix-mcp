# Pitch de três minutos — Ummix MCP

**Hackathon AKCIT 2026 · versão para a banca · 24/10/2026**

Tempo-alvo: **3:00**. Texto para fala, com pausas curtas e apoio das capturas. A gravação complementar do protótipo tem 3:12; não é necessário reproduzi-la inteira junto com esta fala de três minutos.

## 00:00–00:25 · Problema

Planejar rádio e TV exige transformar cidade, público, objetivo e orçamento em escolhas concretas. Nossa hipótese é que parte desse trabalho pode ser simplificada por uma conversa, mantendo os cálculos verificáveis e a decisão com o anunciante. O Ummix MCP conecta uma inteligência artificial externa à infraestrutura de planejamento de mídia.

## 00:25–00:50 · Como funciona

O anunciante informa o briefing no chat. O agente consulta mercados, segmentos e inventário por ferramentas MCP reais. O motor valida as regras e calcula alternativas. Na tela, acompanhamos argumentos e respostas das ferramentas. Não mostramos uma encenação do raciocínio: mostramos ações e resultados que podem ser conferidos.

## 00:50–01:30 · Decisão verificável

Na demonstração, usamos cinco mil reais fictícios, público adulto, sete dias e três cidades: Goiânia, Anápolis e Rio Verde. Eficiência retorna cinco veículos, dezesseis inserções e investimento de cinco mil reais. Diversificação retorna seis veículos, dezessete inserções e quatro mil novecentos e noventa reais.

O agente recomenda Diversificação porque inclui rádio e TV nas três cidades. A opção de eficiência deixa Rio Verde sem TV. O backend confere esse critério nas saídas MCP. São seis combinações de cidade e canal contra cinco, sem inventar alcance ou resultado comercial.

## 01:30–02:00 · Controle e confiança

Todos os veículos, preços, capacidades e impressões são simulados. Alcance único e frequência ficam indisponíveis, porque não temos deduplicação válida. O painel distingue filtros atendidos, não atendidos e não comprovados. O pedido de planejamento não autoriza aprovação: o anunciante precisa escolher, marcar uma caixa inicialmente desmarcada e confirmar a alternativa.

## 02:00–02:30 · Evidência técnica

Só depois da confirmação o agente registra a aprovação, cria o rascunho e consulta o plano. A interface exibe o identificador e a recuperação do SQLite, com auditoria de simulação, aprovação e criação. A gravação mostra as sete ferramentas usadas por uma IA real. A suíte passou com cento e dezesseis testes. Não há compra, pagamento, reserva ou publicação de mídia.

## 02:30–03:00 · Negócio e próximo passo

Nosso público inicial proposto são agências regionais, com hipótese de assinatura B2B ou licença de integração. O próximo passo é validar o problema, a disposição a pagar e um catálogo autorizado em piloto. Ainda não temos validação comercial ou parceria comprovada. Entregamos uma base funcional para decisões de mídia explicáveis: a IA planeja, o MCP conecta e a pessoa confirma.

---

## Apoio para a apresentação

- [Vídeo público — 3min12s](https://raw.githubusercontent.com/mmbassetto/Ummix-mcp/main/video-demo/ummix-mcp-demo.mp4)
- [Captura da comparação](../video-demo/capturas/03-duas-alternativas.png)
- [Captura da confirmação obrigatória](../video-demo/capturas/07-confirmacao-obrigatoria.png)
- [Plano recuperado do SQLite](../video-demo/capturas/video-sqlite.png)
- [BMC atualizado](BMC.md) · [README e execução](../README.md)

**Orientação:** ensaiar a fala para ajustar as pausas ao ritmo do apresentador. Se mostrar o vídeo, identificá-lo como gravação de uma execução real anterior, com dados de mídia simulados. Não apresentar o vídeo como sessão ao vivo nem prometer métricas ausentes.
