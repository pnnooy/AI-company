# 协作规范 (Contributing Guide)

## Git 工作流

本项目采用 **GitHub Flow**：

```
main ← feature/xxx ← feature/yyy
  ↑                    ↑
  ├── PR + Review ─────┘
  └── 禁止直接 push
```

### 分支命名

| 类型 | 格式 | 示例 |
|------|------|------|
| 新功能 | `feature/<模块>-<描述>` | `feature/ai-state-machine` |
| Bug 修复 | `fix/<描述>` | `fix/uart-crc-error` |
| 文档 | `docs/<内容>` | `docs/api-reference` |
| 重构 | `refactor/<模块>` | `refactor/comm-protocol` |

### 工作流程

```bash
# 1. 从最新的 main 创建功能分支
git checkout main
git pull origin main
git checkout -b feature/my-module

# 2. 开发 + 频繁提交
git add <files>
git commit -m "feat(module): description of change"

# 3. 推送前同步 main（如果有冲突）
git pull origin main

# 4. 推送到 GitHub
git push origin feature/my-module

# 5. 在 GitHub 网页上创建 Pull Request
#    选择 base: main ← compare: feature/my-module
#    填写 PR 模板，至少指定 1 位 Reviewer

# 6. Review 通过后，由 Reviewer 或你自己点击 Merge
# 7. 删除远程 feature 分支（PR 页面会提示）
```

### Commit 规范

推荐使用约定式提交格式（英文或中文）：

```
feat(模块): 简短描述
fix(模块): 简短描述
docs: 简短描述
refactor(模块): 简短描述
```

示例：
```
feat(ai): add emotion state machine
fix(uart): correct CRC calculation for long packets
docs: add API reference for comm protocol
```

## 代码规范

### 固件 (C)
- 文件名：`snake_case`
- 函数名：`MODULE_FunctionName()`
- 禁止 `HAL_Delay()`，统一使用 `HAL_GetTick()` 非阻塞计时
- 详见 `CLAUDE.md`

### PC 后端 (Python)
- 使用 Python 3.11+
- `black` 格式化，`ruff` 检查
- 函数和变量：`snake_case`
- 类名：`PascalCase`
- 所有公共函数需有 docstring

### 前端 (TypeScript/React)
- 使用 Prettier 格式化
- 组件名：`PascalCase`
- 文件名：`kebab-case` 或 `PascalCase`（跟业界惯例）

## PR Review 清单

作为 Reviewer，检查以下内容：

- [ ] 代码逻辑正确，无明显 bug
- [ ] 符合对应模块的代码规范
- [ ] 没有多余调试代码（print/console.log）
- [ ] 新增功能有对应的测试或验证说明
- [ ] 文档已更新（如有必要）
- [ ] PR 描述清楚，关联了对应 Issue

## 求助

- 技术问题：在对应 Issue 下 @ 模块负责人
- 紧急问题：群里 @ 或私聊
