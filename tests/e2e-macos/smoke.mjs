// macOS 端到端冒烟验证
// 用 frontend 里已有的 playwright-core，驱动 ms-playwright 缓存里的 Chromium
import { chromium } from '/Users/admin/.npm/_npx/e41f203b7505f1fb/node_modules/playwright-core/index.mjs';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const OUT = path.resolve('tests/e2e-macos');
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

const consoleLogs = [];
page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
const pageErrors = [];
page.on('pageerror', err => pageErrors.push(String(err)));

const resp = await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 30000 });
console.log('HTTP', resp.status(), resp.url());

await page.waitForTimeout(1500); // Vue 应用初始化

const title = await page.title();
console.log('TITLE:', title);

// 抓取一些明显的 UI 痕迹
const bodyTxt = (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 600);
console.log('VISIBLE TEXT (first 600 chars):', bodyTxt);

const buttonsAll = await page.locator('button, [role=button]').allInnerTexts();
const buttons = buttonsAll.map(s => s.trim()).filter(Boolean).slice(0, 30);
console.log('BUTTONS:', JSON.stringify(buttons));

// 检查后端可达（浏览器里发起 fetch，验证 CORS 是通的）
const backendProbe = await page.evaluate(async () => {
  try {
    const r = await fetch('http://localhost:8000/docs');
    return { ok: r.ok, status: r.status };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
});
console.log('BACKEND PROBE FROM BROWSER:', JSON.stringify(backendProbe));

await page.screenshot({ path: path.join(OUT, 'home.png'), fullPage: true });
console.log('SCREENSHOT:', path.join(OUT, 'home.png'));

if (pageErrors.length) {
  console.log('PAGE ERRORS:'); pageErrors.forEach(e => console.log('  ' + e));
} else {
  console.log('PAGE ERRORS: none');
}
console.log('CONSOLE (last 10):');
consoleLogs.slice(-10).forEach(l => console.log('  ' + l));

await browser.close();
