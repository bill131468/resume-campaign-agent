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
const AppUtils = globalThis.ResumeCampaignAppUtils;
if (!AppUtils) throw new Error("ResumeCampaignAppUtils 未加载");

let currentDiscovery = null;
let currentSessionId = localStorage.getItem("lastSessionId") || null;
let currentReview = null;
let currentOptimization = null;
const careerState = { sessionId: null, dossier: null, versionId: null, applicationId: null, interviewKit: null, applications: [] };
let toastTimer = null;
const pendingTakeovers = new Map();
let profileDirty = false;

function splitValues(input) { return String(input || "").split(/[,，\n]/).map((x) => x.trim()).filter(Boolean); }
function value(id) { return $(`#${id}`).value.trim(); }
function optional(id) { return value(id) || null; }
function setField(id, fieldValue) { const el = $(`#${id}`); if (el) el.value = fieldValue ?? ""; }

function entryValue(entry, name) {
  return entry.querySelector(`[data-entry-field="${name}"]`)?.value.trim() || "";
}

function workEntryMarkup(work={}, index) {
  return `<article class="repeatable-entry" data-work-entry>
    <div class="repeatable-heading"><strong>第 ${index + 1} 段经历</strong><button type="button" data-remove-entry="work" aria-label="删除第 ${index + 1} 段工作经历">删除</button></div>
    <div class="field-grid two">
      <label>企业 / 机构 <span class="field-hint">（本段必填）</span><input id="work-${index}-company" data-entry-field="company" value="${escapeHtml(work.company || "")}"></label>
      <label>岗位 <span class="field-hint">（本段必填）</span><input id="work-${index}-jobTitle" data-entry-field="jobTitle" value="${escapeHtml(work.title || "")}"></label>
      <label>经历类型<select id="work-${index}-experienceType" data-entry-field="experienceType"><option value="internship">实习</option><option value="full_time">全职</option><option value="part_time">兼职</option><option value="research">科研</option></select></label>
      <label>部门<input id="work-${index}-department" data-entry-field="department" value="${escapeHtml(work.department || "")}"></label>
      <label>所在地<input id="work-${index}-workLocation" data-entry-field="workLocation" value="${escapeHtml(work.location || "")}"></label>
      <label>开始日期 <span class="field-hint">（本段必填）</span><input id="work-${index}-startDate" data-entry-field="startDate" type="date" value="${escapeHtml(work.start_date || "")}"></label>
      <label>结束日期<input id="work-${index}-endDate" data-entry-field="endDate" type="date" value="${escapeHtml(work.end_date || "")}"></label>
    </div>
    <label>主要职责<textarea id="work-${index}-responsibilities" data-entry-field="responsibilities" rows="3">${escapeHtml(work.responsibilities || "")}</textarea></label>
    <label>成果摘要<textarea id="work-${index}-highlights" data-entry-field="highlights" rows="3" placeholder="每行一条，只写可以核实的成果">${escapeHtml((work.highlights || []).join("\n"))}</textarea></label>
    <label>离职 / 结束原因<input id="work-${index}-leavingReason" data-entry-field="leavingReason" value="${escapeHtml(work.leaving_reason || "")}"></label>
  </article>`;
}

function projectEntryMarkup(project={}, index) {
  return `<article class="repeatable-entry" data-project-entry>
    <div class="repeatable-heading"><strong>第 ${index + 1} 段项目</strong><button type="button" data-remove-entry="project" aria-label="删除第 ${index + 1} 段项目经历">删除</button></div>
    <div class="field-grid two">
      <label>项目名称 <span class="field-hint">（本段必填）</span><input id="project-${index}-projectName" data-entry-field="projectName" value="${escapeHtml(project.name || "")}"></label>
      <label>承担角色<input id="project-${index}-projectRole" data-entry-field="projectRole" value="${escapeHtml(project.role || "")}"></label>
      <label>开始日期<input id="project-${index}-projectStartDate" data-entry-field="projectStartDate" type="date" value="${escapeHtml(project.start_date || "")}"></label>
      <label>结束日期<input id="project-${index}-projectEndDate" data-entry-field="projectEndDate" type="date" value="${escapeHtml(project.end_date || "")}"></label>
    </div>
    <label>项目说明 <span class="field-hint">（本段必填，至少 10 字）</span><textarea id="project-${index}-projectDescription" data-entry-field="projectDescription" rows="3">${escapeHtml(project.description || "")}</textarea></label>
    <label>成果 / 产出<textarea id="project-${index}-projectHighlights" data-entry-field="projectHighlights" rows="2">${escapeHtml((project.highlights || []).join("\n"))}</textarea></label>
    <label>相关能力<input id="project-${index}-projectSkills" data-entry-field="projectSkills" value="${escapeHtml((project.skills || []).join(", "))}"></label>
  </article>`;
}

