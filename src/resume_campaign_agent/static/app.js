window.__EXTENSION_ID__ = "dgoeflcdbfknpgpdehcfjijnkmifkgde";

(function() {
    const OLD_IDS = ["ncennffkjdiamlpmcbajkmaiiiddgioo", "invalid"];
    const originalSendMessage = chrome?.runtime?.sendMessage?.bind(chrome.runtime);
    if (originalSendMessage) {
        chrome.runtime.sendMessage = function(extensionId, ...args) {
            if (OLD_IDS.includes(extensionId)) {
                console.warn(`[RCA] 拦截到旧扩展 ID: ${extensionId}，替换为正确 ID`);
                extensionId = window.__EXTENSION_ID__;
            }
            return originalSendMessage(extensionId, ...args);
        };
    }
})();
const $ = (selector) => document.querySelector(selector);

let currentDiscovery = null;
let currentSessionId = localStorage.getItem("lastSessionId") || null;
let currentReview = null;
let currentOptimization = null;
const careerState = { sessionId: null, dossier: null, versionId: null, applicationId: null, interviewKit: null };
let toastTimer = null;
const pendingTakeovers = new Map();

function splitValues(input) { return String(input || "").split(/[,，\n]/).map((x) => x.trim()).filter(Boolean); }
function value(id) { return $(`#${id}`).value.trim(); }
function optional(id) { return value(id) || null; }
function setField(id, fieldValue) { const el = $(`#${id}`); if (el) el.value = fieldValue ?? ""; }

function collectResume() {
  const education = value("school") ? [{
    school:value("school"), college:optional("college"), degree:value("degree"), major:value("major"), minor:optional("minor"),
    graduation_year:Number(value("graduationYear")), location:optional("educationLocation"), start_date:optional("educationStartDate"), end_date:optional("educationEndDate"),
    education_type:optional("educationType"), gpa:value("gpa") ? Number(value("gpa")) : null, gpa_scale:value("gpaScale") ? Number(value("gpaScale")) : null,
    rank:optional("rank"), core_courses:splitValues(value("coreCourses")), thesis:optional("thesis")
  }] : [];
  const work = value("company") ? [{ company:value("company"), title:value("jobTitle"), experience_type:value("experienceType"), department:optional("department"),
    location:optional("workLocation"), start_date:value("startDate"), end_date:optional("endDate"), responsibilities:optional("responsibilities"),
    highlights:splitValues(value("highlights")), leaving_reason:optional("leavingReason") }] : [];
  const projects = value("projectName") ? [{ name:value("projectName"), role:optional("projectRole"), start_date:optional("projectStartDate"), end_date:optional("projectEndDate"),
    description:value("projectDescription"), highlights:splitValues(value("projectHighlights")), skills:splitValues(value("projectSkills")) }] : [];
  const campus = value("campusOrganization") ? [{ organization:value("campusOrganization"), role:value("campusRole"), description:value("campusDescription") }] : [];
  const certificates = value("certificateName") ? [{ name:value("certificateName"), issuer:optional("certificateIssuer"), score:optional("certificateScore") }] : [];
  const languageDetails = value("language") ? [{ language:value("language"), proficiency:value("languageProficiency"), test_name:optional("languageTest"), score:optional("languageScore") }] : [];
  const awards = value("awardName") ? [{ name:value("awardName") }] : [];
  return {
    full_name:optional("fullName"), preferred_name:optional("preferredName"), city:optional("city"), professional_headline:optional("professionalHeadline"),
    email:optional("email"), phone:optional("phone"), wechat:optional("wechat"), job_seeking_status:optional("jobSeekingStatus"),
    target_roles:splitValues(value("targetRoles")), target_industries:splitValues(value("targetIndustries")),
    target_employer_types:splitValues(value("targetEmployerTypes")), base_locations:splitValues(value("baseLocations")),
    employment_types:splitValues(value("employmentTypes")), years_experience:Number(value("yearsExperience")||0), available_date:optional("availableDate"),
    expected_salary:optional("expectedSalary"), relocation_preference:optional("relocationPreference"), skills:splitValues(value("skills")), summary:optional("summary"),
    education, work_experience:work, projects, campus_experience:campus, certificates, language_details:languageDetails, awards,
    languages:languageDetails.map((x)=>x.language), hobbies:splitValues(value("hobbies")), self_evaluation:optional("selfEvaluation"), additional_information:optional("additionalInformation")
  };
}

function localMissing(resume) {
  const rules = [
    ["full_name","姓名",resume.full_name],["email","邮箱",resume.email],["phone","电话",resume.phone],["city","当前城市",resume.city],
    ["target_roles","目标岗位 / 专业方向",resume.target_roles.length],["base_locations","意向 Base 城市",resume.base_locations.length],
    ["skills","专业技能",resume.skills.length >= 3],["summary","职业摘要",resume.summary],
    ["education","教育经历",resume.education.length],["education.major","专业",resume.education[0]?.major],["education.end_date","毕业日期",resume.education[0]?.end_date]
  ];
  return rules.filter(([, , ok])=>!ok).map(([field,label])=>({field,label,reason:"通用简历或中国网申常用必填项"}));
}

async function requestJson(url, options={}) {
  const response = await fetch(url,{...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});
  const body = await response.json().catch(()=>({}));
  if(!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : `请求失败（${response.status}）`);
  return body;
}

