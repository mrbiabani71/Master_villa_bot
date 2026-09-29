import app from "./app";
import { logger } from "./lib/logger";

// Get port from environment
const rawPort =
  process.env.PORT ||
  process.env.SERVER_PORT ||
  "8080";

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

app.listen(port, () => {
  logger.info({ port }, "API Server is running");
});