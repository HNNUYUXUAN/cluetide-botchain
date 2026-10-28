import {test,expect} from '@playwright/test';
for(const mode of ['EOA','Safe']){
  test(`${mode} exact-version browser journey`,async({page})=>{
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('/');
    const role=value=>page.getByLabel('Test role').selectOption(value);
    const run=async(label)=>{
      const response=page.waitForResponse(r=>r.url().includes('/api/local/')&&r.request().method()==='POST');
      await page.getByRole('button',{name:label,exact:true}).click();
      const r=await response;expect(r.ok(),await r.text()).toBeTruthy();
      await expect(page.getByRole('status')).toHaveCount(0,{timeout:90000});
    };
    const review=async(action)=>{
      await role('reviewer');
      await run(mode==='Safe'?`Prepare ${action}`:action==='approval'?'Approve exact version':'Request correction');
      if(mode==='Safe'){
        await run('Sign as owner 1');
        await expect(page.getByRole('button',{name:'Execute Safe decision'})).toBeDisabled();
        await run('Sign as owner 2');
        await run('Execute Safe decision');
      }
    };
    await expect(page.getByText('LOCAL CHAIN · 31337',{exact:true})).toBeVisible();
    await run(`New ${mode} task`);await role('proposer');await run('Submit v1');
    await review('correction');
    await run(mode==='Safe'?'Sign feedback with two owners':'Sign correction feedback');
    await role('proposer');
    await page.getByLabel('Artifact HTML').fill('<!doctype html><html lang=en><title>ClueTide verified delivery</title><h1>Release v2</h1><p>Download acceptance ZIP, trust the deployment separately, verify exact bytes.</p></html>');
    await page.getByLabel('Change summary').fill('Add independent verification instructions');
    await run('Submit revised version');await review('approval');
    await page.reload();await expect(page.getByText('Version 2 · Approved',{exact:true})).toBeVisible();
    await role('executor');await run('Consume approval');await run('Publish / recover');await run('Publish / recover');await run('Record signed receipt');
    await role('auditor');await run('Verify offline');
    await expect(page.getByTestId('result')).toContainText('"chain_authorization": "not_checked"');
    if(mode==='Safe')await expect(page.getByTestId('result')).toContainText('requires_chain_state');
    await run('Verify chain + delivery');await expect(page.getByTestId('result')).toContainText('"live_artifact_verified": true');
    const download=page.waitForEvent('download');await page.getByText('Download acceptance ZIP',{exact:true}).click();
    expect((await download).suggestedFilename()).toContain('.zip');
    await page.getByRole('button',{name:'Test one-byte tamper'}).click();
    await expect(page.getByRole('alert')).toContainText('Delivered artifact differs');
    await page.screenshot({path:`test-results/${mode.toLowerCase()}-desktop.png`,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await expect(page.getByRole('heading',{name:'Evidence anyone can check'})).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    await page.screenshot({path:`test-results/${mode.toLowerCase()}-mobile.png`,fullPage:true});
    expect(errors).toEqual([]);
  });
}
