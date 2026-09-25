import { defineStore } from 'pinia'

// 演示用账号列表：调度员负责派发/接管，巡查人员只能接受自己的单据。
export const PERSONNEL = ['调度员周敏', '值班管理员', '李建军', '王海涛', '赵晓峰', '陈志远', '孙鹏飞']

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '调度员周敏',
    shiftLabel: '白班 08:00-20:00',
    scope: '市政道路桥梁养护平台',
    personnel: PERSONNEL,
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setOperator(name: string) {
      this.operator = name
    },
  },
})
