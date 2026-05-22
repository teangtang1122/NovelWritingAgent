import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button, Card, Empty, Select, Space, Spin, Tooltip, Typography, message } from 'antd'
import {
  CheckSquareOutlined,
  ClearOutlined,
  StarOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import { apiClient } from '../api/client'

const { Text, Title } = Typography

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

interface CharacterNode {
  id: string
  name: string
  role_type: string
  current_version: number
}

interface RelationshipEdge {
  id: string
  from: string
  to: string
  relationship_type: string
  description: string | null
}

interface RelationshipNetwork {
  nodes: CharacterNode[]
  edges: RelationshipEdge[]
  total: number
}

interface VisualizationPageProps {
  projectId: string
}

const DEFAULT_RELATIONSHIP_VISIBLE_COUNT = 12

const ROLE_COLOR: Record<string, string> = {
  protagonist: '#f5222d',
  antagonist: '#722ed1',
  supporting: '#1677ff',
  mentor: '#13c2c2',
}

const ROLE_PRIORITY: Record<string, number> = {
  protagonist: 100,
  antagonist: 80,
  mentor: 70,
  supporting: 50,
}

function buildDefaultVisibleCharacterIds(nodes: CharacterNode[], edges: RelationshipEdge[]) {
  if (nodes.length <= DEFAULT_RELATIONSHIP_VISIBLE_COUNT) {
    return nodes.map((node) => node.id)
  }

  const degreeMap = new Map<string, number>()
  for (const edge of edges) {
    degreeMap.set(edge.from, (degreeMap.get(edge.from) || 0) + 1)
    degreeMap.set(edge.to, (degreeMap.get(edge.to) || 0) + 1)
  }

  return [...nodes]
    .sort((a, b) => {
      const roleDiff = (ROLE_PRIORITY[b.role_type] || 0) - (ROLE_PRIORITY[a.role_type] || 0)
      if (roleDiff !== 0) return roleDiff
      const degreeDiff = (degreeMap.get(b.id) || 0) - (degreeMap.get(a.id) || 0)
      if (degreeDiff !== 0) return degreeDiff
      return a.name.localeCompare(b.name, 'zh-CN')
    })
    .slice(0, DEFAULT_RELATIONSHIP_VISIBLE_COUNT)
    .map((node) => node.id)
}

function VisualizationPage({ projectId }: VisualizationPageProps) {
  const [loading, setLoading] = useState(false)
  const [relationshipNetwork, setRelationshipNetwork] = useState<RelationshipNetwork | null>(null)
  const [selectedCharacterIds, setSelectedCharacterIds] = useState<string[]>([])
  const relationshipSelectionTouchedRef = useRef(false)
  const relRef = useRef<HTMLDivElement>(null)
  const relNetRef = useRef<Network | null>(null)

  const selectedRelationshipData = useMemo(() => {
    if (!relationshipNetwork) {
      return { nodes: [] as CharacterNode[], edges: [] as RelationshipEdge[] }
    }

    const selectedIds = new Set(selectedCharacterIds)
    const nodes = relationshipNetwork.nodes.filter((node) => selectedIds.has(node.id))
    const visibleIds = new Set(nodes.map((node) => node.id))
    const edges = relationshipNetwork.edges.filter((edge) => visibleIds.has(edge.from) && visibleIds.has(edge.to))
    return { nodes, edges }
  }, [relationshipNetwork, selectedCharacterIds])

  const characterSelectOptions = useMemo(() => (
    relationshipNetwork?.nodes.map((node) => ({
      value: node.id,
      label: node.name,
    })) || []
  ), [relationshipNetwork])

  const resetToKeyCharacters = useCallback(() => {
    if (!relationshipNetwork) return
    relationshipSelectionTouchedRef.current = true
    setSelectedCharacterIds(buildDefaultVisibleCharacterIds(relationshipNetwork.nodes, relationshipNetwork.edges))
  }, [relationshipNetwork])

  const selectAllCharacters = useCallback(() => {
    if (!relationshipNetwork) return
    relationshipSelectionTouchedRef.current = true
    setSelectedCharacterIds(relationshipNetwork.nodes.map((node) => node.id))
  }, [relationshipNetwork])

  const clearSelectedCharacters = useCallback(() => {
    relationshipSelectionTouchedRef.current = true
    setSelectedCharacterIds([])
  }, [])

  const handleSelectedCharacterChange = useCallback((ids: string[]) => {
    relationshipSelectionTouchedRef.current = true
    setSelectedCharacterIds(ids)
  }, [])

  const loadRelationshipNetwork = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.get<ApiResponse<RelationshipNetwork>>(`/projects/${projectId}/characters/relationships`)
      const network = res.data.data
      setRelationshipNetwork(network)
      setSelectedCharacterIds((current) => {
        const validIds = new Set(network.nodes.map((node) => node.id))
        const preserved = current.filter((id) => validIds.has(id))
        if (relationshipSelectionTouchedRef.current) {
          return preserved
        }
        return buildDefaultVisibleCharacterIds(network.nodes, network.edges)
      })
    } catch (err: any) {
      setRelationshipNetwork(null)
      setSelectedCharacterIds([])
      message.error(err.message || '加载关系网络失败')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  const renderRelationshipGraph = useCallback(() => {
    if (!relRef.current || !relationshipNetwork) return

    if (relNetRef.current) {
      relNetRef.current.destroy()
      relNetRef.current = null
    }

    const { nodes, edges } = selectedRelationshipData
    if (nodes.length === 0) return

    const graphNodes = nodes.map((node) => ({
      id: node.id,
      label: node.name,
      color: ROLE_COLOR[node.role_type] || '#666',
      shape: node.role_type === 'protagonist' ? 'star' : 'dot',
      size: node.role_type === 'protagonist' ? 20 : 12,
    }))

    const graphEdges = edges.map((edge) => ({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      label: edge.relationship_type,
      arrows: 'to',
      font: { size: 10, strokeWidth: 2, align: 'middle' },
      title: edge.description || edge.relationship_type,
    }))

    const data = { nodes: new DataSet(graphNodes), edges: new DataSet(graphEdges) }
    const net = new Network(relRef.current, data, {
      layout: { improvedLayout: true },
      physics: {
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -40,
          centralGravity: 0.005,
          springLength: 150,
          springConstant: 0.08,
        },
      },
      edges: { smooth: { enabled: true, type: 'continuous', roundness: 0.5 } },
      interaction: { hover: true, zoomView: true, dragView: true, navigationButtons: true },
    })
    relNetRef.current = net
  }, [relationshipNetwork, selectedRelationshipData])

  useEffect(() => {
    relationshipSelectionTouchedRef.current = false
    setRelationshipNetwork(null)
    setSelectedCharacterIds([])
    loadRelationshipNetwork()
  }, [projectId, loadRelationshipNetwork])

  useEffect(() => {
    renderRelationshipGraph()
  }, [renderRelationshipGraph])

  useEffect(() => () => {
    relNetRef.current?.destroy()
  }, [])

  const relationshipEmptyDescription = useMemo(() => {
    if (!relationshipNetwork || relationshipNetwork.nodes.length === 0) return '暂无角色关系数据'
    if (selectedRelationshipData.nodes.length === 0) return '请选择要显示的角色'
    return ''
  }, [relationshipNetwork, selectedRelationshipData.nodes.length])

  const showEmpty = !loading && relationshipEmptyDescription.length > 0

  return (
    <div style={{ padding: 16, height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      <Space style={{ marginBottom: 12 }} wrap>
        <Title level={4} style={{ margin: 0 }}><TeamOutlined /> 角色关系图</Title>
      </Space>

      {relationshipNetwork && relationshipNetwork.nodes.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <Select
            mode="multiple"
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="选择要显示的角色"
            maxTagCount="responsive"
            value={selectedCharacterIds}
            options={characterSelectOptions}
            onChange={handleSelectedCharacterChange}
            style={{ minWidth: 280, flex: '1 1 420px' }}
          />
          <Tooltip title="按主角优先和关系密度显示一组核心角色">
            <Button icon={<StarOutlined />} onClick={resetToKeyCharacters}>
              主要角色
            </Button>
          </Tooltip>
          <Button icon={<CheckSquareOutlined />} onClick={selectAllCharacters}>
            全选
          </Button>
          <Button icon={<ClearOutlined />} onClick={clearSelectedCharacters}>
            清空
          </Button>
          <Text type="secondary">
            显示 {selectedRelationshipData.nodes.length}/{relationshipNetwork.nodes.length} 角色，
            {selectedRelationshipData.edges.length} 条关系
          </Text>
        </div>
      )}

      <Card style={{ flex: 1, overflow: 'hidden' }} bodyStyle={{ height: '100%', padding: 0, position: 'relative' }}>
        {loading && (
          <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 10 }}>
            <Spin />
          </div>
        )}
        <div
          ref={relRef}
          style={{ width: '100%', height: '100%', minHeight: 500 }}
        />
        {showEmpty && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={relationshipEmptyDescription}
            style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}
          />
        )}
      </Card>
    </div>
  )
}

export default VisualizationPage
