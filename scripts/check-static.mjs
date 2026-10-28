/** Exercise the historical case in the built static site with external networking blocked. */
import {chromium,expect} from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve('frontend/dist');
const types={'.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json','.zip':'application/zip','.svg':'image/svg+xml','.png':'image/png'};
const server=http.createServer((request,response)=>{
  const pathname=new URL(request.url,'http://localhost').pathname;
  const target=path.resolve(root,'.'+decodeURIComponent(pathname==='/'?'/index.html':pathname));
  if(!target.startsWith(root+path.sep)||!fs.existsSync(target)||!fs.statSync(target).isFile()){response.writeHead(404).end();return;}
  response.setHeader('Content-Type',types[path.extname(target)]||'application/octet-stream');fs.createReadStream(target).pipe(response);
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({channel:'chromium'});
try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const base='http://127.0.0.1:'+server.address().port;
  await page.route('**/*',route=>route.request().url().startsWith(base)?route.continue():route.abort());
  await page.goto(base);
  await expect(page.getByRole('heading',{name:'Three versions. One verifiable delivery.'})).toBeVisible();
  await expect(page.getByRole('link',{name:'Source code',exact:true})).toHaveAttribute('href','https://github.com/HNNUYUXUAN/cluetide-botchain');
  const download=page.waitForEvent('download');await page.getByText('Download original acceptance ZIP',{exact:true}).click();await download;
  await page.getByRole('button',{name:'Open the three-version case'}).click();
  await expect(page).toHaveURL(/version=3/);
  await expect(page.getByText('This link opens version 3. You control which version you review.')).toBeVisible();
  await page.goto(base+'/#/verify');
  await page.getByLabel('Offline acceptance bundle').setInputFiles('evidence/complete-mainnet/acceptance-v3.zip');
  await page.getByRole('button',{name:'Verify bundle offline'}).click();
  await expect(page.getByText(/Offline check passed for .*version 3: original files and executor signature are consistent/)).toBeVisible();
  await page.screenshot({path:'test-results/static-offline.png',fullPage:true});
  expect(errors).toEqual([]);
  console.log('Static flagship v3, original download and offline verification passed with external networking blocked');
}finally{await browser.close();server.close();}
