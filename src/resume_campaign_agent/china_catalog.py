from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEnterprise:
    name: str
    bases: tuple[str, ...]
    industries: tuple[str, ...]
    employer_type: str
    career_url: str


@dataclass(frozen=True)
class CatalogChannel:
    label: str
    url: str
    channel_type: str
    availability: str
    login_required: bool = False
    supports_job_search: bool = True
    official_evidence_url: str | None = None
    notes: str = ""


CHINA_ENTERPRISE_CATALOG: tuple[CatalogEnterprise, ...] = (
    CatalogEnterprise("中国银行", ("全国", "北京", "上海", "深圳", "广州", "成都", "武汉", "西安", "合肥"), ("银行", "金融", "金融科技"), "央企/国企", "https://www.boc.cn/aboutboc/bi4/"),
    CatalogEnterprise("中国工商银行", ("全国", "北京", "上海", "深圳", "广州", "杭州", "成都"), ("银行", "金融", "金融科技"), "央企/国企", "https://job.icbc.com.cn/"),
    CatalogEnterprise("中国建设银行", ("全国", "北京", "上海", "深圳", "广州", "成都", "武汉"), ("银行", "金融", "金融科技"), "央企/国企", "https://job.ccb.com/"),
    CatalogEnterprise("中国农业银行", ("全国", "北京", "上海", "深圳", "广州", "成都"), ("银行", "金融", "乡村金融"), "央企/国企", "https://career.abchina.com/"),
    CatalogEnterprise("交通银行", ("全国", "上海", "北京", "深圳", "广州", "武汉"), ("银行", "金融", "金融科技"), "央企/国企", "https://job.bankcomm.com/"),
    CatalogEnterprise("招商银行", ("深圳", "全国", "上海", "北京", "杭州", "成都"), ("银行", "金融", "金融科技"), "股份制/民营", "https://career.cmbchina.com/"),
    CatalogEnterprise("上海证券交易所", ("上海",), ("证券", "金融", "监管科技", "公共机构"), "事业单位/公共机构", "https://www.sse.com.cn/aboutus/recruitment/sse/"),
    CatalogEnterprise("腾讯", ("深圳", "北京", "上海", "广州", "成都", "武汉"), ("互联网", "游戏", "云计算", "内容", "金融科技"), "民营", "https://careers.tencent.com/"),
    CatalogEnterprise("字节跳动", ("北京", "上海", "深圳", "杭州", "广州", "成都"), ("互联网", "内容", "电商", "人工智能", "商业化"), "民营", "https://jobs.bytedance.com/"),
    CatalogEnterprise("阿里巴巴", ("杭州", "北京", "上海", "深圳", "广州", "成都"), ("互联网", "电商", "云计算", "物流", "本地生活"), "民营", "https://talent.alibaba.com/"),
    CatalogEnterprise("华为", ("深圳", "北京", "上海", "杭州", "成都", "武汉", "西安", "南京", "苏州"), ("通信", "ICT", "终端", "云计算", "汽车", "制造"), "民营", "https://career.huawei.com/"),
    CatalogEnterprise("百度", ("北京", "上海", "深圳", "广州"), ("互联网", "人工智能", "搜索", "自动驾驶", "云计算"), "民营", "https://talent.baidu.com/"),
    CatalogEnterprise("京东", ("北京", "上海", "深圳", "成都", "武汉"), ("电商", "物流", "零售", "科技", "供应链"), "民营", "https://zhaopin.jd.com/"),
    CatalogEnterprise("美团", ("北京", "上海", "深圳", "成都", "武汉", "广州"), ("互联网", "本地生活", "零售", "物流", "商业分析"), "民营", "https://zhaopin.meituan.com/"),
    CatalogEnterprise("小米", ("北京", "深圳", "武汉", "上海", "南京"), ("消费电子", "互联网", "智能制造", "汽车", "零售"), "民营", "https://hr.xiaomi.com/"),
    CatalogEnterprise("网易", ("杭州", "广州", "北京", "上海"), ("互联网", "游戏", "教育", "音乐", "电商"), "民营", "https://campus.163.com/"),
    CatalogEnterprise("大疆创新", ("深圳", "上海", "西安"), ("智能硬件", "无人机", "机器人", "制造", "影像"), "民营", "https://we.dji.com/"),
    CatalogEnterprise("比亚迪", ("深圳", "西安", "长沙", "合肥", "济南", "郑州"), ("汽车", "新能源", "电池", "轨道交通", "制造"), "民营", "https://job.byd.com/"),
    CatalogEnterprise("上汽集团", ("上海", "南京", "郑州"), ("汽车", "新能源", "智能制造", "供应链"), "地方国企", "https://career.saicmotor.com/"),
    CatalogEnterprise("宁德时代", ("宁德", "上海", "深圳", "溧阳", "宜宾"), ("新能源", "电池", "汽车", "材料", "制造"), "民营", "https://talent.catl.com/"),
    CatalogEnterprise("美的集团", ("佛山", "深圳", "上海", "合肥", "无锡"), ("家电", "机器人", "智能制造", "供应链", "消费品"), "民营", "https://careers.midea.com/"),
    CatalogEnterprise("海尔集团", ("青岛", "上海", "北京", "深圳"), ("家电", "智能制造", "物联网", "供应链", "消费品"), "民营", "https://maker.haier.net/"),
    CatalogEnterprise("联想", ("北京", "上海", "深圳", "武汉", "合肥"), ("计算机", "智能设备", "企业服务", "供应链", "制造"), "民营", "https://jobs.lenovo.com/"),
    CatalogEnterprise("携程集团", ("上海", "北京", "南通", "成都"), ("旅游", "互联网", "客户服务", "商业分析", "市场"), "民营", "https://careers.trip.com/"),
    CatalogEnterprise("顺丰", ("深圳", "全国", "武汉", "杭州", "上海"), ("物流", "供应链", "航空", "零售科技"), "民营", "https://hr.sf-express.com/"),
    CatalogEnterprise("中国移动", ("全国", "北京", "上海", "深圳", "广州", "成都"), ("通信", "云计算", "市场营销", "客户运营", "数字化"), "央企/国企", "https://job.10086.cn/"),
    CatalogEnterprise("中国电信", ("全国", "北京", "上海", "广州", "成都", "武汉"), ("通信", "云计算", "网络安全", "市场营销", "客户运营"), "央企/国企", "https://job.chinatelecom.com.cn/"),
    CatalogEnterprise("国家电网", ("全国", "北京", "上海", "南京", "武汉", "成都"), ("能源", "电力", "电气", "数字化", "公共服务"), "央企/国企", "https://zhaopin.sgcc.com.cn/"),
    CatalogEnterprise("中国石化", ("全国", "北京", "上海", "南京", "青岛"), ("能源", "化工", "材料", "工程", "贸易"), "央企/国企", "https://job.sinopec.com/"),
    CatalogEnterprise("中国中车", ("北京", "株洲", "长春", "青岛", "南京", "成都"), ("轨道交通", "装备制造", "机械", "电气", "供应链"), "央企/国企", "https://www.crrcgc.cc/rczp"),
    CatalogEnterprise("国药集团", ("北京", "上海", "武汉", "广州"), ("医药", "医疗器械", "供应链", "研发", "零售"), "央企/国企", "https://www.sinopharm.com/rlzy/rczp/"),
    CatalogEnterprise("复星", ("上海", "北京", "深圳", "广州"), ("医药", "保险", "消费", "文旅", "投资"), "民营", "https://career.fosun.com/"),
    CatalogEnterprise("迈瑞医疗", ("深圳", "北京", "上海", "南京", "武汉"), ("医疗器械", "医药", "研发", "制造", "国际营销"), "民营", "https://career.mindray.com/"),
    CatalogEnterprise("康弘药业", ("成都", "北京", "上海", "广州"), ("医药", "生物制品", "医疗器械", "市场营销", "制造"), "民营", "https://www.cnkh.com/"),
    CatalogEnterprise("埃森哲中国", ("上海", "北京", "大连", "广州", "深圳", "成都"), ("咨询", "技术服务", "智能运营", "数字化", "商业分析"), "外企", "https://www.accenture.cn/cn-zh/careers/local/accenture-china-campus-page"),
)


