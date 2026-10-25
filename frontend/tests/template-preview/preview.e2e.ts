/// <reference lib="dom" />
import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const read = (path: string) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8')
const html = read('../../dist-mcp/index.html')
const fixtures = JSON.parse(read('../../../output/template-browser/fixtures.json'))

/** Minimal MCP host simulator. This does not claim a real ChatGPT host run. */
async function mount(page: Page, name: string) {
  const result = fixtures[name]
  test.info().annotations.push({ type: 'candidate_hash', description: result.candidate_hash },
    { type: 'renderer_abi', description: result.renderer_abi })
  await page.route('http://flama.test/**', async (route) => {
    if (new URL(route.request().url()).pathname === '/app') {
      await route.fulfill({ contentType: 'text/html', body: html,
        headers: { 'Content-Security-Policy': "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-src 'self' blob:; img-src data:; connect-src 'none'; object-src 'none'; base-uri 'self'" } })
      return
    }
    await route.fulfill({ contentType: 'text/html', body: `<!doctype html><html><body style="margin:0"><iframe title="MCP App" id="app" sandbox="allow-scripts allow-same-origin" style="width:100%;height:920px;border:0"></iframe><script>
window.reports = [];
window.addEventListener('message', function(event) {
  const frame = document.getElementById('app');
  if(event.source !== frame.contentWindow || !event.data || event.data.jsonrpc !== '2.0') return;
  const data = event.data;
  if(data.method === 'ui/initialize') {
    event.source.postMessage({jsonrpc:'2.0',id:data.id,result:{protocolVersion:data.params.protocolVersion,hostInfo:{name:'Flama test host',version:'1'},hostCapabilities:{message:{text:{}},updateModelContext:{text:{}}},hostContext:{theme:'light'}}},'*');
  } else if(data.method === 'ui/notifications/initialized') {
    event.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:${JSON.stringify({content:[],structuredContent:result}).replace(/</g, '\\u003c')}},'*');
  } else if(data.method === 'ui/message' || data.method === 'ui/update-model-context') {
    window.reports.push(data);
    event.source.postMessage({jsonrpc:'2.0',id:data.id,result:{}},'*');
  }
});
document.getElementById('app').src='/app';
</script></body></html>` })
  })
  await page.goto('http://flama.test/host')
  const app = page.frameLocator('#app')
  await expect(app.getByTestId('candidate-hash')).toHaveText(result.candidate_hash)
  return app
}

test.afterEach(async ({ page }, info) => {
  const reports = await page.evaluate(() => (window as unknown as { reports?: unknown[] }).reports ?? []).catch(() => [])
  await info.attach('preview-evidence.json', { contentType: 'application/json', body: JSON.stringify({
    source: 'mcp_host_simulator', status: info.status, viewport: page.viewportSize(),
    candidate_hash: info.annotations.find((a) => a.type === 'candidate_hash')?.description,
    renderer_abi: info.annotations.find((a) => a.type === 'renderer_abi')?.description,
    host_reports: reports,
  }, null, 2) })
})

