import {
  ApiOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import {
  App as AntdApp,
  Button,
  Card,
  ConfigProvider,
  Layout,
  Space,
  Tabs,
  Tag,
  Typography,
  message,
  theme,
} from 'antd';
import { useEffect, useMemo, useState, useTransition } from 'react';
import { extractCaseData, fetchBackendSettings, renderWordDocument } from './api';
import { FileInputPanel } from './components/FileInputPanel';
import { JsonEditorCard } from './components/JsonEditorCard';
import { OutputPanel } from './components/OutputPanel';
import { ReplaceMapTable } from './components/ReplaceMapTable';
import { SettingsPanel } from './components/SettingsPanel';
import {
  defaultSettings,
  initialReplaceMapConfig,
  mockDefandent,
  mockDemandLetter,
  mockLogical,
  mockOcrMarkdown,
} from './mockData';
import type { AppSettings, JsonObject, LogItem, OutputSummary, ReplaceMapConfig } from './types';
import { buildReplaceMap, safeParseConfig, toPrettyJson } from './utils/replaceMap';
import './styles.css';

const { Header, Sider, Content } = Layout;

const fallbackSources = {
  Defandent: mockDefandent,
  DemandLetter: mockDemandLetter,
  logical: mockLogical,
};

function nowLabel(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false });
}

function createLog(level: LogItem['level'], messageText: string): LogItem {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    time: nowLabel(),
    level,
    message: messageText,
  };
}

