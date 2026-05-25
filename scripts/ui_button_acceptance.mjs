const API_BASE = (process.env.VITE_API_BASE_URL || process.env.INFOEDGE_API_BASE || "http://127.0.0.1:8000")
  .replace(/\/api\/?$/, "")
  .replace(/\/+$/, "");

function baseUrl(path) {
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function request(path, init = {}) {
  const url = baseUrl(path.startsWith("/api") ? path : `/api${path}`);
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...init
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`HTTP ${response.status} ${response.statusText}: ${body}`);
  }
  const payload = await response.json();
  if (payload && payload.success === false) {
    throw new Error(payload.error || "API returned success=false");
  }
  return payload;
}

async function main() {
  const checks = [];
  const pass = (name) => checks.push(`[OK] ${name}`);
  const fail = (name, err) => checks.push(`[FAIL] ${name} => ${err.message}`);

  const getOppData = async () => {
    const executable = await request("/opportunities?stage=executable&sort=score&limit=10");
    const executableItem = executable?.data?.items?.find((item) => item?.id && item.execution_gate_passed !== false);
    if (executableItem?.id) return { opportunity: executableItem, executable: true };
    const opportunities = await request("/opportunities?limit=5");
    const first = opportunities?.data?.items?.[0];
    if (!first?.id) throw new Error("No opportunity found");
    return { opportunity: first, executable: false };
  };

  try {
    const { opportunity: opp, executable } = await getOppData();
    pass("opportunity list loaded");

    if (!executable || opp.execution_gate_passed === false) {
      try {
        await request(`/opportunities/${opp.id}/execute`, {
          method: "POST",
          body: JSON.stringify({ opportunity_id: opp.id })
        });
        throw new Error("blocked opportunity unexpectedly executed");
      } catch (err) {
        if (String(err.message || "").includes("unexpectedly")) throw err;
        pass(`opportunity execute gate surfaced (${opp.opportunity_stage || "blocked"})`);
      }
    } else {
      const exec = await request(`/opportunities/${opp.id}/execute`, {
        method: "POST",
        body: JSON.stringify({ opportunity_id: opp.id })
      });
      const action = exec?.data?.action;
      if (!action?.id) throw new Error("No action returned by execute");
      pass(`opportunity execute created action ${action.id}`);

      const progress = await request(`/actions/${action.id}/progress`, {
        method: "PUT",
        body: JSON.stringify({ current_step: Math.min(action.total_steps, action.current_step + 1), note: "button smoke: next" })
      });
      if (typeof progress?.data?.current_step !== "number") {
        throw new Error("progress response missing current_step");
      }
      pass("action next-step button");

      const review = await request(`/actions/${action.id}/review`, {
        method: "POST",
        body: JSON.stringify({ result: "profit", rating: 5, amount: 0, notes: "button smoke review" })
      });
      if (review?.data?.result !== "profit") {
        throw new Error("review response missing profit");
      }
      pass("action complete button");
    }
  } catch (err) {
    fail("action execution chain", err);
  }

  try {
    const briefBefore = await request("/brief/latest");
    const generated = await request("/brief/generate", { method: "POST" });
    const latest = await request("/brief/latest");
    if (!generated?.data?.id || latest?.data?.id !== generated.data.id) {
      throw new Error("generated brief not persisted");
    }
    if (!briefBefore?.data?.id || briefBefore.data.id !== latest.data.id) {
      pass("brief generate button");
    } else {
      pass("brief generate button");
    }
  } catch (err) {
    fail("brief generation button", err);
  }

  try {
    const sourceList = await request("/sources/status");
    const source = sourceList?.data?.items?.[0];
    if (!source?.id) throw new Error("no source found");
    await request(`/sources/${encodeURIComponent(source.id)}/freshness`);
    pass(`source detail refresh button (${source.source || source.id})`);
  } catch (err) {
    fail("source refresh button", err);
  }

  try {
    await request("/pipeline/run", { method: "POST", body: JSON.stringify({ steps: ["collect", "clean", "analyze", "score"] }) });
    const pipeline = await request("/pipeline/status");
    if (!pipeline?.data?.id && pipeline?.data?.status !== "success" && pipeline?.data?.status !== "running") {
      throw new Error("pipeline status missing expected state");
    }
    pass("pipeline run button");
  } catch (err) {
    fail("pipeline run button", err);
  }

  try {
    const registry = await request("/settings/models/registry");
    const first = registry?.data?.[0];
    if (!first?.name) throw new Error("no model found");
    await request(`/settings/models/registry/${encodeURIComponent(first.name)}/test`, {
      method: "POST",
      body: JSON.stringify({})
    });
    const usage = await request("/settings/models/usage");
    if (!usage?.data?.items) throw new Error("usage data missing");
    pass(`model test button (${first.name})`);
    await request("/settings/models/allocation", {
      method: "PUT",
      body: JSON.stringify([
        {
          agent_name: "agent_frontend_smoke",
          model_name: first.name,
          recommended_model: first.name
        }
      ])
    });
    pass("settings save allocation");
  } catch (err) {
    fail("settings buttons", err);
  }

  console.log(checks.join("\n"));
  const allPass = checks.every((item) => item.startsWith("[OK]"));
  if (!allPass) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
