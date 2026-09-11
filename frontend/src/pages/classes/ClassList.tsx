/**
 * 班级 / 学生管理页（W4-T2）
 *
 * 班级列表 + 创建班级 + 单个改密 + 批量改密 + 批量导入学生 CSV
 * 对接 W1-T4 后端 5 个端点（teachers / classes / students / bulk-import / reset-passwords）。
 */

import { useEffect, useState } from 'react'
import {
  Card,
  Tabs,
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  Popconfirm,
  Upload,
  App as AntApp,
  Row,
  Col,
  Statistic,
} from 'antd'
import {
  PlusOutlined,
  ReloadOutlined,
  ImportOutlined,
  KeyOutlined,
  InboxOutlined,
} from '@ant-design/icons'
import type { UploadProps } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { apiFetch } from '../../api/client'

interface Teacher {
  id: number
  name: string
}

interface ClassEntity {
  id: number
  name: string
  grade: number
  teacher_id: number
  teacher?: Teacher
}

interface Student {
  id: number
  name: string
  student_no: string
  class_id: number
  initial_password: string
}

const { Dragger } = Upload

export function ClassList() {
  const { message } = AntApp.useApp()
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [classes, setClasses] = useState<ClassEntity[]>([])
  const [students, setStudents] = useState<Student[]>([])
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null)
  const [classModalOpen, setClassModalOpen] = useState(false)
  const [pwdModalOpen, setPwdModalOpen] = useState(false)
  const [batchPwdModalOpen, setBatchPwdModalOpen] = useState(false)
  const [classForm] = Form.useForm()
  const [pwdForm] = Form.useForm()
  const [batchPwdForm] = Form.useForm()

  async function loadTeachers() {
    try {
      const data = await apiFetch<Teacher[]>('/api/teachers')
      setTeachers(data)
    } catch (e) {
      message.error(`老师加载失败：${(e as Error).message}`)
    }
  }

  async function loadClasses() {
    try {
      const data = await apiFetch<ClassEntity[]>('/api/classes')
      setClasses(data)
      if (!selectedClassId && data.length > 0) {
        setSelectedClassId(data[0].id)
      }
    } catch (e) {
      message.error(`班级加载失败：${(e as Error).message}`)
    }
  }

  async function loadStudents(classId: number) {
    try {
      const data = await apiFetch<Student[]>(`/api/classes/${classId}/students`)
      setStudents(data)
    } catch (e) {
      message.error(`学生加载失败：${(e as Error).message}`)
    }
  }

  useEffect(() => {
    loadTeachers()
    loadClasses()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (selectedClassId) loadStudents(selectedClassId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClassId])

  async function onCreateClass() {
    try {
      const values = await classForm.validateFields()
      await apiFetch('/api/classes', {
        method: 'POST',
        body: JSON.stringify({ ...values, grade: 2 }),
      })
      message.success('班级已创建')
      setClassModalOpen(false)
      classForm.resetFields()
      loadClasses()
    } catch (e) {
      if ((e as { errorFields?: unknown }).errorFields) return
      message.error(`创建失败：${(e as Error).message}`)
    }
  }

  // CSV 上传配置
  const uploadProps: UploadProps = {
    name: 'file',
    accept: '.csv',
    showUploadList: false,
    customRequest: async ({ file, onSuccess, onError }) => {
      if (!selectedClassId) {
        message.error('请先选班级')
        onError?.(new Error('No class selected'))
        return
      }
      try {
        const fd = new FormData()
        fd.append('file', file as Blob)
        const res = await fetch(`http://localhost:8000/api/classes/${selectedClassId}/students/bulk-import`, {
          method: 'POST',
          body: fd,
        })
        const body = await res.json()
        if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`)
        message.success(`导入：成功 ${body.inserted}，失败 ${body.failed.length}`)
        onSuccess?.(body)
        loadStudents(selectedClassId)
      } catch (e) {
        message.error(`导入失败：${(e as Error).message}`)
        onError?.(e as Error)
      }
    },
  }

  async function onChangePassword() {
    try {
      const values = await pwdForm.validateFields()
      const sid = values.student_id as number
      await apiFetch(`/api/students/${sid}/change-password`, {
        method: 'POST',
        body: JSON.stringify({ new_password: values.new_password }),
      })
      message.success(`学生 ${sid} 密码已改`)
      setPwdModalOpen(false)
      pwdForm.resetFields()
      if (selectedClassId) loadStudents(selectedClassId)
    } catch (e) {
      if ((e as { errorFields?: unknown }).errorFields) return
      message.error(`改密失败：${(e as Error).message}`)
    }
  }

  async function onBatchResetPassword() {
    if (!selectedClassId) return
    try {
      const values = await batchPwdForm.validateFields()
      const res = await apiFetch<{ reset_count: number }>(
        `/api/classes/${selectedClassId}/students/reset-passwords`,
        {
          method: 'POST',
          body: JSON.stringify({ default_password: values.default_password }),
        },
      )
      message.success(`已重置 ${res.reset_count} 个学生密码`)
      setBatchPwdModalOpen(false)
      batchPwdForm.resetFields()
      loadStudents(selectedClassId)
    } catch (e) {
      if ((e as { errorFields?: unknown }).errorFields) return
      message.error(`批量改密失败：${(e as Error).message}`)
    }
  }

  const studentColumns: ColumnsType<Student> = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '姓名', dataIndex: 'name', width: 120 },
    { title: '学号', dataIndex: 'student_no', width: 120 },
    {
      title: '初始密码',
      dataIndex: 'initial_password',
      width: 120,
      render: (p: string) => <Tag>{p}</Tag>,
    },
  ]

  return (
    <Card title="班级 / 学生（W1-T4：批量导入 + 改密）">
      <Row gutter={16}>
        <Col span={6}>
          <Card
            type="inner"
            title="班级"
            extra={
              <Space>
                <Button size="small" icon={<ReloadOutlined />} onClick={loadClasses} />
                <Button
                  size="small"
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setClassModalOpen(true)}
                >
                  新建
                </Button>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <div style={{ maxHeight: 400, overflowY: 'auto' }}>
              {classes.map((c) => (
                <div
                  key={c.id}
                  onClick={() => setSelectedClassId(c.id)}
                  style={{
                    padding: '8px 12px',
                    margin: '4px 0',
                    cursor: 'pointer',
                    borderRadius: 4,
                    background: selectedClassId === c.id ? '#e6f4ff' : 'transparent',
                    border:
                      selectedClassId === c.id ? '1px solid #1677ff' : '1px solid transparent',
                  }}
                >
                  <div style={{ fontWeight: 500 }}>{c.name}</div>
                  <div style={{ fontSize: 12, color: '#999' }}>
                    高{c.grade} · 老师 ID={c.teacher_id}
                  </div>
                </div>
              ))}
              {classes.length === 0 && (
                <div style={{ color: '#999', padding: 16 }}>暂无班级，点"新建"创建</div>
              )}
            </div>
          </Card>
        </Col>

        <Col span={18}>
          <Card
            type="inner"
            title={selectedClassId ? `班级 ${selectedClassId} 的学生` : '请先选班级'}
            extra={
              <Space>
                <Button
                  size="small"
                  icon={<KeyOutlined />}
                  disabled={!selectedClassId}
                  onClick={() => setBatchPwdModalOpen(true)}
                >
                  批量改密
                </Button>
                <Button
                  size="small"
                  icon={<KeyOutlined />}
                  disabled={!selectedClassId}
                  onClick={() => setPwdModalOpen(true)}
                >
                  单个改密
                </Button>
              </Space>
            }
          >
            {!selectedClassId ? (
              <div style={{ color: '#999', padding: 16 }}>请从左侧选班级</div>
            ) : (
              <Tabs
                items={[
                  {
                    key: 'list',
                    label: '学生列表',
                    children: (
                      <>
                        <Row gutter={16} style={{ marginBottom: 16 }}>
                          <Col span={6}>
                            <Statistic title="学生总数" value={students.length} />
                          </Col>
                        </Row>
                        <Table
                          rowKey="id"
                          columns={studentColumns}
                          dataSource={students}
                          size="small"
                          pagination={{ pageSize: 20 }}
                        />
                      </>
                    ),
                  },
                  {
                    key: 'import',
                    label: '批量导入 CSV',
                    children: (
                      <Dragger {...uploadProps}>
                        <p className="ant-upload-drag-icon">
                          <InboxOutlined />
                        </p>
                        <p className="ant-upload-text">点击或拖拽 CSV 文件到此区域</p>
                        <p className="ant-upload-hint" style={{ color: '#999' }}>
                          CSV 字段：name, student_no, [可选 initial_password]
                          <br />
                          错误行不中断批量，返回 inserted + failed 详情
                        </p>
                      </Dragger>
                    ),
                  },
                ]}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title="新建班级"
        open={classModalOpen}
        onCancel={() => setClassModalOpen(false)}
        onOk={onCreateClass}
        okText="创建"
        cancelText="取消"
      >
        <Form form={classForm} layout="vertical" initialValues={{ grade: 2 }}>
          <Form.Item name="name" label="班级名" rules={[{ required: true }]}>
            <Input placeholder="如：高二(1)班" />
          </Form.Item>
          <Form.Item name="teacher_id" label="归属老师" rules={[{ required: true }]}>
            <Select
              options={teachers.map((t) => ({ value: t.id, label: `${t.name} (id=${t.id})` }))}
              placeholder="选老师"
            />
          </Form.Item>
          <Form.Item name="grade" label="年级" rules={[{ required: true }]}>
            <Input type="number" disabled />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="单个改密"
        open={pwdModalOpen}
        onCancel={() => setPwdModalOpen(false)}
        onOk={onChangePassword}
        okText="改密"
        cancelText="取消"
      >
        <Form form={pwdForm} layout="vertical">
          <Form.Item name="student_id" label="学生 ID" rules={[{ required: true }]}>
            <Select
              options={students.map((s) => ({
                value: s.id,
                label: `${s.name} (${s.student_no}, id=${s.id})`,
              }))}
              placeholder="选学生"
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="新密码（≥6 字符）"
            rules={[{ required: true, min: 6 }]}
          >
            <Input.Password placeholder="≥6 字符" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="批量改密（当前班级所有学生）"
        open={batchPwdModalOpen}
        onCancel={() => setBatchPwdModalOpen(false)}
        onOk={onBatchResetPassword}
        okText="重置"
        cancelText="取消"
      >
        <Form form={batchPwdForm} layout="vertical">
          <Form.Item
            name="default_password"
            label="默认密码（所有学生都将被重置为这个）"
            rules={[{ required: true, min: 6 }]}
          >
            <Input.Password placeholder="≥6 字符" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
