// 截图 /style-lab（新）+ /（主页，验证 Tailwind 不污染现有页面）
import { chromium } from '/Users/admin/.npm/_npx/e41f203b7505f1fb/node_modules/playwright-core/index.mjs';
import path from 'node:path';

const OUT = path.resolve('tests/e2e-macos');

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });

for (const [route, name] of [['/style-lab', 'style-lab'], ['/', 'home-after-tailwind']]) {
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('http://localhost:5173' + route, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
  console.log(`[${route}] saved -> ${name}.png, errors:`, errors.length ? errors : 'none');
  await page.close();
}

await browser.close();