KNOWN_OFFICIAL_DOMAINS = {
    entry.career_url.split("/")[2].casefold() for entry in CHINA_ENTERPRISE_CATALOG
}


# These overrides separate an official announcement from the system that actually accepts
# a resume. Seasonal portals are retained as evidence but are never presented as currently open.
APPLICATION_CHANNEL_OVERRIDES: dict[str, tuple[CatalogChannel, ...]] = {
    "中国银行": (
        CatalogChannel(
            "招聘公告与当期入口",
            "https://www.boc.cn/aboutboc/bi4/",
            "official_announcement",
            "entry_hub",
            notes="先打开最新公告；中行会在当期公告中指定唯一报名网站。",
        ),
        CatalogChannel(
            "2026 春招/实习报名系统（已结束）",
            "https://campus.chinahr.com/pages/boc-2026-Spring/",
            "designated_application_system",
            "seasonal_closed",
            login_required=True,
            official_evidence_url="https://www.boc.cn/aboutboc/bi4/202603/t20260311_25654053.html",
            notes="官方公告指定入口；报名已于 2026-03-30 截止，仅用于验证报名路径。",
        ),
    ),
    "中国工商银行": (
        CatalogChannel("工行人才招聘", "https://job.icbc.com.cn/", "official_career_home", "entry_hub", True, True, notes="在站内按招聘类型、机构和工作地点筛选后投递。"),
    ),
    "中国建设银行": (
        CatalogChannel("建行人才招聘", "https://job.ccb.com/", "official_career_home", "entry_hub", True, True, notes="进入公告或岗位列表后注册并完善简历。"),
    ),
    "中国农业银行": (
        CatalogChannel("农行招聘", "https://career.abchina.com/", "official_career_home", "entry_hub", True, True, notes="按校园招聘、社会招聘和分支机构查询。"),
    ),
    "交通银行": (
        CatalogChannel("交行人才招聘", "https://job.bankcomm.com/", "official_career_home", "entry_hub", True, True, notes="按招聘项目、机构与 Base 查询岗位。"),
    ),
    "招商银行": (
        CatalogChannel("招商银行校园招聘", "https://career.cmbchina.com/campus/home", "campus_portal", "entry_hub", True, True, notes="面向应届生与实习生，站内登录后投递。"),
        CatalogChannel("招商银行社会招聘", "https://career.cmbchina.com/social/home", "social_portal", "openings_live", True, True, notes="当前页面展示各分行社会招聘公告与投递岗位。"),
    ),
    "上海证券交易所": (
        CatalogChannel("上交所招聘信息", "https://www.sse.com.cn/aboutus/recruitment/sse/", "official_announcement", "entry_hub", False, True, notes="先核对当期员工、实习或社招公告中的报名截止日期。"),
        CatalogChannel("上交所 2026 指定投递系统（已结束）", "https://ideal.51job.com/sse2026", "designated_application_system", "seasonal_closed", True, True, official_evidence_url="https://www.sse.com.cn/aboutus/recruitment/sse/wanted/c/c_20260122_10806234.shtml", notes="官方公告指定入口；2026 员工招聘已于 2026-03-08 截止。"),
    ),
    "腾讯": (
        CatalogChannel("腾讯招聘", "https://careers.tencent.com/", "official_career_home", "openings_live", True, True, notes="在官网切换校园招聘或社会招聘并按城市筛选。"),
    ),
    "字节跳动": (
        CatalogChannel("字节跳动招聘", "https://jobs.bytedance.com/", "official_career_home", "openings_live", True, True, notes="支持按职位类别、城市和招聘类型查询。"),
    ),
    "阿里巴巴": (
        CatalogChannel("阿里巴巴人才招聘", "https://talent.alibaba.com/", "official_career_home", "openings_live", True, True, notes="登录后按业务、职类与地点检索。"),
    ),
    "华为": (
        CatalogChannel("华为招聘", "https://career.huawei.com/", "official_career_home", "openings_live", True, True, notes="官网覆盖校园招聘、社会招聘和实习生招聘。"),
    ),
    "国家电网": (
        CatalogChannel("国家电网招聘平台", "https://zhaopin.sgcc.com.cn/", "official_career_home", "entry_hub", True, True, notes="按批次、单位和专业申报；以当期公告资格条件为准。"),
    ),
}


def application_channels_for(entry: CatalogEnterprise) -> tuple[CatalogChannel, ...]:
    override = APPLICATION_CHANNEL_OVERRIDES.get(entry.name)
    if override:
        return override
    return (
        CatalogChannel(
            label=f"{entry.name}官方招聘",
            url=entry.career_url,
            channel_type="official_career_home",
            availability="check_required",
            login_required=True,
            supports_job_search=True,
            notes="已收录官方招聘入口；需在官网核对当期岗位、截止日期与登录方式。",
        ),
    )
