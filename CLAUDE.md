# CLAUDE.md

本文件内容见 [AGENTS.md](./AGENTS.md)。

本仓库的权威工作指引、项目梗概、权威文档清单与开发约束均以 AGENTS.md 为准。开始工作前请先阅读 AGENTS.md，以及当前任务直接引用的设计文档。

当前正式用户接口直接使用 `kflow init`、`kflow add-node` 等顶层命令；`v2` 是内部实现版本，不是用户命令层级。旧 v1 接口仅通过 `kflow legacy` 显式访问。
