import type { TreeModule } from './types'
import { classicPipelineTree } from './classic-pipeline'
import { soloGraphTree } from './solo-graph'
import { contextEngineTree } from './context-engine'
import { memoryLifecycleTree } from './memory-lifecycle'
import { ragStrategiesTree } from './rag-strategies'
import { architectureTree } from './architecture'

export const allTrees: TreeModule[] = [
  classicPipelineTree,
  soloGraphTree,
  contextEngineTree,
  memoryLifecycleTree,
  ragStrategiesTree,
  architectureTree,
]

export type { TreeModule, TreeNode } from './types'
