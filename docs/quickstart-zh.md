# 中文快速入门

ClueTide 解决协作发布中的三个问题：批准了哪一版、谁有权发布、实际交付了哪些字节。v0.2.0 提供独立验收工具和完整本地 EOA／Safe 演示。

## 查看历史案例

下载 `evidence/complete-mainnet/acceptance-v3.zip`。这是 BOT 主网 677、Witness v1 的三版本案例，原记录时间为 2026-10-14 05:16:22 UTC。原始 ZIP、manifest、旧合约源码与构建产物保留原字节。

```sh
python -m pip install .
cluetide-release verify evidence/complete-mainnet/acceptance-v3.zip
```

默认离线，不启动服务器或数据库。离线成功表示原件和 EOA 签名通过，不表示刚刚查询了链或当前网站。

## 一条命令启动

准备 Python 3.12，在 x86-64 Windows 或 Linux 上运行：

```sh
python scripts/demo.py
```

首次需要网络下载固定工具及依赖。打开 http://127.0.0.1:8787 。程序只绑定回环地址，使用 Anvil 31337 和公开测试身份，不需要 Docker、浏览器钱包或真实资产。

1. Task owner：新建 EOA 或 Safe 任务。
2. Proposer：提交 v1 原始 HTML 和摘要。
3. Reviewer：请求更正并签署反馈。Safe 先准备交易，由两位 owner 签名，再执行。
4. Proposer：修改 HTML，提交修订版本。
5. Reviewer：准确批准新版本；Safe 同样需要两签。
6. Executor：依次消费授权、发布、登记签名回执。
7. Independent verifier：离线验收、核验本地链与当前交付、下载 ZIP，并测试单字节篡改拒绝。

角色选择是测试操作入口，实际交易仍由对应测试地址发送并受合约校验。刷新恢复任务和链状态。`Publish / recover` 复用原消费记录，不会盲目再次发布。

```sh
cluetide-release verify cluetide-local-v2.zip --deployment deployment.json
cluetide-release verify cluetide-local-v2.zip --deployment deployment.json --online
```

部署配置需要作为独立可信来源核对。Safe 反馈离线显示 `requires_chain_state`，联网时在记录区块执行 ERC-1271 校验。真实网络 v2 部署和生产写入切换见 [迁移说明](deployment-v2.md)。
