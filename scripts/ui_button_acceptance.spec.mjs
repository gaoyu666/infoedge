import { test, expect } from "@playwright/test";

const APP_URL = "http://127.0.0.1:5177";
const API_URL = "http://127.0.0.1:8000";

test("frontend button acceptance", async ({ page }) => {
  test.setTimeout(120000);
  const executableResponse = await page.request.get(`${API_URL}/api/opportunities?stage=executable&sort=score&limit=10`);
  const executablePayload = await executableResponse.json();
  const executableOpportunityId = executablePayload?.data?.items?.find((item) => item?.id && item.execution_gate_passed !== false)?.id;
  const opportunitiesResponse = await page.request.get(`${API_URL}/api/opportunities?limit=5`);
  const opportunitiesPayload = await opportunitiesResponse.json();
  const firstOpportunityId = executableOpportunityId || opportunitiesPayload?.data?.items?.[0]?.id;

  await page.goto(`${APP_URL}/workspace/opportunities`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("opportunities-refresh").waitFor({ state: "visible" });

  if (firstOpportunityId) {
    const executeButton = page.getByTestId(/opportunity-execute-/).first();
    await expect(executeButton).toBeVisible({ timeout: 60000 });
    if (await executeButton.isEnabled()) {
      await executeButton.click();
    }
  }

  await page.goto(`${APP_URL}/workspace/actions`, { waitUntil: "domcontentloaded" });
  const nextButton = page.getByTestId(/action-next-step-/).first();
  if (await nextButton.count()) {
    await expect(nextButton).toBeVisible();
    await nextButton.click();
  }

  const completeButton = page.getByTestId(/action-complete-/).first();
  if (await completeButton.count()) {
    await expect(completeButton).toBeVisible();
    await completeButton.click();
  }

  await page.goto(`${APP_URL}/workspace/brief`, { waitUntil: "domcontentloaded" });
  const generateButton = page.getByTestId("brief-generate-new");
  await expect(generateButton).toBeVisible();
  await generateButton.click();

  await page.goto(`${APP_URL}/workspace/sources`, { waitUntil: "domcontentloaded" });
  const refreshButton = page.getByTestId(/source-freshness-/).first();
  if (await refreshButton.count()) {
    await expect(refreshButton).toBeVisible();
    await refreshButton.click();
  }

  await page.goto(`${APP_URL}/workspace/settings`, { waitUntil: "domcontentloaded" });
  const runPipelineButton = page.getByTestId("settings-run-pipeline");
  await expect(runPipelineButton).toBeVisible();
  await runPipelineButton.click();

  const testModelButton = page.getByTestId(/settings-test-model-/).first();
  if (await testModelButton.count()) {
    await testModelButton.click();
  }

  const saveAllocationButton = page.getByTestId("settings-save-allocation");
  await expect(saveAllocationButton).toBeVisible();
  await saveAllocationButton.click();
});
