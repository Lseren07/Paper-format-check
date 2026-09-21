# 论文格式检测系统

本项目按《论文格式检测系统技术设计文档 V1.0》建立本地开发环境。当前目录保留了产品原型 `paper-checker-prototype`，并新增前后端工程配置骨架。

## Docker 一键运行（推荐协作者）

适合 Windows Docker Desktop。构建后只对外开放本机 80 端口，浏览器访问 http://127.0.0.1/ 即可；/api 由 nginx 转发到后端，前后端同源。

### 前置条件

- 已安装并启动 Docker Desktop
- 本机 80 端口未被 IIS 或其他网站占用

### 启动

在仓库根目录执行：

```powershell
docker compose up --build
```

- 页面：http://127.0.0.1/
- API 文档：http://127.0.0.1/docs
- 健康检查：http://127.0.0.1/api/v1/health

停止：在该终端按 Ctrl+C，或另开终端执行 docker compose down。

uploads/ 与 reports/ 会挂载到仓库目录，容器删除后仍保留。任务状态仍在内存中，重启后旧 task_id 会失效，但已生成的 PDF 还在。

### 常见问题

- 80 端口被占用：把 docker-compose.yml 里的 80:80 改成 8080:80，改访问 http://127.0.0.1:8080/
- 首次构建需要联网拉取基础镜像和中文字体包
- 仓库路径含中文时，请使用较新的 Docker Desktop（WSL2 后端）

## 本机开发（不使用 Docker）

## 环境版本

- Python 3.12.x
- FastAPI 0.115.x
- Pydantic 2.10.x
- SQLAlchemy 2.0.x
- python-docx 1.1.2
- Node.js 20 LTS
- React 18.3.x
- TypeScript 5.x
- Vite 6.x

仓库根目录的 `.nvmrc` 固定了 Node 20。用 [fnm](https://github.com/Schniz/fnm) 进入本目录时会自动切换版本，避免和系统里的其他 Node 混淆：

```bash
fnm install 20                                    # 只需执行一次
eval "$(fnm env --use-on-cd --shell bash)"         # Git Bash，写进 ~/.bashrc
fnm env --use-on-cd --shell powershell | Out-String | Invoke-Expression   # PowerShell，写进 $PROFILE
```

## 初始化后端

```powershell
uv venv --python "C:\Users\Fight\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe" backend\.venv
uv pip install --python backend\.venv\Scripts\python.exe -r backend\requirements.txt
Copy-Item .env.example .env
```

如果 Python 3.12 的实际路径不同，先使用 `py -0p` 查找，再替换命令中的解释器路径。

## 启动后端

```powershell
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

健康检查：`http://127.0.0.1:8000/api/v1/health`

## 初始化前端

```powershell
Set-Location frontend
npm install
npm run dev
```

## 当前边界

- 当前文件处理范围仅为有效 `.docx` 文档；暂不支持旧版 `.doc`。

- `paper-checker-prototype` 是现有静态交互原型，未删除或覆盖。
- 本次只配置运行环境和健康检查入口，不创建数据库表，不写入密钥，不实现未确定的业务接口。
- `uploads` 和 `reports` 仅用于本地运行时文件，已加入 Git 忽略规则。
## 当前验证状态（2026-09-16）

本阶段已完成以下验证：

- 后端测试：`151 passed`（0 warning，加 `-W error` 亦通过）。测试临时目录已通过 `.verification-tmp/pytest` 隔离，31 个权限错误不属于业务失败。
- 前端测试：使用 `npm.cmd test -- --run`，结果为 `2 files passed, 3 tests passed`。
- 前端生产构建：使用 `npm.cmd run build`，TypeScript 编译和 Vite 构建均成功。
- 端到端功能链路：使用真实 `.docx` 文件验证上传、检测、结果、格式分析、PDF/Markdown 报告下载和任务清理。

### 质量验收边界

当前端到端验证证明系统链路可用，但检测质量仍需使用“人工确认合规论文”和“人工植入已知错误论文”进行真值对照，才能正式计算误报率、漏报率和规则覆盖率。当前演示文件输出的错误数仅作为功能验证结果，不作为质量达标结论。

## 答辩演示流程

1. 启动后端：`backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`。
2. 启动前端：进入 `frontend` 后执行 `npm.cmd run dev`。
3. 在首页选择有效 `.docx` 论文并上传。
4. 查看检测进度和错误列表，重点演示错误位置、错误文本、当前格式与规范要求。
5. 打开格式分析页，展示结构化格式摘要。
6. 生成并下载 PDF 或 Markdown 报告，展示真实规范来源和错误明细。
7. 演示完成后删除任务，确认临时文件被清理。

> 当前版本只支持有效 `.docx`；旧版 `.doc` 不纳入本阶段演示。
