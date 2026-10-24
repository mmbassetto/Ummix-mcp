/* Grava interações reais com Playwright. Não intercepta nem modifica respostas. */
const fs = require('node:fs');
const path = require('node:path');
const {spawn, execFileSync} = require('node:child_process');
const {chromium} = require('playwright');

const root = path.resolve(__dirname, '..');
const output = path.join(root, 'video-demo');
const attempt = path.join(output, 'originais', new Date().toISOString().replace(/[:.]/g, '-'));
const captures = path.join(output, 'capturas');
const base = 'http://127.0.0.1:8765';
const python = path.join(root, '.venv', 'Scripts', 'python.exe');
fs.mkdirSync(attempt, {recursive:true});
fs.mkdirSync(captures, {recursive:true});
const save = (name, value) => fs.writeFileSync(path.join(attempt, name), JSON.stringify(value, null, 2), 'utf8');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const assert = (condition, message) => {if (!condition) throw new Error(message);};
const report = {started_at:new Date().toISOString(), viewport:{width:1920,height:1080}, chapters:[],
  errors:[], tools:[], app_changes:false, mocked_responses:false, recording:'Playwright recordVideo, tempo real sem cortes'};
let browser, context, page, originTime, sid, video;
const observed=new Set();
const elapsed = () => (Date.now()-originTime)/1000;
const chapter = (id, title, caption, narration) => {
  if (report.chapters.length) report.chapters.at(-1).end = elapsed();
  report.chapters.push({id,title,caption,narration,start:elapsed()});
  console.log(`ETAPA ${id}: ${title} (${elapsed().toFixed(1)}s)`);
};
async function minimumFrom(start, seconds) {while (elapsed()-start < seconds) await sleep(Math.min(1000,(seconds-(elapsed()-start))*1000));}
async function screenshot(name) {await page.screenshot({path:path.join(captures,name+'.png')});}
async function jsonRequest(route, options={}) {
  const response = await fetch(base+route, {...options, headers:{'X-Ummix-Local':'1',Origin:base,...options.headers}, signal:AbortSignal.timeout(160000)});
  const data = await response.json();
  assert(response.ok, `${route}: HTTP ${response.status}: ${JSON.stringify(data)}`);
  return data;
}
function sqlite(simulationId, planId='') {
  const code = `import sqlite3,json,sys\nfrom pathlib import Path\nwith sqlite3.connect(Path(sys.argv[1]).resolve().as_uri()+'?mode=ro',uri=True) as c:\n r={t:c.execute('SELECT count(*) FROM '+t+' WHERE simulation_id=?',(sys.argv[2],)).fetchone()[0] for t in ('approvals','plans')}\n row=c.execute('SELECT body FROM plans WHERE id=?',(sys.argv[3],)).fetchone() if sys.argv[3] else None\n r['body']=json.loads(row[0]) if row else None\n print(json.dumps(r))`;
  return JSON.parse(execFileSync(python,['-c',code,path.join(root,'var/web.sqlite3'),simulationId,planId],{encoding:'utf8',windowsHide:true}));
}
async function focus(locator) {
  await locator.evaluate(el => el.scrollIntoView({behavior:'smooth',block:'center'}));
  await sleep(1000);
}
async function monitor() {
  const deadline=Date.now()+250000;
  while(Date.now()<deadline) {
    const state=await jsonRequest('/api/sessions/'+sid);
    if(state.last_error) throw new Error('Falha real do agente: '+state.last_error);
    for(const event of state.events.filter(e=>e.type==='tool')) {
      const unique=event.key+':'+event.status;
      if(observed.has(unique)) continue;
      observed.add(unique);
      report.tools.push({time:elapsed(),key:event.key,tool:event.tool,status:event.status});
      console.log(`MCP ${event.tool}: ${event.status}`);
      const details=page.locator('.tool-event').filter({has:page.locator('summary code').filter({hasText:event.tool})}).last();
      if(await details.count()) {
        await focus(page.locator('.activity-panel'));
        if(event.tool==='consultar_inventario' || event.tool==='registrar_aprovacao' || event.tool==='consultar_plano') {
          if(await details.getAttribute('open')===null) await details.locator('summary').click();
        }
        if(event.status==='completed') await screenshot('mcp-'+event.tool);
      }
      if(event.status==='error') report.errors.push({kind:'mcp',time:elapsed(),event});
    }
    if(!state.busy) return state;
    await sleep(650);
  }
  throw new Error('Tempo limite do turno real; o vídeo não presume sucesso.');
}

