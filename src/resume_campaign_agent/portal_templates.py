from __future__ import annotations

from .models import PortalFieldRequirement, PortalTemplate


def _field(
    field: str,
    label: str,
    section: str,
    required: bool,
    storage_policy: str = "master_resume",
    *,
    sensitive: bool = False,
    notes: str = "",
) -> PortalFieldRequirement:
    return PortalFieldRequirement(
        field=field,
        label=label,
        section=section,
        required=required,
        storage_policy=storage_policy,
        sensitive=sensitive,
        notes=notes,
    )


UNIVERSAL_CN_FIELDS = [
    _field("full_name", "姓名", "基本信息", True),
    _field("preferred_name", "常用名", "基本信息", False),
    _field("phone", "手机", "联系方式", True),
    _field("email", "邮箱", "联系方式", True),
    _field("wechat", "微信", "联系方式", False, sensitive=True),
    _field("city", "当前城市", "基本信息", True),
    _field("professional_headline", "职业定位", "求职意向", False),
    _field("job_seeking_status", "求职状态", "求职意向", False),
    _field("target_roles", "目标岗位/专业方向", "求职意向", True),
    _field("target_industries", "目标行业", "求职意向", False),
    _field("target_employer_types", "企业类型偏好", "求职意向", False),
    _field("base_locations", "意向 Base 城市", "求职意向", True),
    _field("employment_types", "全职/实习/校招/社招", "求职意向", False),
    _field("available_date", "可到岗日期", "求职意向", False),
    _field("expected_salary", "期望薪资", "求职意向", False),
    _field("relocation_preference", "搬迁/调剂意愿", "求职意向", False),
    _field("work_authorization", "工作许可", "求职意向", False, sensitive=True),
    _field("education.school", "学校", "教育经历", True),
    _field("education.college", "院系", "教育经历", False),
    _field("education.degree", "学历/学位", "教育经历", True),
    _field("education.major", "主修专业", "教育经历", True),
    _field("education.minor", "辅修/双学位", "教育经历", False),
    _field("education.start_date", "入学日期", "教育经历", False),
    _field("education.end_date", "毕业日期", "教育经历", True),
    _field("education.education_type", "全日制/非全日制等学习类型", "教育经历", False),
    _field("education.gpa", "GPA 与满分", "教育经历", False),
    _field("education.rank", "年级/专业排名", "教育经历", False),
    _field("education.core_courses", "主修课程与成绩", "教育经历", False),
    _field("education.thesis", "论文/毕业设计", "教育经历", False),
    _field("work_experience", "全职工作经历", "经历", False),
    _field("work_experience.experience_type", "经历类型", "经历", False),
    _field("work_experience.department", "部门", "经历", False),
    _field("work_experience.responsibilities", "职责", "经历", False),
    _field("work_experience.highlights", "可核实成果", "经历", False),
    _field("work_experience.leaving_reason", "离职原因", "经历", False),
    _field("projects", "项目/作品/课题", "能力证据", False),
    _field("campus_experience", "校园/社团活动", "能力证据", False),
    _field("volunteer_experience", "志愿服务", "能力证据", False),
    _field("skills", "专业技能", "能力证据", True),
    _field("certificates", "职业/资格/IT证书", "能力证据", False),
    _field("language_details", "语言与考试成绩", "能力证据", False),
    _field("awards", "荣誉与奖惩", "能力证据", False),
    _field("publications", "论文/发表", "能力证据", False),
    _field("patents", "专利", "能力证据", False),
    _field("portfolio_url", "作品集/个人主页", "能力证据", False),
    _field("summary", "职业摘要", "自述", True),
    _field("self_evaluation", "自我评价", "自述", False),
    _field("hobbies", "兴趣爱好", "自述", False),
    _field("additional_information", "补充说明", "自述", False),
]


