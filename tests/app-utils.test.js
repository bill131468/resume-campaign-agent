const test = require("node:test");
const assert = require("node:assert/strict");

const {
  describeApiError,
  fieldForLocation,
  missingResumeFields,
  validationMessage,
} = require("../src/resume_campaign_agent/static/app-utils.js");

test("formats Pydantic resume validation details and maps the first form section", () => {
  const result = describeApiError(422, {
    detail: [
      {
        type: "string_too_short",
        loc: ["body", "resume", "work_experience", 0, "title"],
        msg: "String should have at least 2 characters",
        ctx: { min_length: 2 },
      },
      {
        type: "date_from_datetime_parsing",
        loc: ["body", "resume", "work_experience", 0, "start_date"],
        msg: "Input should be a valid date or datetime, input is too short",
      },
    ],
  });

  assert.equal(
    result.message,
    "工作 / 实习经历第 1 段 · 岗位：至少填写 2 个字符；工作 / 实习经历第 1 段 · 开始日期：请输入有效日期",
  );
  assert.deepEqual(result.fieldIds, ["jobTitle", "startDate"]);
});

test("maps career request aliases without claiming that optional URL is required", () => {
  const result = describeApiError(422, {
    detail: [
      {
        type: "string_too_short",
        loc: ["body", "job_description"],
        msg: "String should have at least 10 characters",
        ctx: { min_length: 10 },
      },
    ],
  });

  assert.equal(result.message, "岗位 JD：至少填写 10 个字符");
  assert.deepEqual(result.fieldIds, ["careerJD"]);
  assert.equal(result.message.includes("URL"), false);
});

test("does not focus a later array item that the current single-entry UI cannot edit", () => {
  assert.deepEqual(
    fieldForLocation(["body", "resume", "education", 1, "major"]),
    { label: "教育经历第 2 段 · 专业", fieldId: null },
  );
});

test("preserves explicit API errors and provides a status fallback", () => {
  assert.deepEqual(describeApiError(404, { detail: "session not found" }), {
    message: "session not found",
    fieldIds: [],
    details: [],
  });
  assert.equal(describeApiError(503, {}).message, "请求失败（503）");
  assert.equal(validationMessage({ type: "url_parsing" }), "请输入有效 URL");
});

test("translates the actual Pydantic email and list length error types", () => {
  assert.equal(
    validationMessage({
      type: "value_error",
      msg: "value is not a valid email address: An email address must have an @-sign.",
    }),
    "请输入有效邮箱",
  );
  assert.equal(
    validationMessage({ type: "too_long", ctx: { max_length: 30 } }),
    "最多填写 30 项",
  );
});

test("checks the same resume fields that the workbench marks as required", () => {
  const complete = {
    full_name: "测试用户",
    email: "user@example.com",
    phone: "13800000000",
    city: "上海",
    target_roles: ["产品经理"],
    base_locations: ["上海"],
    skills: ["需求分析", "SQL", "原型设计"],
    summary: "具备真实项目经验，能够完成需求分析、跨团队协作与项目交付。",
    education: [{ school: "测试大学", major: "信息管理", degree: "本科", graduation_year: 2026 }],
    years_experience: 0,
    work_experience: [],
  };

  assert.deepEqual(missingResumeFields(complete), []);
  const missing = missingResumeFields({
    ...complete,
    summary: "太短",
    education: [{ ...complete.education[0], degree: "", graduation_year: 0 }],
    years_experience: 1,
  }).map((item) => item.field);
  assert.deepEqual(missing, [
    "summary",
    "education.degree",
    "education.graduation_year",
    "work_experience",
  ]);
});
