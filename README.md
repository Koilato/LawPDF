# 独立案件文书处理项目

这是一个本地运行的“前端工作台 + 后端服务”项目，用来完成以下流程：

1. 上传企业报告 PDF、律师函 PDF、Word 模板
2. 对 PDF 执行 OCR，生成 Markdown
3. 抽取企业报告为 `Defandent`
4. 抽取律师函为 `DemandLetter`
5. 根据企业名称和目标关键词生成 `logical`
6. 使用 `replace_map_config.json` 生成最终 `replace_map`
7. 按 `replace_map` 替换 Word 模板中的占位符并输出文档

## 当前目录

- `frontend/`
  - 本地网页工作台
  - 技术栈：React + TypeScript + Vite + Ant Design + Monaco Editor
- `backend/app/`
  - 本地 HTTP API、配置、路由、服务层
- `backend/tools/`
  - OCR、抽取器、逻辑字段生成器、Word 替换器
- `backend/workflows/`
  - 端到端流程、自检流程
- `backend/configs/`
  - JSON 配置，例如 `replace_map_config.json`
- `backend/storage/`
  - 上传文件、案例目录、临时目录、输出目录

## 核心数据对象

- `Defandent`
  - 企业报告抽取结果
- `DemandLetter`
  - 律师函抽取结果
- `logical`
  - 根据规则自动推导出的逻辑字段，例如案由、诉讼请求三、不正当竞争事实段
- `replace_map`
  - 最终的“Word 占位符 -> 替换文本”映射

## replace_map 配置

`backend/configs/replace_map_config.json` 用来描述如何生成 `replace_map`。

当前支持三种模式：

- `path`
  - 从 `Defandent` / `DemandLetter` / `logical` 中按路径取值
- `literal`
  - 使用固定文本
- `template`
  - 用简单变量拼接字符串

## Python 依赖安装

推荐直接使用：

```powershell
cd .\independent_case_pipeline
pip install -r .\requirements.txt
```

如果你使用 conda，也可以：

```powershell
conda env create -f .\environment.yml
conda activate case-ocr-extract
```

## 启动后端

```powershell
cd .\independent_case_pipeline
& 'C:\Users\xhi\Documents\New project\.conda\case-pipeline\python.exe' .\backend\app\main.py
```

默认地址：

- `http://127.0.0.1:8000`

当前接口：

- `GET /api/health`
- `GET /api/settings`
- `POST /api/extract`
- `POST /api/render`
- `GET /api/files?path=...`

## 启动前端

```powershell
cd .\independent_case_pipeline\frontend
npm install
npm run dev
```

默认地址：

- `http://127.0.0.1:5173`

## 前端可设置项

这些设置由前端传给后端：

- `api_url`
- `api_key`
- `model`
- `target_keyword`
- `trim_last_page_for_lawyer_letter`
- `write_intermediate_jsons`
- `debug`
- `image_align`
- `image_width_cm`
- `image_height_cm`

后端默认值集中在：

- `backend/app/config.py`

## 常用入口

- 后端主入口：
  - `backend/app/main.py`
- 抽取服务：
  - `backend/app/services/extract_service.py`
- replace_map 服务：
  - `backend/app/services/replace_map_service.py`
- Word 渲染服务：
  - `backend/app/services/render_service.py`

## 注意事项

- Word 输出文档如果正在被 WPS 或 Word 打开，重新生成时可能会因为文件占用而失败。
- 这个项目现在以网页端流程为主，历史兼容入口文件已尽量弱化。
- `requirements.txt` 只描述 Python 后端依赖；前端依赖由 `frontend/package.json` 管理。
