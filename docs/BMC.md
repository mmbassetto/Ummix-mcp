# Business Model Canvas — Ummix MCP

**Hackathon AKCIT 2026 · atualizado em 24/10/2026**

> Protótipo funcional validado tecnicamente. Hipóteses comerciais ainda não validadas. Todos os dados de mídia da demonstração são simulados; não há compra, pagamento ou veiculação real.

## Negócio proposto

Oferecer a agências e anunciantes regionais uma infraestrutura de planejamento de rádio e TV que possa ser operada por agentes de IA através do MCP. O anunciante descreve o briefing; as ferramentas retornam alternativas calculadas; o agente recomenda com evidências; a pessoa escolhe e confirma; o sistema registra um rascunho auditável.

| Bloco do BMC | Modelo proposto e hipótese a validar |
|---|---|
| **1. Segmentos de clientes** | Agências regionais e equipes de planejamento de mídia como público inicial. Anunciantes locais que precisam comparar rádio e TV como usuários finais. Validar quem opera, quem decide a compra e quem paga. |
| **2. Proposta de valor** | Transformar briefing em cenários comparáveis com veículos, investimento e inserções; justificar a recomendação com dados verificáveis; manter aprovação explícita e registro recuperável. Hipótese: reduzir trabalho operacional e tornar a decisão mais transparente. Não há economia de tempo ou ROI medidos. |
| **3. Canais** | Demonstração web, pilotos assistidos com agências e integração MCP com clientes de IA. O GitHub e o vídeo apresentam o protótipo; não representam um canal comercial já validado. |
| **4. Relacionamento com clientes** | Onboarding assistido, suporte ao planejador, documentação e revisão humana. O cliente mantém a decisão de aprovação. Validar necessidade de treinamento, suporte e governança em cada agência. |
| **5. Fontes de receita** | Hipóteses de assinatura B2B por equipe/uso e licença de integração para plataformas de planejamento. Preço, disposição a pagar e unidade de cobrança ainda não definidos. Não há faturamento, clientes pagantes ou comissão sobre compra de mídia comprovados. |
| **6. Recursos principais** | Servidor MCP e schemas, motor de planejamento, inventário autorizado e atualizado, agente/interface, armazenamento e trilha de decisão, equipe técnica e governança de dados. Hoje o inventário é totalmente fictício. |
| **7. Atividades principais** | Manter catálogo e integrações, validar cálculos e decisões, testar aprovação/persistência, operar pilotos, avaliar utilidade e atualizar dados. A execução comercial futura exige identidade, autorização e operação apropriadas. |
| **8. Parcerias principais** | Potenciais provedores autorizados de inventário, emissoras, agências e provedores de IA. Nenhuma parceria, API comercial oficial ou contrato de dados é comprovado nesta entrega. |
| **9. Estrutura de custos** | Engenharia e manutenção, curadoria/licenciamento de dados, suporte, segurança, hospedagem e consumo de modelos. O protótipo usa infraestrutura local e a conta de IA autenticada; os custos de uma operação comercial ainda precisam ser medidos. |

## O que já está comprovado

- Chat web com LLM externo real pelo Codex CLI e sete ferramentas MCP stdio.
- Coleta de briefing, duas alternativas quando viáveis e conferência do critério escolhido pelo agente.
- Veículos, orçamento, inserções e filtros comparáveis; alcance único e frequência indisponíveis de forma explícita.
- Confirmação obrigatória na interface, SQLite, idempotência e recuperação com auditoria.
- **116 testes aprovados** e [gravação contínua real](../video-demo/ummix-mcp-demo.mp4), com evidências das sete ferramentas.

Esses resultados comprovam execução técnica. Não comprovam demanda, precisão de audiência, aumento de vendas, redução de custos ou integração de produção com a Ummix Ads. A identidade visual é inspirada na marca; o projeto não acessa seus serviços comerciais.

## Experimentos de negócio propostos

| Hipótese | Experimento | Evidência a coletar |
|---|---|---|
| Há trabalho repetitivo relevante no planejamento regional | Entrevistar planejadores e observar uma tarefa com autorização | Etapas atuais, retrabalho, restrições e responsável pela decisão |
| A comparação reduz esforço e melhora compreensão | Piloto assistido com a mesma tarefa antes/depois | Tempo por etapa, correções e compreensão dos limites; sem prometer redução antecipada |
| Existe disposição a pagar | Entrevistas e proposta de piloto com preço a testar | Interesse, objeções, decisor de compra e intenção de contratação; não confundir interesse com receita |
| Dados autorizados sustentam a operação | Prova de integração após autorização do provedor | Atualização, completude, direitos de uso, cobertura e capacidade de auditoria |

## Próxima decisão após o hackathon

Selecionar um segmento inicial, validar o problema e obter um piloto com dados autorizados. Identidade de aprovadores, catálogo real e operação comercial são condições futuras; não foram implementadas para a entrega. [Protótipo e documentação](../README.md) · [Pitch](PITCH_3_MIN.md).