function AppShell() {
  const [messageApi, contextHolder] = message.useMessage();
  const [isPending, startTransition] = useTransition();
  const [isBackendReady, setIsBackendReady] = useState(false);
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [selectedFiles, setSelectedFiles] = useState({
    enterpriseReportPdf: null as File | null,
    lawyerLetterPdf: null as File | null,
    templateFile: null as File | null,
  });
  const [caseName, setCaseName] = useState('');
  const [templateFilePath, setTemplateFilePath] = useState<string | undefined>();
  const [ocrMarkdown, setOcrMarkdown] = useState(mockOcrMarkdown);
  const [defandent, setDefandent] = useState<JsonObject>(mockDefandent as JsonObject);
  const [demandLetter, setDemandLetter] = useState<JsonObject>(mockDemandLetter as JsonObject);
  const [logical, setLogical] = useState<JsonObject>(mockLogical as JsonObject);
  const [replaceMapConfigText, setReplaceMapConfigText] = useState(() => toPrettyJson(initialReplaceMapConfig));
  const [replaceMapText, setReplaceMapText] = useState(() =>
    toPrettyJson(buildReplaceMap(initialReplaceMapConfig, fallbackSources)),
  );
  const [isExtracting, setIsExtracting] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [logs, setLogs] = useState<LogItem[]>([
    createLog('info', '工作台已启动，正在等待连接本地后端。'),
  ]);
  const [output, setOutput] = useState<OutputSummary>({
    status: 'idle',
    replaceMapPath: undefined,
    docxPath: undefined,
    manifestPath: undefined,
    downloadUrl: undefined,
    caseName: undefined,
  });

  const replaceMapSources = useMemo(
    () => ({ Defandent: defandent, DemandLetter: demandLetter, logical }),
    [defandent, demandLetter, logical],
  );

  const currentReplaceMap = useMemo(() => {
    try {
      return JSON.parse(replaceMapText) as Record<string, string>;
    } catch {
      return {};
    }
  }, [replaceMapText]);

  const appendLog = (level: LogItem['level'], text: string) => {
    setLogs((current) => [createLog(level, text), ...current].slice(0, 18));
  };

  const handleSettingChange = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setSettings((current) => ({ ...current, [key]: value }));
  };

  const handleFileChange = (key: 'enterpriseReportPdf' | 'lawyerLetterPdf' | 'templateFile', file: File | null) => {
    setSelectedFiles((current) => ({ ...current, [key]: file }));
    if (key === 'templateFile') {
      setTemplateFilePath(undefined);
    }
    setOutput((current) => ({
      ...current,
      status: current.docxPath ? 'ready' : current.status,
      docxPath: undefined,
      downloadUrl: undefined,
    }));
    appendLog('info', `${key}${file ? ` 已选择：${file.name}` : ' 已清空'}`);
  };

  const regenerateReplaceMap = (nextConfigText: string = replaceMapConfigText) => {
    try {
      const parsedConfig = safeParseConfig(nextConfigText) as ReplaceMapConfig;
      const nextReplaceMap = buildReplaceMap(parsedConfig, replaceMapSources);
      setReplaceMapText(toPrettyJson(nextReplaceMap));
      setOutput((current) => ({
        ...current,
        status: Object.keys(nextReplaceMap).length > 0 ? 'ready' : current.status,
        docxPath: undefined,
        manifestPath: undefined,
        downloadUrl: undefined,
      }));
      appendLog('success', '已根据 replace_map_config 重新生成 replace_map。');
      messageApi.success('replace_map 已刷新');
    } catch (error) {
      const text = error instanceof Error ? error.message : 'replace_map_config 解析失败';
      appendLog('error', `replace_map_config 解析失败：${text}`);
      messageApi.error('replace_map_config 解析失败，请检查 JSON 内容');
    }
  };

  const handleExtract = async () => {
    if (!selectedFiles.enterpriseReportPdf || !selectedFiles.lawyerLetterPdf) {
      messageApi.warning('请先上传企业报告 PDF 和律师函 PDF');
      appendLog('warning', '执行抽取前必须先选择企业报告 PDF 和律师函 PDF。');
      return;
    }

    setIsExtracting(true);
    appendLog('info', '正在调用后端抽取流程：上传文件、执行 OCR、提取 JSON，并生成默认 replace_map。');

    try {
      const result = await extractCaseData({
        files: selectedFiles,
        settings,
        replaceMapConfigText,
        caseName: caseName || undefined,
      });

      startTransition(() => {
        setCaseName(result.case_name);
        setTemplateFilePath(result.paths.template_file ?? undefined);
        setOcrMarkdown({
          enterpriseReport: result.markdowns.enterprise_report,
          lawyerLetter: result.markdowns.lawyer_letter,
        });
        setDefandent(result.Defandent);
        setDemandLetter(result.DemandLetter);
        setLogical(result.logical);
        setReplaceMapConfigText(result.replace_map_config_text);
        setReplaceMapText(toPrettyJson(result.replace_map));
        setOutput({
          status: 'ready',
          caseName: result.case_name,
          replaceMapPath: result.paths.replace_map_json ?? undefined,
          docxPath: undefined,
          manifestPath: undefined,
          downloadUrl: undefined,
        });
      });

      appendLog('success', `抽取完成，案件名称：${result.case_name}`);
      messageApi.success('抽取已完成，页面数据已刷新');
    } catch (error) {
      const text = error instanceof Error ? error.message : '抽取失败';
      setOutput((current) => ({ ...current, status: 'error' }));
      appendLog('error', `抽取失败：${text}`);
      messageApi.error(text);
    } finally {
      setIsExtracting(false);
    }
  };

  const handleRender = async () => {
    if (!caseName) {
      messageApi.warning('请先执行抽取，再生成 Word');
      appendLog('warning', '生成 Word 前需要先完成抽取，获得案件名称和 replace_map。');
      return;
    }

    if (!Object.keys(currentReplaceMap).length) {
      messageApi.warning('replace_map 为空');
      appendLog('warning', '生成 Word 需要非空的 replace_map。');
      return;
    }

    setIsRendering(true);
    appendLog('info', '正在调用后端渲染流程，准备生成 Word 文档。');

    try {
      const result = await renderWordDocument({
        caseName,
        replaceMap: currentReplaceMap,
        settings,
        templateFilePath,
        templateFile: templateFilePath ? null : selectedFiles.templateFile,
      });

      setOutput({
        status: 'success',
        caseName: result.case_name,
        replaceMapPath: result.replace_map_json,
        docxPath: result.output_docx,
        manifestPath: result.manifest_path,
        downloadUrl: result.download_url,
      });
      appendLog('success', 'Word 渲染完成，已返回输出路径。');
      messageApi.success('Word 文档已生成');
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Word 渲染失败';
      setOutput((current) => ({ ...current, status: 'error' }));
      appendLog('error', `Word 渲染失败：${text}`);
      messageApi.error(text);
    } finally {
      setIsRendering(false);
    }
  };

  useEffect(() => {
    let active = true;

    const loadBackendDefaults = async () => {
      try {
        const result = await fetchBackendSettings();
        if (!active) {
          return;
        }

        setSettings(result.settings);
        setReplaceMapConfigText(result.replaceMapConfigText);
        setIsBackendReady(true);
        appendLog('success', `已连接本地后端：${result.apiBaseUrl}`);
        startTransition(() => {
          try {
            const parsedConfig = safeParseConfig(result.replaceMapConfigText) as ReplaceMapConfig;
            setReplaceMapText(toPrettyJson(buildReplaceMap(parsedConfig, fallbackSources)));
          } catch {
            setReplaceMapText(toPrettyJson(buildReplaceMap(initialReplaceMapConfig, fallbackSources)));
          }
        });
      } catch (error) {
        if (!active) {
          return;
        }
        const text = error instanceof Error ? error.message : '无法连接本地后端';
        setIsBackendReady(false);
        appendLog('warning', `本地后端不可用，当前停留在演示模式：${text}`);
      }
    };

    void loadBackendDefaults();
    return () => {
      active = false;
    };
  }, []);

  const isWorking = isExtracting || isRendering || isPending;

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#0f766e',
          colorBgLayout: '#f4f1ea',
          colorText: '#1e293b',
          borderRadius: 14,
          fontFamily: 'Aptos, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif',
        },
      }}
    >
      <AntdApp>
        {contextHolder}
        <Layout className="app-layout">
          <Header className="topbar">
            <div>
              <Typography.Title level={3} className="topbar-title">
                光明案件文书工作台
              </Typography.Title>
              <Typography.Text className="topbar-subtitle">
                {isBackendReady
                  ? '本地后端已连接，当前页面正在使用真实的抽取与渲染服务。'
                  : '本地后端未连接，当前页面将停留在演示模式，只展示本地 replace_map 预览。'}
              </Typography.Text>
            </div>
            <Space>
              <Tag icon={isBackendReady ? <ApiOutlined /> : <WarningOutlined />} color={isBackendReady ? 'success' : 'warning'}>
                {isBackendReady ? '后端已连接' : '后端未连接'}
              </Tag>
              <Button icon={<ReloadOutlined />} onClick={() => regenerateReplaceMap()} disabled={isWorking}>
                刷新 replace_map
              </Button>
              <Button type="default" icon={<PlayCircleOutlined />} onClick={() => void handleExtract()} loading={isExtracting}>
                执行抽取
              </Button>
              <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => void handleRender()} loading={isRendering}>
                生成 Word
              </Button>
            </Space>
          </Header>
          <Layout className="workspace-layout">
            <Sider width={356} className="workspace-sider workspace-sider-left">
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <FileInputPanel files={selectedFiles} onFileChange={handleFileChange} />
                <SettingsPanel settings={settings} onChange={handleSettingChange} />
                <Card title="当前输入状态" variant="borderless">
                  <Space direction="vertical" size="small">
                    <Typography.Text>案件名称：{caseName || '等待先执行抽取'}</Typography.Text>
                    <Typography.Text>企业报告：{selectedFiles.enterpriseReportPdf?.name ?? '未选择'}</Typography.Text>
                    <Typography.Text>律师函：{selectedFiles.lawyerLetterPdf?.name ?? '未选择'}</Typography.Text>
                    <Typography.Text>模板文件：{selectedFiles.templateFile?.name ?? templateFilePath ?? '未选择'}</Typography.Text>
                  </Space>
                </Card>
              </Space>
            </Sider>
            <Content className="workspace-content">
              <Tabs
                size="large"
                className="content-tabs"
                items={[
                  {
                    key: 'ocr',
                    label: 'OCR 文本',
                    children: (
                      <div className="split-grid two-columns">
                        <JsonEditorCard title="企业报告 Markdown" value={ocrMarkdown.enterpriseReport} readOnly height={500} />
                        <JsonEditorCard title="律师函 Markdown" value={ocrMarkdown.lawyerLetter} readOnly height={500} />
                      </div>
                    ),
                  },
                  {
                    key: 'extracted',
                    label: '抽取结果 JSON',
                    children: (
                      <div className="split-grid three-columns">
                        <JsonEditorCard title="企业报告抽取结果（Defandent）" value={toPrettyJson(defandent)} readOnly height={500} />
                        <JsonEditorCard title="律师函抽取结果（DemandLetter）" value={toPrettyJson(demandLetter)} readOnly height={500} />
                        <JsonEditorCard title="逻辑判断结果（logical）" value={toPrettyJson(logical)} readOnly height={500} />
                      </div>
                    ),
                  },
                  {
                    key: 'config',
                    label: '替换规则配置',
                    children: (
                      <JsonEditorCard
                        title="replace_map_config.json"
                        description="在这里直接编辑原始 JSON 配置。当前实现支持 path、literal 和 template 三种模式。"
                        value={replaceMapConfigText}
                        onChange={setReplaceMapConfigText}
                        height={560}
                        extra={
                          <Button size="small" onClick={() => regenerateReplaceMap()} disabled={isWorking}>
                            应用配置
                          </Button>
                        }
                      />
                    ),
                  },
                  {
                    key: 'replace-map',
                    label: '替换映射',
                    children: (
                      <div className="split-grid two-columns compact-gap">
                        <ReplaceMapTable replaceMap={currentReplaceMap} />
                        <JsonEditorCard
                          title="replace_map.json"
                          description="这里展示的是最终写入 Word 模板的占位符映射，你仍然可以在这里手动修改。"
                          value={replaceMapText}
                          onChange={setReplaceMapText}
                          height={500}
                        />
                      </div>
                    ),
                  },
                ]}
              />
            </Content>
            <Sider width={348} className="workspace-sider workspace-sider-right">
              <OutputPanel logs={logs} output={output} />
            </Sider>
          </Layout>
        </Layout>
      </AntdApp>
    </ConfigProvider>
  );
}

export default AppShell;
