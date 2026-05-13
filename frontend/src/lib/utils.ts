import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * shadcn-vue 约定的 className 合并器：同时 tailwind-merge（解决冲突）
 * 和 clsx（条件 class）。所有 ui/* 组件都会 import { cn } from '@/lib/utils'。
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
