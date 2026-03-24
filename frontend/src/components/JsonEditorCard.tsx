import { Card, Space, Typography } from 'antd';
import Editor from '@monaco-editor/react';
import type { ReactNode } from 'react';

interface JsonEditorCardProps {
  title: string;
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  height?: number;
  extra?: ReactNode;
  description?: string;
}

// JSON editor card.
export function JsonEditorCard({
  title,
  value,
  onChange,
  readOnly = false,
  height = 420,
  extra,
  description,
}: JsonEditorCardProps) {
  return (
    <Card title={title} extra={extra} bordered={false} className="panel-card">
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        {description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}
        <Editor
          height={height}
          defaultLanguage="json"
          value={value}
          onChange={(nextValue) => onChange?.(nextValue ?? '')}
          options={{
            minimap: { enabled: false },
            readOnly,
            fontSize: 13,
            automaticLayout: true,
            wordWrap: 'on',
            scrollBeyondLastLine: false,
            formatOnPaste: true,
            formatOnType: true,
          }}
        />
      </Space>
    </Card>
  );
}
