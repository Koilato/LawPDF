# 前端工作台

这是案件文书处理项目的本地网页前端。

技术栈：

- React
- TypeScript
- Vite
- Ant Design
- Monaco Editor

## 页面功能

- 上传企业报告 PDF
- 上传律师函 PDF
- 上传 Word 模板
- 设置 LLM 参数和运行参数
- 查看 OCR 文本
- 查看 `Defandent`、`DemandLetter`、`logical`
- 直接编辑 `replace_map_config.json`
- 预览和修正 `replace_map`
- 调用后端生成 Word 文档

## 安装

```powershell
cd .\independent_case_pipeline\frontend
npm install
```

## 启动

```powershell
npm run dev
```

默认地址：

- `http://127.0.0.1:5173`

默认后端地址：

- `http://127.0.0.1:8000`

## 联调方式

1. 先启动后端 `backend/app/main.py`
2. 再启动前端 `npm run dev`
3. 打开页面后确认顶部显示“后端已连接”
4. 上传文件并执行抽取
5. 确认 `replace_map` 后生成 Word

## 主要文件

- `src/App.tsx`
  - 页面主工作台
- `src/api.ts`
  - 前端调用后端接口
- `src/components/`
  - 上传、设置、JSON 编辑、输出面板
- `src/mockData.ts`
  - 后端不可用时的本地演示数据
- `src/utils/replaceMap.ts`
  - 前端本地生成 `replace_map` 的工具
