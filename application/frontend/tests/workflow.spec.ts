import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const values = Object.fromEntries(fs.readFileSync(path.resolve('../.env'), 'utf8').split(/\r?\n/).filter(l => l.includes('=') && !l.startsWith('#')).map(l => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)]));

/** Authenticate through the real UI with local generated credentials; no secrets enter snapshots or reports. */
async function signIn(page: Page, role: 'instructor' | 'trainee') {
  await page.goto('/');
  await page.getByLabel('Email address').fill(values[`${role.toUpperCase()}_EMAIL`]);
  await page.getByLabel('Password', {exact: true}).fill(values[`${role.toUpperCase()}_PASSWORD`]);
  await page.getByRole('button', {name: 'Enter workspace'}).click();
  await expect(page.getByRole('heading', {name: 'Your next breakthrough starts here.'})).toBeVisible();
}

test('instructor reviews and publishes a validated fixture', async ({page}) => {
  await signIn(page, 'instructor');
  await page.getByRole('button', {name: 'Instructor studio', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Instructor studio'})).toBeVisible();
  const drafts = page.locator('.draft-row').filter({has: page.locator('.status.draft')});
  await expect(page.locator('.draft-row').first()).toBeVisible();
  const count = await drafts.count();
  for (let i = 0; i < count; i++) {
    await drafts.first().click();
    await page.getByText('I reviewed the safety framing', {exact: false}).click();
    await page.getByRole('button', {name: 'Approve and publish'}).click();
    await expect(drafts).toHaveCount(count - i - 1);
  }
  await page.getByRole('button', {name: 'Overview', exact: true}).click();
  await expect.poll(() => page.locator('.scenario-card').count()).toBeGreaterThanOrEqual(9);
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({path: '../docs/screenshots/dashboard.png', fullPage: true});
  await page.screenshot({path: '../docs/screenshots/workspace-preview.png'});
});

test('trainee completes a CNC investigation, receives a grade and exports PDF', async ({page}) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await signIn(page, 'trainee');
  await page.getByLabel('Difficulty', {exact: true}).selectOption('Beginner');
  await page.getByRole('button', {name: 'CNC machine', exact: true}).click();
  await page.getByRole('button', {name: 'Enter simulation', exact: true}).first().click();
  await expect(page.getByRole('heading', {name: 'A change in surface finish', level: 1})).toBeVisible();
  await page.getByRole('button', {name: 'Acknowledge safety review'}).click();
  await page.reload();
  await expect(page.getByText('STEP 2 OF 5')).toBeVisible();
  await page.getByRole('button', {name: '3D view', exact: true}).click();
  await expect(page.locator('canvas')).toBeVisible();
  for (let i = 0; i < 4; i++) {
    await page.getByRole('button', {name: 'Review and continue', exact: true}).click();
    await expect(page.getByText(i === 3 ? 'INVESTIGATION COMPLETE' : `STEP ${i + 3} OF 5`, {exact: true})).toBeVisible();
  }
  await page.screenshot({path: '../docs/screenshots/simulation.png', fullPage: true});
  await page.getByLabel('Excessive tool overhang', {exact: true}).check();
  await page.getByLabel('Tooling record', {exact: true}).check();
  await page.getByLabel('Controlled comparison', {exact: true}).check();
  await page.getByLabel('Review the authorized energy-isolation plan and verify isolation', {exact: true}).check();
  await page.getByLabel('Correlate independent evidence and test alternatives', {exact: true}).check();
  await page.getByLabel('Use them only within this synthetic training fixture', {exact: true}).check();
  await page.getByRole('button', {name: 'Submit diagnosis', exact: true}).click();
  await expect(page.getByText('Final assessment score', {exact: true})).toBeVisible();
  await expect(page.locator('.result-score strong')).toHaveText('100/100');
  const download = page.waitForEvent('download');
  await page.getByRole('link', {name: 'Download PDF'}).click();
  const file = await download;
  await file.saveAs('../docs/screenshots/example-training-report.pdf');
  await page.screenshot({path: '../docs/screenshots/result.png', fullPage: true});
  expect(errors).toEqual([]);
});

test('Expert hides hints and queues an explanation for instructor review', async ({page}) => {
  await signIn(page, 'trainee');
  await page.getByLabel('Difficulty', {exact: true}).selectOption('Expert');
  await page.getByRole('button', {name: 'Hydraulic press', exact: true}).click();
  await page.getByRole('button', {name: 'Enter simulation', exact: true}).first().click();
  await expect(page.getByRole('button', {name: 'Need a thinking prompt?'})).toHaveCount(0);
  await page.getByRole('button', {name: 'Acknowledge safety review'}).click();
  for (let i = 0; i < 4; i++) {
    await page.getByRole('button', {name: 'Review and continue', exact: true}).click();
    await expect(page.getByText(i === 3 ? 'INVESTIGATION COMPLETE' : `STEP ${i + 3} OF 5`, {exact: true})).toBeVisible();
  }
  await page.getByLabel('Suction-side air ingress', {exact: true}).check();
  await page.getByLabel('Reservoir observation', {exact: true}).check();
  await page.getByLabel('Supply comparison', {exact: true}).check();
  await page.getByLabel('Review the authorized energy-isolation plan and verify isolation', {exact: true}).check();
  await page.getByLabel('Correlate independent evidence and test alternatives', {exact: true}).check();
  await page.getByLabel('Use them only within this synthetic training fixture', {exact: true}).check();
  await page.getByPlaceholder('My strongest evidence is… An alternative could be…').fill('Aeration and the controlled suction connection comparison support air ingress. Pressure-control drift is less consistent with removal of the aeration after the virtual connection correction.');
  await page.getByRole('button', {name: 'Submit diagnosis', exact: true}).click();
  await expect(page.getByText('Provisional automatic score')).toBeVisible();
  await expect(page.locator('.result-score strong')).toHaveText('80/80');
  await page.getByRole('button', {name: 'Sign out'}).click();
  await signIn(page, 'instructor');
  await page.getByRole('button', {name: 'Instructor studio', exact: true}).click();
  await page.getByRole('button', {name: /Reasoning review/}).click();
  await page.getByLabel('Evidence reasoning · 0–10', {exact: false}).fill('10');
  await page.getByLabel('Alternative reasoning · 0–10', {exact: false}).fill('9');
  await page.getByLabel('Explain the feedback', {exact: true}).fill('You connect independent observations and compare pressure-control drift. Make the comparison acceptance condition explicit next time.');
  await page.getByRole('button', {name: 'Save review'}).click();
  await expect(page.getByText('No reasoning reviews waiting.')).toBeVisible();
});

test('generation worker produces a draft without publishing it', async ({page}) => {
  await signIn(page, 'instructor');
  await page.getByRole('button', {name: 'Instructor studio', exact: true}).click();
  await page.getByRole('button', {name: 'Generate scenario', exact: true}).click();
  await page.getByRole('button', {name: 'Generate validated draft'}).click();
  await expect(page.locator('.job-status .status')).toHaveText('succeeded', {timeout: 30000});
  await expect(page.locator('.draft-row .status.draft')).toHaveCount(1);
});

test('mobile catalog remains readable and has no horizontal overflow', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await signIn(page, 'trainee');
  await expect(page.locator('.scenario-card').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  await page.screenshot({path: '../docs/screenshots/mobile.png', fullPage: true});
});

test('failed WebGL keeps the accessible component map usable', async ({page}) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type: string, ...args: unknown[]) {
      if (type.includes('webgl')) return null;
      return original.apply(this, [type, ...args] as Parameters<typeof original>);
    } as typeof original;
  });
  await signIn(page, 'trainee');
  await page.getByLabel('Difficulty', {exact: true}).selectOption('Beginner');
  await page.getByRole('button', {name: 'Conveyor belt', exact: true}).click();
  await page.getByRole('button', {name: 'Enter simulation', exact: true}).first().click();
  await page.getByRole('button', {name: '3D view', exact: true}).click();
  await expect(page.getByText('3D is unavailable on this device.', {exact: false})).toBeVisible();
  await page.getByRole('button', {name: 'Belt', exact: true}).click();
  await expect(page.getByText('Belt selected.', {exact: false})).toBeVisible();
});
