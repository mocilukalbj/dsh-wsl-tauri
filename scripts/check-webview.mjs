import { readFile, writeFile } from 'node:fs/promises';

const config = JSON.parse(await readFile(new URL('../backend.json', import.meta.url), 'utf8'));
const targets = await (await fetch('http://127.0.0.1:9227/json/list')).json();
const target = targets.find(row => row.type === 'page' && ['127.0.0.1', 'localhost'].includes(new URL(row.url).hostname) && Number(new URL(row.url).port) === config.port);
if (!target) throw new Error('Harness WebView target not found');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let sequence = 0;
const pending = new Map();
const stats = { failedRequests: [], pageErrors: 0, websocketFrames: 0 };
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.id) {
    const waiter = pending.get(message.id);
    if (!waiter) return;
    pending.delete(message.id);
    if (message.error) waiter.reject(new Error(message.error.message));
    else waiter.resolve(message.result);
  }
  if (message.method === 'Runtime.exceptionThrown') stats.pageErrors++;
  if (message.method === 'Network.webSocketFrameReceived') stats.websocketFrames++;
  if (message.method === 'Network.responseReceived' && message.params.response.status >= 400) {
    const response = message.params.response;
    stats.failedRequests.push({ path: new URL(response.url).pathname, status: response.status });
  }
};
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
await send('Network.enable');
await send('Runtime.enable');
await send('Page.enable');
await send('Page.reload', { ignoreCache: true });
await new Promise(resolve => setTimeout(resolve, 15000));
const result = await send('Runtime.evaluate', {
  expression: `JSON.stringify({title:document.title, origin:location.origin, tokenRemoved:!location.search.includes('token='), rootChildren:document.getElementById('root')?.childElementCount, bootPresent:!!window.__DSH_BOOT__, bodyTextLength:document.body.innerText.length, hasEditor:!!document.querySelector('textarea,[contenteditable="true"]'), hasConnectionError:/连接失败|连接已断开|Connection failed|Disconnected/.test(document.body.innerText)})`,
  returnByValue: true,
});
const screenshot = await send('Page.captureScreenshot', { format: 'png' });
await writeFile(new URL('../webview-smoke.png', import.meta.url), Buffer.from(screenshot.data, 'base64'));
const report = { ...JSON.parse(result.result.value), ...stats };
await writeFile(new URL('../webview-smoke.json', import.meta.url), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
socket.close();
if (!report.bootPresent || !report.hasEditor || report.hasConnectionError || report.pageErrors || report.failedRequests.length || !report.websocketFrames) process.exitCode = 1;
