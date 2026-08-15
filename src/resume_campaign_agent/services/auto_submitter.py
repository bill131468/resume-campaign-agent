"""通用 Playwright 自动投递 Agent - 支持任意招聘网站（含北森焦点验证修复）"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright


class AutoSubmitter:
    """通用自动投递器 - 不绑定特定平台，AI 自动识别表单"""

    def __init__(self, llm_api_key: str | None = None, llm_base_url: str | None = None):
        self.llm_api_key = llm_api_key
        self.llm_base_url = llm_base_url or "https://api.siliconflow.cn/v1"
        self.screenshot_dir = Path("submission_screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)

    async def scan_form_fields(self, page) -> list[dict]:
        """扫描页面所有表单字段"""
        return await page.evaluate('''
            () => {
                const fields = [];
                const inputs = document.querySelectorAll(
                    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]), select, textarea'
                );
                inputs.forEach((el, index) => {
                    const labelEl = el.closest('label') 
                        || document.querySelector(`label[for="${el.id}"]`)
                        || el.closest('.form-group')?.querySelector('label')
                        || el.closest('.form-item')?.querySelector('label')
                        || el.closest('.el-form-item')?.querySelector('.el-form-item__label')
                        || el.closest('td')?.previousElementSibling
                        || el.closest('tr')?.querySelector('td:first-child')
                        || el.closest('div')?.querySelector('label');
                    const placeholder = el.placeholder || el.getAttribute('aria-label') || '';
                    const labelText = labelEl?.textContent?.trim() || '';
                    const name = el.name || el.id || '';
                    fields.push({
                        index: index, tag: el.tagName.toLowerCase(), type: el.type || 'text',
                        name: name, id: el.id || '', placeholder: placeholder, label: labelText,
                        required: el.required || false,
                        selector: el.id ? `#${CSS.escape(el.id)}` : (el.name ? `[name="${el.name}"]` : ''),
                        classes: el.className || '', options: el.tagName === 'SELECT' ? Array.from(el.options).map(o => o.text) : []
                    });
                });
                return fields;
            }
        ''')

    async def match_fields_with_ai(self, form_fields: list[dict], resume_data: dict) -> list[dict]:
        """AI 字段匹配（DeepSeek-V3）"""
        import requests

        safe_resume = {}
        for k, v in resume_data.items():
            if k in ("phone", "email", "full_name", "wechat"):
                safe_resume[k] = "***"
            elif isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                safe_resume[k] = [
                    {"school": "***", "degree": e.get("degree", "")} if "school" in e else e
                    for e in v[:1]
                ]
            else:
                safe_resume[k] = v

        if resume_data.get("education"):
            edu = resume_data["education"][0]
            if isinstance(edu, dict):
                safe_resume["school"] = "***"
                safe_resume["degree"] = edu.get("degree", "")
                safe_resume["major"] = edu.get("major", "")
                safe_resume["graduation_year"] = edu.get("graduation_year", "")

        if resume_data.get("work_experience"):
            work = resume_data["work_experience"][0]
            if isinstance(work, dict):
                safe_resume["work_company"] = work.get("company", "")
                safe_resume["work_title"] = work.get("title", "")
                safe_resume["work_department"] = work.get("department", "")

        prompt = f"""你是一个智能表单填写助手。请分析以下招聘网站的表单字段，并将其与候选人的简历数据进行匹配。

【表单字段】
{json.dumps(form_fields, ensure_ascii=False, indent=2)}

【简历数据】
{json.dumps(safe_resume, ensure_ascii=False, indent=2)}

【任务】
对于每个表单字段，判断它是否对应简历中的某项数据。如果对应，填写 field_index、resume_field 和 value。
如果无法匹配，跳过该字段。
注意：*** 表示该字段有值但已脱敏，你仍然需要匹配它，value 先填占位符即可。

