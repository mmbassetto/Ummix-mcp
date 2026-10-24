"use strict";
const $ = (selector) => document.querySelector(selector);
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const money = (value) => new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL"}).format(Number(value));
const number = (value) => value == null ? "Indisponível" : new Intl.NumberFormat("pt-BR").format(value);
const dateLabel = (date) => date ? new Date(date + "T12:00:00").toLocaleDateString("pt-BR",{day:"2-digit",month:"2-digit"}) : "";
let session = null, stream = null, ready = false, selected = null, toolEvents = new Map(), startTime = null, displayedCursor = 0, checkingHealth = false, approvalTarget = null;
const emptyMessages = $("#messages").innerHTML;
const emptyPlan = $("#plan-content").innerHTML;

async function api(path, data) {
  const response = await fetch(path, data === undefined ? {headers:{"X-Ummix-Local":"1"}} : {method:"POST",headers:{"Content-Type":"application/json","X-Ummix-Local":"1"},body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Não foi possível completar a solicitação.");
  return result;
}
function showError(message) { $("#chat-error").textContent=message; $("#chat-error").hidden=!message; }
function updateStatus() {
  const busy=!!session?.busy;
  $("#send").disabled=!ready || busy;
  $("#new-chat").disabled=busy;
  $("#working").hidden=!busy;
  $(".results-column").classList.toggle("agent-busy",busy);
  $("#chat-status").textContent=busy?"AO VIVO":session?.plan?"REGISTRADO":"PRONTO";
  if(busy && !startTime) startTime=Date.now();
  if(!busy) startTime=null;
  const stage=session?.plan?4:busy?2:session?.simulation?3:1;
  document.querySelectorAll("[data-step]").forEach(el=>{const n=Number(el.dataset.step);el.classList.toggle("current",n===stage);el.classList.toggle("complete",n<stage);});
}
function renderMessages() {
  const box=$("#messages");
  if (!session?.messages.length) {box.innerHTML=emptyMessages;return;}
  const nearBottom=box.scrollTop+box.clientHeight>box.scrollHeight-100;
  box.innerHTML=session.messages.map(m=>`<div class="message ${m.role==="user"?"user":"assistant"}"><div class="message-label">${m.role==="user"?"VOCÊ · ANUNCIANTE":'<span class="message-icon">✦</span> UMMIX · IA REAL'}</div><div class="message-body">${escapeHTML(m.content).replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").replace(/`([^`]+)`/g,"<code>$1</code>")}</div></div>`).join("");
  if(nearBottom || session.messages.at(-1)?.role==="user") box.scrollTop=box.scrollHeight;
}
function currentAlternative() {return session?.simulation?.alternativas.find(a=>a.alternativa_id===selected) || session?.simulation?.alternativas[0];}
function renderDecision() {
  const decision=session?.decision;
  if(!decision?.verificada || decision.simulation_id!==session.simulation?.simulation_id) return `<p class="justify-note">${escapeHTML(session.decision_error||"Aguardando a recomendação verificável do agente. As alternativas abaixo são saídas do motor MCP.")}</p>`;
  const chosen=session.simulation.alternativas.find(a=>a.alternativa_id===decision.alternativa_id);
  const label=value=>["custo_total","cpm_estimado"].includes(decision.campo_comparado)?money(value):number(value);
  return `<div class="justify-note" data-decision="verified"><strong>Recomendação do agente: ${escapeHTML(chosen.nome)}</strong><p>Critério escolhido pela IA: ${escapeHTML(decision.criterio_label)}.</p><p>${decision.comparacao.map(a=>`${escapeHTML(a.nome)}: <b>${label(a.valor)}</b>`).join(" · ")}${decision.empate?". Há empate neste critério; não comprova superioridade entre as opções.":"."}</p><small>Valores conferidos em simular_plano · ${escapeHTML(decision.simulation_id)}. Critério não comprova alcance ou resultado comercial.</small></div>`;
}
function renderFilters(alt) {
  const labels={atendido_no_seed:"✓ Atendido no seed",nao_atendido:"! Não atendido",nao_comprovado:"? Não comprovado"};
  const filters=(session?.briefing_evidence||[]).filter(f=>f.alternativa_id===alt.alternativa_id);
  if(!filters.length)return "";
  return `<div class="block-heading">Conferência dos filtros <small>${escapeHTML(alt.nome)}</small></div><p class="metrics-note">Comparação com o briefing estruturado enviado ao MCP. Detalhes adicionais do texto livre não são validados automaticamente; público detalhado e resultados reais não são comprovados pelo seed.</p><div class="table-scroll"><table style="white-space:normal"><thead><tr><th>FILTRO</th><th>RESULTADO E EVIDÊNCIA MCP</th></tr></thead><tbody>${filters.map(f=>`<tr><td><strong>${escapeHTML(f.filtro)}</strong><small>${escapeHTML(labels[f.status])}</small></td><td>${escapeHTML(f.detalhe)}<small>Fonte: ${escapeHTML(f.fonte)}</small></td></tr>`).join("")}</tbody></table></div>`;
}
function renderPlan() {
  const sim=session?.simulation, plan=session?.plan;
  const status=$("#plan-status");
  status.className="status-pill";
  if(!sim && !plan){$("#plan-content").innerHTML=emptyPlan;status.textContent="Aguardando briefing";return;}
  const briefing=sim?.briefing || plan.briefing;
  const alt=plan?.alternativa || currentAlternative();
  if(!alt) return;
  const recovered=session.plan_verification?.verified===true && session.plan_verification.plan_id===plan?.plan_id;
  if(plan){status.textContent=recovered?"Recuperado do SQLite":"Aguardando leitura SQLite";if(recovered)status.classList.add("saved");}else{status.textContent=session.busy?"Construindo plano":"Aguardando sua aprovação";status.classList.add("approval");}
  const total=Number(alt.custo_total);
  const radio=alt.alocacao.filter(r=>r.canal==="radio").reduce((s,r)=>s+Number(r.custo_total),0);
  const tv=alt.alocacao.filter(r=>r.canal==="tv").reduce((s,r)=>s+Number(r.custo_total),0);
  const pct=total>0?Math.min(100,Math.max(0,radio/total*100)):0;
  const insertions=alt.alocacao.reduce((s,r)=>s+r.insercoes,0);
  const alternatives=sim?`<div class="block-heading">Alternativas retornadas pelo MCP <small>${sim.alternativas.length} opção(ões) viável(is)</small></div>${renderDecision()}<div class="alternatives" role="group" aria-label="Alternativas de planejamento">${sim.alternativas.map(a=>`<button class="alternative ${a.alternativa_id===alt.alternativa_id?"selected":""}" data-alt="${escapeHTML(a.alternativa_id)}" aria-pressed="${a.alternativa_id===alt.alternativa_id}" ${session.busy||plan?"disabled":""}><span class="alternative-title">${escapeHTML(a.nome)}${session.decision?.alternativa_id===a.alternativa_id?" · Recomendada pela IA":""}<i class="selection-dot"></i></span><strong class="alternative-price">${money(a.custo_total)}</strong><span class="alternative-meta">${a.alocacao.length} veículos · ${number(a.alocacao.reduce((s,r)=>s+r.insercoes,0))} inserções<br>Saldo ${money(a.saldo)} · CPM sintético ${a.cpm_estimado==null?"indisponível":money(a.cpm_estimado)}<br><br>${a.alocacao.map(r=>`${escapeHTML(r.nome)} (${r.canal==="tv"?"TV":"Rádio"}): ${number(r.insercoes)} inserções`).join("<br>")}<br><br>${escapeHTML(a.justificativa)}</span></button>`).join("")}</div>`:"";
  const audit=plan?.auditoria || [];
  const saved=plan?`<div class="saved-card" role="status"><h3>${recovered?"✓ Plano recuperado do SQLite via consultar_plano":"Plano criado; recuperação do SQLite ainda não comprovada"}</h3><p>Plano <code>${escapeHTML(plan.plan_id)}</code></p>${recovered?`<p>Leitura MCP confirmada em ${new Date(session.plan_verification.checked_at).toLocaleTimeString("pt-BR")}.</p>`:""}<p>Estado: ${escapeHTML(plan.status)} · nenhuma contratação realizada</p>${audit.length?`<div class="audit">${audit.map(e=>`<div><b>✓ ${escapeHTML(e.evento.replaceAll("_"," "))}</b><time>${new Date(e.criado_em).toLocaleTimeString("pt-BR")}</time></div>`).join("")}</div>`:"<p>O agente está recuperando a trilha de auditoria…</p>"}</div>`:`<div class="approval-bar"><span>Sua aprovação salva apenas um rascunho.<br>Exige marcar a confirmação na próxima tela.</span><button class="button primary" id="approve-button" ${session.busy?"disabled":""}>Aprovar e registrar rascunho →</button></div>`;
  $("#plan-content").innerHTML=`<div class="plan-data"><div class="brief-summary"><span>⌖ ${escapeHTML(briefing.mercados.join(" · "))}</span><span>◎ ${escapeHTML(briefing.publico)}</span><span>◷ ${dateLabel(briefing.periodo.inicio)} — ${dateLabel(briefing.periodo.fim)}</span><span>BRL ${number(Number(briefing.orcamento))} de orçamento</span></div>${alternatives}<div class="metric-grid"><div class="metric"><label>Impressões sintéticas</label><strong>${number(alt.impressoes_estimadas)}</strong><small>${insertions} inserções · ${alt.alocacao.length} veículos</small></div><div class="metric unavailable"><label>Alcance único</label><strong>Indisponível</strong><small>Sem deduplicação</small></div><div class="metric unavailable"><label>Frequência média</label><strong>Indisponível</strong><small>Depende do alcance único</small></div></div><p class="metrics-note">Dados simulados. Impressões brutas não representam pessoas únicas ou promessa de entrega.</p><div class="block-heading">Distribuição do investimento <small>${money(alt.custo_total)} planejados</small></div><div class="investment-track" aria-label="Distribuição por canal"><span style="width:${pct}%;background:var(--red)"></span><span style="width:${100-pct}%;background:#333"></span></div><div class="channel-legend"><span><i></i>Rádio · ${money(radio)}</span><span class="tv"><i></i>TV · ${money(tv)}</span></div><div class="block-heading">Veículos fictícios selecionados <small>Capacidade validada pelo motor</small></div><div class="table-scroll"><table><thead><tr><th>VEÍCULO / PRAÇA</th><th>CANAL</th><th>INSERÇÕES</th><th>INVESTIMENTO</th></tr></thead><tbody>${alt.alocacao.map(r=>`<tr><td><strong>${escapeHTML(r.nome)}</strong><small>${escapeHTML(r.mercado)} · ${escapeHTML(r.faixa_horaria)}</small></td><td><span class="channel-tag ${r.canal==="tv"?"tv":""}">${r.canal==="tv"?"TV":"RÁDIO"}</span></td><td>${r.insercoes}<small>de ${r.capacidade_periodo} disponíveis</small></td><td>${money(r.custo_total)}<small>${number(r.impressoes_estimadas)} impr. sintéticas</small></td></tr>`).join("")}</tbody></table></div><p class="justify-note">${escapeHTML(alt.justificativa)}</p>${(sim?.alertas||plan?.alertas||[]).map(a=>`<p class="justify-note">⚑ ${escapeHTML(a)}</p>`).join("")}<details class="justify-note"><summary>Premissas e limites dos dados</summary>${(sim?.premissas||plan?.premissas||[]).map(p=>`<p>${escapeHTML(p)}</p>`).join("")}</details><div class="simulation-ref">SIMULAÇÃO <code>${escapeHTML(sim?.simulation_id||plan.simulation_id)}</code> · ALTERNATIVA <code>${escapeHTML(alt.alternativa_id)}</code></div>${renderFilters(alt)}${saved}</div>`;
}
const toolHints={listar_mercados:"Consultando praças cadastradas no inventário simulado",listar_segmentos:"Verificando públicos disponíveis por praça",consultar_inventario:"Lendo veículos fictícios, preços e capacidades",simular_plano:"Calculando alternativas com o motor determinístico",registrar_aprovacao:"Vinculando sua confirmação à alternativa selecionada",criar_plano:"Gravando o rascunho aprovado no SQLite",consultar_plano:"Recuperando o plano e a trilha de auditoria"};
function renderTools() {
  const tools=[...toolEvents.values()];$("#tool-count").textContent=`${tools.length} chamada${tools.length===1?"":"s"}`;
  if(!tools.length)return;
  const expanded=new Set([...document.querySelectorAll(".tool-event[open]")].map(e=>e.dataset.key));
  $("#activity-content").innerHTML=tools.map(e=>`<details class="tool-event ${e.status}" data-key="${escapeHTML(e.key)}" ${expanded.has(e.key)?"open":""}><summary><span class="tool-badge">${e.status==="running"?"◌":e.status==="error"?"!":"✓"}</span><code>${escapeHTML(e.tool)}</code><span class="tool-status">${e.status==="running"?"executando":e.status==="error"?"verificar erro":"concluído"}</span><time>${new Date(e.timestamp).toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit",second:"2-digit"})} ⌄</time></summary><p class="tool-hint">${escapeHTML(toolHints[e.tool]||"Ferramenta MCP")}</p><pre>${escapeHTML(JSON.stringify({argumentos:e.arguments,resposta:e.response,erro:e.error},null,2))}</pre></details>`).join("");
  const box=$("#activity-content");box.scrollTop=box.scrollHeight;
}
function onEvent(e) {
  displayedCursor=e.id;
  if(e.type==="message"){session.messages.push(e.message);renderMessages();}
  if(e.type==="status") $("#working-text").textContent=e.message;
  if(e.type==="tool"){toolEvents.set(e.key,e);renderTools();if(e.status==="running")$("#working-text").textContent=toolHints[e.tool]||"Executando ferramenta MCP…";}
  if(e.type==="simulation"){approvalTarget=null;session.simulation=e.simulation;session.plan=null;session.plan_verification=null;session.decision=null;session.briefing_evidence=[];selected=e.simulation.alternativas[0]?.alternativa_id;renderPlan();}
  if(e.type==="plan"){session.plan=e.plan;session.plan_verification=e.plan_verification;renderPlan();}
  if(e.type==="decision"){session.decision=e.decision;session.decision_error=e.error;renderPlan();}
  if(e.type==="failure"){ready=false;$("#connection").className="connection offline";$("#connection").querySelector("strong").textContent="Agente indisponível";showError(e.message);}
  if(e.type==="done"){session={...session,...e.snapshot};renderMessages();renderPlan();updateStatus();checkHealth();}
}
async function loadSession(id) {
  session=await api("/api/sessions/"+id);displayedCursor=session.cursor||0;toolEvents=new Map();
  (session.events||[]).filter(e=>e.type==="tool").forEach(e=>toolEvents.set(e.key,e));
  selected=session.simulation?.alternativas[0]?.alternativa_id;
  renderMessages();$("#messages").scrollTop=$("#messages").scrollHeight;renderPlan();renderTools();updateStatus();showError(session.last_error||"");connectEvents();
}
function connectEvents(){if(stream)stream.close();stream=new EventSource(`/api/sessions/${session.id}/events?after=${displayedCursor}`);stream.onmessage=e=>{try{onEvent(JSON.parse(e.data));}catch(error){showError("Não foi possível renderizar um evento do agente. Recarregue para recuperar o estado.");}};stream.onerror=()=>{if(session?.busy)$("#working-text").textContent="Reconectando ao fluxo de eventos…";};$("#export-link").href=`/api/sessions/${session.id}/export`;$("#compact-export").href=`/api/sessions/${session.id}/export`;}
async function createSession(){if(stream)stream.close();toolEvents.clear();$("#activity-content").innerHTML='<div class="activity-empty"><span>◌</span><p>Aguardando as primeiras chamadas MCP.<small>Eventos reais, sem animação de chamadas fictícias.</small></p></div>';approvalTarget=null;session=await api("/api/sessions",{});localStorage.setItem("ummix-session",session.id);displayedCursor=0;selected=null;renderMessages();renderPlan();renderTools();updateStatus();showError("");connectEvents();}
async function checkHealth(force=false){if(checkingHealth)return;checkingHealth=true;try{ready=false;$("#connection").className="connection";$("#connection").querySelector("strong").textContent="Verificando agente";$("#connection").title="Verificando executável, autenticação, resposta do modelo e ferramenta MCP real…";updateStatus();const health=await api("/api/health"+(force?"?refresh=1":""));ready=health.ready===true&&health.model_verified===true&&health.mcp_verified===true;$("#connection").className="connection "+(ready?"ready":"offline");$("#connection").querySelector("strong").textContent=ready?"Agente disponível":"Agente indisponível";$("#connection").querySelector("small").textContent="Codex CLI · LLM externo";$("#connection").title=health.message+(health.checked_at?" Verificado em "+new Date(health.checked_at).toLocaleTimeString("pt-BR")+".":"");if(!ready)showError(health.message);else if(!session?.last_error)showError("");}catch(error){ready=false;$("#connection").className="connection offline";$("#connection").querySelector("strong").textContent="Agente indisponível";showError("Não foi possível verificar a conexão real. Confira o terminal e tente Verificar conexão.");}finally{checkingHealth=false;updateStatus();}}
$("#chat-form").addEventListener("submit",async e=>{e.preventDefault();const field=$("#prompt"),text=field.value.trim();if(!text||!session||session.busy||!ready)return;showError("");session.busy=true;updateStatus();try{await api(`/api/sessions/${session.id}/messages`,{message:text});field.value="";field.style.height="";}catch(error){session.busy=false;updateStatus();showError(error.message);}});
$("#prompt").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){e.preventDefault();$("#chat-form").requestSubmit();}});
$("#prompt").addEventListener("input",e=>{e.target.style.height="auto";e.target.style.height=Math.min(e.target.scrollHeight,130)+"px";});
document.addEventListener("click",e=>{const example=e.target.closest("[data-example]");if(example){$("#prompt").value=example.dataset.example==="complete"?"Quero divulgar um produto fictício para adultos em Goiânia, Anápolis e Rio Verde. Tenho R$ 5.000 para 7 dias de campanha, em rádio e TV, começando amanhã. Compare duas alternativas e aguarde minha aprovação.":"Quero divulgar minha loja em Goiânia. Você pode me ajudar a planejar uma campanha de rádio e TV?";$("#prompt").focus();}const alternative=e.target.closest("[data-alt]");if(alternative){selected=alternative.dataset.alt;renderPlan();}if(e.target.closest("#approve-button")){const alt=currentAlternative(),sim=session.simulation;approvalTarget={simulation_id:sim.simulation_id,alternativa_id:alt.alternativa_id};$("#approval-summary").innerHTML=`<div class="approval-detail">${escapeHTML(alt.nome)}<strong>${money(alt.custo_total)}</strong><small>${escapeHTML(sim.briefing.mercados.join(" · "))} · ${dateLabel(sim.briefing.periodo.inicio)} a ${dateLabel(sim.briefing.periodo.fim)}</small><small>Simulação: ${escapeHTML(sim.simulation_id)}</small><small>Alternativa: ${escapeHTML(alt.alternativa_id)}</small></div>`;$("#approval-check").checked=false;$("#confirm-approval").disabled=true;$("#approval-dialog").showModal();}});
$("#approval-check").addEventListener("change",e=>$("#confirm-approval").disabled=!e.target.checked);
$("#confirm-approval").addEventListener("click",async()=>{if(!$("#approval-check").checked||session.busy||!approvalTarget)return;if(approvalTarget.simulation_id!==session.simulation?.simulation_id||approvalTarget.alternativa_id!==currentAlternative()?.alternativa_id){$("#approval-dialog").close();approvalTarget=null;showError("O planejamento mudou. Confira e confirme novamente.");return;}$("#confirm-approval").disabled=true;try{await api(`/api/sessions/${session.id}/approve`,{...approvalTarget,confirmacao_explicita:true});session.busy=true;updateStatus();renderPlan();$("#approval-dialog").close();}catch(error){$("#approval-dialog").close();showError(error.message);}});
$("#new-chat").addEventListener("click",()=>createSession().catch(e=>showError(e.message)));
$("#check-connection").addEventListener("click",()=>checkHealth(true));
$("#help-button").addEventListener("click",()=>$("#help-dialog").showModal());
$("#compact-help").addEventListener("click",()=>$("#help-dialog").showModal());
$("#close-help").addEventListener("click",()=>$("#help-dialog").close());
setInterval(()=>{$("#elapsed").textContent=startTime?Math.floor((Date.now()-startTime)/1000)+"s":"";},1000);
setInterval(()=>{if(session&&!session.busy)checkHealth();},30000);
(async()=>{try{const saved=localStorage.getItem("ummix-session");if(saved){try{await loadSession(saved);}catch{await createSession();}}else await createSession();await checkHealth();}catch(e){showError(e.message);}})();