PORTAL_ONLY_BOC_FIELDS = [
    _field("application_category", "应聘类别/应届身份", "中行岗位问题", True, "portal_only"),
    _field("willing_to_transfer", "是否接受岗位或地区调剂", "中行岗位问题", True, "portal_only"),
    _field("transfer_locations", "调剂意向地区", "中行岗位问题", False, "portal_only"),
    _field("photo", "证件照", "中行个人信息", True, "prepare_only", sensitive=True, notes="仅在官方招聘门户上传。"),
    _field("identity_document", "证件类型与号码", "中行个人信息", True, "portal_only", sensitive=True),
    _field("gender", "性别", "中行个人信息", True, "portal_only", sensitive=True),
    _field("date_of_birth", "出生日期", "中行个人信息", True, "portal_only", sensitive=True),
    _field("nationality", "国籍", "中行个人信息", True, "portal_only", sensitive=True),
    _field("ethnicity", "民族", "中行个人信息", False, "portal_only", sensitive=True),
    _field("political_status", "政治面貌", "中行个人信息", False, "portal_only", sensitive=True),
    _field("marital_status", "婚姻状况", "中行个人信息", True, "portal_only", sensitive=True),
    _field("height", "身高", "中行个人信息", True, "portal_only", sensitive=True),
    _field("hukou_location", "当前户籍所在地", "中行个人信息", True, "portal_only", sensitive=True),
    _field("hukou_type", "户籍类型", "中行个人信息", True, "portal_only", sensitive=True),
    _field("student_origin", "生源地/生活基础所在地", "中行个人信息", True, "portal_only", sensitive=True),
    _field("home_address", "家庭地址", "中行个人信息", True, "portal_only", sensitive=True),
    _field("emergency_contact", "紧急联系人与电话", "中行个人信息", True, "portal_only", sensitive=True),
    _field("education.student_id", "学号", "中行教育背景", False, "portal_only", sensitive=True),
    _field("poverty_status", "专项招聘相关身份及证明", "中行补充资料", False, "portal_only", sensitive=True),
    _field("family_members", "父母/配偶等家庭成员信息", "中行家庭成员", True, "portal_only", sensitive=True),
    _field("relatives_at_boc", "是否有亲属受雇于中国银行", "中行家庭成员", True, "portal_only", sensitive=True),
    _field("discipline_and_rewards", "成果、奖励与处分情况", "中行其他情况", False, "portal_only", sensitive=True),
]


PORTAL_TEMPLATES = {
    "universal-cn": PortalTemplate(
        id="universal-cn",
        name="中国企业通用主简历",
        organization="通用",
        evidence_level="official_plus_application_guide",
        source_urls=[
            "https://www.boc.cn/aboutboc/bi4/202603/t20260311_25654053.html",
            "https://www.sse.com.cn/aboutus/recruitment/sse/",
        ],
        fields=UNIVERSAL_CN_FIELDS,
        application_rules=[
            "主简历只保存可跨企业复用的事实字段。",
            "岗位门户新增问题需按企业和岗位单独回答。",
            "证件、家庭关系等敏感信息只在核验过的官方门户临时填写。",
        ],
        privacy_notice="遵循最小化原则，不在通用模板中长期保存证件号、家庭住址、婚姻、户籍或家庭成员信息。",
    ),
    "boc-campus-2026-reference": PortalTemplate(
        id="boc-campus-2026-reference",
        name="中国银行 2026 网申字段参考",
        organization="中国银行",
        evidence_level="official_plus_application_guide",
        source_urls=[
            "https://www.boc.cn/aboutboc/bi4/202509/t20250905_25484753.html",
            "https://www.boc.cn/aboutboc/bi4/202603/t20260311_25654053.html",
            "https://yinhangzhaopin.com/yhkpzs/yingjiesheng/214595.html",
            "https://hefei.huatu.com/zt/zgyhjlmb/",
        ],
        fields=[*UNIVERSAL_CN_FIELDS, *PORTAL_ONLY_BOC_FIELDS],
        application_rules=[
            "官方公告要求准确、完整填写简历和相关资料并保证真实性。",
            "同一家一级机构最多申请 1 个岗位，每人最多申请 4 个岗位；以当期公告为准。",
            "手机和电子邮件必须准确并保持畅通。",
            "岗位可能追加是否接受地区/岗位调剂、应届身份等问题。",
            "详细字段来自当期网申指南与参考模板，实际门户可能调整，投递前必须再次核对。",
        ],
        privacy_notice="证件、户籍、住址、婚姻、身高、家庭成员和亲属关系属于敏感门户字段，本系统只提醒准备，不集中保存其值。",
    ),
}


def list_portal_templates() -> list[PortalTemplate]:
    return list(PORTAL_TEMPLATES.values())


def get_portal_template(template_id: str) -> PortalTemplate | None:
    return PORTAL_TEMPLATES.get(template_id)