返回格式（纯 JSON 数组）：
[{{"field_index": 0, "resume_field": "full_name", "value": "***"}}]"""

        try:
            response = requests.post(
                f"{self.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.llm_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-ai/DeepSeek-V3",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 2000
                },
                timeout=30
            )

            if response.status_code != 200:
                print(f"⚠️ AI 匹配失败（{response.status_code}），使用规则匹配")
                return self._rule_based_match(form_fields, resume_data)

            content = response.json()["choices"][0]["message"]["content"]

            for prefix in ["```json", "```"]:
                if prefix in content:
                    content = content.split(prefix)[1].split("```")[0]
                    break

            content = content.strip()
            if content.startswith("["):
                ai_mappings = json.loads(content)
                for m in ai_mappings:
                    field_name = m.get("resume_field", "")
                    if field_name in resume_data:
                        real_value = resume_data[field_name]
                        if isinstance(real_value, list):
                            m["value"] = "、".join(real_value) if real_value and isinstance(real_value[0], str) else str(real_value)
                        else:
                            m["value"] = real_value
                    elif field_name == "school" and resume_data.get("education"):
                        m["value"] = resume_data["education"][0].get("school", "")
                    elif field_name == "major" and resume_data.get("education"):
                        m["value"] = resume_data["education"][0].get("major", "")
                    elif field_name == "degree" and resume_data.get("education"):
                        m["value"] = resume_data["education"][0].get("degree", "")
                    elif field_name == "graduation_year" and resume_data.get("education"):
                        m["value"] = resume_data["education"][0].get("graduation_year", "")
                print(f"   AI 匹配成功: {len(ai_mappings)} 个字段")
                return ai_mappings
            else:
                print("⚠️ AI 返回格式异常，使用规则匹配")
                return self._rule_based_match(form_fields, resume_data)

        except Exception as e:
            print(f"⚠️ AI 匹配异常: {e}，使用规则匹配")
            return self._rule_based_match(form_fields, resume_data)

    def _rule_based_match(self, form_fields: list[dict], resume_data: dict) -> list[dict]:
        """基于规则的字段匹配（AI 失败时兜底）"""
        exact_rules = [
            ("姓名", "full_name", ["紧急联系人","联系人","单位","公司","学校","职位","部门","专业","项目","证明人","导师","名称"]),
            ("手机号码", "phone", ["紧急联系人","联系人","家庭","父母"]),
            ("邮箱", "email", []),
            ("现居住地", "city", ["户口","籍贯","生源","期望"]),
            ("毕业时间", "graduation_year", []),
            ("学校名称", "school", []),
            ("专业名称", "major", []),
            ("学历", "degree", ["最高学历","第一学历"]),
            ("期望月薪", "expected_salary", ["年薪"]),
            ("自我评价", "summary", []),
            ("技能", "skills", ["突出技能","专业技能"]),
            ("英语等级", "language_proficiency", []),
            ("单位名称", "work_company", ["学校","毕业"]),
            ("职位名称", "work_title", []),
            ("部门名称", "work_department", []),
            ("出生日期", "birth_date", []),
            ("籍贯", "native_place", ["生源"]),
            ("民族", "ethnicity", []),
            ("政治面貌", "political_status", []),
            ("参加工作时间", "work_start_date", []),
            ("预计报到时间", "available_date", []),
        ]

        flat_resume = {}
        for k, v in resume_data.items():
            if isinstance(v, str): flat_resume[k] = v
            elif isinstance(v, (int, float)): flat_resume[k] = str(v)
            elif isinstance(v, list) and v and isinstance(v[0], str): flat_resume[k] = "、".join(v)

        if resume_data.get("education"):
            edu = resume_data["education"][0]
            for ek in ["school","degree","major","graduation_year"]:
                if ek in edu and ek not in flat_resume: flat_resume[ek] = str(edu[ek])

        if resume_data.get("language_details"):
            lang = resume_data["language_details"][0]
            flat_resume["language_proficiency"] = f"{lang.get('test_name','')} {lang.get('score','')}"

        if resume_data.get("work_experience"):
            w = resume_data["work_experience"][0]
            for wk in [("work_company","company"),("work_title","title"),("work_department","department")]:
                if wk[1] in w and wk[0] not in flat_resume: flat_resume[wk[0]] = str(w[wk[1]])

        mappings, matched = [], set()

        for rule in exact_rules:
            label_kw, resume_field, excludes = rule
            if resume_field not in flat_resume: continue
            for f in form_fields:
                if f["index"] in matched: continue
                combined = f"{f.get('label','')} {f.get('placeholder','')} {f.get('name','')}".lower()
                if label_kw not in combined: continue
                if any(ex in f.get('label','') for ex in excludes): continue
                mappings.append({"field_index": f["index"], "resume_field": resume_field, "value": flat_resume[resume_field]})
                matched.add(f["index"]); break

        remaining = [f for f in form_fields if f["index"] not in matched]
        loose_rules = [
            ("job_seeking_status", ["求职状态","目前状态"]),
            ("available_date", ["到岗时间","报到时间","预计报到"]),
            ("base_locations", ["期望城市","期望工作地"]),
            ("target_roles", ["期望职位","求职意向"]),
            ("city", ["户口所在地","籍贯"]),
            ("self_evaluation", ["自我评价"]),
            ("expected_salary", ["期望薪资","期望月薪","期望年薪"]),
        ]

        for resume_field, keywords in loose_rules:
            if resume_field not in flat_resume: continue
            for f in remaining:
                if f["index"] in matched: continue
                combined = f"{f.get('label','')} {f.get('placeholder','')}".lower()
                if any(kw in combined for kw in keywords):
                    mappings.append({"field_index": f["index"], "resume_field": resume_field, "value": flat_resume[resume_field]})
                    matched.add(f["index"]); break

        print(f"   规则匹配: {len(mappings)} 个字段")
        return mappings

    async def fill_form(self, page, mappings: list[dict], form_fields: list[dict]) -> list[str]:
        """填表 - 通过 Vue 组件实例直接赋值（北森 Element UI 专用）"""
        filled, skipped = [], []

        for mapping in mappings:
            field = next((f for f in form_fields if f["index"] == mapping["field_index"]), None)
            if not field:
                continue

            label_text = field.get("label", "").strip()
            placeholder = field.get("placeholder", "").strip()
            value = str(mapping.get("value", ""))

            if not label_text and not placeholder:
                skipped.append(f"⚠️ 无标签可定位")
                continue

            # ── 核心：用 JS 找到 label 对应的真正的输入元素并设置值 ──
            js_fill = f'''
                (() => {{
                    const searchText = "{label_text}" || "{placeholder}";
                    if (!searchText) return "NO_LABEL";

                    // 查找所有可能的 label 元素
                    const labelEls = document.querySelectorAll('label, .el-form-item__label, span, td');

                    for (const label of labelEls) {{
                        const text = label.textContent.trim();
                        if (text.includes(searchText) && text.length < 50) {{
                            // 向上找父容器
                            let parent = label.closest('.el-form-item, .form-item, .form-group, td, div');
                            if (!parent) continue;

                            // 在父容器中找真正的 input/textarea/select
                            const input = parent.querySelector('input:not([type="hidden"]):not([type="file"]), textarea, select');
                            if (!input) continue;

                            // 判断 input 类型
                            if (input.tagName === 'SELECT') {{
                                // 下拉框
                                const options = input.options;
                                for (const opt of options) {{
                                    if (opt.text.includes("{value}") || "{value}".includes(opt.text)) {{
                                        input.value = opt.value;
                                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        return "FILLED_SELECT";
                                    }}
                                }}
                                if (options.length > 1) {{
                                    input.value = options[1].value;
                                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return "FILLED_SELECT_FIRST";
                                }}
                            }}

                            // 输入框：设置值 + 触发 Vue 事件链
                            const valueSetter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'value'
                            ).set;
                            valueSetter.call(input, "{value}");
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('blur', {{ bubbles: true }}));

                            // 触发键盘事件（Vue 有时需要）
                            input.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true }}));

                            return "FILLED_INPUT";
                        }}
                    }}

                    return "NOT_FOUND";
                }})()
            '''

            try:
                result = await page.evaluate(js_fill)

                if result == "FILLED_INPUT":
                    filled.append(f"✅ [Vue] {label_text} ← {value}")
                elif result == "FILLED_SELECT":
                    filled.append(f"✅ [Vue下拉] {label_text} ← {value}")
                elif result == "FILLED_SELECT_FIRST":
                    filled.append(f"✅ [Vue下拉] {label_text} ← 第一个选项")
                elif result == "NOT_FOUND":
                    skipped.append(f"⚠️ 未找到匹配元素: {label_text}")
                elif result == "NO_LABEL":
                    skipped.append(f"⚠️ 无标签: {field}")
                else:
                    skipped.append(f"⚠️ 未知结果 {result}: {label_text}")

            except Exception as e:
                skipped.append(f"❌ {label_text}: {str(e)[:80]}")

        # 填完后截图，验证实际填写情况
        print("\n📋 验证实际填写结果...")
        verify_js = '''
            () => {
                const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="file"])');
                const filled = [];
                inputs.forEach((el, i) => {
                    if (el.value && el.value.length > 0) {
                        const label = el.closest('.el-form-item, .form-item, .form-group, td, div')
                            ?.querySelector('label, .el-form-item__label, span')?.textContent?.trim() || `input_${i}`;
                        filled.push(`${label} = ${el.value.substring(0, 20)}`);
                    }
                });
                return filled;
            }
        '''
        try:
            actual_filled = await page.evaluate(verify_js)
            print(f"   页面上实际有 {len(actual_filled)} 个输入框有值:")
            for item in actual_filled[:15]:
                print(f"   {item}")
        except:
            pass

        return filled + skipped

    async def upload_resume_file(self, page, file_path: str) -> bool:
        """上传简历附件"""
        for inp in await page.query_selector_all('input[type="file"]'):
            try:
                await inp.set_input_files(file_path)
                await page.wait_for_timeout(1000)
                print(f"✅ 已上传: {file_path}")
                return True
            except: continue
        print("⚠️ 未找到文件上传区域")
        return False

    async def take_screenshot(self, page, name: str) -> str:
        """截图保存"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fp = self.screenshot_dir / f"{name}_{ts}.png"
        await page.screenshot(path=str(fp), full_page=True)
        print(f"   📸 {fp.name}")
        return str(fp)

    async def _find_submit_button(self, page):
        """智能查找提交按钮"""
        for sel in [
            'button[type="submit"]', 'input[type="submit"]',
            'button:has-text("提交")', 'button:has-text("投递")',
            'button:has-text("申请")', 'button:has-text("确认")',
            'button:has-text("保存")', 'a:has-text("提交")',
            'a:has-text("投递")', '.submit-btn', '#submit',
            '[data-action="submit"]',
        ]:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible(): return btn, sel
            except: continue
        return None, None

    async def apply(
        self,
        job_url: str,
        resume_data: dict,
        resume_file_path: str | None = None,
        headless: bool = False,
        auto_submit: bool = False,
    ) -> dict:
        """自动投递主流程"""
        result = {
            "success": False, "job_url": job_url,
            "steps": [], "screenshots": [], "filled_fields": 0, "errors": [],
        }

        async with async_playwright() as p:
            udd = Path("browser_data")
            udd.mkdir(exist_ok=True)

            context = await p.chromium.launch_persistent_context(
                str(udd), headless=headless, viewport={"width": 1280, "height": 900},
                locale="zh-CN",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = await context.new_page()

            try:
                print(f"🌐 打开: {job_url[:80]}...")
                await page.goto(job_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)

                if "login" in page.url.lower() or "auth" in page.url.lower():
                    print("⚠️ 需要登录，请扫码后按 Enter...")
                    input()
                    await page.goto(job_url, wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(3000)

                result["steps"].append("页面加载完成")
                result["screenshots"].append(await self.take_screenshot(page, "01_page"))

                print("🔍 扫描表单...")
                form_fields = await self.scan_form_fields(page)
                print(f"   检测到 {len(form_fields)} 个字段")

                if len(form_fields) < 3:
                    await page.wait_for_timeout(5000)
                    form_fields = await self.scan_form_fields(page)
                    print(f"   重试后: {len(form_fields)} 个字段")

                print("\n📋 字段列表：")
                for f in form_fields[:15]:
                    print(f"   [{f['index']}] {f['tag']}[type={f['type']}] label='{f.get('label','')}' placeholder='{f.get('placeholder','')}'")

                print("\n🧠 匹配字段...")
                if self.llm_api_key:
                    mappings = await self.match_fields_with_ai(form_fields, resume_data)
                else:
                    mappings = self._rule_based_match(form_fields, resume_data)
                result["filled_fields"] = len(mappings)

                print("\n✍️ 填写表单...")
                filled = await self.fill_form(page, mappings, form_fields)
                for item in filled:
                    print(f"   {item}")
                result["steps"].extend(filled)
                result["screenshots"].append(await self.take_screenshot(page, "02_filled"))

                if resume_file_path and os.path.exists(resume_file_path):
                    print(f"\n📎 上传附件: {resume_file_path}")
                    await self.upload_resume_file(page, resume_file_path)
                    result["screenshots"].append(await self.take_screenshot(page, "03_upload"))

                print("\n" + "=" * 50)
                print("📱 请手动完成验证码和协议勾选")
                print("=" * 50)
                print("完成后按 Enter...")
                input()
                result["steps"].append("人工确认完成")
                result["screenshots"].append(await self.take_screenshot(page, "04_confirmed"))

                submit_btn, btn_sel = await self._find_submit_button(page)
                if submit_btn:
                    print(f"\n🎯 找到提交按钮: {btn_sel}")
                    print("按 Enter 提交，输入 q 取消...")
                    ui = input()
                    if ui.lower() != 'q':
                        await submit_btn.click()
                        await page.wait_for_timeout(3000)
                        result["success"] = True
                        result["steps"].append("已提交")
                    else:
                        result["steps"].append("用户取消")
                    result["screenshots"].append(await self.take_screenshot(page, "05_submitted"))
                else:
                    print("\n⚠️ 未找到提交按钮，请手动点击")
                    print("按 Enter 继续...")
                    input()
                    result["steps"].append("需手动提交")
                    result["screenshots"].append(await self.take_screenshot(page, "05_manual"))

                print("\n🎉 完成！" if result["success"] else "\n⚠️ 流程结束")

            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)[:200]}"
                result["errors"].append(error_msg)
                print(f"\n❌ {error_msg}")

            finally:
                print("\n⏳ 浏览器 10 秒后关闭...")
                await page.wait_for_timeout(10000)
                await context.close()

        print(f"\n📊 成功:{result['success']} | 填写:{result['filled_fields']}字段 | 截图:{len(result['screenshots'])}张")
        return result


async def quick_apply(
    job_url: str, resume_data: dict, resume_file: str | None = None,
    api_key: str | None = None, headless: bool = False,
):
    """快速投递"""
    return await AutoSubmitter(llm_api_key=api_key).apply(job_url, resume_data, resume_file, headless=headless)