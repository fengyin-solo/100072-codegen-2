/** 巡查派发与回执模块：与后端 /api/patrol 对齐的类型、状态机常量与请求封装。 */
import { request } from '@/api/client'

export const STATUSES = ['待派发', '进行中', '已回执', '已关闭'] as const
export type PatrolStatus = (typeof STATUSES)[number]

export const ACTIONS = {
  dispatch: '派发',
  accept: '接受',
  receipt: '提交回执',
  close: '关闭',
  return: '退回',
  takeover: '换人接管',
} as const
export type PatrolAction = (typeof ACTIONS)[keyof typeof ACTIONS]

export interface FlowRecord {
  时间: string
  操作人: string
  动作: string
  原状态: string
  目标状态: string
  原因: string
  备注: string
}

export interface PatrolEntry {
  id: number
  status: PatrolStatus
  巡查状态: PatrolStatus
  巡查单号: string
  巡查路线: string
  巡查人员: string
  巡查日期: string
  巡查里程: string | number
  发现问题数: string | number
  巡查时长: string
  已接受: boolean
  pending: boolean
  abnormal: boolean
  流转记录: FlowRecord[]
  [key: string]: unknown
}

export interface PagePayload {
  items: PatrolEntry[]
  total: number
  page: number
  size: number
}

export interface BoardColumn {
  status: PatrolStatus
  items: PatrolEntry[]
}

export interface RouteGroup {
  route: string
  blocked: boolean
  items: PatrolEntry[]
}

export interface ActionResponse {
  ok: boolean
  message: string
  entry: PatrolEntry | null
}

export async function fetchBoard(): Promise<{ columns: BoardColumn[]; total: number }> {
  const response = await request('/api/patrol/board')
  if (!response.ok) throw new Error('派发看板读取失败')
  return response.json()
}

export async function fetchRoutes(): Promise<{ groups: RouteGroup[]; total: number }> {
  const response = await request('/api/patrol/routes')
  if (!response.ok) throw new Error('巡查路线视图读取失败')
  return response.json()
}

export async function fetchTodo(person: string): Promise<{ items: PatrolEntry[]; total: number }> {
  const query = new URLSearchParams({ person })
  const response = await request(`/api/patrol/todo?${query.toString()}`)
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))).detail
    throw new Error(detail ?? '人员待办读取失败')
  }
  return response.json()
}

export async function fetchPatrolList(filters: Record<string, string>): Promise<PagePayload> {
  const query = new URLSearchParams(Object.fromEntries(Object.entries(filters).filter(([, v]) => v)))
  const response = await request(`/api/patrol?${query.toString()}`)
  if (!response.ok) throw new Error('巡查单列表读取失败')
  return response.json()
}

/**
 * 执行巡查单动作。后端不满足前置条件时返回 200 + ok:false，
 * message 里写明卡在哪一步，这里原样透传给页面。
 */
export async function runPatrolAction(
  entryId: number,
  values: Record<string, unknown>,
): Promise<ActionResponse> {
  const response = await request(`/api/patrol/${entryId}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  if (!response.ok) throw new Error('巡查动作请求失败')
  return response.json()
}

export async function createPatrol(values: Record<string, unknown>): Promise<ActionResponse> {
  const response = await request('/api/patrol', {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  if (!response.ok) throw new Error('巡查单登记请求失败')
  return response.json()
}

/** 各状态下允许的动作，按钮按此渲染，后端还会再校验一遍。 */
export function actionsFor(entry: PatrolEntry): PatrolAction[] {
  if (entry.status === '待派发') return [ACTIONS.dispatch]
  if (entry.status === '进行中') {
    return entry.已接受
      ? [ACTIONS.receipt, ACTIONS.return, ACTIONS.takeover]
      : [ACTIONS.accept, ACTIONS.return, ACTIONS.takeover]
  }
  if (entry.status === '已回执') return [ACTIONS.close, ACTIONS.return]
  return []
}

export function badgeClass(status: PatrolStatus): string {
  if (status === '待派发') return 'badge badge-pending'
  if (status === '进行中') return 'badge badge-doing'
  if (status === '已回执') return 'badge badge-receipt'
  return 'badge badge-closed'
}