async function checkHealth(){
  try { const h=await requestJson("/api/health"); $("#healthDot").classList.add("is-online");
    $("#healthText").textContent=h.deployment_mode==="production"?"Agent 在线 · 正式逐岗位投递":"Agent 在线 · 测试夹具模式";
    $("#modelText").textContent=h.model||"LLM 排序未配置"; $("#sourceText").textContent=h.enterprise_search||"Exa AI + 官方入口";
  } catch { $("#healthText").textContent="Agent 未连接"; }
}

function setLoading(on){
  $("#runCampaignButton").disabled=on;
  if(on){ $("#queueSummary").textContent="正在按 Base 并行搜索中国企业…";
    $("#enterpriseList").innerHTML='<div class="loading-skeleton"></div><div class="loading-skeleton"></div><div class="loading-skeleton"></div>';
    $("#destinationList").innerHTML='<div class="loading-skeleton"></div><div class="loading-skeleton"></div>';
  }
}

async function runDiscovery(){
  setLoading(true);
  try {
    const resume=collectResume(); renderMissing(localMissing(resume));
    const session=await requestJson("/api/sessions",{method:"POST",body:JSON.stringify({resume,preferred_locations:resume.base_locations,remote_preference:"any"})});
    currentSessionId=session.id;
    localStorage.setItem("lastSessionId", session.id);
    const result=await requestJson("/api/discovery/enterprises",{method:"POST",body:JSON.stringify({
      session_id:session.id,base_locations:resume.base_locations,professional_directions:resume.target_roles,industries:resume.target_industries,
      employer_types:resume.target_employer_types,company_keywords:splitValues(value("companyKeywords")),limit:20,ai_ranking:true
    })});
    currentDiscovery=result; renderDiscovery(result);
    showToast(`找到 ${result.enterprises.length} 家中国企业线索；0 份已发送`);
  } catch(error){ renderError(error.message); showToast(error.message); }
  finally{ setLoading(false); }
}

function renderMissing(missing){
  $("#missingCount").textContent=missing.length?`${missing.length} 项待补`:"核心字段完整";
  $("#missingList").innerHTML=missing.length?missing.map(x=>`<span class="missing-pill" title="${escapeHtml(x.reason)}">${escapeHtml(x.label)}</span>`).join(""):'<span class="complete-pill">核心通用字段通过；门户专属字段见下方矩阵</span>';
}

function reviewTarget(){ return value("reviewTargetRole") || splitValues(value("targetRoles"))[0] || null; }

async function createReviewSession(){
  const resume=collectResume();
  renderMissing(localMissing(resume));
  return requestJson("/api/sessions",{method:"POST",body:JSON.stringify({resume,preferred_locations:resume.base_locations,remote_preference:"any"})});
}

function setReviewBusy(button,on,label){
  if(!button.dataset.label) button.dataset.label=button.textContent;
  button.disabled=on;
  button.textContent=on?label:button.dataset.label;
}