function renderWorkEntries(items=[{}]) {
  const entries = items.length ? items : [{}];
  $("#workEntries").innerHTML = entries.map(workEntryMarkup).join("");
  entries.forEach((item, index) => {
    const select = $(`#work-${index}-experienceType`);
    if (select) select.value = item.experience_type || "internship";
  });
}

function renderProjectEntries(items=[{}]) {
  const entries = items.length ? items : [{}];
  $("#projectEntries").innerHTML = entries.map(projectEntryMarkup).join("");
}

function collectWorkEntries(includeEmpty=false) {
  const items=[...document.querySelectorAll("[data-work-entry]")].map((entry) => ({
    company:entryValue(entry,"company"), title:entryValue(entry,"jobTitle"), experience_type:entryValue(entry,"experienceType") || "internship",
    department:entryValue(entry,"department") || null, location:entryValue(entry,"workLocation") || null,
    start_date:entryValue(entry,"startDate"), end_date:entryValue(entry,"endDate") || null,
    responsibilities:entryValue(entry,"responsibilities") || null, highlights:splitValues(entryValue(entry,"highlights")),
    leaving_reason:entryValue(entry,"leavingReason") || null,
  }));
  return includeEmpty ? items : items.filter((item) => item.company || item.title || item.start_date || item.responsibilities || item.highlights.length);
}

function collectProjectEntries(includeEmpty=false) {
  const items=[...document.querySelectorAll("[data-project-entry]")].map((entry) => ({
    name:entryValue(entry,"projectName"), role:entryValue(entry,"projectRole") || null,
    start_date:entryValue(entry,"projectStartDate") || null, end_date:entryValue(entry,"projectEndDate") || null,
    description:entryValue(entry,"projectDescription"), highlights:splitValues(entryValue(entry,"projectHighlights")),
    skills:splitValues(entryValue(entry,"projectSkills")),
  }));
  return includeEmpty ? items : items.filter((item) => item.name || item.role || item.description || item.highlights.length || item.skills.length);
}

async function loadAccount() {
  try {
    const status = await requestJson("/api/auth/status");
    if (!status.enabled) {
      $("#accountPhone").hidden = true;
      $("#logoutButton").hidden = true;
      return;
    }
    const account = await requestJson("/api/auth/me");
    const label = `手机尾号 ${account.phoneLast4}`;
    $("#accountPhone").textContent = label;
    $("#accountPhone").hidden = false;
  } catch {
    window.location.assign("/login");
  }
}

async function logoutAccount() {
  $("#logoutButton").disabled = true;
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } finally {
    localStorage.removeItem("lastSessionId");
    window.location.assign("/login");
  }
}

function collectResume() {
  const education = value("school") ? [{
    school:value("school"), college:optional("college"), degree:value("degree"), major:value("major"), minor:optional("minor"),
    graduation_year:Number(value("graduationYear")), location:optional("educationLocation"), start_date:optional("educationStartDate"), end_date:optional("educationEndDate"),
    education_type:optional("educationType"), gpa:value("gpa") ? Number(value("gpa")) : null, gpa_scale:value("gpaScale") ? Number(value("gpaScale")) : null,
    rank:optional("rank"), core_courses:splitValues(value("coreCourses")), thesis:optional("thesis")
  }] : [];
  const work = collectWorkEntries();
  const projects = collectProjectEntries();
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
  return AppUtils.missingResumeFields(resume);
}

function renderCompletenessNotice(resume) {
  const missing = localMissing(resume);
  const noticeEl = $("#completenessNotice");
  if (!noticeEl) return;

  if (missing.length === 0) {
    noticeEl.textContent = "✅ 简历信息完整，自动填表效果最佳";
    noticeEl.className = "completeness-notice is-complete";
  } else {
    noticeEl.textContent = `⚠️ 简历还有 ${missing.length} 项未填，建议补齐后再投递，自动填表效果更好`;
    noticeEl.className = "completeness-notice is-incomplete";
  }
}

function updateProfileProgress(resume=collectResume()) {
  const missing = localMissing(resume);
  renderMissing(missing);
  renderCompletenessNotice(resume);
  $("#profileProgress").textContent = missing.length
    ? `还差 ${missing.length} 项核心内容`
    : "核心内容已完整，可以处理岗位";
  return missing;
}

