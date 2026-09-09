# 论文格式检测系统

本项目按《论文格式检测系统技术设计文档 V1.0》建立本地开发环境。当前目录保留了产品原型 `paper-checker-prototype`，并新增前后端工程配置骨架。

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
