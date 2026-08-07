import { create } from 'zustand'

type State = { selectedCustomerId: number | null; setSelectedCustomerId: (id:number|null)=>void; sidebarOpen:boolean; setSidebarOpen:(value:boolean)=>void }
export const useAppStore = create<State>((set) => ({ selectedCustomerId: null, setSelectedCustomerId: (id) => set({ selectedCustomerId:id }), sidebarOpen:false, setSidebarOpen:(value)=>set({sidebarOpen:value}) }))
