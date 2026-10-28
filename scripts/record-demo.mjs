/** Record a real local Safe journey. No wallet extension, remote chain or simulated UI. */
import {chromium} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const directory=path.resolve('.local-demo/recordings');fs.mkdirSync(directory,{recursive:true});
const browser=await chromium.launch({channel:'chromium'});
const context=await browser.newContext({viewport:{width:1280,height:900},recordVideo:{dir:directory,size:{width:1280,height:900}}});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const start=Date.now();
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const role=value=>page.getByLabel('Test role').selectOption(value);
async function run(label){
  const response=page.waitForResponse(r=>r.url().includes('/api/local/')&&r.request().method()==='POST');
  await page.getByRole('button',{name:label,exact:true}).click();
  const result=await response;if(!result.ok())throw Error(await result.text());
  await page.getByRole('status').waitFor({state:'hidden',timeout:90000});
}
await page.goto(process.env.CLUETIDE_DEMO_URL||'http://127.0.0.1:8787');
await page.getByRole('button',{name:'New Safe task',exact:true}).waitFor();await pause(5000);
await run('New Safe task');await role('proposer');await run('Submit v1');
await role('reviewer');await run('Prepare correction');await pause(3000);
await run('Sign as owner 1');await pause(3000);await run('Sign as owner 2');await run('Execute Safe decision');
await run('Sign feedback with two owners');
await page.getByRole('heading',{name:'Verification & activity'}).scrollIntoViewIfNeeded();await pause(5000);
await role('proposer');await page.getByLabel('Change summary').fill('Add independent verification and recovery instructions');
await page.getByLabel('Artifact HTML').fill('<!doctype html><html lang=en><meta charset=utf-8><title>ClueTide verified release</title><h1>Release v2 — verified delivery</h1><p>Download the acceptance ZIP. Obtain the deployment profile separately. Run cluetide-release verify.</p></html>');
await run('Submit revised version');await role('reviewer');await run('Prepare approval');
await run('Sign as owner 1');await pause(3000);await run('Sign as owner 2');await run('Execute Safe decision');
await role('executor');await run('Consume approval');await run('Publish / recover');await run('Record signed receipt');
await role('auditor');await run('Verify offline');await page.getByTestId('result').scrollIntoViewIfNeeded();await pause(5000);
await run('Verify chain + delivery');await page.getByTestId('result').scrollIntoViewIfNeeded();await pause(5000);
await page.getByRole('button',{name:'Test one-byte tamper'}).click();await page.getByRole('alert').waitFor();
await page.getByRole('alert').scrollIntoViewIfNeeded();await pause(6000);
await page.screenshot({path:'docs/media/local-safe-demo.png',fullPage:true});
if(Date.now()-start<120000)await pause(120000-(Date.now()-start));
const video=page.video();await context.close();await video.saveAs('docs/media/cluetide-v0.2.0-local-demo.webm');await browser.close();
if(errors.length)throw Error(errors.join('\n'));
fs.writeFileSync('docs/media/recording.json',JSON.stringify({version:'0.2.0',chain_id:31337,kind:'actual_local_browser_recording',duration_seconds:Math.round((Date.now()-start)/1000),recorded_at:new Date().toISOString(),console_errors:errors},null,2)+'\n');
console.log('Recorded real local Safe workflow: docs/media/cluetide-v0.2.0-local-demo.webm');
