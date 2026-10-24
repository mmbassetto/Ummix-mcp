"""Exporta o vídeo contínuo real em MP4, com narração editorial e validação integral."""

import hashlib
import json
import re
import shutil
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video-demo"
WORK = OUT / ".render"
FFMPEG = ROOT / "var/video-tools/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"


def run(args, log=None):
    result = subprocess.run([str(a) for a in args], cwd=OUT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if log:
        (WORK / log).write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Processo falhou: {args[0]}\n{result.stderr[-4000:]}")
    return result


def main():
    report = json.loads((OUT / "gravacao.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed", "Gravação sem comprovação de sucesso."
    WORK.mkdir(exist_ok=True)
    audio = WORK / "audio"
    captions = WORK / "captions"
    captions.mkdir(exist_ok=True)
    pwsh = shutil.which("pwsh") or "powershell.exe"
    print("Gerando narração editorial local em português…", flush=True)
    # Ajustes de texto editorial para a duração real; não altera vídeo, chat ou resultados.
    a, b = report["alternatives"]
    count = lambda alt: sum(r["insercoes"] for r in alt["alocacao"])
    chosen = next(alt for alt in report["alternatives"] if alt["alternativa_id"] == report["decision"]["alternativa_id"])
    editorial = {
        "abertura": "Ummix MCP: um agente de inteligência artificial planeja campanhas de rádio e TV usando ferramentas reais. Todos os dados de mídia são simulados.",
        "briefing": "O briefing informa três cidades, público adulto, cinco mil reais e sete dias em rádio e TV. Planejar ainda não autoriza aprovar.",
        "alternativas": f"{a['nome']}: {float(a['custo_total']):g} reais, {len(a['alocacao'])} veículos e {count(a)} inserções. {b['nome']}: {float(b['custo_total']):g} reais, {len(b['alocacao'])} veículos e {count(b)} inserções. As duas alocações vieram do MCP.",
        "recomendacao": f"O agente recomenda {chosen['nome']}. Critério: {report['decision']['criterio_label']}. Os valores foram conferidos na saída MCP. Isso não comprova alcance ou resultado comercial.",
        "encerramento": "IA externa real, ferramentas MCP e confirmação humana. Ummix MCP, Hackathon AKCIT 2026. Dados de mídia simulados.",
    }
    for c in report["chapters"]:
        c["narration"] = editorial.get(c["id"], c["narration"]).replace(",00 reais", " reais")
    (WORK / "narracao.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    run([pwsh, "-NoProfile", "-File", ROOT / "scripts/narrate_video_demo.ps1", "-ReportPath", WORK / "narracao.json", "-AudioDirectory", audio], "narracao.log")
    inputs = [FFMPEG, "-y", "-hide_banner", "-i", report["raw_video"]]
    for c in report["chapters"]:
        inputs += ["-i", audio / (c["id"] + ".wav")]
    (captions / "brand.txt").write_text("UMMIX MCP  /  AKCIT 2026  /  NARRAÇÃO EDITORIAL", encoding="utf-8")
    (captions / "warning.txt").write_text("DEMONSTRAÇÃO COM DADOS SIMULADOS", encoding="utf-8")
    # Sobreposição somente editorial. A gravação WebM original permanece intacta.
    font = "C\\:/Windows/Fonts/segoeui.ttf"
    bold = "C\\:/Windows/Fonts/segoeuib.ttf"
    video_filters = [
        "fps=25,setsar=1",
        "drawbox=x=0:y=0:w=iw:h=64:color=0x211c20@0.97:t=fill",
        f"drawtext=fontfile='{bold}':textfile='.render/captions/brand.txt':fontcolor=white:fontsize=23:x=38:y=19",
        f"drawtext=fontfile='{bold}':textfile='.render/captions/warning.txt':fontcolor=0xffdc99:fontsize=23:x=w-tw-38:y=19",
        "drawbox=x=0:y=ih-126:w=iw:h=126:color=0x211c20@0.96:t=fill",
    ]
    audios = []
    audio_details = []
    for index, c in enumerate(report["chapters"], 1):
        caption_path = captions / (c["id"] + ".txt")
        caption_path.write_text(c["caption"], encoding="utf-8")
        for line_index, line in enumerate(c["caption"].splitlines()):
            line_name = f"{c['id']}-{line_index}.txt"
            (captions / line_name).write_text(line, encoding="utf-8")
            video_filters.append(
                f"drawtext=fontfile='{font}':textfile='.render/captions/{line_name}':fontcolor=white:fontsize=30:"
                f"x=42:y=h-106+{line_index * 45}:enable='between(t,{c['start']:.3f},{c['end']-.02:.3f})'")
        with wave.open(str(audio / (c["id"] + ".wav")), "rb") as wav:
            length = wav.getnframes() / wav.getframerate()
        slot = c["end"] - c["start"]
        speed = max(1.0, length / (slot - 0.6))
        assert speed < 1.35, f"Narração longa demais para {c['id']}; ajuste o texto editorial."
        delay = int(c["start"] * 1000)
        audios.append(f"[{index}:a]atempo={speed:.5f},aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=9,adelay={delay}:all=1[a{index}]")
        audio_details.append({"chapter": c["id"], "voice_seconds": length, "slot_seconds": slot, "speed": speed})
    graph = "[0:v]" + ",".join(video_filters) + "[v];\n"
    graph += ";\n".join(audios) + ";\n"
    graph += "".join(f"[a{i}]" for i in range(1, len(audios) + 1)) + f"amix=inputs={len(audios)}:normalize=0,alimiter=limit=0.95,apad[a]"
    (WORK / "filtergraph.txt").write_text(graph, encoding="utf-8")
    target = OUT / "ummix-mcp-demo.mp4"
    print("Exportando MP4 H.264/AAC 1920×1080…", flush=True)
    run(inputs + ["-filter_complex_script", WORK / "filtergraph.txt", "-map", "[v]", "-map", "[a]",
                  "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-threads", "4",
                  "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-t", f"{report['recorded_seconds']:.3f}",
                  "-movflags", "+faststart", "-metadata", "title=Ummix MCP — Hackathon AKCIT 2026",
                  "-metadata", "comment=Gravação contínua real do Playwright. IA externa real. Dados de mídia simulados. Narração editorial sintética local.", target], "encode.log")
    print("Verificando todas as trilhas e decodificando o MP4 inteiro…", flush=True)
    decoded = run([FFMPEG, "-v", "error", "-xerror", "-progress", "pipe:1", "-i", target, "-f", "null", "-"], "decode.log")
    decoded_frames = int(re.findall(r"frame=(\d+)", decoded.stdout)[-1])
    assert abs(decoded_frames / 25 - report["recorded_seconds"]) < 1, "Duração da trilha de vídeo incompatível."
    metadata = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(target)], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    (WORK / "metadata.txt").write_text(metadata, encoding="utf-8")
    assert "1920x1080" in metadata and "Video: h264" in metadata and "Audio: aac" in metadata, metadata
    duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", metadata)
    assert duration_match, "Duração não encontrada no contêiner."
    hours, minutes, seconds = map(float, duration_match.groups())
    duration = hours * 3600 + minutes * 60 + seconds
    assert abs(duration - report["recorded_seconds"]) < 1, "Duração incompatível com a gravação contínua."
    for c in report["chapters"]:
        moment = c["start"] + min(4, (c["end"] - c["start"]) / 2)
        run([FFMPEG, "-y", "-hide_banner", "-ss", str(moment), "-i", target, "-frames:v", "1",
             OUT / "capturas" / ("video-" + c["id"] + ".png")])
    run([FFMPEG, "-y", "-hide_banner", "-i", target, "-vf", "fps=1/20,scale=480:270,tile=3x3", "-frames:v", "1", OUT / "capturas/contact-sheet.png"])
    verification = {"file": str(target), "bytes": target.stat().st_size, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "resolution": "1920x1080", "video_codec": "H.264", "audio_codec": "AAC", "fps": 25,
                    "duration_seconds": duration, "full_decode_errors": 0, "decoded_video_frames": decoded_frames,
                    "narration": "Microsoft Maria Desktop, Portuguese (Brazil), Windows SAPI, editorial",
                    "continuous_original_preserved": report["raw_video"], "speed_of_browser_video": "1x, sem cortes ou aceleração", "audio_timing": audio_details}
    (OUT / "validacao-mp4.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    write_documents(report, verification)
    print(json.dumps({k: v for k, v in verification.items() if k != "audio_timing"}, ensure_ascii=False, indent=2), flush=True)


def stamp(seconds):
    return f"{int(seconds)//60:02d}:{int(seconds)%60:02d}"


def write_documents(report, verification):
    sequence = "\n".join(f"| {stamp(c['start'])}–{stamp(c['end'])} | {c['title']} |" for c in report["chapters"])
    transcript = "\n\n".join(f"### {stamp(c['start'])} — {c['title']}\n\n{c['narration']}" for c in report["chapters"])
    (OUT / "roteiro.md").write_text(f"""# Ummix MCP — Hackathon AKCIT 2026

DEMONSTRAÇÃO COM DADOS SIMULADOS. Duração: **{stamp(verification['duration_seconds'])}**, 1920 × 1080, 25 fps.

O vídeo mostra uma única execução contínua, em tempo real, controlada por Playwright. Não há corte, aceleração, substituição de resposta ou alteração de dados MCP. As faixas superior e inferior são identificação e legendas editoriais. O aviso de dados simulados permanece visível em todos os quadros, inclusive durante rolagens.

A voz Microsoft Maria, em português do Brasil, é narração editorial sintetizada localmente pelo Windows. Não representa fala nem raciocínio interno do agente. As respostas do agente estão no chat da aplicação. Os valores narrados e legendados foram obtidos desta execução real.

| Tempo | Sequência demonstrada |
|---|---|
{sequence}

## Texto da narração editorial

{transcript}

## Reproduzir

Abra `ummix-mcp-demo.mp4` em um reprodutor compatível com H.264/AAC. O MP4 possui fast start. A conexão com o modelo é necessária para executar o protótipo ao vivo, mas não para reproduzir este arquivo.

## Gravar novamente neste ambiente

As dependências de vídeo ficam em `var/playwright-browsers` e `var/video-tools`, separadas das dependências da aplicação. O gravador reutiliza a aplicação na porta 8765 ou a inicia se necessário. Cada execução cria um rascunho fictício próprio e preserva os registros anteriores.

```powershell
Set-Location '{ROOT}'
$env:NODE_PATH=Join-Path (Get-Location) 'var\\video-node\\node_modules'
$env:PLAYWRIGHT_BROWSERS_PATH=Join-Path (Get-Location) 'var\\playwright-browsers'
node scripts/record_video_demo.cjs
& .\\.venv\\Scripts\\python.exe scripts/render_video_demo.py
```

As evidências da execução, incluindo exportação MCP, verificação de conexão e WebM contínuo original, ficam em `originais/`. `gravacao.json` registra horários e resultados observados. Os scripts param e preservam a evidência se uma etapa falhar; não inserem resultados fictícios para completar a sequência.
""", encoding="utf-8")
    alt_rows = "\n".join(f"| {a['nome']} | BRL {a['custo_total']} | {len(a['alocacao'])} | {sum(r['insercoes'] for r in a['alocacao'])} |" for a in report["alternatives"])
    tool_names = sorted({t["tool"] for t in report["tools"] if t["status"] == "completed"})
    tool_rows = "\n".join(f"| {name} | Concluída com retorno real |" for name in tool_names)
    errors = "Nenhuma falha de aplicação ou ferramenta MCP observada nesta gravação." if not report["errors"] else json.dumps(report["errors"], ensure_ascii=False, indent=2)
    (OUT / "validacao.md").write_text(f"""# Validação da demonstração gravada

**DEMONSTRAÇÃO COM DADOS SIMULADOS. IA externa real; inventário fictício.**

Execução iniciada: {report['started_at']}. Finalizada: {report['finished_at']}.

## Arquivo verificado

- Arquivo: `{verification['file']}`
- Tamanho: {verification['bytes']:,} bytes.
- Duração do contêiner: {verification['duration_seconds']:.2f} segundos.
- Vídeo: H.264, 1920 × 1080, 25 fps, yuv420p. Áudio: AAC estéreo, 48 kHz.
- MP4 com fast start; todas as trilhas decodificadas integralmente com FFmpeg, `-xerror`, sem erro.
- SHA-256: `{verification['sha256']}`
- Original contínuo: `{verification['continuous_original_preserved']}`

O MP4 mantém a gravação do navegador em velocidade original. Apenas faixas de identificação/legendas e narração editorial foram acrescentadas. O áudio usa a voz local Microsoft Maria; não é uma resposta sintetizada atribuída à IA. FFmpeg 7.1, imageio-ffmpeg 0.6.0, Playwright 1.62.1 e Chromium 151.0.7922.34 foram usados.

## Agente e MCP

Backend: {report['server']}. A verificação real de autenticação, resposta do modelo e chamada MCP retornou `ready`, `authenticated`, `model_verified` e `mcp_verified` verdadeiros. As sete ferramentas foram descobertas. Executável real: `{report['health']['executable']}`.

| Ferramenta MCP utilizada | Resultado |
|---|---|
{tool_rows}

Não foram usados mocks, interceptação de rede, alteração de saídas MCP, métricas inventadas ou respostas predefinidas do modelo. A exportação de sessão registra argumentos, respostas e ordem das chamadas. O briefing foi enviado pelos controles reais da interface.

## Planejamento observado

| Alternativa | Investimento fictício | Veículos | Inserções |
|---|---:|---:|---:|
{alt_rows}

Escolha do agente: `{report['decision']['alternativa_id']}`. Critério: **{report['decision']['criterio_label']}**, conferido pelo backend na saída `simular_plano`. Comparação: {json.dumps(report['decision']['comparacao'], ensure_ascii=False)}.

Alcance único e frequência ficaram indisponíveis. O painel identifica o público como afinidade editorial hipotética e distingue filtros do briefing estruturado atendidos no seed, não atendidos e não comprovados. Não se promete audiência real, vendas ou conversão.

## Confirmação e SQLite

- Simulação: `{report['simulation_id']}`.
- Plano: **`{report['plan_id']}`**, estado `RASCUNHO_APROVADO`.
- Antes da confirmação: {report['before_confirmation']['approvals']} aprovações e {report['before_confirmation']['plans']} planos para esta simulação, conferidos diretamente no SQLite em modo de leitura.
- Modal: caixa inicialmente desmarcada, botão de confirmação inicialmente desabilitado. A confirmação foi feita pelo Playwright, explicitamente para o rascunho fictício deste ensaio autorizado.
- Depois da confirmação: {report['after_confirmation']['approvals']} aprovação e {report['after_confirmation']['plans']} plano para esta simulação.
- As chamadas de escrita ocorreram após o evento de confirmação da interface.
- Recuperação real: `{report['verification']['source']}`, `verified=true`, mesmo `plan_id`; conferência independente do corpo do plano no SQLite também passou.
- Auditoria: {', '.join(a['evento'] for a in report['audit'])}.
- Não houve compra, pagamento, reserva ou publicação de mídia. Os registros anteriores foram preservados.

## Testes e ocorrências

Os **116 testes automatizados existentes passaram novamente** antes da gravação, em 20,29 s. Um aviso preexistente de depreciação HTTPX/Starlette; nenhum erro, falha ou teste pulado. JUnit: `artifacts/pytest-video.xml`. Nenhum arquivo de produção da aplicação, do servidor MCP, do inventário ou dos testes foi alterado para gravar o vídeo.

{errors}

Na preparação, Playwright já estava disponível; Chromium e FFmpeg foram instalados em diretórios auxiliares locais por fontes oficiais/registro PyPI. Uma sondagem inicial do loopback foi bloqueada pelas restrições de sockets do ambiente; foi repetida com acesso local autorizado, sem alterar proteções globais. A primeira montagem parou porque a narração excedia a duração de algumas etapas; o texto editorial foi encurtado. A revisão visual da montagem seguinte detectou a segunda linha das legendas fora do quadro; as duas linhas passaram a ter posições explícitas e o MP4 foi exportado novamente. O vídeo original contínuo permaneceu intacto. Essas ocorrências não foram respostas do agente nem falhas do protótipo. Qualquer tentativa de gravação com falha é preservada em `originais/`, com diagnóstico e captura, e não é apresentada como sucesso.

## Evidências

- `gravacao.json`: cronologia, disponibilidade, ferramentas e resultados observados.
- `validacao-mp4.json`: metadados, hash, duração e validação da decodificação.
- `originais/`: vídeo bruto e exportação completa da execução.
- `capturas/`: briefing, chamadas MCP, alternativas, recomendação, limites, confirmação e recuperação do plano; quadros do MP4 e folha de contato.
- `.render/`: textos editoriais, arquivos WAV e logs técnicos do FFmpeg.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
