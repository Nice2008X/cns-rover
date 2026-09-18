import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8877",
    viewport: { width: 1440, height: 1000 },
  },
  webServer: {
    command:
      ".venv/bin/python -c \"import tempfile,uvicorn; from cns_rover.server import create_app; from cns_rover.scenario import Scenario; from cns_rover.controllers import BaselineRoverController; uvicorn.run(create_app(Scenario(),BaselineRoverController,tempfile.mkdtemp(prefix='cns-browser-'),port=8877),host='127.0.0.1',port=8877)\"",
    cwd: "..",
    url: "http://127.0.0.1:8877",
    reuseExistingServer: false,
  },
  timeout: 30000,
});
