"use strict";
const $ = id => document.getElementById(id);
const statuses = {pending:"待执行",running:"执行中",succeeded:"已完成",failed:"失败",completed:"已完成",rejected:"未通过审校"};
const names = {analyzer:"分析 Agent",writer:"文档 Agent",reviewer:"审校 Agent",orchestrator:"编排器"};
const events = {workflow_started:"工作流开始",node_started:"节点开始",node_completed:"节点完成",node_failed:"节点失败",workflow_completed:"工作流完成",revision_requested:"请求修订",workflow_rejected:"审校拒绝",checkpoint_reused:"复用检查点"};
let selected = null, pollTimer = null, selectedTab = "document", loading = false;
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}
function el(tag, text, cls) { const node = document.createElement(tag); if(text !== undefined)node.textContent=text;if(cls)node.className=cls;return node; }
function time(value) { return new Date(value).toLocaleString("zh-CN", {hour12:false}); }
function notice(text) { $("notice").textContent = text || ""; }
function enableLink(id, url) { $(id).href=url;$(id).classList.remove("disabled");$(id).setAttribute("aria-disabled","false"); }
function setTab(tab) {
  selectedTab = tab;
  document.querySelectorAll(".tab").forEach(button=>{ const active=button.dataset.tab===tab;button.classList.toggle("active",active);button.setAttribute("aria-selected",String(active)); });
  ["document","analysis","review","trace"].forEach(id=>$(id+"-panel").hidden=id!==tab);
}
document.querySelectorAll(".tab").forEach(button=>button.addEventListener("click",()=>setTab(button.dataset.tab)));
function render(state) {
  $("empty").hidden=true;$("result").hidden=false;
  $("run-status").textContent=statuses[state.status]||state.status;
  $("run-status").className="status-pill "+state.status;
  document.querySelectorAll(".node").forEach(node=>{const status=state.nodes[node.dataset.agent]||"pending";node.className="node "+status;node.querySelector(".badge").textContent=statuses[status]||status;});
  $("document-text").textContent=state.outputs.writer?.document || "正在等待文档 Agent 生成草稿…";
  $("analysis-panel").replaceChildren();
  const analysis=state.outputs.analyzer;
  if(analysis){
    $("analysis-panel").append(el("div",`${analysis.line_count} 行代码 · ${analysis.functions.length} 个顶层函数 · ${analysis.classes.length} 个类`,"summary"));
    $("analysis-panel").append(el("pre",JSON.stringify(analysis,null,2)));
  }else $("analysis-panel").textContent="等待分析结果…";
  const panel=$("review-panel");panel.replaceChildren();const review=state.outputs.reviewer;
  if(review){
    panel.append(el("div",`${review.approved?"审校通过":"审校需修订"} · 签名覆盖 ${review.coverage.covered}/${review.coverage.total}`,review.approved?"summary":"check bad"));
    review.checks.forEach(check=>panel.append(el("div",(check.passed?"✓ ":"× ")+check.name,"check "+(check.passed?"good":"bad"))));
    if(review.issues.length){panel.append(el("p","需修复的问题","section-title"));review.issues.forEach(i=>panel.append(el("div",i,"check bad")));}
    if(review.warnings.length){panel.append(el("p","补充提示","section-title"));review.warnings.forEach(w=>panel.append(el("div",w,"check")));}
    panel.append(el("p",review.scope,"hint"));
  }else panel.textContent="等待独立审校…";
  const trace=$("trace-panel");trace.replaceChildren();trace.append(el("p",`Agent 通信 · ${state.messages.length} 条消息`,"section-title"));
  state.messages.forEach(m=>{const box=el("div",undefined,"message");box.append(el("strong",`${names[m.sender]||m.sender} → ${names[m.receiver]||m.receiver}`),el("small",`${time(m.timestamp)} / ${m.kind}`));const details=el("details");details.append(el("summary","查看消息载荷"),el("pre",JSON.stringify(m.payload,null,2)));box.append(details);trace.append(box);});
  trace.append(el("p","执行日志","section-title"));state.logs.forEach(log=>{const row=el("div",undefined,"log");row.append(el("span",new Date(log.time).toLocaleTimeString("zh-CN")),el("span",`${events[log.event]||log.event}${log.agent?" / "+(names[log.agent]||log.agent):""} ${log.detail}`));trace.append(row);});
  notice(state.error);
  $("resume").hidden=state.status!=="failed";
  $("run").disabled=["running","pending"].includes(state.status)||loading;
  if(state.outputs.writer?.document)enableLink("download",`/api/runs/${state.id}/document`);
  else {$("download").classList.add("disabled");$("download").removeAttribute("href");$("download").setAttribute("aria-disabled","true");}
  enableLink("export",`/api/runs/${state.id}/trace`);
  setTab(selectedTab);
}
async function watch(id) {
  selected=id; clearTimeout(pollTimer);
  try { const state=await api(`/api/runs/${id}`);if(selected!==id)return;render(state); if(["pending","running"].includes(state.status))pollTimer=setTimeout(()=>watch(id),1000);else await history(); }
  catch(error){notice(error.message);$("run").disabled=false;}
}
async function history() {
  const list=await api("/api/runs");$("history-list").replaceChildren();
  if(!list.length){$("history-list").textContent="暂无任务，运行一次后会自动保存。";return;}
  list.slice(0,12).forEach(run=>{const button=el("button",undefined,"history-item");button.append(el("span",run.filename,"history-name"),el("span",run.mode==="ai"?"DeepSeek":"离线"),el("span",statuses[run.status]||run.status),el("span",time(run.created_at),"history-time"));button.addEventListener("click",()=>watch(run.id));$("history-list").append(button);});
}
$("run").addEventListener("click",async()=>{loading=true;$("run").disabled=true;notice();try{const result=await api("/api/runs",{filename:$("filename").value.trim(),source:$("source").value,mode:$("mode").value});loading=false;await watch(result.id);await history();}catch(error){notice(error.message);$("run").disabled=false;}finally{loading=false;}});
$("resume").addEventListener("click",async()=>{const id=selected;$("resume").disabled=true;try{await api(`/api/runs/${id}/resume`,{});await watch(id);}catch(error){notice(error.message);}finally{$("resume").disabled=false;}});
$("sample").addEventListener("click",async()=>{try{const data=await api("/api/sample");$("filename").value=data.filename;$("source").value=data.source;notice();}catch(error){notice(error.message);}});
$("file").addEventListener("change",async event=>{const file=event.target.files[0];if(!file)return;if(file.size>256*1024)return notice("文件不能超过 256 KB");$("filename").value=file.name;$("source").value=await file.text();notice();event.target.value="";});
$("refresh").addEventListener("click",()=>history().catch(error=>notice(error.message)));
function modeHelp(){ $("mode-help").textContent=$("mode").value==="ai"?"分析事实与文档草稿会发送给 DeepSeek。密钥在本地读取，界面不显示密钥。":"离线模式使用 AST 与规则生成文档，无需网络或 API Key。"; }
$("mode").addEventListener("change",modeHelp);
async function init(){try{const config=await api("/api/config");$("connection").textContent=config.configured?`DeepSeek 已配置 · ${config.model}`:"本地服务已就绪 · 未配置密钥";$("mode").value=config.default_mode;modeHelp();await history();}catch(error){$("connection").textContent="本地服务未连接";notice(error.message);}}
init();