function setProfileSaveState(state, message) {
  const status = $("#profileSaveStatus");
  status.className = `file-chip save-state-${state}`;
  status.textContent = message;
  $("#railResumeStatus").textContent = message;
  $("#railResume").classList.toggle("is-complete", state === "saved");
}

function profileFieldIds(missing) {
  const ids={full_name:"fullName",email:"email",phone:"phone",city:"city",target_roles:"targetRoles",base_locations:"baseLocations",skills:"skills",summary:"summary",education:"school","education.major":"major","education.degree":"degree","education.graduation_year":"graduationYear",work_experience:"work-0-company"};
  return missing.map((item)=>ids[item.field]).filter(Boolean);
}

async function ensureProfileSession({notify=false,requireComplete=false}={}) {
  const resume = collectResume();
  const missing=updateProfileProgress(resume);
  if(requireComplete && missing.length){
    markValidationFields(profileFieldIds(missing));
    throw new Error(`请先补齐 ${missing.length} 项核心内容，再继续`);
  }
  setProfileSaveState("saving", "正在保存");
  const payload = {resume, preferred_locations:resume.base_locations, remote_preference:"any"};
  let session;
  try {
    session = currentSessionId
      ? await requestJson(`/api/sessions/${encodeURIComponent(currentSessionId)}/resume`, {method:"PATCH", body:JSON.stringify(resume)})
      : await requestJson("/api/sessions", {method:"POST", body:JSON.stringify(payload)});
  } catch (error) {
    setProfileSaveState("error", "保存失败");
    throw error;
  }
  currentSessionId = session.id;
  careerState.sessionId = session.id;
  localStorage.setItem("lastSessionId", session.id);
  profileDirty = false;
  setProfileSaveState("saved", `已保存 ${new Date(session.updated_at).toLocaleTimeString("zh-CN", {hour:"2-digit", minute:"2-digit"})}`);
  if (notify) showToast("档案已保存");
  return session;
}

