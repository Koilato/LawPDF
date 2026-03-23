import { InboxOutlined } from '@ant-design/icons';
import { Card, Space, Typography, Upload } from 'antd';
import type { UploadFile, UploadProps } from 'antd';

interface FileInputPanelProps {
  files: {
    enterpriseReportPdf?: File | null;
    lawyerLetterPdf?: File | null;
    templateFile?: File | null;
  };
  onFileChange: (key: 'enterpriseReportPdf' | 'lawyerLetterPdf' | 'templateFile', file: File | null) => void;
}

const buildFileList = (file?: File | null): UploadFile[] => {
  if (!file) {
    return [];
  }
  return [
    {
      uid: file.name,
      name: file.name,
      status: 'done',
      size: file.size,
      type: file.type,
    },
  ];
};

const createUploadProps = (
  file: File | null | undefined,
  onChange: (file: File | null) => void,
): UploadProps => ({
  multiple: false,
  fileList: buildFileList(file),
  beforeUpload: (nextFile) => {
    onChange(nextFile);
    return false;
  },
  onRemove: () => {
    onChange(null);
  },
  accept: '.pdf,.doc,.docx',
  maxCount: 1,
});

export function FileInputPanel({ files, onFileChange }: FileInputPanelProps) {
  return (
    <Card title="文件上传" bordered={false}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div>
          <Typography.Text strong>企业报告 PDF</Typography.Text>
          <Upload.Dragger {...createUploadProps(files.enterpriseReportPdf, (file) => onFileChange('enterpriseReportPdf', file))}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">拖入企业报告 PDF，或点击选择</p>
          </Upload.Dragger>
        </div>
        <div>
          <Typography.Text strong>律师函 PDF</Typography.Text>
          <Upload.Dragger {...createUploadProps(files.lawyerLetterPdf, (file) => onFileChange('lawyerLetterPdf', file))}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">拖入律师函 PDF，或点击选择</p>
          </Upload.Dragger>
        </div>
        <div>
          <Typography.Text strong>Word 模板</Typography.Text>
          <Upload.Dragger {...createUploadProps(files.templateFile, (file) => onFileChange('templateFile', file))}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">拖入 doc / docx 模板，或点击选择</p>
          </Upload.Dragger>
        </div>
      </Space>
    </Card>
  );
}
