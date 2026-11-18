# Aestitch · 由 Suatlora 创建

**发现你的审美，把灵感变成设计契约，并在反复开发中保留设计意图。**

Aestitch v0.2.0 是一个本地优先的 Agent Skill 与命令行工具。它**不是**自动美化网站的模型，也不能直接从截图理解你的审美、替代用户做最终设计判断。

## 首版已实现的能力

- **Reference Intelligence 的基础**：记录 URL 元数据或复制你提供的本地截图，保存参考重点和观察；不会自动访问或解析网页。
- **Taste Discovery 的基础**：记录成对参考的选择，允许“都喜欢 / 都不喜欢 / 不确定”，保留场景，不武断生成固定风格标签。
- **Design Contract**：把页面目标、创意方向、参考 ID 和实现范围保存为 JSON，并输出可交给 Codex、Claude Code 等工具的 Markdown。正式批准要求显式确认和项目内的原型截图证据。
- **Architecture Guardian 的第一步**：通过源码文件 SHA-256 快照，检查本轮增加、删除、修改的文件，越界修改和新增 package.json 依赖；这不是完整复杂度分析。
- **Visual Guardian（保留 v0.1）**：真实浏览器桌面/移动截图、像素差异、横向溢出与基础错误诊断。像素差异不是美学评分。

## Windows / PowerShell

仓库地址：<https://github.com/kanannaku/Aestitch-skill>

```powershell
cd F:\Projects
git clone https://github.com/kanannaku/Aestitch-skill.git
cd .\Aestitch-skill
uv sync --extra all
uv run python -m playwright install chromium
uv run aestitch doctor
```

请在目标网站项目下执行命令（将 `PATH_TO_AESTITCH` 替换为本地真实路径），例如：

```powershell
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py init
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py reference add --label "排版参考" --url "https://example.org" --focus typography --context homepage
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py reference list
# 先参考实际返回的 ref-ID，再执行 taste compare
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py taste report
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py contract create --page home --goal "展示项目" --direction "编辑式构图" --scope "app/page.tsx"
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py contract show --page home
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py scope snapshot --tag homepage-v1
# 修改文件后，检查范围：
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py scope check --tag homepage-v1 --allow app/page.tsx --max-added 0 --max-changed 2
```

在其他目录执行时，将 `--root F:\Projects\your-site` 放在子命令之前。请以 `--help` 和英文 README 为准查看完整参数。

## 重要限制

- URL 只作为参考记录；工具不会自动下载、复刻或分析网页。
- 反馈只能代表当前用户在指定场景的选择；目前不具备自动风格学习能力。
- Design Contract 依靠用户和 Agent 正确填写；`--user-confirmed` 只是操作者声明，不能代替真实授权。
- Scope 检测只处理小于 2MB 的受支持源码文件及 package.json 依赖名称，不是代码质量评分，必须继续使用原有 lint/build/test。
- `.aestitch/` 默认 Git 忽略，包含偏好、截图和设计契约；分享前请仔细审核隐私。
- **不要在正式个人网站上直接冒险测试。** 先在独立小项目中验证效果，并遵循 [对照实验协议](examples/evaluation-protocol.md)。目前尚无 Aestitch 优于其他 Skill 的实验结果。

完整流程参见 [SKILL.md](skills/aestitch/SKILL.md) 与 [English README](README.md)。
