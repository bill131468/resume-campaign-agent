"""通用 Playwright 自动投递 Agent - 支持任意招聘网站（含北森 Element UI 优化 + Tab 键兜底）"""

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
        """AI 字段匹配"""
        import requests
        safe_resume = {k: ("***" if k in ("phone", "email", "full_name", "wechat") else v) for k, v in
                       resume_data.items()}
        try:
            response = requests.post(
                f"{self.llm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.llm_api_key}", "Content-Type": "application/json"},
                json={"model": "deepseek-ai/DeepSeek-V3", "messages": [{"role": "user", "content": f"""匹配表单字段和简历数据。返回 JSON 数组：[{{"field_index": 0, "resume_field": "full_name", "value": "张三"}}]
表单字段：{json.dumps(form_fields, ensure_ascii=False, indent=2)}
简历数据：{json.dumps(safe_resume, ensure_ascii=False, indent=2)}"""}], "temperature": 0.1, "max_tokens": 2000},
                timeout=30)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                for prefix in ["```json", "```"]:
                    if prefix in content: content = content.split(prefix)[1].split("```")[0]
                content = content.strip()
                if content.startswith("["): return json.loads(content)
        except:
            pass
        return self._rule_based_match(form_fields, resume_data)

    def _rule_based_match(self, form_fields: list[dict], resume_data: dict) -> list[dict]:
        """基于规则的字段匹配（北森优化版，含更多字段）"""
        exact_rules = [
            ("姓名", "full_name",
             ["紧急联系人", "联系人", "单位", "公司", "学校", "职位", "部门", "专业", "项目", "证明人", "导师",
              "名称"]),
            ("手机号码", "phone", ["紧急联系人", "联系人", "家庭", "父母"]),
            ("邮箱", "email", []),
            ("现居住地", "city", ["户口", "籍贯", "生源", "期望"]),
            ("毕业时间", "graduation_year", []),
            ("学校名称", "school", []),
            ("专业名称", "major", []),
            ("学历", "degree", ["最高学历", "第一学历"]),
            ("期望月薪", "expected_salary", ["年薪"]),
            ("自我评价", "summary", []),
            ("技能", "skills", ["突出技能", "专业技能"]),
            ("英语等级", "language_proficiency", []),
            ("单位名称", "work_company", ["学校", "毕业"]),
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
            if isinstance(v, str):
                flat_resume[k] = v
            elif isinstance(v, (int, float)):
                flat_resume[k] = str(v)
            elif isinstance(v, list) and v and isinstance(v[0], str):
                flat_resume[k] = "、".join(v)

        if resume_data.get("education"):
            edu = resume_data["education"][0]
            for ek in ["school", "degree", "major", "graduation_year"]:
                if ek in edu and ek not in flat_resume: flat_resume[ek] = str(edu[ek])

        if resume_data.get("language_details"):
            lang = resume_data["language_details"][0]
            flat_resume["language_proficiency"] = f"{lang.get('test_name', '')} {lang.get('score', '')}"

        if resume_data.get("work_experience"):
            w = resume_data["work_experience"][0]
            for wk in [("work_company", "company"), ("work_title", "title"), ("work_department", "department")]:
                if wk[1] in w and wk[0] not in flat_resume: flat_resume[wk[0]] = str(w[wk[1]])

        mappings, matched = [], set()

        for rule in exact_rules:
            label_kw, resume_field, excludes = rule
            if resume_field not in flat_resume: continue
            for f in form_fields:
                if f["index"] in matched: continue
                combined = f"{f.get('label', '')} {f.get('placeholder', '')} {f.get('name', '')}".lower()
                if label_kw not in combined: continue
                if any(ex in f.get('label', '') for ex in excludes): continue
                mappings.append(
                    {"field_index": f["index"], "resume_field": resume_field, "value": flat_resume[resume_field]})
                matched.add(f["index"]);
                break

        remaining = [f for f in form_fields if f["index"] not in matched]
        loose_rules = [
            ("job_seeking_status", ["求职状态", "目前状态"]),
            ("available_date", ["到岗时间", "报到时间", "预计报到"]),
            ("base_locations", ["期望城市", "期望工作地"]),
            ("target_roles", ["期望职位", "求职意向"]),
            ("city", ["户口所在地", "籍贯"]),
            ("self_evaluation", ["自我评价"]),
            ("expected_salary", ["期望薪资", "期望月薪", "期望年薪"]),
        ]

        for resume_field, keywords in loose_rules:
            if resume_field not in flat_resume: continue
            for f in remaining:
                if f["index"] in matched: continue
                combined = f"{f.get('label', '')} {f.get('placeholder', '')}".lower()
                if any(kw in combined for kw in keywords):
                    mappings.append(
                        {"field_index": f["index"], "resume_field": resume_field, "value": flat_resume[resume_field]})
                    matched.add(f["index"]);
                    break

        print(f"   规则匹配: {len(mappings)} 个字段")
        return mappings

    async def fill_form(self, page, mappings: list[dict], form_fields: list[dict]) -> list[str]:
        """填表（5 种策略 + Tab 键兜底）"""
        filled, skipped = [], []

        for mapping in mappings:
            field = next((f for f in form_fields if f["index"] == mapping["field_index"]), None)
            if not field: continue

            label_text = field.get("label", "")
            placeholder = field.get("placeholder", "")
            value = str(mapping.get("value", ""))
            success = False

            # ── 策略 1：placeholder 定位 ──
            if not success and placeholder:
                try:
                    el = await page.wait_for_selector(f'input[placeholder*="{placeholder}"]', state="visible",
                                                      timeout=1500)
                    if el:
                        await el.click()
                        await el.fill(value)
                        filled.append(f"✅ {label_text} ← {value}")
                        success = True
                except:
                    pass

            # ── 策略 2：Element UI el-form-item ──
            if not success and label_text:
                try:
                    xpath = (
                        f'//label[contains(text(),"{label_text}")]/following-sibling::div//input | '
                        f'//span[contains(text(),"{label_text}")]/ancestor::div[contains(@class,"el-form-item")]//input'
                    )
                    el = await page.wait_for_selector(f'xpath={xpath}', state="visible", timeout=1500)
                    if el:
                        await el.click()
                        await page.wait_for_timeout(300)
                        dropdown = await page.query_selector('.el-select-dropdown:visible, .el-popper:visible')
                        if dropdown:
                            option = await dropdown.query_selector(f'li:has-text("{value}"), span:has-text("{value}")')
                            if option:
                                await option.click()
                                filled.append(f"✅ [下拉] {label_text} ← {value}")
                            else:
                                first = await dropdown.query_selector('li:first-child')
                                if first:
                                    await first.click()
                                    filled.append(f"✅ [下拉] {label_text} ← 第一个")
                                else:
                                    skipped.append(f"⚠️ 下拉无选项: {label_text}")
                        else:
                            await el.fill(value)
                            filled.append(f"✅ {label_text} ← {value}")
                        success = True
                except:
                    pass

            # ── 策略 3：label for 属性 ──
            if not success and label_text:
                try:
                    label_el = await page.query_selector(f'label:has-text("{label_text}")')
                    if label_el:
                        for_attr = await label_el.get_attribute('for')
                        if for_attr:
                            el = await page.wait_for_selector(f'#{for_attr}', state="visible", timeout=1000)
                            if el:
                                await el.click()
                                await el.fill(value)
                                filled.append(f"✅ {label_text} ← {value}")
                                success = True
                except:
                    pass

            # ── 策略 4：点击 label 文本后，Tab 切换到下一个输入框 ──
            if not success and label_text:
                try:
                    label_xpath = f'//label[contains(text(),"{label_text}")] | //span[contains(text(),"{label_text}")]'
                    label_el = await page.wait_for_selector(f'xpath={label_xpath}', state="visible", timeout=1500)
                    if label_el:
                        await label_el.click()
                        await page.wait_for_timeout(300)
                        await page.keyboard.press("Tab")
                        await page.wait_for_timeout(200)
                        await page.keyboard.type(value)
                        filled.append(f"✅ [Tab] {label_text} ← {value}")
                        success = True
                except:
                    pass

            # ── 策略 5：通用 XPath 查找最近的 input/select ──
            if not success and label_text:
                try:
                    generic_xpath = (
                        f'//*[contains(text(),"{label_text}")]/ancestor::*[self::td or self::div or self::li][1]'
                        f'//input | //*[contains(text(),"{label_text}")]/ancestor::*[self::td or self::div or self::li][1]//select'
                    )
                    el = await page.wait_for_selector(f'xpath={generic_xpath}', state="visible", timeout=1500)
                    if el:
                        await el.click()
                        await el.fill(value)
                        filled.append(f"✅ [XPath] {label_text} ← {value}")
                        success = True
                except:
                    pass

            if not success:
                skipped.append(f"⚠️ 无法定位: {label_text}")

        return filled + skipped

    async def upload_resume_file(self, page, file_path: str) -> bool:
        """上传简历附件"""
        for inp in await page.query_selector_all('input[type="file"]'):
            try:
                await inp.set_input_files(file_path)
                await page.wait_for_timeout(1000)
                print(f"✅ 已上传: {file_path}")
                return True
            except:
                continue
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
            except:
                continue
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
                # 1. 打开页面
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

                # 2. 扫描表单
                print("🔍 扫描表单...")
                form_fields = await self.scan_form_fields(page)
                print(f"   检测到 {len(form_fields)} 个字段")

                if len(form_fields) < 3:
                    await page.wait_for_timeout(5000)
                    form_fields = await self.scan_form_fields(page)
                    print(f"   重试后: {len(form_fields)} 个字段")

                print("\n📋 字段列表：")
                for f in form_fields[:15]:
                    print(
                        f"   [{f['index']}] {f['tag']}[type={f['type']}] label='{f.get('label', '')}' placeholder='{f.get('placeholder', '')}'")

                # 3. 匹配字段
                print("\n🧠 匹配字段...")
                if self.llm_api_key:
                    mappings = await self.match_fields_with_ai(form_fields, resume_data)
                else:
                    mappings = self._rule_based_match(form_fields, resume_data)
                result["filled_fields"] = len(mappings)

                # 4. 填表
                print("\n✍️ 填写表单...")
                filled = await self.fill_form(page, mappings, form_fields)
                for item in filled:
                    print(f"   {item}")
                result["steps"].extend(filled)
                result["screenshots"].append(await self.take_screenshot(page, "02_filled"))

                # 5. 上传附件
                if resume_file_path and os.path.exists(resume_file_path):
                    print(f"\n📎 上传附件: {resume_file_path}")
                    await self.upload_resume_file(page, resume_file_path)
                    result["screenshots"].append(await self.take_screenshot(page, "03_upload"))

                # 6. 人工确认
                print("\n" + "=" * 50)
                print("📱 请手动完成验证码和协议勾选")
                print("=" * 50)
                print("完成后按 Enter...")
                input()
                result["steps"].append("人工确认完成")
                result["screenshots"].append(await self.take_screenshot(page, "04_confirmed"))

                # 7. 提交
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

        print(
            f"\n📊 成功:{result['success']} | 填写:{result['filled_fields']}字段 | 截图:{len(result['screenshots'])}张")
        return result


async def quick_apply(
        job_url: str, resume_data: dict, resume_file: str | None = None,
        api_key: str | None = None, headless: bool = False,
):
    """快速投递"""
    return await AutoSubmitter(llm_api_key=api_key).apply(job_url, resume_data, resume_file, headless=headless)