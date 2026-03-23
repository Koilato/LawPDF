import { CheckCircleOutlined, ClockCircleOutlined, DownloadOutlined, FileTextOutlined, FileWordOutlined, WarningOutlined } from '@ant-design/icons';
import { Button, Card, Divider, List, Space, Tag, Timeline, Typography } from 'antd';
import type { LogItem, OutputSummary } from '../types';

interface OutputPanelProps {
  logs: LogItem[];
  output: OutputSummary;
}

const statusMap = {
  idle: { color: 'default', icon: <ClockCircleOutlined />, text: '等待执行' },
  ready: { color: 'processing', icon: <ClockCircleOutlined />, text: '已生成 replace_map' },
  success: { color: 'success', icon: <CheckCircleOutlined />, text: '输出已完成' },
  error: { color: 'error', icon: <WarningOutlined />, text: '执行失败' },
} as const;

export function OutputPanel({ logs, output }: OutputPanelProps) {
  const status = statusMap[output.status];
  const hasDocx = Boolean(output.docxPath);
  const canDownload = Boolean(output.downloadUrl);

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card title="输出结果" bordered={false}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Tag icon={status.icon} color={status.color}>{status.text}</Tag>

          <Typography.Text strong>案件名称</Typography.Text>
          <Typography.Paragraph copyable>{output.caseName ?? '未生成'}</Typography.Paragraph>

          <Typography.Text strong>replace_map 路径</Typography.Text>
          <Typography.Paragraph copyable>{output.replaceMapPath ?? '未生成'}</Typography.Paragraph>

          <Typography.Text strong>输出文书路径</Typography.Text>
          <Typography.Paragraph copyable>{output.docxPath ?? '未生成'}</Typography.Paragraph>

          <Typography.Text strong>渲染清单路径</Typography.Text>
          <Typography.Paragraph copyable>{output.manifestPath ?? '未生成'}</Typography.Paragraph>

          <Space wrap>
            <Button
              type="primary"
              icon={<FileWordOutlined />}
              href={output.downloadUrl}
              target="_blank"
              disabled={!canDownload}
            >
              打开或下载文书
            </Button>
            <Button
              icon={<DownloadOutlined />}
              href={output.downloadUrl}
              target="_blank"
              disabled={!canDownload}
            >
              下载文书
            </Button>
          </Space>

          <Divider style={{ margin: '8px 0' }} />

          <Typography.Text strong>文件说明</Typography.Text>
          {hasDocx ? (
            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              <Typography.Text>
                浏览器无法直接内嵌预览 `docx`，请通过上方按钮下载后使用本地 Word 打开。
              </Typography.Text>
              {canDownload ? (
                <Typography.Link href={output.downloadUrl} target="_blank">
                  打开下载链接
                </Typography.Link>
              ) : null}
            </Space>
          ) : (
            <Typography.Text type="secondary">当前还没有生成 Word 文书，请先完成抽取和渲染。</Typography.Text>
          )}
        </Space>
      </Card>

      <Card title="运行日志" bordered={false}>
        <Timeline
          items={logs.map((item) => ({
            color: item.level === 'error' ? 'red' : item.level === 'warning' ? 'orange' : item.level === 'success' ? 'green' : 'blue',
            children: (
              <Space direction="vertical" size={0}>
                <Typography.Text strong>{item.message}</Typography.Text>
                <Typography.Text type="secondary">{item.time}</Typography.Text>
              </Space>
            ),
          }))}
        />
      </Card>

      <Card title="检查信息" bordered={false}>
        <List
          size="small"
          dataSource={[
            output.replaceMapPath ? 'replace_map 已生成' : 'replace_map 未生成',
            output.docxPath ? 'Word 文书已生成' : 'Word 文书未生成',
            output.downloadUrl ? '下载链接已生成' : '下载链接未生成',
            output.manifestPath ? '渲染清单已生成' : '渲染清单未生成',
          ]}
          renderItem={(item) => (
            <List.Item>
              <Space>
                <FileTextOutlined />
                <span>{item}</span>
              </Space>
            </List.Item>
          )}
        />
      </Card>
    </Space>
  );
}
