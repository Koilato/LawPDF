import { Card, Flex, Input, Select, Space, Switch, Typography } from 'antd';
import type { AppSettings } from '../types';

interface SettingsPanelProps {
  settings: AppSettings;
  onChange: <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => void;
}

// Settings panel.
export function SettingsPanel({ settings, onChange }: SettingsPanelProps) {
  return (
    <Card title="运行设置" bordered={false}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Flex justify="space-between" align="center">
          <Typography.Text>律师函 OCR 前去掉最后一页</Typography.Text>
          <Switch checked={settings.trimLastPageForLawyerLetter} onChange={(checked) => onChange('trimLastPageForLawyerLetter', checked)} />
        </Flex>
        <Flex justify="space-between" align="center">
          <Typography.Text>输出中间 JSON</Typography.Text>
          <Switch checked={settings.writeIntermediateJsons} onChange={(checked) => onChange('writeIntermediateJsons', checked)} />
        </Flex>
        <Flex justify="space-between" align="center">
          <Typography.Text>保留调试信息</Typography.Text>
          <Switch checked={settings.debug} onChange={(checked) => onChange('debug', checked)} />
        </Flex>
        <div>
          <Typography.Text strong>目标关键词</Typography.Text>
          <Input value={settings.targetKeyword} onChange={(event) => onChange('targetKeyword', event.target.value)} placeholder="例如：光明" />
        </div>
        <div>
          <Typography.Text strong>LLM 接口地址</Typography.Text>
          <Input value={settings.apiUrl} onChange={(event) => onChange('apiUrl', event.target.value)} placeholder="http://.../v1/chat/completions" />
        </div>
        <div>
          <Typography.Text strong>LLM API 密钥</Typography.Text>
          <Input.Password value={settings.apiKey} onChange={(event) => onChange('apiKey', event.target.value)} placeholder="sk-..." />
        </div>
        <div>
          <Typography.Text strong>模型</Typography.Text>
          <Input value={settings.model} onChange={(event) => onChange('model', event.target.value)} placeholder="gemini-3-flash-preview" />
        </div>
        <div>
          <Typography.Text strong>图片对齐</Typography.Text>
          <Select
            value={settings.imageAlign}
            onChange={(value) => onChange('imageAlign', value)}
            options={[
              { label: '左对齐', value: 'left' },
              { label: '居中', value: 'center' },
              { label: '右对齐', value: 'right' },
            ]}
          />
        </div>
      </Space>
    </Card>
  );
}
