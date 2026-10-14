# ClueTide

**Approve an exact release. Verify what shipped.**

面向 Web3 团队的 AI Agent 发布协作与交付核验工具。Agent 准备项目页面与测试证据，指定合作方审阅准确版本、批准或签署更正要求，Agent 修订后重新审阅，执行方一次启动受控发布，各方独立核验交付。

- [产品首页](https://cluetide.vercel.app/)
- [完整主网验收任务 · v3](https://cluetide.vercel.app/#/task/0x0fd2d90c3d351480ce7d8de15c62285610d40fa532f31b872777fe0528901b02?version=3)
- [回传正文](submission.txt)
- [结构化主网证据](mainnet-evidence.json)
- [完整任务验收包](evidence/complete-mainnet/acceptance-v3.zip)

## 产品与链上价值

修改形成新版本和摘要，需要指定审阅方重新批准；一次批准只授予一次启动；签名更正把准确版本和具体修改要求交给 Agent；产物与回执可以带离产品独立核验。BOT Mainnet 记录角色、版本、决定、启动和回执承诺。原件与意见在链下保存，公开共享时明确说明材料会公开。

核验分为原件/签名、当前链上承诺、实际下载产物三项。文件一致性和执行器声明各有范围，业务质量由测试和人工审阅判断。当前执行目标为隔离目录内单个最多 32 KiB 的 UTF-8 HTML。

## 真实主网证据

网络为 BOT Chain Mainnet 677，见证合约 [0xca71b77708674f5f2407c0ad4e599eaf5eb07281](https://scan.botchain.ai/address/0xca71b77708674f5f2407c0ad4e599eaf5eb07281)。公开页面提供 Connect Wallet；本轮真实钱包验收使用 MetaMask，两个角色账户由同一持有人控制。每笔主网操作均由持有人确认费用及签名。

| 验收 | 实际结果 | 证据 |
| --- | --- | --- |
| 完整协作任务 | 九笔交易、签名反馈、v3 发布、最终回执登记；0.02004582 BOT | [台账](evidence/complete-mainnet/transactions.json)、[原始回执](evidence/complete-mainnet/receipt-response-v3.json)、[验收 ZIP](evidence/complete-mainnet/acceptance-v3.zip) |
| 跨浏览器补充任务 | 八笔交易、签名反馈、另一浏览器恢复 attempt 1 并实际发布；最终回执待登记；0.01835736 BOT | [台账](evidence/cross-browser-publication/transactions.json)、[成果 ZIP](evidence/cross-browser-publication/acceptance-v3-receipt-pending.zip) |

验收包的离线核验在网络调用立即失败条件下通过，当前链与在线产物需要另作在线检查。主网状态在 2026-10-14T16:16:16+08:00 重新回读，完整任务回执和实际产物保持原字节。原始 JSON 中的确认数是各文件生成时的观察。

## 使用与本地运行

首页优先导入 Agent 包，也可选择 Prepare a browser release。匿名检查文件后，按 Your next step 连接所需角色账户；审阅更正完成后，Agent 读取 feedback / wait 状态，再 export 下一版。恢复使用原包和启动交易 Hash。

Python 3.12、Node.js 24：

```sh
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cd frontend
npm ci
npm test
npm run build
cd ..
.venv/bin/python -m uvicorn cluetide.release_server:app --host 127.0.0.1 --port 8787
```

Windows 使用 `.venv/Scripts/python.exe`，或 `scripts/run-local.ps1`。完整安装配置见 [getting started](docs/getting-started.md)、[首次使用与恢复](docs/first-use-and-recovery.md)、[Vercel 部署](docs/vercel-deployment.md)。生产签名身份和数据库由部署环境配置，独立部署需使用自己的身份和数据库。

## 源码来源与维护

本仓库收录已部署源码及公开验收材料。线上生产源码来源于 [cluetide-review 的 1655aa8](https://github.com/HNNUYUXUAN/cluetide-review/commit/1655aa887fadf30bbdf8a0ce9dfbe02c2b0a1609)；执行代码、前端、合约和测试保持该版字节。Vercel 生产部署继续关联原发布仓库。本仓库 main 作为本次独立审核入口。

- [部署源码原始清单](provenance/deployed-source-manifest-1655aa8.json)
- [当前仓库文件清单](source-manifest.json)
- [Agent 协作说明](docs/collaboration-guide.md)
- [合约源码](contracts/ClueTideReleaseWitness.sol)
- [MIT 许可](LICENSE)与 [浏览器依赖许可](frontend/public/licenses/BROWSER-DEPENDENCIES.txt)

已部署源码的重建记录为 246 Python／75 前端／17 启动检查通过；原 GitHub CI 为 257 Python 通过、2 平台跳过。此独立仓库的 CI 结果以本仓库 Actions 为准。视频未作为已核验公开证据。
