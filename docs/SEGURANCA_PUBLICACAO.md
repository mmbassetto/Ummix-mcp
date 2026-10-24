# Revisão de segurança da publicação

Revisão do conjunto de entrega antes do primeiro push para `mmbassetto/Ummix-mcp`, em 24/10/2026.

## Incluído

- Código do protótipo, dependências declaradas, testes e scripts auxiliares.
- README, BMC, pitch, fluxo e validação atualizados.
- MP4 final e capturas selecionadas da aplicação com dados fictícios.
- Evidências públicas das chamadas MCP e resumo de testes, sem diretórios pessoais ou detalhes de autenticação.

## Excluído do versionamento

- `.venv/`, caches, pacotes/navegadores/FFmpeg auxiliares em `var/`, builds e artefatos locais.
- SQLite e outros bancos, logs brutos, credenciais, tokens, `.env` real, chaves e configurações pessoais.
- Documentos locais de instrução, relatórios históricos com caminhos específicos da máquina, hostname e diretórios de usuário.
- WebM original, arquivos WAV, textos intermediários, logs de montagem e metadados locais do vídeo.

Esses arquivos permanecem no computador; foram excluídos da publicação por `.gitignore`, sem remover os dados locais. `.env.example` contém somente exemplos genéricos e não é carregado automaticamente.

## Verificações

O conjunto elegível foi inspecionado por nome/tipo/tamanho e por padrões de tokens GitHub/OpenAI/AWS, JWT, cabeçalhos de chave privada, atribuições suspeitas de segredo e caminhos pessoais. As capturas selecionadas foram revisadas: mostram apenas o produto fictício e a aplicação. O MP4 contém somente a execução do protótipo e faixas editoriais, sem tela de login ou credenciais.

O resumo da varredura do conjunto efetivamente preparado para commit está em [evidencias/revisao_publicacao.json](evidencias/revisao_publicacao.json). A varredura é uma verificação preventiva e não constitui garantia universal de ausência de qualquer informação sensível.

A autenticação GitHub foi feita pelo fluxo oficial de dispositivo do Git Credential Manager. Credenciais não foram inseridas no código, URL remota, documentos ou logs públicos. Nenhum token foi impresso na conversa ou incorporado ao commit. O autor Git usa o endereço público de privacidade `noreply` do GitHub.

Os dados de mídia são inteiramente simulados, conforme avisos da interface, README e vídeo. IDs públicos são de ensaios fictícios; o banco local correspondente não foi enviado.
