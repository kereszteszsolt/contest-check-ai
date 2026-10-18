// SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
// SPDX-License-Identifier: Apache-2.0

// Operator-only checks against verify_authoring_ui.py's fixed offline fixture API.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const modulePath = process.env.CCA_PLAYWRIGHT_MODULE || 'playwright';
const { chromium } = require(modulePath);
const { expect: baseExpect } = require(path.join(modulePath, 'test'));
const expect = baseExpect.configure({ timeout: 15000 });
const [url, apiUrl, output] = process.argv.slice(2);

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CCA_BROWSER_EXECUTABLE });
  let page;
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
    const blocked = [], errors = [];
    await context.route('**/*', route => {
      if (new URL(route.request().url()).hostname === '127.0.0.1') return route.continue();
      blocked.push(route.request().url());
      return route.abort();
    });
    page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    const button = label => page.getByRole('button', { name: label, exact: true });
    const calls = async () => (await (await context.request.get(`${apiUrl}/_offline/evidence`)).json()).calls.length;
    const start = async (instructions = 'Create an addition exercise.') => {
      await page.getByRole('combobox').first().click();
      await page.getByRole('option', { name: 'ollama · offline-fixture:1', exact: true }).click();
      await page.getByRole('textbox', { name: 'Topic', exact: true }).fill('arithmetic');
      await page.getByRole('textbox', { name: 'Teacher instructions', exact: true }).fill(instructions);
      await page.getByRole('textbox', { name: 'Teacher instructions', exact: true }).press('Control+Enter');
      await expect(button('Generate draft')).toBeEnabled();
      await button('Generate draft').click();
      await expect(button('Reject draft')).toBeVisible();
    };
    await page.goto(url);
    await page.getByText('AI task draft', { exact: true }).click();
    await expect(button('Generate draft')).toBeDisabled();
    await page.getByRole('combobox').first().click();
    await page.getByRole('option', { name: 'openrouter · offline/fixture', exact: true }).click();
    await expect(page.getByText(/may incur charges/)).toBeVisible();
    assert.equal(await calls(), 0);
    await page.screenshot({ path: path.join(output, 'initial-desktop.png'), fullPage: true });
    await start();
    await expect(button('Approve draft')).toBeDisabled();
    await expect(button('Download student ZIP')).toHaveCount(0);
    const workflowId = (await (await context.request.get(`${apiUrl}/_offline/evidence`)).json()).workflow_ids[0];
    await button('Refresh draft').click();
    await expect(button('Reject draft')).toBeVisible();
    assert.equal(await calls(), 1);
    await page.getByRole('textbox', { name: 'Changes requested', exact: true }).fill('Explain negative integers.');
    await page.getByRole('textbox', { name: 'Changes requested', exact: true }).press('Control+Enter');
    await expect(button('Request changes')).toBeEnabled();
    await button('Request changes').click();
    await expect(page.getByText(/Attempt: 2\/3/)).toBeVisible();
    assert.equal(await calls(), 2);
    await page.getByTestId('stSidebar').hover();
    await page.getByRole('button', { name: 'Collapse sidebar', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Expand sidebar', exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => page.getByTestId('stSidebar').evaluate(element => element.getBoundingClientRect().right)).toBeLessThanOrEqual(1);
    await page.getByRole('heading', { name: 'AI task draft', exact: true }).evaluate(element => {
      for (let parent = element.parentElement; parent; parent = parent.parentElement) {
        if (parent.scrollHeight > parent.clientHeight) parent.scrollTop = 0;
      }
    });
    await expect(page.getByRole('heading', { name: 'AI task draft', exact: true })).toBeVisible();
    await page.screenshot({ path: path.join(output, 'review-mobile.png'), fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.getByRole('textbox', { name: 'Changes requested', exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'review-controls-mobile.png'), fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByText(/^I reviewed the statement, examples, reference and private tests, and accept the warnings\.$/).click();
    await expect(page.getByRole('checkbox', { name: /^I reviewed/ })).toBeChecked();
    await button('Approve draft').click();
    await expect(page.getByText('Teacher approval recorded. The challenge remains unverified.', { exact: true })).toBeVisible();
    await button('Prepare separate ZIP downloads').click();
    const downloadUrls = [];
    for (const audience of ['student', 'teacher']) {
      await expect(button(`Download ${audience} ZIP`)).toBeVisible();
      const pending = page.waitForEvent('download');
      await button(`Download ${audience} ZIP`).click();
      const download = await pending;
      downloadUrls.push(download.url());
      assert.equal(download.suggestedFilename(), `offline-authoring-${audience}.zip`);
      await download.saveAs(path.join(output, `${audience}.zip`));
    }
    await page.screenshot({ path: path.join(output, 'approved-desktop.png'), fullPage: true });
    assert.equal(await calls(), 2);
    // Closing a tab must delete even an approved checkpoint and its packages.
    const oldPage = page;
    page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    await expect(page.getByRole('heading', { name: 'ContestCheck AI', exact: true })).toBeVisible();
    const expand = page.getByRole('button', { name: 'Expand sidebar', exact: true });
    if (await expand.isVisible()) await expand.click();
    await page.getByText('AI task draft', { exact: true }).click();
    await expect(button('Generate draft')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Resume workflow', exact: true })).toHaveCount(0);
    await expect(page.getByRole('textbox', { name: 'Private workflow ID', exact: true })).toHaveCount(0);
    await expect(button('Download student ZIP')).toHaveCount(0);
    assert.equal(await calls(), 2);
    await oldPage.close();
    await expect.poll(async () => (await context.request.get(`${apiUrl}/api/authoring/workflows/${workflowId}`)).status()).toBe(404);
    for (const downloadUrl of downloadUrls) {
      await expect.poll(async () => (await context.request.get(downloadUrl)).status()).toBe(404);
    }
    for (const audience of ['student', 'teacher']) {
      assert.equal((await context.request.post(`${apiUrl}/api/authoring/workflows/${workflowId}/packages/${audience}`, { data: {} })).status(), 404);
    }
    await start();
    await button('Reject draft').click();
    await expect(page.getByText('Draft rejected. No final packages are available.', { exact: true })).toBeVisible();
    await expect(button('Download student ZIP')).toHaveCount(0);
    await page.screenshot({ path: path.join(output, 'rejected-desktop.png'), fullPage: true });
    await button('Discard draft and start over').click();
    await start('Malformed output fixture.');
    await expect(button('Approve draft')).toBeDisabled();
    await expect(page.getByText('Attempt 1: invalid_output', { exact: true })).toBeVisible();
    await page.screenshot({ path: path.join(output, 'invalid-output-desktop.png'), fullPage: true });
    await button('Reject draft').click();
    await expect(page.getByText('Draft rejected. No final packages are available.', { exact: true })).toBeVisible();
    assert.equal(await calls(), 4);
    await button('Discard draft and start over').click();
    await start();
    const activeId = async () => (await (await context.request.get(`${apiUrl}/_offline/evidence`)).json()).workflow_ids[0];
    const assertGone = async id => {
      await expect.poll(async () => (await context.request.get(`${apiUrl}/api/authoring/workflows/${id}`)).status()).toBe(404);
    };
    const workspaceId = await activeId();
    await page.getByText('Judge submissions', { exact: true }).click();
    await assertGone(workspaceId);
    await page.getByText('AI task draft', { exact: true }).click();
    await expect(button('Generate draft')).toBeDisabled();
    await start();
    const navigationId = await activeId();
    await page.goto('about:blank');
    await assertGone(navigationId);
    await page.goto(url);
    await expect(page.getByRole('heading', { name: 'ContestCheck AI', exact: true })).toBeVisible();
    const expandAgain = page.getByRole('button', { name: 'Expand sidebar', exact: true });
    if (await expandAgain.isVisible()) await expandAgain.click();
    await page.getByText('AI task draft', { exact: true }).click();
    await expect(button('Generate draft')).toBeDisabled();
    await start();
    const browserId = await activeId();
    await page.screenshot({ path: path.join(output, 'temporary-draft-desktop.png'), fullPage: true });
    const observer = await chromium.launch({ headless: true, executablePath: process.env.CCA_BROWSER_EXECUTABLE });
    try {
      const observerContext = await observer.newContext();
      await browser.close();
      await expect.poll(async () => (await observerContext.request.get(`${apiUrl}/api/authoring/workflows/${browserId}`)).status()).toBe(404);
      const final = await (await observerContext.request.get(`${apiUrl}/_offline/evidence`)).json();
      assert.deepEqual(final.workflow_ids, []);
      assert.equal(final.checkpoint_count, 0);
      assert.equal(final.retained_previews, 0);
      assert.equal(final.calls.length, 7);
    } finally { await observer.close(); }
    assert.deepEqual(errors, []);
    assert.deepEqual(blocked, []); // Generated image markup is text; no external request attempted.
    process.stdout.write(JSON.stringify({ browser: browser.version(), viewports: ['1440x1000', '390x844'],
      decisions: ['revise', 'approve', 'reject'], separate_downloads: true, checkpoint_resume: false, tab_close_cleanup: true, old_download_urls_removed: true, navigation_cleanup: true, workspace_exit_cleanup: true, browser_close_cleanup: true, checkpoint_count_after_close: 0,
      refresh_without_generation: true, malformed_output: true, page_errors: errors,
      blocked_external_requests: blocked }));

  } catch (error) {
    if (page && !page.isClosed()) {
      await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true });
      fs.writeFileSync(path.join(output, 'failure-text.txt'), await page.locator('body').innerText());
    }
    throw error;
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(String(error)); process.exit(1); });