(async()=>{
 try {
  try {assert((await fetch(base+'/',{signal:AbortSignal.timeout(3000)})).ok,'HTTP indisponível'); report.server='Aplicação existente reutilizada';}
  catch {
    const log=fs.openSync(path.join(attempt,'backend.log'),'a');
    const child=spawn(python,['-u','-m','ummix_mcp.web','--port','8765'],{cwd:root,env:{...process.env,PYTHONUTF8:'1'},detached:true,windowsHide:true,stdio:['ignore',log,log]});
    child.unref(); report.server='Aplicação iniciada pelo gravador';
    await sleep(2500);
  }
  console.log('Verificando IA real, autenticação e MCP antes de gravar…');
  report.health=await jsonRequest('/api/health?refresh=1');
  assert(['ready','authenticated','model_verified','mcp_verified'].every(k=>report.health[k]===true),'Agente/MCP indisponível: '+report.health.message);
  assert(report.health.mcp_tools.length===7,'As sete ferramentas não foram descobertas.');
  save('health.json',report.health);
  browser=await chromium.launch({headless:true});
  context=await browser.newContext({viewport:report.viewport,deviceScaleFactor:1,locale:'pt-BR',timezoneId:'America/Sao_Paulo',
    recordVideo:{dir:attempt,size:report.viewport}});
  originTime=Date.now();
  page=await context.newPage();
  video=page.video();
  page.on('pageerror',error=>report.errors.push({kind:'browser',time:elapsed(),message:error.message}));
  page.on('console',message=>{if(message.type()==='error')report.errors.push({kind:'console',time:elapsed(),message:message.text()});});
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.locator('#connection.ready').waitFor({timeout:120000});
  assert(await page.getByText('DEMONSTRAÇÃO COM DADOS SIMULADOS',{exact:true}).isVisible(),'Aviso de simulação ausente.');
  chapter('abertura','Ummix MCP • Hackathon AKCIT 2026','IA externa real • ferramentas MCP • SQLite\nDemonstração gravada no protótipo funcional.',
    'O Ummix MCP conecta um agente de inteligência artificial à infraestrutura de planejamento de rádio e TV. Esta demonstração foi gravada no protótipo real. Todos os dados de mídia são simulados.');
  await screenshot('01-agente-disponivel');
  await minimumFrom(report.chapters.at(-1).start,14);
  chapter('briefing','Briefing do anunciante','Goiânia, Anápolis e Rio Verde • adultos\nR$ 5.000 • rádio e TV • sete dias',
    'O anunciante informa três cidades, o público adulto, cinco mil reais e sete dias de campanha em rádio e TV. O pedido de planejamento ainda não autoriza a aprovação.');
  await page.locator('.quick-demo').click();
  report.briefing=await page.locator('#prompt').inputValue();
  await page.locator('#prompt').focus();
  await screenshot('02-briefing');
  await minimumFrom(report.chapters.at(-1).start,12);
  const href=await page.locator('#export-link').getAttribute('href');
  sid=href.split('/')[3]; report.session_id=sid;
  chapter('planejamento','Agente e ferramentas em execução','Ferramentas reais, eventos reais\nMercados → segmentos → inventário → simulação',
    'O agente consulta mercados, segmentos e inventário pelo MCP. As chamadas exibidas são reais. Os resultados chegam das ferramentas, sem respostas pré-programadas.');
  await page.locator('#send').click();
  const planned=await monitor();
  save('planejamento.json',planned);
  assert(planned.simulation?.alternativas.length===2,'O MCP não retornou duas alternativas nesta execução.');
  assert(planned.decision?.verificada===true,'A recomendação da IA não passou pela conferência MCP.');
  assert(planned.plan===null,'Plano criado antes da confirmação.');
  report.before_confirmation=sqlite(planned.simulation.simulation_id);
  assert(report.before_confirmation.approvals===0 && report.before_confirmation.plans===0,'Aprovação automática indevida no SQLite.');
  await minimumFrom(report.chapters.at(-1).start,24);
  const [a,b]=planned.simulation.alternativas;
  const count=a=>a.alocacao.reduce((s,r)=>s+r.insercoes,0);
  const brl=x=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(x));
  chapter('alternativas','Duas alternativas retornadas pelo MCP',
    `${a.nome}: ${brl(a.custo_total)} • ${a.alocacao.length} veículos • ${count(a)} inserções\n${b.nome}: ${brl(b.custo_total)} • ${b.alocacao.length} veículos • ${count(b)} inserções`,
    `Compare as alternativas retornadas pelo motor. ${a.nome} usa ${a.custo_total.replace('.',',')} reais, ${a.alocacao.length} veículos e ${count(a)} inserções. ${b.nome} usa ${b.custo_total.replace('.',',')} reais, ${b.alocacao.length} veículos e ${count(b)} inserções. São estratégias diferentes, com orçamento e alocação conferíveis.`);
  await page.locator(`[data-alt="${a.alternativa_id}"]`).click();
  await focus(page.locator('.alternatives'));
  await screenshot('03-duas-alternativas');
  await sleep(7000);
  await focus(page.locator('.channel-legend'));
  await sleep(5000);
  await page.locator(`[data-alt="${b.alternativa_id}"]`).click();
  await focus(page.locator('.channel-legend'));
  await screenshot('04-veiculos-insercoes');
  await minimumFrom(report.chapters.at(-1).start,22);
  const chosen=planned.simulation.alternativas.find(a=>a.alternativa_id===planned.decision.alternativa_id);
  chapter('recomendacao','Decisão do agente, conferida nas ferramentas',
    `Recomendação da IA: ${chosen.nome}\nCritério verificável: ${planned.decision.criterio_label}`,
    `O agente recomenda ${chosen.nome}. O critério escolhido foi: ${planned.decision.criterio_label}. A interface compara os valores das duas alternativas na saída da ferramenta MCP. Essa justificativa não comprova alcance ou resultado comercial.`);
  await page.locator(`[data-alt="${chosen.alternativa_id}"]`).click();
  await focus(page.locator('[data-decision="verified"]'));
  await screenshot('05-recomendacao-verificada');
  await minimumFrom(report.chapters.at(-1).start,18);
  chapter('limites','Filtros atendidos e limites dos dados','Atendido no seed • não atendido • não comprovado\nAlcance único e frequência: indisponíveis',
    'O painel separa filtros atendidos, não atendidos e não comprovados. Os segmentos são afinidades hipotéticas do catálogo. Alcance único, frequência, perfil demográfico detalhado e resultados de venda não são comprovados por estes dados.');
  const filterTable=page.locator('table').filter({has:page.getByText('FILTRO',{exact:true})});
  await focus(filterTable.getByText('Canais em cada cidade',{exact:true}));
  await sleep(7000);
  await focus(filterTable.getByText('Objetivo e público real',{exact:true}));
  await screenshot('06-filtros-e-limites');
  await minimumFrom(report.chapters.at(-1).start,20);
  chapter('confirmacao','Aprovação exige confirmação explícita','Selecionar uma alternativa não registra aprovação\nCaixa desmarcada → botão bloqueado → confirmação explícita',
    'Selecionar uma opção ou pedir o planejamento não aprova a campanha. A caixa começa desmarcada e o botão permanece desabilitado. O anunciante precisa confirmar a simulação e a alternativa exibidas.');
  await page.locator('#approve-button').click();
  assert(!(await page.locator('#approval-check').isChecked()),'Caixa iniciou marcada indevidamente.');
  assert(!(await page.locator('#confirm-approval').isEnabled()),'Botão de confirmação começou habilitado.');
  report.explicit_confirmation={initial_checkbox:false,initial_button_disabled:true,simulation_id:planned.simulation.simulation_id,alternative_id:chosen.alternativa_id};
  await screenshot('07-confirmacao-obrigatoria');
  await minimumFrom(report.chapters.at(-1).start,15);
  await page.locator('#approval-check').check();
  assert(await page.locator('#confirm-approval').isEnabled(),'Confirmação não habilitou o botão.');
  await screenshot('08-confirmacao-marcada');
  await minimumFrom(report.chapters.at(-1).start,20);
  chapter('registro','Registro pelo agente, através do MCP','registrar_aprovacao → criar_plano → consultar_plano\nSomente um rascunho aprovado com dados simulados',
    'Depois da confirmação explícita, o agente registra a aprovação, cria o rascunho e consulta o plano. A interface acompanha essas chamadas pelo MCP. Não há compra, pagamento ou veiculação.');
  report.confirmation_clicked_at=elapsed();
  await page.locator('#confirm-approval').click();
  const approved=await monitor();
  assert(approved.plan_verification?.verified===true,'Recuperação do SQLite não comprovada.');
  assert(approved.plan?.status==='RASCUNHO_APROVADO','Estado inesperado do plano.');
  assert(approved.plan.alternativa_id===chosen.alternativa_id,'Foi salva outra alternativa.');
  report.after_confirmation=sqlite(planned.simulation.simulation_id,approved.plan.plan_id);
  assert(report.after_confirmation.approvals===1 && report.after_confirmation.plans===1,'Contagem inesperada de aprovações/planos.');
  assert(report.after_confirmation.body?.simulation_id===planned.simulation.simulation_id,'Plano não encontrado no SQLite.');
  const confirmed=approved.events.find(e=>e.type==='approval_confirmed');
  const completed=approved.events.filter(e=>e.type==='tool'&&e.status==='completed');
  assert(completed.filter(e=>['registrar_aprovacao','criar_plano'].includes(e.tool)).every(e=>e.id>confirmed.id),'Escrita anterior à confirmação.');
  assert(new Set(completed.map(e=>e.tool)).size===7,'Não foram comprovadas as sete ferramentas.');
  report.plan_id=approved.plan.plan_id;
  report.simulation_id=planned.simulation.simulation_id;
  report.decision=planned.decision;
  report.alternatives=planned.simulation.alternativas;
  report.verification=approved.plan_verification;
  report.audit=approved.plan.auditoria;
  save('exportacao.json',await jsonRequest('/api/sessions/'+sid+'/export'));
  await minimumFrom(report.chapters.at(-1).start,18);
  chapter('sqlite','Plano registrado e recuperado do SQLite',
    `Leitura MCP e conferência independente do SQLite confirmadas\nPlano: ${report.plan_id}`,
    'O plano recebeu um identificador real e foi recuperado do SQLite. A trilha comprova simulação, aprovação e criação. O mesmo registro foi conferido diretamente no banco, em modo de leitura.');
  await focus(page.locator('.saved-card'));
  await screenshot('09-plano-recuperado-sqlite');
  await minimumFrom(report.chapters.at(-1).start,16);
  chapter('encerramento','Decisões verificáveis, aprovação humana','Ummix MCP • Hackathon AKCIT 2026\nSem compra, pagamento, reserva ou publicação de mídia',
    'Do briefing à decisão verificável: inteligência artificial externa real, ferramentas MCP e confirmação humana. Ummix MCP, protótipo para o Hackathon AKCIT 2026. Todos os dados de mídia são simulados.');
  await focus(page.locator('.saved-card'));
  await minimumFrom(report.chapters.at(-1).start,Math.max(14,180-report.chapters.at(-1).start));
  report.chapters.at(-1).end=elapsed();
  report.recorded_seconds=elapsed();
  report.status='passed';
 } catch(error) {
  report.status='failed'; report.failure=error.stack; console.error(error.stack);
  if(page) await page.screenshot({path:path.join(attempt,'falha-real.png')}).catch(()=>{});
  process.exitCode=1;
 } finally {
  if(context) await context.close();
  if(video) report.raw_video=await video.path();
  if(browser) await browser.close();
  report.finished_at=new Date().toISOString();
  save('resultado.json',report);
  fs.writeFileSync(path.join(output,report.status==='passed'?'gravacao.json':'ultima-falha.json'),JSON.stringify(report,null,2),'utf8');
  console.log('RESULTADO '+report.status+' '+attempt);
 }
})();
