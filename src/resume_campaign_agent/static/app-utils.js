(function (root, factory) {
  const api = factory();
  root.ResumeCampaignAppUtils = api;
  if (typeof module === "object" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const FIELD_META = {
    "resume.full_name": ["姓名", "fullName"],
    "resume.preferred_name": ["常用名", "preferredName"],
    "resume.city": ["当前城市", "city"],
    "resume.professional_headline": ["职业定位", "professionalHeadline"],
    "resume.email": ["邮箱", "email"],
    "resume.phone": ["电话", "phone"],
    "resume.wechat": ["微信", "wechat"],
    "resume.job_seeking_status": ["求职状态", "jobSeekingStatus"],
    "resume.target_roles": ["目标岗位 / 专业方向", "targetRoles"],
    "resume.target_industries": ["目标行业", "targetIndustries"],
    "resume.target_employer_types": ["企业类型", "targetEmployerTypes"],
    "resume.base_locations": ["意向 Base 城市", "baseLocations"],
    "resume.employment_types": ["用工类型", "employmentTypes"],
    "resume.years_experience": ["工作年限", "yearsExperience"],
    "resume.available_date": ["可到岗日期", "availableDate"],
    "resume.expected_salary": ["期望薪资", "expectedSalary"],
    "resume.relocation_preference": ["搬迁 / 调剂意愿", "relocationPreference"],
    "resume.skills": ["专业技能与工具", "skills"],
    "resume.summary": ["职业摘要", "summary"],
    "resume.hobbies": ["兴趣爱好", "hobbies"],
    "resume.self_evaluation": ["自我评价", "selfEvaluation"],
    "resume.additional_information": ["补充说明", "additionalInformation"],
    "resume.education.school": ["学校", "school"],
    "resume.education.college": ["院系", "college"],
    "resume.education.major": ["专业", "major"],
    "resume.education.minor": ["辅修 / 双学位", "minor"],
    "resume.education.degree": ["学历 / 学位", "degree"],
    "resume.education.education_type": ["学习类型", "educationType"],
    "resume.education.start_date": ["入学日期", "educationStartDate"],
    "resume.education.end_date": ["毕业日期", "educationEndDate"],
    "resume.education.graduation_year": ["毕业年份", "graduationYear"],
    "resume.education.location": ["学校所在地", "educationLocation"],
    "resume.education.gpa": ["GPA", "gpa"],
    "resume.education.gpa_scale": ["GPA 满分", "gpaScale"],
    "resume.education.rank": ["排名", "rank"],
    "resume.education.core_courses": ["核心课程", "coreCourses"],
    "resume.education.thesis": ["论文 / 毕业设计", "thesis"],
    "resume.work_experience.company": ["企业 / 机构", "company"],
    "resume.work_experience.title": ["岗位", "jobTitle"],
    "resume.work_experience.experience_type": ["经历类型", "experienceType"],
    "resume.work_experience.department": ["部门", "department"],
    "resume.work_experience.location": ["所在地", "workLocation"],
    "resume.work_experience.start_date": ["开始日期", "startDate"],
    "resume.work_experience.end_date": ["结束日期", "endDate"],
    "resume.work_experience.responsibilities": ["职责", "responsibilities"],
    "resume.work_experience.highlights": ["成果摘要", "highlights"],
    "resume.work_experience.leaving_reason": ["离职 / 结束原因", "leavingReason"],
    "resume.projects.name": ["项目名称", "projectName"],
    "resume.projects.role": ["承担角色", "projectRole"],
    "resume.projects.start_date": ["开始日期", "projectStartDate"],
    "resume.projects.end_date": ["结束日期", "projectEndDate"],
    "resume.projects.description": ["项目说明", "projectDescription"],
    "resume.projects.highlights": ["成果 / 产出", "projectHighlights"],
    "resume.projects.skills": ["相关能力", "projectSkills"],
    "resume.campus_experience.organization": ["校园组织", "campusOrganization"],
    "resume.campus_experience.role": ["校园职务", "campusRole"],
    "resume.campus_experience.description": ["校园经历说明", "campusDescription"],
    "resume.certificates.name": ["证书名称", "certificateName"],
    "resume.certificates.issuer": ["证书颁发方", "certificateIssuer"],
    "resume.certificates.score": ["证书成绩", "certificateScore"],
    "resume.language_details.language": ["语言", "language"],
    "resume.language_details.proficiency": ["熟练度", "languageProficiency"],
    "resume.language_details.test_name": ["语言考试", "languageTest"],
    "resume.language_details.score": ["语言成绩", "languageScore"],
    "resume.awards.name": ["荣誉 / 奖项", "awardName"],
    company: ["企业", "careerCompany"],
    target_company: ["企业", "careerCompany"],
    title: ["岗位", "careerTitle"],
    target_title: ["岗位", "careerTitle"],
    description: ["岗位 JD", "careerJD"],
    job_description: ["岗位 JD", "careerJD"],
    location: ["工作城市", "careerLocation"],
    url: ["官网投递 URL", "careerUrl"],
    deadline: ["截止日期", "careerDeadline"],
    target_role: ["本轮审核目标岗位", "reviewTargetRole"],
    target_job_description: ["职位描述", "reviewJobDescription"],
    question: ["面试问题", "interviewQuestion"],
    answer: ["你的回答", "interviewAnswer"],
    label: ["证据名称", "evidenceLabel"],
    values: ["敏感字段值", "vaultValue"],
  };

  const GROUP_LABELS = {
    "resume.education": "教育经历",
    "resume.work_experience": "工作 / 实习经历",
    "resume.projects": "项目 / 课题经历",
    "resume.campus_experience": "校园经历",
    "resume.certificates": "证书",
    "resume.language_details": "语言",
    "resume.awards": "荣誉 / 奖项",
  };

  function normalizeLocation(location) {
    return Array.isArray(location) ? location.filter((part) => part !== "body") : [];
  }

  function fieldForLocation(location) {
    const parts = normalizeLocation(location);
    const itemIndex = parts.find((part) => Number.isInteger(part));
    const canonical = parts.filter((part) => !Number.isInteger(part)).join(".");
    const meta = FIELD_META[canonical];
    const fallback = String(parts.at(-1) || "字段").replaceAll("_", " ");
    let label = meta?.[0] || fallback;
    const groupPath = Object.keys(GROUP_LABELS).find((path) => canonical.startsWith(`${path}.`));
    if (groupPath) {
      const itemLabel = Number.isInteger(itemIndex) ? `第 ${itemIndex + 1} 段` : "";
      label = `${GROUP_LABELS[groupPath]}${itemLabel} · ${label}`;
    }
    let fieldId = meta?.[1] || null;
    if (Number.isInteger(itemIndex) && canonical.startsWith("resume.work_experience.")) {
      fieldId = `work-${itemIndex}-${meta?.[1] || ""}`;
    } else if (Number.isInteger(itemIndex) && canonical.startsWith("resume.projects.")) {
      fieldId = `project-${itemIndex}-${meta?.[1] || ""}`;
    } else if (Number.isInteger(itemIndex) && itemIndex > 0) {
      fieldId = null;
    }
    return {
      label,
      fieldId,
    };
  }

  function validationMessage(detail) {
    const context = detail?.ctx || {};
    switch (detail?.type) {
      case "missing":
        return "不能为空";
      case "string_too_short":
        return `至少填写 ${context.min_length} 个字符`;
      case "string_too_long":
        return `最多填写 ${context.max_length} 个字符`;
      case "list_too_short":
      case "too_short":
        return `至少填写 ${context.min_length} 项`;
      case "list_too_long":
      case "too_long":
        return `最多填写 ${context.max_length} 项`;
      case "date_from_datetime_parsing":
      case "date_parsing":
      case "date_type":
        return "请输入有效日期";
      case "int_parsing":
      case "int_type":
      case "float_parsing":
      case "float_type":
        return "请输入有效数字";
      case "greater_than_equal":
        return `不能小于 ${context.ge}`;
      case "less_than_equal":
        return `不能大于 ${context.le}`;
      case "greater_than":
        return `必须大于 ${context.gt}`;
      case "less_than":
        return `必须小于 ${context.lt}`;
      case "url_parsing":
      case "url_type":
        return "请输入有效 URL";
      case "literal_error":
        return "请选择有效选项";
      case "value_error":
        if (/email address/i.test(detail.msg || "")) return "请输入有效邮箱";
        return String(detail.msg || "内容不符合要求").replace(/^Value error,\s*/i, "");
      default:
        return detail?.msg || "内容不符合要求";
    }
  }

  function describeApiError(status, body) {
    if (typeof body?.detail === "string") {
      return { message: body.detail, fieldIds: [], details: [] };
    }
    if (Array.isArray(body?.detail) && body.detail.length) {
      const details = body.detail.map((detail) => {
        const field = fieldForLocation(detail.loc);
        return { ...field, message: validationMessage(detail), detail };
      });
      const uniqueMessages = [...new Set(details.map((item) => `${item.label}：${item.message}`))];
      const visible = uniqueMessages.slice(0, 4);
      const remainder = uniqueMessages.length - visible.length;
      return {
        message: `${visible.join("；")}${remainder > 0 ? `；另有 ${remainder} 项请修正` : ""}`,
        fieldIds: [...new Set(details.map((item) => item.fieldId).filter(Boolean))],
        details,
      };
    }
    if (typeof body?.message === "string") {
      return { message: body.message, fieldIds: [], details: [] };
    }
    return { message: `请求失败（${status}）`, fieldIds: [], details: [] };
  }

  function missingResumeFields(resume) {
    const education = resume?.education?.[0];
    const rules = [
      ["full_name", "姓名", Boolean(resume?.full_name?.trim())],
      ["email", "邮箱", Boolean(resume?.email)],
      ["phone", "电话", Boolean(resume?.phone?.trim().length >= 7)],
      ["city", "当前城市", Boolean(resume?.city?.trim())],
      ["target_roles", "目标岗位 / 专业方向", Boolean(resume?.target_roles?.length)],
      ["base_locations", "意向 Base 城市", Boolean(resume?.base_locations?.length)],
      ["skills", "专业技能", Boolean(resume?.skills?.length >= 3)],
      ["summary", "职业摘要", Boolean(resume?.summary?.trim().length >= 20)],
      ["education", "教育经历", Boolean(resume?.education?.length)],
      ["education.major", "专业", Boolean(education?.major)],
      ["education.degree", "学历 / 学位", Boolean(education?.degree)],
      ["education.graduation_year", "毕业年份", Boolean(education?.graduation_year)],
      [
        "work_experience",
        "工作 / 实习经历",
        Number(resume?.years_experience || 0) <= 0 || Boolean(resume?.work_experience?.length),
      ],
    ];
    return rules
      .filter(([, , valid]) => !valid)
      .map(([field, label]) => ({
        field,
        label,
        reason: "通用简历、岗位匹配或中国网申所需字段",
      }));
  }

  return { describeApiError, fieldForLocation, missingResumeFields, validationMessage };
});
