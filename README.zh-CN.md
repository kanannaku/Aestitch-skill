# Aestitch（由 Suatlora 创建）

**Your taste. Your design. Every iteration.**

Aestitch 是面向 Codex、Claude Code 等编码 Agent 的个人化设计记忆与视觉变更检查 Skill。

它不是「一键变好看」提示词，也不声称能自动判断美学优劣。首版解决两个问题：

1. **Design Memory**：仅把用户明确确认的喜欢/不喜欢记录为可编辑的项目级偏好。
2. **Design Guardian**：使用浏览器真实截图建立基线，比较修改前后变化，生成差异图片与审查报告。

## Windows / PowerShell 使用

请在你的网站项目根目录打开终端，用真正的 Aestitch 路径替换以下的 `PATH_TO_AESTITCH`：

```powershell
python -m pip install pillow playwright
python -m playwright install chromium

python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py init
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py record --kind avoid --axis color --note "不要默认蓝紫渐变" --context "首页"
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py brief

# 先按项目本身的说明启动 Next.js 开发服务器，默认这里示例 3000 端口
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py capture --url http://127.0.0.1:3000 --tag baseline
# 修改完成后：
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py capture --url http://127.0.0.1:3000 --tag candidate
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py guard
```

输出默认位于网站项目的 `.aestitch/` 目录，包含 `profile.json`、截图以及 `reports/guard-report.md`。该目录内默认附带 `.gitignore`，防止个人偏好和截图被意外提交。不会读取 API Key，不会上传你的页面，不会修改你的网站代码。

`capture` 只允许 localhost；远程网页需要显式 `--allow-remote`。也支持 `--html-file .\prototype.html` 来渲染项目内部、自包含样式的离线 HTML 原型。`guard` 的差异数值表示**变化多少**，并非**好看多少**。屏幕高度不同也会报告需要人工核验。

详细架构、局限和路线图见 [English README](README.md)；Agent 工作流程见 [SKILL.md](skills/aestitch/SKILL.md)。
