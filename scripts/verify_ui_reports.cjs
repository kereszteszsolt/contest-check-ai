// SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
// SPDX-License-Identifier: Apache-2.0

// Operator-only browser checks against the accompanying fixed offline service.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.CCA_PLAYWRIGHT_MODULE || 'playwright');
const [url, fixtures, output] = process.argv.slice(2);
const { expect: baseExpect } = require(path.join(process.env.CCA_PLAYWRIGHT_MODULE || 'playwright', 'test'));
const expect = baseExpect.configure({ timeout: 15000 });

async function showFromTop(locator) {
  await locator.evaluate(element => {
    element.scrollIntoView({ block: 'start' });
    for (let parent = element.parentElement; parent; parent = parent.parentElement) {
      if (parent.scrollHeight > parent.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(parent).overflowY)) {
        parent.scrollTop -= 75;
        break;
      }
    }
  });
}

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CCA_BROWSER_EXECUTABLE || undefined });
  let page;
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
    const blocked = [];
    await context.route('**/*', route => {
      const target = new URL(route.request().url());
      if (target.hostname === '127.0.0.1') return route.continue();
      blocked.push(target.origin);
      return route.abort();
    });
    page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    await expect(page.getByRole('heading', { name: 'ContestCheck AI', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Run solutions', exact: true })).toBeDisabled();
    await page.screenshot({ path: path.join(output, 'initial-desktop.png'), fullPage: true });
    const uploads = page.locator('input[type=file]');
    await uploads.nth(0).setInputFiles(path.join(fixtures, 'task.zip'));
    await uploads.nth(1).setInputFiles(path.join(fixtures, 'invalid.zip'));
    await page.getByRole('button', { name: 'Validate archives', exact: true }).click();
    await expect(page.getByText('Upload must be a complete, supported ZIP archive.', { exact: true })).toBeVisible();
    await page.screenshot({ path: path.join(output, 'rejected-desktop.png'), fullPage: true });
    await uploads.nth(1).setInputFiles(path.join(fixtures, 'submissions.zip'));
    await expect(page.getByText('Upload must be a complete, supported ZIP archive.', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Validate archives', exact: true }).click();
    await expect(page.getByText('Both archives passed validation.', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Run solutions', exact: true }).click();
    await expect(page.getByText('Running solutions…', { exact: true })).toBeVisible();
    await page.screenshot({ path: path.join(output, 'running-desktop.png'), fullPage: true });
    await expect(page.getByText('Batch complete. Results contain anonymous participant IDs only.', { exact: true })).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId('stDataFrame')).toHaveCount(4);
    await page.getByRole('button', { name: 'Prepare PDF and XLSX', exact: true }).click();
    for (const format of ['pdf', 'xlsx']) {
      const button = page.getByRole('button', { name: `Download ${format.toUpperCase()}`, exact: true });
      await expect(button).toBeVisible({ timeout: 30000 });
      const pending = page.waitForEvent('download');
      await button.click();
      const download = await pending;
      assert.equal(download.suggestedFilename(), `contestcheck-offline-ui-fixture.${format}`);
      await download.saveAs(path.join(output, `download.${format}`));
    }
    await page.screenshot({ path: path.join(output, 'results-downloads-desktop.png'), fullPage: true });
    await showFromTop(page.getByRole('heading', { name: 'Results', exact: true }));
    await page.screenshot({ path: path.join(output, 'results-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await showFromTop(page.getByRole('heading', { name: 'ContestCheck AI', exact: true }));
    await page.screenshot({ path: path.join(output, 'uploads-mobile.png'), fullPage: true });
    await showFromTop(page.getByRole('heading', { name: 'Results', exact: true }));
    await page.screenshot({ path: path.join(output, 'results-mobile.png'), fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.setViewportSize({ width: 1440, height: 1000 });
    await uploads.nth(1).setInputFiles(path.join(fixtures, 'incomplete.zip'));
    await expect(page.getByRole('button', { name: 'Download PDF', exact: true })).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Results', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Run solutions', exact: true })).toBeDisabled();
    await page.getByRole('button', { name: 'Validate archives', exact: true }).click();
    await expect(page.getByText('Both archives passed validation.', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Run solutions', exact: true }).click();
    await expect(page.getByText('The batch stopped after a judge system error. Not-run tests are not participant failures.', { exact: true })).toBeVisible({ timeout: 30000 });
    await page.screenshot({ path: path.join(output, 'incomplete-desktop.png'), fullPage: true });
    assert.deepEqual(errors, []);
    assert(fs.statSync(path.join(output, 'download.pdf')).size > 1000);
    assert(fs.statSync(path.join(output, 'download.xlsx')).size > 1000);
    process.stdout.write(JSON.stringify({ browser: browser.version(), viewports: ['1440x1000', '390x844'],
      upload_rejection: true, running_state: true, downloads: ['pdf', 'xlsx'], stale_results_cleared: true,
      incomplete_batch: true, page_errors: errors, blocked_external_origins: [...new Set(blocked)] }));
    await context.close();
  } catch (error) {
    if (page) {
      await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true });
      fs.writeFileSync(path.join(output, 'failure-text.txt'), await page.locator('body').innerText());
    }
    throw error;
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(String(error)); process.exit(1); });
