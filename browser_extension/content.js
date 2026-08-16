(() => {
  if (globalThis.__resumeCopilotLoaded) return;
  globalThis.__resumeCopilotLoaded = true;

  const MAX_FIELDS = 500;
  const BLOCKED_TYPES = new Set([
    "password", "hidden", "file", "submit", "button", "reset", "image",
    "checkbox", "radio", "color", "range"
  ]);
  const PROTECTED = [
    "password", "passcode", "密码", "验证码", "captcha", "otp", "身份证",
    "证件号", "护照", "passport", "性别", "gender", "出生", "birth",
    "婚姻", "marital", "民族", "ethnicity", "政治面貌", "户籍", "户口",
    "家庭成员", "紧急联系人", "家庭住址", "详细地址", "home address",
    "期望薪资", "expected salary", "薪酬", "salary", "同意", "授权", "隐私",
    "consent", "agreement"
  ];

  function clean(value, limit = 500) {
    return String(value || "").replace(/\s+/g, " ").trim().slice(0, limit);
  }

    function getLabel(element) {
    const direct = Array.from(element.labels || []).map((label) => label.innerText).join(" ");
    if (clean(direct)) return clean(direct);
    const aria = element.getAttribute("aria-label");
    if (clean(aria)) return clean(aria);
    const labelledBy = clean(element.getAttribute("aria-labelledby"));
    if (labelledBy) {
      const text = labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.innerText || "").join(" ");
      if (clean(text)) return clean(text);
    }
    const parent = element.closest("label");
    if (parent) return clean(parent.innerText);
    const formItem = element.closest(
      ".form-item, .ant-form-item, .el-form-item, [class*='formItem'], [class*='form-item'], fieldset"
    );
    if (formItem) {
      const label = formItem.querySelector("label, legend, .ant-form-item-label, .el-form-item__label, [class*='label']");
      if (label && label !== element && clean(label.innerText)) return clean(label.innerText);
    }
    const preceding = element.previousElementSibling;
    if (preceding && /^(LABEL|SPAN|DIV|P|LEGEND)$/.test(preceding.tagName)) return clean(preceding.innerText);

    // 新增：向上查找父容器文字（字节跳动等自研组件）
    let ancestor = element.parentElement;
    let bestText = "";
    for (let depth = 0; depth < 10 && ancestor; depth++) {
      const text = clean(ancestor.innerText);
      // 只保存短文本（长文本是容器说明，短文本更可能是字段 label）
      if (text && text.length <= 100) {
        bestText = text.slice(0, 80);
      }
      ancestor = ancestor.parentElement;
    }
    if (bestText) return bestText;

    return "";
  }

  function signature(field) {
    return [field.tag, field.input_type, field.name, field.element_id, field.label]
      .map((part) => clean(part, 160)).join("|").slice(0, 800);
  }

  function scanFields() {
    return Array.from(document.querySelectorAll("input, textarea, select"))
      .slice(0, MAX_FIELDS)
      .map((element, index) => {
        const tag = element.tagName.toLowerCase();
        const field = {
          index,
          tag,
          input_type: tag === "input" ? clean(element.type || "text", 40).toLowerCase() : tag,
          name: clean(element.getAttribute("name"), 200),
          element_id: clean(element.id, 200),
          label: getLabel(element),
          placeholder: clean(element.getAttribute("placeholder")),
          autocomplete: clean(element.getAttribute("autocomplete"), 100),
          required: Boolean(element.required || element.getAttribute("aria-required") === "true"),
          max_length: element.maxLength >= 0 ? element.maxLength : null,
          options: tag === "select"
            ? Array.from(element.options).slice(0, 200).map((option) => ({
                value: clean(option.value, 300), label: clean(option.textContent, 300)
              }))
            : []          ,
          context: clean(element.parentElement?.parentElement?.innerText || element.parentElement?.innerText || "", 500)
        };
        field.signature = signature(field);
        return field;
      });
  }

  function isProtected(element, field) {
    if (BLOCKED_TYPES.has(field.input_type)) return true;
    const text = [field.label, field.name, field.element_id, field.placeholder, field.autocomplete]
      .join(" ").toLowerCase();
    return PROTECTED.some((word) => text.includes(word.toLowerCase()));
  }

  function setNativeValue(element, value) {
    if (element.tagName === "SELECT") {
      const wanted = clean(value).toLowerCase();
      const option = Array.from(element.options).find((item) =>
        clean(item.value).toLowerCase() === wanted || clean(item.textContent).toLowerCase() === wanted
      ) || Array.from(element.options).find((item) =>
        clean(item.textContent).toLowerCase().includes(wanted) || wanted.includes(clean(item.textContent).toLowerCase())
      );
      if (!option) return false;
      element.value = option.value;
    } else {
      const prototype = element.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
      if (!setter) return false;
      setter.call(element, value);
    }
    element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function applyPlan(actions) {
    const elements = Array.from(document.querySelectorAll("input, textarea, select")).slice(0, MAX_FIELDS);
    const fields = scanFields();
    const result = { filled: [], skipped: [] };
    for (const action of actions || []) {
      const element = elements[action.field_index];
      const field = fields[action.field_index];
      if (!element || !field || field.signature !== action.field_signature) {
        result.skipped.push({ field_index: action.field_index, reason: "页面字段已变化，请重新扫描" });
        continue;
      }
      if (isProtected(element, field)) {
        result.skipped.push({ field_index: action.field_index, reason: "浏览器安全规则拒绝操作" });
        continue;
      }
      if (element.disabled || element.readOnly || clean(element.value)) {
        result.skipped.push({ field_index: action.field_index, reason: "字段已填写、只读或已禁用" });
        continue;
      }
      if (!setNativeValue(element, action.value)) {
        result.skipped.push({ field_index: action.field_index, reason: "页面选项与简历值不匹配" });
        continue;
      }
      element.dataset.resumeCopilotFilled = "true";
      element.style.outline = "2px solid #2f6d52";
      element.style.outlineOffset = "2px";
      result.filled.push({ field_index: action.field_index, resume_field: action.resume_field });
    }
    return result;
  }

  function highlightPlan(actions) {
    const elements = Array.from(document.querySelectorAll("input, textarea, select")).slice(0, MAX_FIELDS);
    const fields = scanFields();
    const result = { highlighted: [], skipped: [] };
    let firstElement = null;
    for (const action of actions || []) {
      const element = elements[action.field_index];
      const field = fields[action.field_index];
      if (!element || !field || field.signature !== action.field_signature || isProtected(element, field)) {
        result.skipped.push({ field_index: action.field_index, reason: "字段变化或安全规则拒绝标记" });
        continue;
      }
      element.dataset.resumeCopilotPending = "true";
      element.style.outline = "2px dashed #b87529";
      element.style.outlineOffset = "2px";
      if (!firstElement) firstElement = element;
      result.highlighted.push({ field_index: action.field_index, resume_field: action.resume_field });
    }
    firstElement?.scrollIntoView({ behavior: "smooth", block: "center" });
    return result;
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "RC_SCAN_FORM") {
      sendResponse({
        ok: true,
        page: { url: location.href, title: document.title, fields: scanFields() }
      });
      return;
    }
    if (message?.type === "RC_APPLY_PLAN") {
      sendResponse({ ok: true, result: applyPlan(message.actions) });
      return;
    }
    if (message?.type === "RC_HIGHLIGHT_PLAN") {
      sendResponse({ ok: true, result: highlightPlan(message.actions) });
    }
  });
})();