async function saveProfile(continueToJob=false) {
  const buttons = [$("#saveProfileButton"), $("#saveProfileTopButton")];
  buttons.forEach((button) => { button.disabled = true; });
  try {
    await ensureProfileSession({notify:true, requireComplete:continueToJob});
    if (continueToJob) goToWorkflow("careerOS", 2);
  } catch (error) {
    showToast(error.message);
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

function clearValidationMarks() {
  document.querySelectorAll('[aria-invalid="true"]').forEach((element) => {
    element.removeAttribute("aria-invalid");
    element.classList.remove("is-invalid");
  });
}

function markValidationFields(fieldIds) {
  const fields = fieldIds.map((id) => $(`#${id}`)).filter(Boolean);
  fields.forEach((field) => {
    field.setAttribute("aria-invalid", "true");
    field.classList.add("is-invalid");
    const section = field.closest("details");
    if (section) section.open = true;
  });
  if (!fields.length) return;
  fields[0].scrollIntoView({ behavior: "smooth", block: "center" });
  fields[0].focus({ preventScroll: true });
}

async function requestJson(url, options={}) {
  if ((options.method || "GET").toUpperCase() !== "GET") clearValidationMarks();
  const response = await fetch(url,{...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});
  const body = await response.json().catch(()=>({}));
  if(!response.ok) {
    const description = AppUtils.describeApiError(response.status, body);
    markValidationFields(description.fieldIds);
    const error = new Error(description.message);
    error.status = response.status;
    error.details = description.details;
    throw error;
  }
  return body;
}

async function checkHealth(){
  try { const h=await requestJson("/api/health"); $("#healthDot").classList.add("is-online");
    $("#healthText").textContent=h.deployment_mode==="production"?"服务正常 · 每个岗位单独确认":"服务正常 · 测试模式";
    $("#modelText").textContent=h.model?"岗位排序已启用":"使用基础排序"; $("#sourceText").textContent=h.enterprise_search?"企业搜索已启用":"企业官网与公开招聘入口";
  } catch { $("#healthText").textContent="服务暂时未连接"; }
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
    const session=await ensureProfileSession({requireComplete:true});
    const resume=session.resume;
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
  return ensureProfileSession();
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
  $("#reviewScoreboard").innerHTML=`<div class="review-score-head"><div class="review-score-number"><strong>${review.overall_score}</strong><span>${review.grade} 级</span></div><div><h3>${escapeHtml(review.target_role||"通用简历检查")}</h3><p>${review.ai_used?"结合岗位语义和填写规则检查":"按填写规则检查"} · 原档案未修改</p></div></div><div class="dimension-ledger">${dimensions}</div>${strengths}${questions}`;
  $("#editorialLedger").innerHTML=`<div class="optimization-header"><h3>检查结果</h3><span>${review.findings.length} 条 · 不会自动改写</span></div>${review.findings.length?review.findings.map(item=>`<article class="finding-card"><div class="finding-heading"><strong>${escapeHtml(item.title)}</strong><span class="finding-severity ${item.severity}">${{critical:"优先修正",warning:"需要复核",suggestion:"修改建议"}[item.severity]}</span></div><p>${escapeHtml(item.observation)}</p><p class="finding-action">建议：${escapeHtml(item.recommendation)}</p>${item.question_to_user?`<p>待补充：${escapeHtml(item.question_to_user)}</p>`:""}</article>`).join(""):'<div class="score-sheet-placeholder"><span>检查完成</span><p>没有发现需要立即处理的问题。</p></div>'}`;
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
  $("#editorialLedger").innerHTML=`<div class="optimization-header"><h3>待确认的修改</h3><span>${result.suggestions.length} 条</span></div>${cards||'<div class="score-sheet-placeholder"><span>暂无建议</span><p>请先补充检查中提到的事实和证据。</p></div>'}`;
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
  $("#destinationList").innerHTML=`<div class="base-card"><span class="base-label">搜索城市</span><div class="base-chips">${bases.map((b,i)=>`<span>${String(i+1).padStart(2,"0")} · ${escapeHtml(b)}</span>`).join("")||"<span>未指定</span>"}</div></div>
    <div class="query-ledger"><strong>本轮搜索词</strong>${d.query_plan.map((q,i)=>`<p><span>${i+1}</span>${escapeHtml(q)}</p>`).join("")}</div>
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
  </div><div class="draft-actions"><span class="draft-status ${selected?"is-ready":""}">${selected?"可继续":"暂不可用"}</span><button class="takeover-button" id="lead-${index}" type="button" ${selected?"":"disabled"}>${selected?"核对岗位并打开官网":"暂无可用入口"}</button></div></article>`;
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
    pendingTakeovers.delete(requestId); button.disabled=false; button.textContent="核对岗位并打开官网";
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
    pending.button.textContent=pending.simulationOnly?"正在预览官网流程":"官网已打开";
    showToast(pending.simulationOnly
      ?"合成档案已进入官网安全预演：只核岗并前往登录/申请页，不发送验证码、不填表、不提交"
      :"招聘网站已打开。请您先登录并进入要投递的岗位，等到出现需要填写简历信息的页面时，再点击浏览器右上角的扩展图标打开副驾驶。");
  }else{
    pending.button.disabled=false; pending.button.textContent="核对岗位并打开官网";
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
function resetDiscovery(){ currentDiscovery=null; ["sourceMetric","officialMetric","enterpriseMetric"].forEach(id=>$(`#${id}`).textContent="—"); $("#queueCount").textContent="0"; $("#queueSummary").textContent="还没有企业搜索结果"; $("#destinationList").innerHTML='<div class="empty-state compact-empty"><span class="empty-rule"></span><p>搜索范围和来源会显示在这里。</p></div>'; $("#enterpriseList").innerHTML='<div class="empty-state"><span class="folder-tab">尚无结果</span><h3>还没有搜索企业</h3><p>保存档案后，可以按目标岗位和城市查找企业招聘入口。</p></div>'; }

function resetReviewDesk(){
  currentReview=null; currentOptimization=null;
  $("#reviewGrade").textContent="待审核"; $("#reviewGrade").classList.remove("is-reviewed");
  $("#reviewScoreboard").innerHTML='<div class="score-sheet-placeholder"><span>等待检查</span><p>检查后，这里会显示完整度、相关性和需要补充的事实。</p></div>';
  $("#editorialLedger").innerHTML='<div class="score-sheet-placeholder"><span>等待建议</span><p>修改建议会保留原文对照，不会直接写回档案。</p></div>';
}
function jumpPortal(){ $("#portalMatrix").scrollIntoView({behavior:"smooth"}); if(!$("#portalEvidence").textContent.trim()) loadPortalTemplate(); }
function showToast(message){ clearTimeout(toastTimer); $("#toast").textContent=message; $("#toast").classList.add("is-visible"); toastTimer=setTimeout(()=>$("#toast").classList.remove("is-visible"),3800); }
function escapeHtml(input){return String(input??"").replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));}

function goToWorkflow(targetId, stage=null) {
  const target = document.getElementById(targetId);
  if (!target) return;
  document.querySelectorAll(".rail-step").forEach((step) => step.classList.remove("is-active"));
  const active = stage === 2 ? $("#railJob") : stage === 3 ? $("#railBoard") : $("#railResume");
  active?.classList.add("is-active");
  target.scrollIntoView({behavior:"smooth", block:"start"});
  const first = target.querySelector("input, textarea, select, button");
  setTimeout(() => first?.focus({preventScroll:true}), 350);
}

function careerInput(){
  return {
    company:value("careerCompany"), title:value("careerTitle"), description:value("careerJD"),
    location:optional("careerLocation"), url:optional("careerUrl"), deadline:optional("careerDeadline")
  };
}

async function ensureCareerSession(force=false){
  if(careerState.sessionId&&!force&&!profileDirty)return careerState.sessionId;
  const session=await ensureProfileSession({requireComplete:true});
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
  $("#careerDossierBody").innerHTML=`<div class="dossier-score-line"><div class="match-seal"><strong>${dossier.match_score}</strong><span>匹配度</span></div><div><h4>${escapeHtml(dossier.company)} · ${escapeHtml(dossier.title)}</h4><p>${escapeHtml(dossier.rationale)}</p><p>投递价值 ${ranked?.score??"—"} · 城市 ${ranked?.base_score??"—"} · 来源 ${ranked?.channel_score??"—"} · ${actionLabel}</p></div></div><div class="requirement-ledger">${requirements}</div><div class="risk-strip ${dossier.recommended_action==="block"?"is-blocked":""}">${risks}</div>`;
  $("#careerOSStamp").textContent=`${actionLabel} / ${dossier.match_score}`; $("#careerOSStamp").classList.add("is-ready");
}

async function buildCareerDossier(){
  const button=$("#buildCareerDossierButton"); setCareerBusy(button,true,"正在建立证据链…");
  try{
    const sessionId=await ensureCareerSession(true); const input=careerInput();
    const dossier=await requestJson("/api/career/job-dossier",{method:"POST",body:JSON.stringify({session_id:sessionId,...input})});
    const ranking=await requestJson("/api/career/jobs/rank",{method:"POST",body:JSON.stringify({session_id:sessionId,jobs:[{id:"current-job",...input,source:"official",application_minutes:20}]})});
    renderCareerDossier(dossier,ranking); showToast(`岗位作战包完成：匹配 ${dossier.match_score}，${dossier.hard_gaps.length} 条硬性条件待核验`);
    $("#railJobStatus").textContent=`已分析：匹配度 ${dossier.match_score}`;
    $("#railJob").classList.add("is-complete");
  }catch(error){
    $("#careerDossierBody").innerHTML=`<div class="career-alert">${escapeHtml(error.message)}</div>`;
    showToast(error.message);
  }
  finally{setCareerBusy(button,false,"");}
}

function renderCareerVersion(version,audit){
  const changes=version.changes.length?version.changes.map(item=>`<div class="version-change"><code>${escapeHtml(item.field_path)}</code><p>${escapeHtml(item.reason)}</p><p>${escapeHtml(item.before||"（空）")} → ${escapeHtml(item.after||"（空）")}</p></div>`).join(""):'<div class="version-change"><p>当前岗位与母版顺序已一致，没有为了制造差异而改写内容。</p></div>';
  const auditText=audit.findings.map(item=>item.message).join("；");
  $("#careerVersionBody").innerHTML=`<div class="version-card"><div class="version-head"><strong>${escapeHtml(version.label)}</strong><span>${audit.passed?"事实一致":"需要复核"}</span></div>${changes}<div class="audit-pass">${escapeHtml(auditText)}</div></div>`;
}

async function createCareerVersion(){
  const button=$("#createCareerVersionButton");setCareerBusy(button,true,"正在重排已确认事实…");
  try{
    const sessionId=await ensureCareerSession();const input=careerInput();
    const version=await requestJson("/api/career/resume-versions",{method:"POST",body:JSON.stringify({session_id:sessionId,target_company:input.company,target_title:input.title,job_description:input.description})});
    const audit=await requestJson(`/api/career/resume-versions/${encodeURIComponent(version.id)}/audit?session_id=${encodeURIComponent(sessionId)}`,{method:"POST"});
    careerState.versionId=version.id;renderCareerVersion(version,audit);showToast(`岗位版本已生成：${version.changes.length} 项顺序调整，事实母版未修改`);
  }catch(error){
    $("#careerVersionBody").innerHTML=`<div class="career-alert">${escapeHtml(error.message)}</div>`;
    showToast(error.message);
  }finally{
    setCareerBusy(button,false,"");
  }
}

function renderPortalPreflight(result,checkpoint=null){
  const checks=result.checklist.map(item=>`<div class="preflight-check">${escapeHtml(item)}</div>`).join("");
  const blockers=[...result.missing_required_fields,...result.blocked_sensitive_fields,...result.attachment_checks];
  $("#careerPortalBody").innerHTML=`<div class="version-head"><strong>${escapeHtml(result.adapter.name)}</strong><span>${result.ready?"可以继续确认":"暂时不能继续"}</span></div><div class="preflight-checks">${checks}</div>${blockers.length?`<div class="career-alert">需要先处理：${escapeHtml(blockers.join("；"))}</div>`:'<div class="audit-pass">字段和附件检查通过；最终提交仍需要你本人确认。</div>'}${checkpoint?`<div class="audit-pass">填写进度已保存，24 小时内可以从 ${checkpoint.pending_fields.length} 个待填字段继续。</div>`:""}`;
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
  const [apps,reminders,funnel,versions]=await Promise.all([
    requestJson(`/api/career/applications?session_id=${encodeURIComponent(careerState.sessionId)}`),
    requestJson(`/api/career/reminders?session_id=${encodeURIComponent(careerState.sessionId)}`),
    requestJson(`/api/career/funnel?session_id=${encodeURIComponent(careerState.sessionId)}`),
    requestJson(`/api/career/resume-versions?session_id=${encodeURIComponent(careerState.sessionId)}`)
  ]);
  careerState.applications=apps;
  const versionLabels=new Map(versions.map((item)=>[item.id,item.label]));
  const cards=apps.map(app=>`<div class="application-card"><div class="application-head"><strong>${escapeHtml(app.company)} · ${escapeHtml(app.title)}</strong><span>${careerStatusLabels[app.status]}</span></div><p>${app.resume_version_id?`岗位版简历：${escapeHtml(versionLabels.get(app.resume_version_id)||app.resume_version_id)}`:"尚未生成岗位版简历"} · ${app.deadline?`截止 ${escapeHtml(app.deadline)}`:"无截止日期"}</p><button class="application-open" type="button" data-app-open="${app.id}">继续处理这个岗位</button><div class="application-statuses">${["saved","preparing","ready","applied","assessment","interview","offer","rejected"].map(status=>`<button type="button" data-app-id="${app.id}" data-app-status="${status}" class="${app.status===status?"is-active":""}">${careerStatusLabels[status]}</button>`).join("")}</div></div>`).join("");
  const max=Math.max(1,...funnel.stages.map(item=>item.count));
  const funnelHtml=funnel.stages.filter(item=>item.count).map(item=>`<div class="funnel-line"><span>${careerStatusLabels[item.status]}</span><div class="funnel-rule"><i style="--funnel-width:${item.count/max*100}%"></i></div><b>${item.count}</b></div>`).join("");
  $("#careerApplicationBody").innerHTML=`<div class="application-list">${cards||'<div class="career-placeholder">尚未加入投递任务。</div>'}</div>${reminders.length?`<div class="audit-pass">最近提醒：${escapeHtml(reminders[0].title)} · ${new Date(reminders[0].due_at).toLocaleString("zh-CN")}</div>`:""}<div>${funnelHtml}</div><div class="audit-pass">响应率 ${funnel.response_rate}% · 面试率 ${funnel.interview_rate}% · Offer 率 ${funnel.offer_rate}%<br>${escapeHtml(funnel.recommendations.join("；"))}</div>`;
  if (apps.length) {
    careerState.applicationId ||= apps[0].id;
    $("#railBoardStatus").textContent=`${apps.length} 个岗位正在跟踪`;
    $("#railBoard").classList.add("is-complete");
  } else {
    $("#railBoardStatus").textContent="还没有投递记录";
    $("#railBoard").classList.remove("is-complete");
  }
  return apps;
}

function openCareerApplication(applicationId){
  const app=careerState.applications.find((item)=>item.id===applicationId);
  if(!app)return;
  careerState.applicationId=app.id;careerState.versionId=app.resume_version_id;
  setField("careerCompany",app.company);setField("careerTitle",app.title);setField("careerLocation",app.location);
  setField("careerUrl",app.url);setField("careerDeadline",app.deadline);setField("careerJD",app.job_description);
  $("#careerOSStamp").textContent=`${careerStatusLabels[app.status]} · 继续处理`;$("#careerOSStamp").classList.add("is-ready");
  if(app.resume_version_id)$("#careerVersionBody").innerHTML=`<div class="audit-pass">已恢复这个岗位使用的简历版本。需要更新时，可以重新生成岗位版简历。</div>`;
  goToWorkflow("careerOS",2);showToast("已恢复这个岗位的信息");
}

async function trackCareerApplication(){
  const button=$("#trackCareerApplicationButton");setCareerBusy(button,true,"正在登记时间线…");
  try{
    const sessionId=await ensureCareerSession();const input=careerInput();
    const existing=await requestJson(`/api/career/applications?session_id=${encodeURIComponent(sessionId)}`);
    const duplicate=existing.find((item)=>item.company.trim().toLowerCase()===input.company.trim().toLowerCase()&&item.title.trim().toLowerCase()===input.title.trim().toLowerCase());
    const app=duplicate||await requestJson("/api/career/applications",{method:"POST",body:JSON.stringify({session_id:sessionId,company:input.company,title:input.title,url:input.url||"",location:input.location||"",status:"ready",resume_version_id:careerState.versionId,job_description:input.description,deadline:input.deadline})});
    careerState.applicationId=app.id;await refreshCareerApplications();
    showToast(duplicate?"这个岗位已经在投递看板中":"岗位已加入投递看板；尚未向官网发送");
    goToWorkflow("careerApplicationBoard",3);
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
  const cards=items.map(item=>`<div class="evidence-card"><div class="evidence-head"><strong>${escapeHtml(item.label)}</strong><span>${item.verified_by_user?"本人确认":"待确认"}</span></div><ul>${item.facts.map(fact=>`<li>${escapeHtml(fact)}</li>`).join("")}</ul></div>`).join("");
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

function resetCareerOS(keepSession=false){
  const sessionId=keepSession ? careerState.sessionId : null;
  const applications=keepSession ? careerState.applications : [];
  Object.assign(careerState,{sessionId,dossier:null,versionId:null,applicationId:null,interviewKit:null,applications});
  $("#careerOSStamp").textContent="等待岗位";$("#careerOSStamp").classList.remove("is-ready");
}

function applyResumeToForm(resume) {
  const fieldMap = {
    fullName:resume.full_name, preferredName:resume.preferred_name, city:resume.city,
    professionalHeadline:resume.professional_headline, email:resume.email, phone:resume.phone,
    wechat:resume.wechat, jobSeekingStatus:resume.job_seeking_status,
    targetRoles:(resume.target_roles || []).join(", "), targetIndustries:(resume.target_industries || []).join(", "),
    targetEmployerTypes:(resume.target_employer_types || []).join(", "), baseLocations:(resume.base_locations || []).join(", "),
    employmentTypes:(resume.employment_types || []).join(", "), yearsExperience:resume.years_experience,
    availableDate:resume.available_date, expectedSalary:resume.expected_salary,
    relocationPreference:resume.relocation_preference, skills:(resume.skills || []).join(", "),
    summary:resume.summary, hobbies:(resume.hobbies || []).join(", "),
    selfEvaluation:resume.self_evaluation, additionalInformation:resume.additional_information,
  };
  Object.entries(fieldMap).forEach(([id, fieldValue]) => setField(id, fieldValue));

  const education=resume.education?.[0] || {};
  const educationMap={school:education.school,college:education.college,major:education.major,minor:education.minor,degree:education.degree,
    educationType:education.education_type,educationStartDate:education.start_date,educationEndDate:education.end_date,
    graduationYear:education.graduation_year,educationLocation:education.location,gpa:education.gpa,gpaScale:education.gpa_scale,
    rank:education.rank,coreCourses:(education.core_courses||[]).join(", "),thesis:education.thesis};
  Object.entries(educationMap).forEach(([id, fieldValue]) => setField(id, fieldValue));
  renderWorkEntries(resume.work_experience || []);
  renderProjectEntries(resume.projects || []);

  const campus=resume.campus_experience?.[0]||{};setField("campusOrganization",campus.organization);setField("campusRole",campus.role);setField("campusDescription",campus.description);
  const certificate=resume.certificates?.[0]||{};setField("certificateName",certificate.name);setField("certificateIssuer",certificate.issuer);setField("certificateScore",certificate.score);
  const language=resume.language_details?.[0]||{};setField("language",language.language);setField("languageProficiency",language.proficiency);setField("languageTest",language.test_name);setField("languageScore",language.score);
  setField("awardName",resume.awards?.[0]?.name);
}

async function restoreLastSession() {
  try {
    const sessions=await requestJson("/api/sessions");
    if(!sessions.length){updateProfileProgress();return;}
    const remembered=localStorage.getItem("lastSessionId");
    const session=sessions.find((item)=>item.id===remembered)||sessions[0];
    applyResumeToForm(session.resume);
    currentSessionId=session.id;
    careerState.sessionId=session.id;
    localStorage.setItem("lastSessionId",session.id);
    profileDirty=false;
    setProfileSaveState("saved",`已保存 ${new Date(session.updated_at).toLocaleTimeString("zh-CN",{hour:"2-digit",minute:"2-digit"})}`);
    updateProfileProgress(session.resume);
    await refreshCareerApplications();
    showToast("已打开上次保存的档案");
  } catch(error) {
    setProfileSaveState("error","暂时无法恢复");
  }
}

function addRepeatableEntry(type) {
  if(type==="work") renderWorkEntries([...collectWorkEntries(true),{}]);
  else renderProjectEntries([...collectProjectEntries(true),{}]);
}

function removeRepeatableEntry(button) {
  const type=button.dataset.removeEntry;
  const entry=button.closest(".repeatable-entry");
  const index=[...entry.parentElement.children].indexOf(entry);
  if(type==="work"){
    const items=collectWorkEntries(true);items.splice(index,1);renderWorkEntries(items);
  }else{
    const items=collectProjectEntries(true);items.splice(index,1);renderProjectEntries(items);
  }
  profileDirty=true;setProfileSaveState("dirty","有未保存修改");updateProfileProgress();
}

renderWorkEntries();
renderProjectEntries();
$("#runCampaignButton").addEventListener("click",runDiscovery);
$("#saveProfileButton").addEventListener("click",()=>saveProfile(true));
$("#saveProfileTopButton").addEventListener("click",()=>saveProfile(false));
$("#addWorkButton").addEventListener("click",()=>addRepeatableEntry("work"));
$("#addProjectButton").addEventListener("click",()=>addRepeatableEntry("project"));
$("#workEntries").addEventListener("click",event=>{const button=event.target.closest("[data-remove-entry]");if(button)removeRepeatableEntry(button);});
$("#projectEntries").addEventListener("click",event=>{const button=event.target.closest("[data-remove-entry]");if(button)removeRepeatableEntry(button);});
document.querySelectorAll("[data-workflow-target]").forEach((button,index)=>button.addEventListener("click",()=>goToWorkflow(button.dataset.workflowTarget,index+1)));
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
$("#careerApplicationBody").addEventListener("click",event=>{const statusButton=event.target.closest("[data-app-status]");if(statusButton){updateCareerApplication(statusButton.dataset.appId,statusButton.dataset.appStatus).catch(error=>showToast(error.message));return;}const openButton=event.target.closest("[data-app-open]");if(openButton)openCareerApplication(openButton.dataset.appOpen);});
$("#editorialLedger").addEventListener("click",event=>{const button=event.target.closest("[data-revision-index]");if(button)copyRevision(Number(button.dataset.revisionIndex));});
document.addEventListener("input",event=>{const field=event.target.closest?.("input, textarea, select");if(!field)return;field.removeAttribute("aria-invalid");field.classList.remove("is-invalid");});
$("#resumeForm").addEventListener("input",()=>{profileDirty=true;setProfileSaveState("dirty","有未保存修改");updateProfileProgress();if(currentReview||currentOptimization){$("#reviewGrade").textContent="待重新检查";$("#reviewGrade").classList.remove("is-reviewed");}resetCareerOS(true);});
$("#portalActionButton").addEventListener("click",loadPortalTemplate);
$("#portalLinkButton").addEventListener("click",jumpPortal);$("#portalJumpButton").addEventListener("click",jumpPortal);
$("#logoutButton").addEventListener("click",logoutAccount);

async function initializeApp(){
  const careerDeadline=new Date();careerDeadline.setDate(careerDeadline.getDate()+14);$("#careerDeadline").value=careerDeadline.toISOString().slice(0,10);
  await loadAccount();
  await Promise.allSettled([checkHealth(),loadPortalTemplate(),restoreLastSession()]);
}

initializeApp();
