import { chromium } from '/Users/admin/.npm/_npx/e41f203b7505f1fb/node_modules/playwright-core/index.mjs';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const OUT = path.resolve('tests/e2e-macos');
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
await page.goto('http://localhost:5173/knowledge', { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(2000); // 等 /api/embedding/system-info 回来渲染

const txt = (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 800);
console.log('VISIBLE:', txt);

// 检查新标签在不在
const hasMps = txt.includes('MPS') || txt.includes('Apple Silicon');
const hasOldCudaLabel = txt.includes('PyTorch CUDA');
const hasOldNvidiaHint = txt.includes('未检测到 NVIDIA GPU');
const hasCu121Hint = txt.includes('cu121');
console.log('HAS MPS / Apple:', hasMps);
console.log('HAS old "PyTorch CUDA" label:', hasOldCudaLabel);
console.log('HAS old "未检测到 NVIDIA GPU":', hasOldNvidiaHint);
console.log('HAS cu121 hint (should not):', hasCu121Hint);

// GPU radio button 是否可点
const gpuBtn = page.getByRole('radio', { name: 'GPU 推理' });
const disabled = await gpuBtn.isDisabled().catch(() => 'N/A');
console.log('GPU 推理 disabled:', disabled);

await page.screenshot({ path: path.join(OUT, 'knowledge.png'), fullPage: true });
console.log('SCREENSHOT:', path.join(OUT, 'knowledge.png'));

await browser.close();