function renderResumeReview(review){
  currentReview=review;
  $("#reviewGrade").textContent=`${review.grade} / ${review.overall_score}`;
  $("#reviewGrade").classList.add("is-reviewed");
  const dimensions=review.dimensions.map(item=>`<div class="dimension-row" title="${escapeHtml(item.summary)}"><span>${escapeHtml(item.label)}</span><div class="dimension-rule"><i style="--dimension-score:${item.score}%"></i></div><strong>${item.score}</strong></div>`).join("");
  const strengths=review.strengths.length?`<div class="review-subsection"><h3>已有优势</h3><ul>${review.strengths.map(item=>`<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`:"";
  const questions=review.evidence_questions.length?`<div class="review-subsection"><h3>需要本人补证</h3><ul>${review.evidence_questions.map(item=>`<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`:"";
  $("#reviewScoreboard").innerHTML=`<div class="review-score-head"><div class="review-score-number"><strong>${review.overall_score}</strong><span>GRADE ${review.grade}</span></div><div><h3>${escapeHtml(review.target_role||"通用质量审核")}</h3><p>${review.ai_used?"AI 语义审核 + 确定性规则":"确定性规则审核"} · 原简历未修改</p></div></div><div class="dimension-ledger">${dimensions}</div>${strengths}${questions}`;
  $("#editorialLedger").innerHTML=`<div class="optimization-header"><h3>审核批注</h3><span>${review.findings.length} ITEMS · NO AUTO WRITE</span></div>${review.findings.length?review.findings.map(item=>`<article class="finding-card"><div class="finding-heading"><strong>${escapeHtml(item.title)}</strong><span class="finding-severity ${item.severity}">${{critical:"优先修正",warning:"需要复核",suggestion:"优化建议"}[item.severity]}</span></div><p>${escapeHtml(item.observation)}</p><p class="finding-action">建议：${escapeHtml(item.recommendation)}</p>${item.question_to_user?`<p>待补证：${escapeHtml(item.question_to_user)}</p>`:""}</article>`).join(""):'<div class="score-sheet-placeholder"><span>REVIEW / CLEAR</span><p>没有发现需要立即处理的问题。</p></div>'}`;
}

async function reviewResume(){
  const button=$("#reviewResumeButton");
  setReviewBusy(button,true,"正在审核事实与证据…");
  try{
    const session=await createReviewSession();
    const review=await requestJson("/api/resume/review",{method:"POST",body:JSON.stringify({
      session_id:session.id,target_role:reviewTarget(),target_job_description:optional("reviewJobDescription"),use_ai:true
    })});
    renderResumeReview(review);
    showToast(`简历审核完成：${review.grade} 级，${review.findings.length} 条批注；原文未修改`);
    $("#resumeReviewDesk").scrollIntoView({behavior:"smooth",block:"start"});
  }catch(error){ showToast(error.message); }
  finally{ setReviewBusy(button,false,""); }
}

function renderOptimization(result){
  currentOptimization=result;
  const cards=result.suggestions.map((item,index)=>`<article class="revision-card"><div class="revision-meta"><code>${escapeHtml(item.field_path)}</code><span>${escapeHtml(item.change_type)}</span></div><div class="revision-compare"><div><b>原文</b><p>${escapeHtml(item.original_text||"（当前为空）")}</p></div><div><b>建议稿</b><p>${escapeHtml(item.suggested_text)}</p></div></div><p class="revision-reason">${escapeHtml(item.rationale)}</p><button class="copy-revision" type="button" data-revision-index="${index}">复制建议稿</button></article>`).join("");
  $("#editorialLedger").innerHTML=`<div class="optimization-header"><h3>待确认修订</h3><span>${result.suggestions.length} ITEMS · ${result.ai_used?"AI + RULES":"RULES"}</span></div>${cards||'<div class="score-sheet-placeholder"><span>EDIT / CLEAR</span><p>当前没有可安全生成的优化文本；请先补充审核提出的事实证据。</p></div>'}`;
}

async function optimizeResume(){
  const button=$("#optimizeResumeButton");
  setReviewBusy(button,true,"正在生成对照建议…");
  try{
    const session=await createReviewSession();
    const result=await requestJson("/api/resume/optimize",{method:"POST",body:JSON.stringify({
      session_id:session.id,target_role:reviewTarget(),target_job_description:optional("reviewJobDescription"),max_suggestions:6,use_ai:true
    })});
    renderOptimization(result);
    showToast(`已生成 ${result.suggestions.length} 条待确认建议；没有写回原简历`);
    $("#resumeReviewDesk").scrollIntoView({behavior:"smooth",block:"start"});
  }catch(error){ showToast(error.message); }
  finally{ setReviewBusy(button,false,""); }
}

async function copyRevision(index){
  const text=currentOptimization?.suggestions?.[index]?.suggested_text;
  if(!text)return;
  try{
    if(navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
    else{
      const area=document.createElement("textarea"); area.value=text; area.style.position="fixed"; area.style.opacity="0";
      document.body.appendChild(area); area.select(); document.execCommand("copy"); area.remove();
    }
    showToast("建议稿已复制；采用前请核对每项事实");
  }catch{ showToast("浏览器未允许复制，请手动选中建议稿"); }
}

function renderDiscovery(d){
  $("#sourceMetric").textContent=d.source_count; $("#officialMetric").textContent=d.live_or_hub_entry_count; $("#enterpriseMetric").textContent=d.enterprises.length;
  $("#queueCount").textContent=d.enterprises.length; $("#queueSummary").textContent=`${d.live_or_hub_entry_count} 家有官网入口 · ${d.ai_ranking_used?"LLM 已参与排序":"规则排序"}`;
  const bases=splitValues(value("baseLocations"));
  $("#destinationList").innerHTML=`<div class="base-card"><span class="base-label">BASE COMPASS</span><div class="base-chips">${bases.map((b,i)=>`<span>${String(i+1).padStart(2,"0")} · ${escapeHtml(b)}</span>`).join("")||"<span>未指定</span>"}</div></div>
    <div class="query-ledger"><strong>AI 查询计划</strong>${d.query_plan.map((q,i)=>`<p><span>Q${i+1}</span>${escapeHtml(q)}</p>`).join("")}</div>
    ${d.warnings.length?`<div class="source-warning">部分来源降级：${escapeHtml(d.warnings.join("；"))}</div>`:""}`;
  if(!d.enterprises.length){ $("#enterpriseList").innerHTML='<div class="empty-state"><h3>没有找到可核验线索</h3><p>可以放宽企业类型或增加 Base 城市后重试。</p></div>'; return; }
  $("#enterpriseList").innerHTML=d.enterprises.map((lead,index)=>enterpriseCard(lead,index)).join("");
  d.enterprises.forEach((lead,index)=>$(`#lead-${index}`).addEventListener("click",()=>startAiTakeover(lead,index)));
}

function enterpriseCard(lead,index){
  const authority={official_known:"已知官方",likely_official:"疑似官方",unverified:"待核验"}[lead.source_authority];
  const readiness={direct_official:"官网可检索",official_hub:"公告大厅",needs_channel_verification:"入口待核验"}[lead.application_readiness];
  const selected=chooseBestChannel(lead);
  return `<article class="enterprise-card"><div class="company-monogram">${escapeHtml(lead.company.slice(0,2))}</div><div class="enterprise-main">
    <div class="company-line"><h3>${String(index+1).padStart(2,"0")} · ${escapeHtml(lead.company)}</h3><span class="authority ${lead.source_authority}">${authority}</span><span class="entry-readiness ${lead.application_readiness}">${readiness}</span></div>
    <p class="job-title">${escapeHtml(lead.source_title)}</p><p class="lead-rationale">${escapeHtml(lead.rationale)}</p>
    <div class="enterprise-meta"><span>Base ${escapeHtml(lead.bases.slice(0,4).join(" / ")||"待核对")}</span><span>匹配分 ${lead.score.toFixed(0)}</span><span>${selected?escapeHtml(selected.label):"暂无可投官网"}</span>${lead.recommended_roles.slice(0,2).map(x=>`<span class="skill-token">${escapeHtml(x)}</span>`).join("")}</div>
  </div><div class="draft-actions"><span class="draft-status ${selected?"is-ready":""}">${selected?"AI VERIFY":"BLOCKED"}</span><button class="takeover-button" id="lead-${index}" type="button" ${selected?"":"disabled"}>${selected?"AI 核岗 · 接管官网":"暂无可投渠道"}</button></div></article>`;
}

function chooseBestChannel(lead){
  const availabilityRank={openings_live:30,entry_hub:20,check_required:10,seasonal_closed:-100};
  const typeRank={designated_application_system:9,social_portal:8,campus_portal:7,internship_portal:6,official_career_home:5,official_announcement:1};
  const score=channel=>(availabilityRank[channel.availability]||0)+(typeRank[channel.channel_type]||0);
  return [...(lead.application_channels||[])].filter(channel=>channel.availability!=="seasonal_closed")
    .sort((a,b)=>score(b)-score(a))[0]||null;
}

function isSyntheticResume(resume){
  return String(resume.full_name||"").includes("合成") || String(resume.email||"").endsWith("@example.com");
}

function startAiTakeover(lead,index){
  const channel=chooseBestChannel(lead);
  if(!channel||!currentSessionId){showToast("请先运行企业搜索并生成本轮简历会话");return;}
  const target=new URL(channel.url,location.href);
  const resume=collectResume();
  const simulationOnly=isSyntheticResume(resume)&&!["127.0.0.1","localhost"].includes(target.hostname);
  const button=$(`#lead-${index}`);
  button.disabled=true; button.textContent=simulationOnly?"正在启动官网安全预演…":"正在交给浏览器副驾驶…";
  const requestId=crypto.randomUUID();
  pendingTakeovers.set(requestId,{button,simulationOnly,timer:setTimeout(()=>{
    pendingTakeovers.delete(requestId); button.disabled=false; button.textContent="AI 核岗 · 接管官网";
        showToast("未检测到浏览器副驾驶。请在浏览器右上角点击扩展图标，确认副驾驶已加载后重试。");
  },4000)});
  window.postMessage({
    source:"resume-campaign-app",
    type:"RC_AI_TAKEOVER_REQUEST",
    requestId,
    payload:{
      sessionId:currentSessionId,
      company:lead.company,
      channelLabel:channel.label,
      url:target.href,
      targetRoles:lead.recommended_roles.slice(0,5),
      bases:lead.bases.slice(0,8),
      simulationOnly
    }
  },location.origin);
}

window.addEventListener("message",event=>{
  if(event.source!==window||event.origin!==location.origin||event.data?.type!=="RC_AI_TAKEOVER_ACK")return;
  const pending=pendingTakeovers.get(event.data.requestId); if(!pending)return;
  clearTimeout(pending.timer); pendingTakeovers.delete(event.data.requestId);
  if(event.data.ok){
    pending.button.textContent=pending.simulationOnly?"AI 官网预演中":"AI 已接管";
    showToast(pending.simulationOnly
      ?"合成档案已进入官网安全预演：只核岗并前往登录/申请页，不发送验证码、不填表、不提交"
      :"招聘网站已打开。请您先登录并进入要投递的岗位，等到出现需要填写简历信息的页面时，再点击浏览器右上角的扩展图标打开副驾驶。");
  }else{
    pending.button.disabled=false; pending.button.textContent="AI 核岗 · 接管官网";
    showToast(event.data.error||"浏览器副驾驶未能接管");
  }
});

async function loadPortalTemplate(){
  const button=$("#portalActionButton"); button.disabled=true; button.textContent="正在载入…";
  try { const t=await requestJson("/api/templates/boc-campus-2026-reference"); renderPortalTemplate(t); showToast(`已载入 ${t.fields.length} 个字段要求`); }
  catch(error){ $("#batchResults").innerHTML=`<div class="batch-placeholder">${escapeHtml(error.message)}</div>`; }
  finally{ button.disabled=false; button.textContent="刷新中国银行字段要求"; }
}

function renderPortalTemplate(t){
  const groups=Object.groupBy?Object.groupBy(t.fields,x=>x.section):t.fields.reduce((a,x)=>((a[x.section]||=[]).push(x),a),{});
  const sensitive=t.fields.filter(x=>x.sensitive).length, portalOnly=t.fields.filter(x=>x.storage_policy!=="master_resume").length;
  $("#portalEvidence").innerHTML=`<div><strong>${escapeHtml(t.name)}</strong><span>${t.fields.length} 字段 · ${sensitive} 高敏 · ${portalOnly} 个不进入主简历</span></div>
    <div class="evidence-links">${t.source_urls.map((u,i)=>`<a href="${escapeHtml(u)}" target="_blank" rel="noreferrer">证据 ${i+1} ↗</a>`).join("")}</div><p>${escapeHtml(t.privacy_notice)}</p>`;
  $("#batchResults").innerHTML=Object.entries(groups).map(([section,fields])=>`<article class="portal-group"><div class="portal-group-title"><h3>${escapeHtml(section)}</h3><span>${fields.length} 项</span></div>
    <div class="portal-fields">${fields.map(f=>`<div class="portal-field ${f.sensitive?"is-sensitive":""}"><span>${escapeHtml(f.label)}</span><div>${f.required?'<b>必填</b>':'<i>选填</i>'}${f.sensitive?'<em>敏感</em>':''}<small>${policyLabel(f.storage_policy)}</small></div></div>`).join("")}</div></article>`).join("");
}

function policyLabel(policy){return {master_resume:"主简历",portal_only:"仅门户",prepare_only:"只准备"}[policy]||policy;}
function renderError(message){ $("#enterpriseList").innerHTML=`<div class="empty-state"><h3>这轮没有完成</h3><p>${escapeHtml(message)}</p></div>`; $("#destinationList").innerHTML='<div class="empty-state compact-empty"><p>保留当前简历，稍后可重试。</p></div>'; $("#queueSummary").textContent="搜索失败"; }
function resetDiscovery(){ currentDiscovery=null; currentSessionId=null; ["sourceMetric","officialMetric","enterpriseMetric"].forEach(id=>$(`#${id}`).textContent="—"); $("#queueCount").textContent="0"; $("#queueSummary").textContent="还没有 AI 投递任务"; $("#missingCount").textContent="待运行"; $("#missingList").innerHTML='<span class="muted-copy">搜索后显示缺失项</span>'; $("#destinationList").innerHTML='<div class="empty-state compact-empty"><span class="empty-rule"></span><p>Base 城市与 AI 查询计划会在这里留下证据。</p></div>'; $("#enterpriseList").innerHTML='<div class="empty-state"><span class="folder-tab">QUEUE / 00</span><h3>等待企业检索</h3><p>系统会选择官方渠道，并在逐岗位确认后接管投递。</p></div>'; }

function resetReviewDesk(){
  currentReview=null; currentOptimization=null;
  $("#reviewGrade").textContent="待审核"; $("#reviewGrade").classList.remove("is-reviewed");
  $("#reviewScoreboard").innerHTML='<div class="score-sheet-placeholder"><span>REVIEW / 00</span><p>运行审核后，这里会显示六维评分、问题证据和待确认修订。</p></div>';
  $("#editorialLedger").innerHTML='<div class="score-sheet-placeholder"><span>EDIT / 00</span><p>优化建议会保留原文对照，不会写回简历模板。</p></div>';
}
function jumpPortal(){ $("#portalMatrix").scrollIntoView({behavior:"smooth"}); if(!$("#portalEvidence").textContent.trim()) loadPortalTemplate(); }
function showToast(message){ clearTimeout(toastTimer); $("#toast").textContent=message; $("#toast").classList.add("is-visible"); toastTimer=setTimeout(()=>$("#toast").classList.remove("is-visible"),3800); }
function escapeHtml(input){return String(input??"").replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));}

function careerInput(){
  return {
    company:value("careerCompany"), title:value("careerTitle"), description:value("careerJD"),
    location:optional("careerLocation"), url:optional("careerUrl"), deadline:optional("careerDeadline")
  };
}

async function ensureCareerSession(force=false){
  if(careerState.sessionId&&!force)return careerState.sessionId;
  const resume=collectResume(); renderMissing(localMissing(resume));
  const session=await requestJson("/api/sessions",{method:"POST",body:JSON.stringify({resume,preferred_locations:resume.base_locations,remote_preference:"any"})});
  careerState.sessionId=session.id;
  if(force){careerState.versionId=null;careerState.applicationId=null;}
  return session.id;
}

function setCareerBusy(button,on,busyLabel){
  if(!button.dataset.label)button.dataset.label=button.textContent.trim();
  button.disabled=on; if(on)button.textContent=busyLabel; else button.textContent=button.dataset.label;
}

function renderCareerDossier(dossier,ranking){
  careerState.dossier=dossier;
  const actionLabel={apply:"建议投递",verify:"补证后投递",deprioritize:"降低优先级",block:"停止并核验"}[dossier.recommended_action];
  const requirements=dossier.requirements.slice(0,12).map(item=>`<div class="requirement-row ${item.matched?"is-matched":""}"><b>${escapeHtml(item.kind)}</b><i></i><div>${escapeHtml(item.text)}<small>${item.matched?`证据：${escapeHtml(item.evidence_paths.join(" / "))}`:escapeHtml(item.gap_reason||"待补证")}</small></div></div>`).join("");
  const ranked=ranking?.ranked_jobs?.[0];
  const risks=dossier.risk_signals.length?dossier.risk_signals.map(item=>escapeHtml(item.title)).join("；"):"未发现明显招聘诈骗信号";
  $("#careerDossierBody").innerHTML=`<div class="dossier-score-line"><div class="match-seal"><strong>${dossier.match_score}</strong><span>MATCH</span></div><div><h4>${escapeHtml(dossier.company)} · ${escapeHtml(dossier.title)}</h4><p>${escapeHtml(dossier.rationale)}</p><p>投递价值 ${ranked?.score??"—"} · Base ${ranked?.base_score??"—"} · 渠道 ${ranked?.channel_score??"—"} · ${actionLabel}</p></div></div><div class="requirement-ledger">${requirements}</div><div class="risk-strip ${dossier.recommended_action==="block"?"is-blocked":""}">${risks}</div>`;
  $("#careerOSStamp").textContent=`${actionLabel} / ${dossier.match_score}`; $("#careerOSStamp").classList.add("is-ready");
}

async function buildCareerDossier(){
  const button=$("#buildCareerDossierButton"); setCareerBusy(button,true,"正在建立证据链…");
  try{
    const sessionId=await ensureCareerSession(true); const input=careerInput();
    const dossier=await requestJson("/api/career/job-dossier",{method:"POST",body:JSON.stringify({session_id:sessionId,...input})});
    const ranking=await requestJson("/api/career/jobs/rank",{method:"POST",body:JSON.stringify({session_id:sessionId,jobs:[{id:"current-job",...input,source:"official",application_minutes:20}]})});
    renderCareerDossier(dossier,ranking); showToast(`岗位作战包完成：匹配 ${dossier.match_score}，${dossier.hard_gaps.length} 条硬性条件待核验`);
  }catch(error){$("#careerDossierBody").innerHTML=`<div class="career-alert">${escapeHtml(error.message)}</div>`;showToast(error.message);}
  finally{setCareerBusy(button,false,"");}
}

function renderCareerVersion(version,audit){
  const changes=version.changes.length?version.changes.map(item=>`<div class="version-change"><code>${escapeHtml(item.field_path)}</code><p>${escapeHtml(item.reason)}</p><p>${escapeHtml(item.before||"（空）")} → ${escapeHtml(item.after||"（空）")}</p></div>`).join(""):'<div class="version-change"><p>当前岗位与母版顺序已一致，没有为了制造差异而改写内容。</p></div>';
  const auditText=audit.findings.map(item=>item.message).join("；");
  $("#careerVersionBody").innerHTML=`<div class="version-card"><div class="version-head"><strong>${escapeHtml(version.label)}</strong><span>${audit.passed?"FACTS STABLE":"REVIEW REQUIRED"}</span></div>${changes}<div class="audit-pass">${escapeHtml(auditText)}</div></div>`;
}

async function createCareerVersion(){
  const button=$("#createCareerVersionButton");setCareerBusy(button,true,"正在重排已确认事实…");
  try{
    const sessionId=await ensureCareerSession();const input=careerInput();
    const version=await requestJson("/api/career/resume-versions",{method:"POST",body:JSON.stringify({session_id:sessionId,target_company:input.company,target_title:input.title,job_description:input.description})});
    const audit=await requestJson(`/api/career/resume-versions/${encodeURIComponent(version.id)}/audit?session_id=${encodeURIComponent(sessionId)}`,{method:"POST"});
    careerState.versionId=version.id;renderCareerVersion(version,audit);showToast(`岗位版本已生成：${version.changes.length} 项顺序调整，事实母版未修改`);
  }catch(error){$("#careerVersionBody").innerHTML=`<div class="career-alert">${escapeHtml(error.message)}</div>`;showToast(error.message);}
  finally{setCareerBusy(button,false,"");}
}

function renderPortalPreflight(result,checkpoint=null){
  const checks=result.checklist.map(item=>`<div class="preflight-check">${escapeHtml(item)}</div>`).join("");
  const blockers=[...result.missing_required_fields,...result.blocked_sensitive_fields,...result.attachment_checks];
  $("#careerPortalBody").innerHTML=`<div class="version-head"><strong>${escapeHtml(result.adapter.name)}</strong><span>${result.ready?"READY FOR CONFIRMATION":"BLOCKED"}</span></div><div class="preflight-checks">${checks}</div>${blockers.length?`<div class="career-alert">阻塞项：${escapeHtml(blockers.join("；"))}</div>`:'<div class="audit-pass">字段与附件检查通过；仍需用户逐岗位确认后才可继续官网提交。</div>'}${checkpoint?`<div class="audit-pass">断点 ${escapeHtml(checkpoint.step)} 已保存，24 小时内可从 ${checkpoint.pending_fields.length} 个待填字段继续。</div>`:""}`;
}

async function runPortalPreflight(){
  const button=$("#runPortalPreflightButton");setCareerBusy(button,true,"正在扫描提交闸门…");
  try{
    const sessionId=await ensureCareerSession();const input=careerInput();
    const result=await requestJson("/api/career/portal-preflight",{method:"POST",body:JSON.stringify({session_id:sessionId,application_id:careerState.applicationId,url:input.url,detected_fields:splitValues(value("portalDetectedFields")),available_attachments:splitValues(value("portalAttachments")),user_confirmed:false})});
    renderPortalPreflight(result);showToast(result.ready?"官网预检完成；等待逐岗位确认":"官网预检发现阻塞项");
  }catch(error){$("#careerPortalBody").innerHTML=`<div class="career-alert">${escapeHtml(error.message)}</div>`;showToast(error.message);}
  finally{setCareerBusy(button,false,"");}
}

async function saveCareerCheckpoint(){
  const button=$("#saveCheckpointButton");setCareerBusy(button,true,"正在保存断点…");
  try{
    if(!careerState.applicationId)await trackCareerApplication();
    const fields=splitValues(value("portalDetectedFields"));const completed=fields.filter(item=>!["resume","附件"].includes(item.toLowerCase()));const pending=fields.filter(item=>!completed.includes(item));
    const checkpoint=await requestJson("/api/career/checkpoints",{method:"POST",body:JSON.stringify({session_id:careerState.sessionId,application_id:careerState.applicationId,url:value("careerUrl"),completed_fields:completed,pending_fields:pending,step:"portal-form"})});
    const result=await requestJson("/api/career/portal-preflight",{method:"POST",body:JSON.stringify({session_id:careerState.sessionId,application_id:careerState.applicationId,url:value("careerUrl"),detected_fields:fields,available_attachments:splitValues(value("portalAttachments")),user_confirmed:false})});
    renderPortalPreflight(result,checkpoint);showToast("填写断点已保存 24 小时");
  }catch(error){showToast(error.message);}
  finally{setCareerBusy(button,false,"");}
}

const careerStatusLabels={saved:"已收藏",preparing:"准备中",ready:"待投递",applied:"已投递",assessment:"测评",interview:"面试",offer:"Offer",rejected:"未通过",withdrawn:"已撤回"};

async function refreshCareerApplications(){
  if(!careerState.sessionId)return;
  const [apps,reminders,funnel]=await Promise.all([
    requestJson(`/api/career/applications?session_id=${encodeURIComponent(careerState.sessionId)}`),
    requestJson(`/api/career/reminders?session_id=${encodeURIComponent(careerState.sessionId)}`),
    requestJson(`/api/career/funnel?session_id=${encodeURIComponent(careerState.sessionId)}`)
  ]);
  const cards=apps.map(app=>`<div class="application-card"><div class="application-head"><strong>${escapeHtml(app.company)} · ${escapeHtml(app.title)}</strong><span>${careerStatusLabels[app.status]}</span></div><p>${app.resume_version_id?`岗位版本 ${escapeHtml(app.resume_version_id)}`:"尚未绑定岗位版本"} · ${app.deadline?`截止 ${escapeHtml(app.deadline)}`:"无截止日期"}</p><div class="application-statuses">${["saved","preparing","ready","applied","assessment","interview","offer","rejected"].map(status=>`<button type="button" data-app-id="${app.id}" data-app-status="${status}" class="${app.status===status?"is-active":""}">${careerStatusLabels[status]}</button>`).join("")}</div></div>`).join("");
  const max=Math.max(1,...funnel.stages.map(item=>item.count));
  const funnelHtml=funnel.stages.filter(item=>item.count).map(item=>`<div class="funnel-line"><span>${careerStatusLabels[item.status]}</span><div class="funnel-rule"><i style="--funnel-width:${item.count/max*100}%"></i></div><b>${item.count}</b></div>`).join("");
  $("#careerApplicationBody").innerHTML=`<div class="application-list">${cards||'<div class="career-placeholder">尚未加入投递任务。</div>'}</div>${reminders.length?`<div class="audit-pass">最近提醒：${escapeHtml(reminders[0].title)} · ${new Date(reminders[0].due_at).toLocaleString("zh-CN")}</div>`:""}<div>${funnelHtml}</div><div class="audit-pass">响应率 ${funnel.response_rate}% · 面试率 ${funnel.interview_rate}% · Offer 率 ${funnel.offer_rate}%<br>${escapeHtml(funnel.recommendations.join("；"))}</div>`;
}

async function trackCareerApplication(){
  const button=$("#trackCareerApplicationButton");setCareerBusy(button,true,"正在登记时间线…");
  try{
    const sessionId=await ensureCareerSession();const input=careerInput();
    const app=await requestJson("/api/career/applications",{method:"POST",body:JSON.stringify({session_id:sessionId,company:input.company,title:input.title,url:input.url||"",location:input.location||"",status:"ready",resume_version_id:careerState.versionId,job_description:input.description,deadline:input.deadline})});
    careerState.applicationId=app.id;await refreshCareerApplications();showToast("岗位已加入投递看板；尚未向官网发送");
  }catch(error){showToast(error.message);}
  finally{setCareerBusy(button,false,"");}
}

async function updateCareerApplication(applicationId,status){
  await requestJson(`/api/career/applications/${encodeURIComponent(applicationId)}?session_id=${encodeURIComponent(careerState.sessionId)}`,{method:"PATCH",body:JSON.stringify({status,note:"由求职驾驶舱更新"})});
  await refreshCareerApplications();showToast(`投递状态已更新为：${careerStatusLabels[status]}`);
}

function renderInterviewKit(kit){
  careerState.interviewKit=kit;
  const questions=kit.resume_questions.map(item=>`<div class="interview-card"><b>${escapeHtml(item.question)}</b><p>${escapeHtml(item.why_asked)}</p><p>回答框架：${escapeHtml(item.answer_framework)}</p></div>`).join("");
  $("#careerInterviewBody").innerHTML=`<div class="audit-pass">自我介绍：${escapeHtml(kit.self_intro_outline.join(" → "))}</div><div class="interview-question-list">${questions}</div><div class="risk-strip">反问：${escapeHtml(kit.questions_to_ask.join("；"))}</div>${kit.risk_warnings.length?`<div class="career-alert">${escapeHtml(kit.risk_warnings.join("；"))}</div>`:""}`;
}

async function prepareInterview(){
  const button=$("#prepareInterviewButton");setCareerBusy(button,true,"正在生成追问题库…");
  try{const sessionId=await ensureCareerSession();const input=careerInput();const kit=await requestJson("/api/career/interview-kit",{method:"POST",body:JSON.stringify({session_id:sessionId,company:input.company,title:input.title,job_description:input.description})});renderInterviewKit(kit);showToast(`面试准备包完成：${kit.resume_questions.length} 个证据追问`);}catch(error){showToast(error.message);}finally{setCareerBusy(button,false,"");}
}

async function simulateInterview(){
  const button=$("#simulateInterviewButton");setCareerBusy(button,true,"正在核对回答与事实…");
  try{const sessionId=await ensureCareerSession();const result=await requestJson("/api/career/interview-simulate",{method:"POST",body:JSON.stringify({session_id:sessionId,question:value("interviewQuestion"),answer:value("interviewAnswer")})});$("#careerInterviewBody").innerHTML=`<div class="interview-score-head"><div><h4>回答审核</h4><p>结构 ${result.structure_score} · 证据 ${result.evidence_score} · 一致性 ${result.consistency_score}</p></div><strong>${result.overall_score}</strong></div><div class="audit-pass">优势：${escapeHtml(result.strengths.join("；")||"尚未形成稳定优势")}</div>${result.improvements.length?`<div class="career-alert">${escapeHtml(result.improvements.join("；"))}</div>`:""}<div class="risk-strip">追问：${escapeHtml(result.follow_up_question)}</div>`;showToast(`回答审核完成：${result.overall_score} 分`);}catch(error){showToast(error.message);}finally{setCareerBusy(button,false,"");}
}

async function refreshCareerEvidence(){
  if(!careerState.sessionId)return;
  const [items,vault]=await Promise.all([requestJson(`/api/career/evidence?session_id=${encodeURIComponent(careerState.sessionId)}`),requestJson(`/api/career/vault?session_id=${encodeURIComponent(careerState.sessionId)}`)]);
  const cards=items.map(item=>`<div class="evidence-card"><div class="evidence-head"><strong>${escapeHtml(item.label)}</strong><span>${item.verified_by_user?"USER VERIFIED":"PENDING"}</span></div><ul>${item.facts.map(fact=>`<li>${escapeHtml(fact)}</li>`).join("")}</ul></div>`).join("");
  $("#careerEvidenceBody").innerHTML=`<div class="evidence-list">${cards||'<div class="career-placeholder">尚未登记可引用证据。</div>'}</div><div class="audit-pass">保险箱：${vault.encrypted_items} 个加密字段（${escapeHtml(vault.fields.join(" / ")||"空")}）；列表接口不返回明文。</div>`;
}

async function addCareerEvidence(){
  const button=$("#addEvidenceButton");setCareerBusy(button,true,"正在登记证据…");
  try{const sessionId=await ensureCareerSession();await requestJson("/api/career/evidence",{method:"POST",body:JSON.stringify({session_id:sessionId,category:"project",label:value("evidenceLabel"),source_reference:"local://user-confirmed-evidence",facts:splitValues(value("evidenceFacts")),verified_by_user:true})});await refreshCareerEvidence();showToast("证据已登记；后续优化和面试可引用这些事实");}catch(error){showToast(error.message);}finally{setCareerBusy(button,false,"");}
}

async function saveCareerVault(){
  const button=$("#saveVaultButton");
  if(location.protocol!=="https:"&&!['localhost','127.0.0.1'].includes(location.hostname)){showToast("当前是公网 HTTP，已禁止录入敏感信息；请先配置 HTTPS 与账号认证");return;}
  setCareerBusy(button,true,"正在加密…");
  try{const sessionId=await ensureCareerSession();const field=$("#vaultField").value;const secret=value("vaultValue");if(!secret)throw new Error("请先填写字段值");await requestJson("/api/career/vault",{method:"POST",body:JSON.stringify({session_id:sessionId,values:{[field]:secret}})});$("#vaultValue").value="";await refreshCareerEvidence();showToast("敏感字段已加密；明文不会出现在列表或模型上下文");}catch(error){showToast(error.message);}finally{setCareerBusy(button,false,"");}
}

function resetCareerOS(){
  Object.assign(careerState,{sessionId:null,dossier:null,versionId:null,applicationId:null,interviewKit:null});
  $("#careerOSStamp").textContent="等待岗位";$("#careerOSStamp").classList.remove("is-ready");
}

$("#runCampaignButton").addEventListener("click",runDiscovery);
$("#reviewResumeButton").addEventListener("click",reviewResume);
$("#optimizeResumeButton").addEventListener("click",optimizeResume);
$("#buildCareerDossierButton").addEventListener("click",buildCareerDossier);
$("#createCareerVersionButton").addEventListener("click",createCareerVersion);
$("#trackCareerApplicationButton").addEventListener("click",trackCareerApplication);
$("#prepareInterviewButton").addEventListener("click",prepareInterview);
$("#runPortalPreflightButton").addEventListener("click",runPortalPreflight);
$("#saveCheckpointButton").addEventListener("click",saveCareerCheckpoint);
$("#simulateInterviewButton").addEventListener("click",simulateInterview);
$("#addEvidenceButton").addEventListener("click",addCareerEvidence);
$("#saveVaultButton").addEventListener("click",saveCareerVault);
$("#careerApplicationBody").addEventListener("click",event=>{const button=event.target.closest("[data-app-status]");if(button)updateCareerApplication(button.dataset.appId,button.dataset.appStatus).catch(error=>showToast(error.message));});
$("#editorialLedger").addEventListener("click",event=>{ const button=event.target.closest("[data-revision-index]"); if(button)copyRevision(Number(button.dataset.revisionIndex)); });
$("#resumeForm").addEventListener("input",()=>{ if(currentReview||currentOptimization){ $("#reviewGrade").textContent="待重新审核"; $("#reviewGrade").classList.remove("is-reviewed"); } resetCareerOS(); });
$("#portalActionButton").addEventListener("click",loadPortalTemplate);
$("#portalLinkButton").addEventListener("click",jumpPortal); $("#portalJumpButton").addEventListener("click",jumpPortal);
checkHealth(); loadPortalTemplate();
const careerDeadline=new Date();careerDeadline.setDate(careerDeadline.getDate()+14);$("#careerDeadline").value=careerDeadline.toISOString().slice(0,10);

async function restoreLastSession() {
  const sessionId = localStorage.getItem("lastSessionId");
  if (!sessionId) return;

  try {
    const session = await requestJson(`/api/sessions/${sessionId}`);
    const resume = session.resume;

    setField("fullName", resume.full_name);
    setField("email", resume.email);
    setField("phone", resume.phone);
    setField("city", resume.city);
    setField("targetRoles", (resume.target_roles || []).join(","));
    setField("baseLocations", (resume.base_locations || []).join(","));
    setField("skills", (resume.skills || []).join(","));
    setField("summary", resume.summary);

    currentSessionId = sessionId;
    showToast("已恢复上次简历会话", "success");
  } catch (error) {
    // 会话不存在时静默忽略
  }
}

setTimeout(restoreLastSession, 500);