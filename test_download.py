import requests

res = requests.post(
    "http://127.0.0.1:18010/api/export/resume/word",
    json={
        "profile": {
            "full_name": "张博涵",
            "skills": ["Python", "FastAPI"],
            "education": [{"school": "测试大学", "degree": "本科", "major": "计算机", "graduation_year": 2026}]
        },
        "company": "华为",
        "position": "Python开发实习生"
    }
)

print(f"状态码: {res.status_code}")
if res.status_code == 200:
    with open("张博涵_简历.docx", "wb") as f:
        f.write(res.content)
    print("✅ 下载成功！文件保存在项目根目录：张博涵_简历.docx")
else:
    print(f"❌ 失败: {res.text}")