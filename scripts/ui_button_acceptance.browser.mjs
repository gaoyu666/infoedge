import { chromium } from "playwright";

const APP_URL = "http://127.0.0.1:5177";
const API_URL = "http://127.0.0.1:8000";

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function run() {
  const checks = [];
  const pass = (name) => checks.push(`[OK] ${name}`);
  const fail = (name, err) => checks.push(`[FAIL] ${name} => ${err.message}`);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    const oppResp = await page.request.get(`${API_URL}/api/opportunities?limit=5`);
    const oppPayload = await oppResp.json();
    const firstOpportunityId = oppPayload?.data?.items?.[0]?.id;

    await page.goto(`${APP_URL}/workspace/opportunities`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("opportunities-refresh").waitFor({ state: "visible" });

    if (firstOpportunityId) {
      await page.getByTestId(`opportunity-execute-${firstOpportunityId}`).click();
      pass("opportunity execute");
      await wait(500);
    } else {
      fail("opportunity execute", new Error("no opportunity id"));
    }

    await page.goto(`${APP_URL}/workspace/actions`, { waitUntil: "domcontentloaded" });
    const nextButton = page.getByTestId(/action-next-step-/).first();
    const completeButton = page.getByTestId(/action-complete-/).first();
    const nextButtons = await nextButton.count();
    const completeButtons = await completeButton.count();
    if (nextButtons > 0) {
      await nextButton.click();
      pass("action next step");
    } else {
      pass("action next step skipped (no button)");
    }
    if (completeButtons > 0) {
      await completeButton.click();
      pass("action complete");
    } else {
      pass("action complete skipped (no button)");
    }

    await page.goto(`${APP_URL}/workspace/brief`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("brief-generate-new").click();
    pass("brief generate");

    await page.goto(`${APP_URL}/workspace/sources`, { waitUntil: "domcontentloaded" });
    const refreshButtons = page.locator("[data-testid^='source-freshness-']");
    const refreshCount = await refreshButtons.count();
    if (refreshCount > 0) {
      await refreshButtons.first().click();
      pass("source refresh");
    } else {
      pass("source refresh skipped (no button)");
    }

    await page.goto(`${APP_URL}/workspace/settings`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("settings-run-pipeline").click();
    pass("settings run pipeline");

    const testButtons = page.locator("[data-testid^='settings-test-model-']");
    const testButtonCount = await testButtons.count();
    if (testButtonCount > 0) {
      await testButtons.first().click();
      pass("settings model test");
      await wait(500);
    } else {
      pass("settings model test skipped (no button)");
    }

    await page.getByTestId("settings-save-allocation").click();
    pass("settings save allocation");
  } catch (error) {
    fail("browser flow", error);
  } finally {
    await browser.close();
  }

  console.log(checks.join("\n"));
  if (checks.some((item) => item.startsWith("[FAIL]"))) {
    process.exitCode = 1;
  }
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