for (const count of [1, 2, 3]) {
  test(`quiz ${count} answers: selection, grading, reveal, keyboard and mobile`, async ({ page }) => {
    if (count === 3) await page.setViewportSize({ width: 390, height: 844 })
    const app = await mount(page, `quiz-${count}`)
    const front = app.frameLocator('iframe[title="Mặt trước thẻ"]')
    await expect(app.locator('iframe[title="Mặt trước thẻ"]')).toBeVisible()
    await expect(app.locator('iframe[title="Mặt sau thẻ"]')).toBeHidden()
    await expect(front.locator('#instruction')).toHaveText(`Select ${count} answer${count === 1 ? '' : 's'}`)
    const boxes = front.locator('input[type="checkbox"]')
    await expect(boxes).toHaveCount(count + 2)
    // Exactly N wrong selections, including one incorrect option.
    for (let index = 1; index <= count; index++) await boxes.nth(index).check()
    await expect(front.locator('#feedback')).toHaveText('Incorrect')
    await boxes.nth(count).uncheck()
    await expect(front.locator('#feedback')).toBeEmpty()
    await boxes.nth(0).focus()
    await boxes.nth(0).press('Space')
    await expect(front.locator('#feedback')).toHaveText('Correct')
    await expect(front.locator('#selection-count')).toHaveText(`${count} / ${count} selected`)
    await app.getByRole('button', { name: 'Back', exact: true }).click()
    await expect(app.locator('iframe[title="Mặt trước thẻ"]')).toBeHidden()
    await expect(app.locator('iframe[title="Mặt sau thẻ"]')).toBeVisible()
    const back = app.frameLocator('iframe[title="Mặt sau thẻ"]')
    await expect(back.locator('#answer-list li')).toHaveCount(count)
    await expect(back.locator('#explanation')).toContainText('Alpha is correct.')
    await app.getByRole('button', { name: 'Front', exact: true }).click()
    await expect(front.locator('#feedback')).toHaveText('Correct')
    await expect(app.getByText('Interaction test: not run.', { exact: false })).toBeVisible()
    await expect(app.locator('[role="alert"]')).toHaveCount(0)
    const outer = page.frames().find((frame) => frame.url() === 'http://flama.test/app')!
    expect(await outer.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    if (count === 1 || count === 3) await test.info().attach(`preview-${count}.png`, {
      contentType: 'image/png', body: await page.screenshot({ fullPage: true }),
    })
    await app.getByRole('textbox').fill(`Selected ${count} correct answers; feedback appeared.`)
    await app.getByRole('button', { name: 'Send report to chat' }).click()
    await expect(app.getByText('Report sent to chat.', { exact: true })).toBeVisible()
    const messages = await page.evaluate(() => (window as unknown as { reports: Array<{method:string;params:{content:Array<{text:string}>}}> }).reports)
    expect(messages.map((m) => m.method)).toEqual(['ui/update-model-context', 'ui/message'])
    expect(messages[0].params.content[0].text).toContain(fixtures[`quiz-${count}`].candidate_hash)
    expect(JSON.parse(messages[0].params.content[0].text).checks.interaction).toBe('not_run')
  })
}

test('missing explanation fallback', async ({ page }) => {
  const app = await mount(page, 'no-explanation')
  await app.getByRole('button', { name: 'Back', exact: true }).click()
  await expect(app.frameLocator('iframe[title="Mặt sau thẻ"]').locator('#explanation')).toHaveText('No explanation provided.')
})

test('runtime errors reach preview and report; candidate script stays inside sandbox', async ({ page }) => {
  const app = await mount(page, 'runtime-error')
  await expect(app.getByRole('alert')).toContainText('fixture runtime failure')
  await app.getByRole('button', { name: 'Send report to chat' }).click()
  await expect(app.getByText('Report sent to chat.', { exact: true })).toBeVisible()
  const reports = await page.evaluate(() => (window as unknown as { reports: unknown[] }).reports)
  expect(JSON.stringify(reports)).toContain('SANDBOX_RUNTIME_ERROR')
})

test('untrusted template never executes in outer document; sandbox permissions preserved', async ({ page }) => {
  const app = await mount(page, 'boundary')
  const front = app.frameLocator('iframe[title="Mặt trước thẻ"]')
  await expect(front.getByText('Which options are correct?', { exact: true })).toBeVisible()
  expect(await app.locator('iframe').first().getAttribute('sandbox')).toBe('allow-scripts')
  const outer = page.frames().find((frame) => frame.url() === 'http://flama.test/app')!
  expect(await outer.evaluate(() => (window as unknown as { __outerEscape?:boolean }).__outerEscape)).toBeUndefined()
})

test('unsupported candidate shows compile diagnostic without rendering', async ({ page }) => {
  const app = await mount(page, 'invalid')
  await expect(app.getByLabel('Template diagnostics')).toContainText('each')
  await expect(app.locator('iframe')).toHaveCount(0)
})
