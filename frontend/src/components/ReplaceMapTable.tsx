import { Card, Table, Typography } from 'antd';

interface ReplaceMapTableProps {
  replaceMap: Record<string, string>;
}

export function ReplaceMapTable({ replaceMap }: ReplaceMapTableProps) {
  const dataSource = Object.entries(replaceMap).map(([keyword, text], index) => ({ key: `${index}-${keyword}`, keyword, text }));

  return (
    <Card title="replace_map 表格预览" bordered={false} className="panel-card">
      <Table
        size="small"
        pagination={false}
        dataSource={dataSource}
        scroll={{ y: 380 }}
        columns={[
          {
            title: '占位符',
            dataIndex: 'keyword',
            key: 'keyword',
            width: 220,
            render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
          },
          {
            title: '最终值',
            dataIndex: 'text',
            key: 'text',
          },
        ]}
      />
    </Card>
  );
}
