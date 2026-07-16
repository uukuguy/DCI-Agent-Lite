# Asterion 文档导航

这里是 Asterion 框架、DCI 能力产品和验证资料的统一入口。第一次使用时不需要读源码，按目的选择文档即可。

## 我想直接使用或验证 DCI

- [能力包使用指南](guides/asterion-capability-usage.md)：从共享 `.env`、功能发现到四级验证命令，适合第一次运行。
- [Asterion DCI 完整产品参考](guides/asterion-dci-complete-reference.md)：逐项解释单次研究、恢复、Context Management、Judge、benchmark、分析、导出和证据状态。
- [完整功能验证指南](verification/asterion-dci-validation-guide.md)：原 DCI 两个基础示例、Asterion 对照、provider-free 全产品矩阵、有界 Pi/Judge 和仓库门禁。

## 我想理解或扩展 Asterion

- [框架与能力包接入指南](architecture/asterion-framework-capability-integration.md)：解释 runtime、adapter、package、capability、assembly、application、provider、host service 和 CLI，并给出完整接入模板。
- [框架总体设计](architecture/agent-framework.md)：Asterion 的长期架构目标和范围边界。
- [应用执行器](architecture/application-runner.md)、[能力执行](architecture/capability-execution.md)、[可组合 package](architecture/composable-packages.md)：各层的详细契约。
- [受控执行器运维](operator/rust-executor.md)：Rust sidecar 的策略和运行边界。

## 我想把 Asterion 独立成项目

- [Asterion 独立项目拆分指南](architecture/asterion-standalone-extraction.md)：自包含清单、外部依赖、目标目录、七阶段迁移、发布门禁、回滚和 DCI 插件决策门。

## 先记住四种证据状态

- **Implemented**：代码和入口存在。
- **Verified**：指定验证在记录的边界内实际通过。
- **External-limited**：Asterion 已正确处理边界，但能力受当前外部 Pi、数据、服务或凭据限制。
- **Not rerun**：实现存在，但完整数据集或已发表分数没有在本轮重新运行。

因此，“Asterion 已实现 benchmark 产品面”和“已经重新复现论文的完整 benchmark 分数”是两件事。当前完整参考会逐项标注，不用完成度记录代替运行证据。
