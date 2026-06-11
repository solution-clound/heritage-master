/**
 * CloakBrowser 辅助脚本 - 用隐身浏览器抓取网页内容
 *
 * 用法: node cloak_fetch.mjs <url> [--json] [--timeout=15000]
 * 输出: 页面文本内容到 stdout
 *
 * 注意: 需要从 CloakBrowser 安装目录运行，或设置 NODE_PATH
 */

import { launch } from 'cloakbrowser';

const args = process.argv.slice(2);
const url = args.find(a => !a.startsWith('--'));
const asJson = args.includes('--json');
const timeoutArg = args.find(a => a.startsWith('--timeout='));
const timeout = timeoutArg ? parseInt(timeoutArg.split('=')[1]) : 15000;

if (!url) {
  console.error('Usage: node cloak_fetch.mjs <url> [--json] [--timeout=15000]');
  process.exit(1);
}

let browser;
try {
  browser = await launch({ headless: true });
  const page = await browser.newPage();

  page.setDefaultTimeout(timeout);

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout });

  // 等待页面渲染
  await new Promise(r => setTimeout(r, 1000));

  let content;
  if (asJson) {
    content = await page.evaluate(() => document.body.innerText);
  } else {
    content = await page.content();
  }

  process.stdout.write(content, 'utf-8');
} catch (e) {
  console.error(`[cloak_fetch] Error: ${e.message}`);
  process.exit(1);
} finally {
  if (browser) await browser.close();
}
