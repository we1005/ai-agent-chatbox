import { cva, type VariantProps } from 'class-variance-authority'

export const buttonVariants = cva(
  // 基础：显式 box-sizing / flex / font 定义，不依赖 Preflight 清零
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius)] text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 cursor-pointer select-none border box-border',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground border-transparent hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground border-transparent hover:bg-destructive/90',
        outline: 'border-border bg-background text-foreground hover:bg-accent hover:text-accent-foreground hover:border-primary/50',
        secondary: 'bg-secondary text-secondary-foreground border-transparent hover:bg-secondary/80',
        ghost: 'border-transparent bg-transparent hover:bg-accent hover:text-accent-foreground',
        link: 'border-transparent bg-transparent text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-md px-3',
        lg: 'h-10 rounded-md px-8',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export type ButtonVariants = VariantProps<typeof buttonVariants>
